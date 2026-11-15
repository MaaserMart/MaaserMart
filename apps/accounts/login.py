"""Logging in, with the 5-tries lockout (§6.2.1.8, D-YOSEF-accounts-login).

Failure counts and locks live in their own shared cache, "login"
(D-YOSEF-shared-cache). They are kept per account: whichever user PostgreSQL
matches, so "Yosef", "YOSEF" and any other spelling that logs in to the same
account share one count. A username that doesn't exist is counted too, by its
lowercased text, so the response never reveals which usernames exist.
"""

import enum
import hashlib

from django.contrib.auth import authenticate, login
from django.core.cache import caches
from django.urls import NoReverseMatch, reverse
from django.utils.http import url_has_allowed_host_and_scheme

from .backends import find_user
from .ratelimit import client_network, take_token
from .services import find_role

# Per client IP: a burst of 20 tries, then one every 3 seconds (20 a minute).
RATE_CAPACITY = 20
RATE_REFILL_SECONDS = 3

MAX_FAILURES = 5
LOCKOUT_SECONDS = 60 * 60
# Failures older than this are forgotten, so 4 typos a day never add up to a lockout.
FAILURE_WINDOW_SECONDS = 60 * 60


class LoginResult(enum.Enum):
    OK = "ok"
    RATE_LIMITED = "rate_limited"
    MISSING_CREDENTIALS = "missing_credentials"
    WRONG_CREDENTIALS = "wrong_credentials"
    LOCKED_OUT = "locked_out"


def _store():
    return caches["login"]


def _account(username):
    """What a lock applies to: the account this username logs in to, else the text."""
    user = find_user(username)
    return f"user:{user.pk}" if user else f"name:{username.lower()}"


def _key(kind, account):
    # Hashed so any username, even a 10,000-character one, makes a short fixed-size key.
    return f"login:{kind}:{hashlib.sha256(account.encode()).hexdigest()}"


def _locked(account):
    return _store().get(_key("locked", account)) is not None


def is_locked_out(username):
    return _locked(_account(username))


def _record_failure(account):
    """Count one failed try. Return True if this try locks the account."""
    cache = _store()
    key = _key("failures", account)
    cache.add(key, 0, timeout=FAILURE_WINDOW_SECONDS)
    # Not atomic on DatabaseCache: failures that arrive together may count once,
    # and requests already past the lock check still get their password checked.
    # Either way the extra tries are bounded by how many requests run at once.
    try:
        failures = cache.incr(key)
    except ValueError:  # The count expired between add() and incr(): this is the first.
        cache.set(key, 1, timeout=FAILURE_WINDOW_SECONDS)
        failures = 1
    if failures < MAX_FAILURES:
        return False
    cache.set(_key("locked", account), True, timeout=LOCKOUT_SECONDS)
    cache.delete(key)
    return True


def _clear_failures(account):
    _store().delete(_key("failures", account))


def attempt_login(request, username, password):
    """Check the credentials and, if they're right, log the user in.

    Returns (LoginResult, user or None). Checks run cheapest first, and the
    expensive password hash runs only after all the others pass: blank input,
    then the per-IP rate limit, then the lockout. While a username is locked,
    even the right password is refused without being checked.
    """
    if not username or not password:
        return LoginResult.MISSING_CREDENTIALS, None
    if not take_token(f"login:{client_network(request)}", RATE_CAPACITY, RATE_REFILL_SECONDS):
        return LoginResult.RATE_LIMITED, None
    account = _account(username)
    if _locked(account):
        return LoginResult.LOCKED_OUT, None
    user = authenticate(request, username=username, password=password)
    if user is None:
        if _record_failure(account):
            return LoginResult.LOCKED_OUT, None
        return LoginResult.WRONG_CREDENTIALS, None
    _clear_failures(account)
    login(request, user)
    return LoginResult.OK, user


# Where each role lands after login (§6.2.1.6). These URL names belong to the
# dashboards app, which has no pages yet (as of 2026-11-15); until a name exists,
# its users land on the home page instead.
DASHBOARD_URL_NAMES = {
    "member": "dashboards:member",
    "rabbi": "dashboards:rabbi",
    "charity_owner": "dashboards:charity_owner",
    "technical_supporter": "dashboards:technical_supporter",
    "admin": "dashboards:admin",
}
CHOOSER_URL_NAME = "accounts:choose_dashboard"


def _url_or_home(name):
    try:
        return reverse(name)
    except NoReverseMatch:
        return reverse("home")


def dashboard_url(role):
    """The dashboard a role lands on, or home while that dashboard doesn't exist."""
    return _url_or_home(DASHBOARD_URL_NAMES[role])


def safe_next_url(request):
    """The ?next= address, if it stays on this site; otherwise None."""
    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return next_url
    return None


def redirect_after_login(request, user):
    """Where to send a user who just logged in or signed up (§6.2.1.6).

    A safe ?next= first; otherwise the dashboard of their one role, or the
    chooser if they hold several.
    """
    next_url = safe_next_url(request)
    if next_url:
        return next_url
    roles = find_role(user)
    if len(roles) > 1:
        return _url_or_home(CHOOSER_URL_NAME)
    if len(roles) == 1:
        return dashboard_url(roles[0])
    return reverse("home")
