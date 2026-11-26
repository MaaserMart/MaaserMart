"""A guest proves they own an email address before filing a ticket (§6.3 Tickets, D-072).

The design asks that a guest's email "must be verified". The flow is the one the
help and report wireframes draw: type the address, press Verify, type the 6-digit
code from the email. The pending code lives in the visitor's session, hashed;
once it matches, the session remembers the address as verified until it ends.

This is support's own check, not the signup code in accounts: §6.1 lets support
depend on nothing, and the two flows differ (no account is created here). The
code, its email and the try counter are shared through `common` (D-078), which
neither app owns.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass

from django.conf import settings
from django.core.cache import cache

from common.verification import (
    CODE_LENGTH,
    CODE_LIFETIME_SECONDS,
    MAX_CODE_TRIES,
    exhaust_tries,
    new_code,
    spend_try,
)

from .tasks import send_ticket_email_code

PENDING_KEY = "support.email_check"
VERIFIED_KEY = "support.verified_email"

MAX_TRIES = MAX_CODE_TRIES
# Codes a single address may be sent per hour, whoever asks: stops the form being
# used to flood someone's inbox from many sessions.
MAX_SENDS_PER_EMAIL_PER_HOUR = 5
# Codes one network may cause per hour, across all addresses (D-078). The
# per-address cap alone can be walked around by trying many different addresses.
MAX_SENDS_PER_IP_PER_HOUR = 20
# Code tries one network may spend per hour, across all its codes (D-078). Each
# code already allows 5 tries, but a network can ask for 20 codes an hour, so
# without this it could spend 100 guesses an hour here. Generous next to the 5 a
# careful visitor uses, so a shared address (an office, a school) is not refused.
MAX_TRIES_PER_NETWORK_PER_HOUR = 30
# Both limits are hourly buckets in the default cache.
LIMIT_WINDOW_SECONDS = 60 * 60


@dataclass(frozen=True)
class CheckResult:
    """What happened when a code was sent or tried, as the form should say it."""

    ok: bool
    message: str


def _normalise(email: str) -> str:
    return (email or "").strip().lower()


def _digest(email: str, code: str) -> str:
    """A keyed hash, so a leaked session row does not reveal the code."""
    message = f"{email}:{code}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), message, hashlib.sha256).hexdigest()


def _send_count_key(email: str) -> str:
    return "support:email-code-sends:" + hashlib.sha256(email.encode()).hexdigest()


def _ip_count_key(network: str) -> str:
    return "support:email-code-sends-ip:" + hashlib.sha256(network.encode()).hexdigest()


def _network_try_key(network: str) -> str:
    return "support:code-tries-ip:" + hashlib.sha256(network.encode()).hexdigest()


def _spend(limits) -> str | None:
    """Spend one from every bucket.

    Returns None when all of them had room, otherwise the message of the first
    full bucket, and spends nothing: a refused send must not eat the others.
    Two sends racing can both pass a full check, which the caps can live with;
    they are spam limits, not the try count (which is locked, D-078).
    """
    for key, cap, message in limits:
        if cache.get(key, 0) >= cap:
            return message
    for key, _, _ in limits:
        cache.add(key, 0, LIMIT_WINDOW_SECONDS)
        try:
            cache.incr(key)
        except ValueError:  # Expired between add and incr: start a fresh window.
            cache.set(key, 1, LIMIT_WINDOW_SECONDS)
    return None


def _tries_key(pending) -> str:
    return f"support:tries:{pending['id']}"


def start(session, email: str, network: str = "") -> CheckResult:
    """Email a fresh code to `email` and remember it in the session as pending.

    `network` is the visitor's rate-limit key from `common.clients`; an empty
    value skips the per-IP cap, for callers with no request (such as unit tests).
    """
    email = _normalise(email)
    limits = [
        (
            _send_count_key(email),
            MAX_SENDS_PER_EMAIL_PER_HOUR,
            "Too many codes were sent to that address. Try again in an hour.",
        )
    ]
    if network:
        limits.append(
            (
                _ip_count_key(network),
                MAX_SENDS_PER_IP_PER_HOUR,
                "Too many codes were sent from this network. Try again in an hour.",
            )
        )
    if refused := _spend(limits):
        return CheckResult(False, refused)

    code = new_code()
    session[PENDING_KEY] = {
        "id": secrets.token_urlsafe(16),
        "email": email,
        "digest": _digest(email, code),
        "expires": time.time() + CODE_LIFETIME_SECONDS,
    }
    session.pop(VERIFIED_KEY, None)
    send_ticket_email_code.delay(email, code)
    return CheckResult(
        True,
        f"We sent a {CODE_LENGTH}-digit code to {email}. "
        f"It works for {CODE_LIFETIME_SECONDS // 60} minutes.",
    )


def confirm(session, code: str, network: str = "") -> CheckResult:
    """Check `code` against the pending one; on a match the address is verified.

    `network` is the visitor's rate-limit key, as in `start`. A try refused by
    that cap does not use up one of the code's own 5, so a shared address is not
    punished twice.
    """
    pending = session.get(PENDING_KEY)
    if not pending:
        return CheckResult(False, "Ask for a code first.")
    if time.time() > pending["expires"]:
        session.pop(PENDING_KEY, None)
        return CheckResult(False, "That code has expired. Ask for a new one.")

    if network:
        refused = _spend(
            [
                (
                    _network_try_key(network),
                    MAX_TRIES_PER_NETWORK_PER_HOUR,
                    "Too many code tries from this network. Try again in an hour.",
                )
            ]
        )
        if refused:
            return CheckResult(False, refused)

    key = _tries_key(pending)
    tries = spend_try(key)  # Counted under a lock; parallel guesses cannot tie (D-078).
    if tries > MAX_TRIES:
        session.pop(PENDING_KEY, None)
        return CheckResult(False, "Too many wrong codes. Ask for a new one.")

    code = (code or "").strip()
    if not hmac.compare_digest(pending["digest"], _digest(pending["email"], code)):
        return CheckResult(False, "That code is not right. Check the email and try again.")

    # A copy of this session elsewhere must not try the same code again.
    exhaust_tries(key)
    session.pop(PENDING_KEY, None)
    session[VERIFIED_KEY] = pending["email"]
    return CheckResult(True, f"{pending['email']} is verified.")


def pending_email(session) -> str | None:
    """The address a code was last sent to, while it is still waiting."""
    pending = session.get(PENDING_KEY)
    return pending["email"] if pending else None


def verified_email(session) -> str | None:
    """The address this session has proved it owns, if any."""
    return session.get(VERIFIED_KEY)
