"""Logging in, with the 5-tries lockout (§6.2.1.8, D-YOSEF-accounts-login).

Failure counts live in the shared cache (D-YOSEF-shared-cache), keyed by the
lowercased username, so "Yosef" and "YOSEF" share one count. A username that
doesn't exist is counted too, so the response never reveals which usernames exist.
"""

import enum
import hashlib

from django.contrib.auth import authenticate, login
from django.core.cache import cache

from .ratelimit import client_ip, take_token

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


def _key(kind, username):
    # Hashed so any username, even a 10,000-character one, makes a short fixed-size key.
    digest = hashlib.sha256(username.lower().encode()).hexdigest()
    return f"login:{kind}:{digest}"


def is_locked_out(username):
    return cache.get(_key("locked", username)) is not None


def _record_failure(username):
    """Count one failed try. Return True if this try locks the username."""
    key = _key("failures", username)
    cache.add(key, 0, timeout=FAILURE_WINDOW_SECONDS)
    # Not atomic on DatabaseCache: two failures at the same instant may count once.
    # The per-IP rate limit bounds how much that can matter.
    try:
        failures = cache.incr(key)
    except ValueError:  # The count expired between add() and incr(): this is the first.
        cache.set(key, 1, timeout=FAILURE_WINDOW_SECONDS)
        failures = 1
    if failures < MAX_FAILURES:
        return False
    cache.set(_key("locked", username), True, timeout=LOCKOUT_SECONDS)
    cache.delete(key)
    return True


def _clear_failures(username):
    cache.delete(_key("failures", username))


def attempt_login(request, username, password):
    """Check the credentials and, if they're right, log the user in.

    Returns (LoginResult, user or None). Checks run cheapest first, and the
    expensive password hash runs only after all the others pass: blank input,
    then the per-IP rate limit, then the lockout. While a username is locked,
    even the right password is refused without being checked.
    """
    if not username or not password:
        return LoginResult.MISSING_CREDENTIALS, None
    if not take_token(f"login:{client_ip(request)}", RATE_CAPACITY, RATE_REFILL_SECONDS):
        return LoginResult.RATE_LIMITED, None
    if is_locked_out(username):
        return LoginResult.LOCKED_OUT, None
    user = authenticate(request, username=username, password=password)
    if user is None:
        if _record_failure(username):
            return LoginResult.LOCKED_OUT, None
        return LoginResult.WRONG_CREDENTIALS, None
    _clear_failures(username)
    login(request, user)
    return LoginResult.OK, user
