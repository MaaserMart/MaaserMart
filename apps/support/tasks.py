"""Emails support sends, queued through Celery (§4.14: email goes out through SES)."""

import logging

from celery import shared_task
from django.core.mail import send_mail

from .models import Ticket

logger = logging.getLogger(__name__)

REPLY_MAX_RETRIES = 3


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


@shared_task(bind=True, max_retries=REPLY_MAX_RETRIES)
def send_ticket_reply(self, ticket_id: int) -> None:
    """Email an admin's answer to whoever filed the ticket (§7.3.10, D-073).

    Reads the ticket when it runs, so the email carries the answer as saved. When
    the retries run out the ticket stays answered and the failure is logged at
    ERROR with the ticket id, as §6.3's failure paths ask.
    """
    ticket = Ticket.objects.filter(pk=ticket_id).first()
    if ticket is None or not ticket.email or not ticket.response:
        return
    subject = (
        "Your MaaserMart report"
        if ticket.kind == Ticket.Kind.REPORT
        else "Your MaaserMart question"
    )
    try:
        send_mail(
            subject=subject,
            message=(f"{ticket.response}\n\n----\nYou wrote:\n{ticket.body}\n"),
            from_email=None,
            recipient_list=[ticket.email],
        )
    except OSError as exc:
        if self.request.retries >= REPLY_MAX_RETRIES:
            logger.error("Reply email for ticket %s failed after retries", ticket_id)
            return
        raise self.retry(exc=exc, countdown=2**self.request.retries * 30) from exc
