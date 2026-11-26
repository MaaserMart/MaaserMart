"""Emails support sends, queued through Celery (§4.14: email goes out through SES)."""

from celery import shared_task

from common.verification import send_verification_code


@shared_task(autoretry_for=(OSError,), retry_backoff=True, max_retries=3)
def send_ticket_email_code(email: str, code: str) -> None:
    """The shared verification-code email, worded for help and report (D-078)."""
    send_verification_code(email, code, "support")
