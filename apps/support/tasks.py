"""Emails support sends, queued through Celery (§4.14: email goes out through SES)."""

from celery import shared_task
from django.core.mail import send_mail


@shared_task(autoretry_for=(OSError,), retry_backoff=True, max_retries=3)
def send_ticket_email_code(email: str, code: str) -> None:
    """The 6-digit code a guest types to prove the address is theirs (D-072)."""
    send_mail(
        subject="Your MaaserMart code",
        message=(
            f"Your code is {code}.\n\n"
            "Type it on the MaaserMart help or report page. It works for 15 minutes.\n"
            "If you did not ask for it, you can ignore this email."
        ),
        from_email=None,
        recipient_list=[email],
    )
