"""Verification codes shared by signup and guest support (D-078).

Neither app may import the other, so the part both need lives here: making a
fresh code, emailing it, and counting tries so parallel guesses cannot each
start from zero. Each app keeps its own policy for where the pending code
lives and what happens after it matches.
"""

from __future__ import annotations

import hashlib
import secrets

from celery import shared_task
from django.core.cache import caches
from django.core.mail import send_mail
from django.db import connection, transaction

CODE_LENGTH = 6
CODE_LIFETIME_SECONDS = 15 * 60
MAX_CODE_TRIES = 5

_TRIES_TIMEOUT = CODE_LIFETIME_SECONDS + 60

_PURPOSES = {
    "signup": "finish signing up",
    "support": "verify your email address on the help or report page",
}


def new_code() -> str:
    """A fresh 6-digit code; each code gets its own try count."""
    return f"{secrets.randbelow(10**CODE_LENGTH):0{CODE_LENGTH}d}"


def spend_try(key: str) -> int:
    """Count one attempt against `key`, returning the count including this one.

    PostgreSQL's advisory lock makes simultaneous guesses take turns, so they
    cannot all read the same old count and stay under the limit (D-078).
    """
    store = caches["login"]
    lock_id = int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big", signed=True)
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [lock_id])
        tries = store.get(key, 0) + 1
        store.set(key, tries, timeout=_TRIES_TIMEOUT)
    return tries


def exhaust_tries(key: str) -> None:
    """Mark the code behind `key` used up, so a copy of the session cannot retry it."""
    caches["login"].set(key, MAX_CODE_TRIES + 1, _TRIES_TIMEOUT)


@shared_task
def send_verification_code(email: str, code: str, purpose: str) -> None:
    """Email a verification code; `purpose` is 'signup' or 'support' (D-078)."""
    send_mail(
        subject="Your MaaserMart code",
        message=(
            f"Your code is {code}.\n\n"
            f"Type it on MaaserMart to {_PURPOSES[purpose]}. "
            "It works for 15 minutes. If you did not ask for it, ignore this email."
        ),
        from_email=None,  # DEFAULT_FROM_EMAIL
        recipient_list=[email],
    )
