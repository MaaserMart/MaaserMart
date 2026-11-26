"""Member signup with an emailed 6-digit code (§6.2.2, D-YOSEF-member-signup).

Step 1, start_signup: check everything up front, cheapest first. Only when every
check passes is the password hashed and a code emailed. The pending signup (the
username, email, password hash and code) waits in the session. Sessions live in
the database, so the code never reaches the browser.

Step 2, verify_signup: the right code, within 15 minutes and 5 tries, creates the
account with the member role and logs the user in.
"""

import enum
import hashlib
import secrets
import time

from django import forms
from django.contrib.auth import login
from django.contrib.auth.hashers import make_password
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.cache import caches
from django.core.exceptions import ValidationError
from django.db.models import Value
from django.db.models.functions import Lower
from django.utils.crypto import constant_time_compare

from common.verification import (
    CODE_LIFETIME_SECONDS,
    MAX_CODE_TRIES,
    exhaust_tries,
    new_code,
    spend_try,
)

from .backends import find_user
from .models import User
from .ratelimit import client_network, take_token
from .services import SignupOutcome, enqueue_signup_code, submit_member_signup

SESSION_KEY = "member_signup"

# Per client network: a burst of 5 signups, then one every 12 minutes (5 an hour).
SIGNUP_CAPACITY = 5
SIGNUP_REFILL_SECONDS = 12 * 60
# Per email address: 3 code emails, then one every 20 minutes (3 an hour).
EMAIL_CAPACITY = 3
EMAIL_REFILL_SECONDS = 20 * 60

# Per client network: 10 code tries at once, then one a minute.
VERIFY_CAPACITY = 10
VERIFY_REFILL_SECONDS = 60

BACKEND = "apps.accounts.backends.CaseInsensitiveModelBackend"


def _now():
    return time.time()


class SignupResult(enum.Enum):
    CODE_SENT = "code_sent"
    RATE_LIMITED = "rate_limited"
    INVALID = "invalid"  # The form says which fields.
    TOO_MANY_EMAILS = "too_many_emails"
    OK = "ok"
    NO_SIGNUP = "no_signup"
    EXPIRED = "expired"
    WRONG_CODE = "wrong_code"
    OUT_OF_TRIES = "out_of_tries"
    TAKEN = "taken"  # Someone took the username or email while the code was out.


class SignupForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        validators=[UnicodeUsernameValidator()],
        error_messages={"required": "Choose a username."},
    )
    email = forms.EmailField(error_messages={"required": "Enter your email address."})
    password = forms.CharField(strip=False, error_messages={"required": "Choose a password."})
    agree = forms.BooleanField(error_messages={"required": "Tick the box to agree to the terms."})

    def clean_email(self):
        return User.objects.normalize_email(self.cleaned_data["email"])

    def clean(self):
        data = super().clean()
        if "username" in data and "password" in data:
            # Django's password rules: length, common passwords, all digits, and
            # not too close to the username or email.
            candidate = User(username=data["username"], email=data.get("email", ""))
            try:
                validate_password(data["password"], candidate)
            except ValidationError as error:
                self.add_error("password", error)
        return data


def email_taken(email):
    """Any capitals. Uses the user_email_ci_uniq index; iexact would scan (see find_user)."""
    return (
        User.objects.alias(email_lower=Lower("email"))
        .filter(email_lower=Lower(Value(email)))
        .exists()
    )


def mailbox(email):
    """The inbox an address delivers to, so its aliases share one email limit.

    'Victim+1@Gmail.com' and 'v.ictim@googlemail.com' both reach victim@gmail.com.
    Any '+tag' is dropped; Gmail also ignores dots. Used only for the limit; the
    account keeps the address as typed.
    """
    local, _, domain = email.lower().rpartition("@")
    local = local.split("+", 1)[0]
    if domain in ("gmail.com", "googlemail.com"):
        local, domain = local.replace(".", ""), "gmail.com"
    return f"{local}@{domain}"


def _email_bucket(email):
    return "signup-email:" + hashlib.sha256(mailbox(email).encode()).hexdigest()


def _spend_email(email):
    """Spend one of the inbox's 3 emails an hour. False if none are left."""
    return take_token(_email_bucket(email), EMAIL_CAPACITY, EMAIL_REFILL_SECONDS)


