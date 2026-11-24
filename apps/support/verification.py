"""A guest proves they own an email address before filing a ticket (§6.3 Tickets, D-072).

The design asks that a guest's email "must be verified". The flow is the one the
help and report wireframes draw: type the address, press Verify, type the 6-digit
code from the email. The pending code lives in the visitor's session, hashed;
once it matches, the session remembers the address as verified until it ends.

This is support's own check, not the signup code in accounts: §6.1 lets support
depend on nothing, and the two flows differ (no account is created here).
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass

from django.conf import settings
from django.core.cache import cache

from .tasks import send_ticket_email_code

PENDING_KEY = "support.email_check"
VERIFIED_KEY = "support.verified_email"

CODE_LIFETIME_SECONDS = 15 * 60
MAX_TRIES = 5
# Codes a single address may be sent per hour, whoever asks: stops the form being
# used to flood someone's inbox from many sessions.
MAX_SENDS_PER_EMAIL_PER_HOUR = 5
SEND_WINDOW_SECONDS = 60 * 60


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


def start(session, email: str) -> CheckResult:
    """Email a fresh code to `email` and remember it in the session as pending."""
    email = _normalise(email)
    key = _send_count_key(email)
    cache.add(key, 0, SEND_WINDOW_SECONDS)
    try:
        sends = cache.incr(key)
    except ValueError:  # Expired between add and incr: start a fresh window.
        cache.set(key, 1, SEND_WINDOW_SECONDS)
        sends = 1
    if sends > MAX_SENDS_PER_EMAIL_PER_HOUR:
        return CheckResult(False, "Too many codes were sent to that address. Try again in an hour.")

    code = f"{secrets.randbelow(1_000_000):06d}"
    session[PENDING_KEY] = {
        "email": email,
        "digest": _digest(email, code),
        "expires": time.time() + CODE_LIFETIME_SECONDS,
        "tries": 0,
    }
    session.pop(VERIFIED_KEY, None)
    send_ticket_email_code.delay(email, code)
    return CheckResult(True, f"We sent a 6-digit code to {email}. It works for 15 minutes.")


def confirm(session, code: str) -> CheckResult:
    """Check `code` against the pending one; on a match the address is verified."""
    pending = session.get(PENDING_KEY)
    if not pending:
        return CheckResult(False, "Ask for a code first.")
    if time.time() > pending["expires"]:
        session.pop(PENDING_KEY, None)
        return CheckResult(False, "That code has expired. Ask for a new one.")
    if pending["tries"] >= MAX_TRIES:
        session.pop(PENDING_KEY, None)
        return CheckResult(False, "Too many wrong codes. Ask for a new one.")

    pending["tries"] += 1
    session[PENDING_KEY] = pending  # Reassign so the session notices the change.
    code = (code or "").strip()
    if not hmac.compare_digest(pending["digest"], _digest(pending["email"], code)):
        return CheckResult(False, "That code is not right. Check the email and try again.")

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
