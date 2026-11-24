"""Public interface of the support app.

Other apps call only the functions defined here, never this app's models.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from django.db import transaction
from django.utils import timezone

from apps.charities.services import get_charity_choices

from .models import Ticket
from .tasks import send_ticket_reply

MAX_BODY_LENGTH = 5000


class TicketError(ValueError):
    """A ticket that cannot be filed or answered as given; the message is safe to show."""


def _clean_text(text: str, empty_message: str) -> str:
    text = (text or "").strip()
    if not text:
        raise TicketError(empty_message)
    if len(text) > MAX_BODY_LENGTH:
        raise TicketError(f"Keep the message under {MAX_BODY_LENGTH} characters.")
    return text


def _reply_to(email: str | None) -> str:
    email = (email or "").strip().lower()
    if not email:
        raise TicketError("A ticket needs an email address for the reply.")
    return email


def submit_help(body: str, *, email: str, user_id: int | None = None) -> int:
    """File a help request (§6.3 Tickets, SRS FR 18). Returns the ticket id.

    `email` is where the answer goes: a guest's verified address, or a signed-in
    user's account address (D-073). `user_id` is the account, if there is one.
    """
    ticket = Ticket.objects.create(
        kind=Ticket.Kind.HELP,
        body=_clean_text(body, "Write your message first."),
        email=_reply_to(email),
        submitted_by_id=user_id,
    )
    return ticket.id


def submit_report(body: str, charity_id: int, *, email: str, user_id: int | None = None) -> int:
    """File a report about one charity (§6.3 Tickets, SRS FR 19). Returns the ticket id.

    The caller has already checked that the charity exists; it is a FK, so a
    stale id fails here rather than filing a report about nothing.
    """
    if charity_id is None:
        raise TicketError("Choose the charity you are reporting.")
    ticket = Ticket.objects.create(
        kind=Ticket.Kind.REPORT,
        charity_id=charity_id,
        body=_clean_text(body, "Write your message first."),
        email=_reply_to(email),
        submitted_by_id=user_id,
    )
    return ticket.id


# --- Admin ticket queue (§7.3.10, D-073) ---------------------------------------


@dataclass(frozen=True)
class TicketCard:
    """One ticket as the admin queue shows it."""

    id: int
    kind: str
    kind_label: str
    body: str
    email: str | None
    # False for a guest: the queue labels the ticket "guest" (§6.3 failure paths).
    from_member: bool
    charity_id: int | None
    charity_name: str | None
    status: str
    status_label: str
    response: str | None
    responded: datetime | None
    created: datetime


def get_tickets() -> list[TicketCard]:
    """Every ticket not yet closed, unanswered first, oldest first within each."""
    rows = list(
        # "not_responded" sorts before "responded", so unanswered tickets lead; the
        # (status, created) index serves this order (§5.3).
        Ticket.objects.exclude(status=Ticket.Status.CLOSED).order_by("status", "created", "id")
    )
    charities = get_charity_choices(row.charity_id for row in rows)
    cards = []
    for row in rows:
        charity = charities.get(row.charity_id)
        cards.append(
            TicketCard(
                id=row.id,
                kind=row.kind,
                kind_label=row.get_kind_display(),
                body=row.body,
                email=row.email,
                from_member=row.submitted_by_id is not None,
                charity_id=row.charity_id,
                charity_name=charity.name if charity else None,
                status=row.status,
                status_label=row.get_status_display(),
                response=row.response,
                responded=row.responded,
                created=row.created,
            )
        )
    return cards


RESPOND = "respond"
CLOSE = "close"


def resolve_ticket(ticket_id: int, user_id: int, text: str, action: str) -> None:
    """Answer or close a ticket (§7.3.10 `resolve_ticket`).

    `respond` emails `text` to the submitter and marks the ticket responded; it
    stays in the queue until closed. `close` takes it out of the queue, emailing
    `text` first when there is any. The email is queued after the commit, so a
    rolled-back answer is never sent; if it fails for good the ticket stays
    answered and the task logs the ticket id (§6.3 failure paths).
    """
    if action not in (RESPOND, CLOSE):
        raise TicketError("Choose to reply or to close.")
    text = (text or "").strip()
    if action == RESPOND:
        text = _clean_text(text, "Write the reply first.")
    elif len(text) > MAX_BODY_LENGTH:
        raise TicketError(f"Keep the message under {MAX_BODY_LENGTH} characters.")

    with transaction.atomic():
        ticket = Ticket.objects.select_for_update().filter(pk=ticket_id).first()
        if ticket is None:
            raise TicketError("That ticket no longer exists.")
        if ticket.status == Ticket.Status.CLOSED:
            raise TicketError("That ticket is already closed.")
        now = timezone.now()
        fields = []
        if text:
            ticket.response = text
            ticket.responded = now
            ticket.responded_by_id = user_id
            ticket.status = Ticket.Status.RESPONDED
            fields += ["response", "responded", "responded_by", "status"]
        if action == CLOSE:
            ticket.status = Ticket.Status.CLOSED
            ticket.closed = now
            fields += ["status", "closed"]
        ticket.save(update_fields=sorted(set(fields)))
        if text and ticket.email:
            transaction.on_commit(lambda: send_ticket_reply.delay(ticket.id))