def _save_and_send(request, pending):
    """Give the signup a fresh code, save it in the session, then email the code."""
    # A new id gives the new code its own try count, starting at zero.
    pending.update(id=secrets.token_urlsafe(16), code=new_code(), sent_at=_now())
    request.session[SESSION_KEY] = pending
    enqueue_signup_code(pending["email"], pending["code"])


def start_signup(request, form, next_url=""):
    """Check a filled-in SignupForm and, if it passes, email a code.

    Returns a SignupResult. On INVALID the errors are on `form`.
    """
    # 1. Cheapest: fields and password rules, no database and no limit spent,
    #    so fixing a typo doesn't use up the network's signups.
    if not form.is_valid():
        return SignupResult.INVALID
    # 2. One cache read: 5 signups an hour per network, before any lookups, which
    #    also caps how fast anyone can check which usernames and emails exist.
    if not take_token(f"signup:{client_network(request)}", SIGNUP_CAPACITY, SIGNUP_REFILL_SECONDS):
        return SignupResult.RATE_LIMITED
    data = form.cleaned_data
    # 3. Database: is the username or email already in use? (D-032: any capitals.)
    if find_user(data["username"]):
        form.add_error("username", "That username is taken.")
    if email_taken(data["email"]):
        form.add_error("email", "This email already has an account. Log in instead.")
    if form.errors:
        return SignupResult.INVALID
    # 4. Last check, because it spends one of the inbox's 3 emails an hour.
    if not _spend_email(data["email"]):
        return SignupResult.TOO_MANY_EMAILS
    # Every check passed. Only the hash is kept, never the password itself.
    pending = {
        "username": data["username"],
        "email": data["email"],
        "password_hash": make_password(data["password"]),
        "next": next_url,
    }
    _save_and_send(request, pending)
    return SignupResult.CODE_SENT


def pending_signup(request):
    return request.session.get(SESSION_KEY)


def resend_code(request):
    """Email a new code for the signup in this session. The old code stops working."""
    pending = pending_signup(request)
    if pending is None:
        return SignupResult.NO_SIGNUP
    if not _spend_email(pending["email"]):
        return SignupResult.TOO_MANY_EMAILS
    _save_and_send(request, pending)
    return SignupResult.CODE_SENT


def _clean_code(code):
    """Accept '482 917' or '482-917' as '482917'."""
    return "".join(ch for ch in code if not ch.isspace() and ch != "-")


def _tries_key(pending):
    return f"signup:tries:{pending['id']}"


def _spend_try(pending):
    """Count one code try for this code, with the shared atomic counter (D-078)."""
    return spend_try(_tries_key(pending))


def verify_signup(request, code):
    """Check the typed code and, if it is right, create and log in the member.

    Returns (SignupResult, user or None).
    """
    # Checks, cheapest first: the network's tries, a signup waiting, not expired.
    if not take_token(
        f"signup-code:{client_network(request)}", VERIFY_CAPACITY, VERIFY_REFILL_SECONDS
    ):
        return SignupResult.RATE_LIMITED, None
    pending = pending_signup(request)
    if pending is None:
        return SignupResult.NO_SIGNUP, None
    if _now() - pending["sent_at"] > CODE_LIFETIME_SECONDS:
        return SignupResult.EXPIRED, None
    # Count the try before comparing, so a burst of guesses can't outrun the count.
    tries = _spend_try(pending)
    if tries > MAX_CODE_TRIES:
        del request.session[SESSION_KEY]
        return SignupResult.OUT_OF_TRIES, None
    if not constant_time_compare(_clean_code(code), pending["code"]):
        if tries == MAX_CODE_TRIES:
            del request.session[SESSION_KEY]
            return SignupResult.OUT_OF_TRIES, None
        return SignupResult.WRONG_CODE, None
    # Used up: a copy of this session elsewhere can't try the code again.
    exhaust_tries(_tries_key(pending))
    outcome, user = submit_member_signup(
        pending["username"], pending["email"], pending["password_hash"]
    )
    del request.session[SESSION_KEY]
    if outcome is not SignupOutcome.CREATED:
        return SignupResult.TAKEN, None
    login(request, user, backend=BACKEND)
    return SignupResult.OK, user


def tries_left(request):
    pending = pending_signup(request)
    if pending is None:
        return 0
    return max(0, MAX_CODE_TRIES - caches["login"].get(_tries_key(pending), 0))


def masked_email(email):
    """'yosef@gmail.com' -> 'y***@gmail.com', for the "we emailed you" line."""
    name, _, domain = email.partition("@")
    return f"{name[:1]}***@{domain}"
