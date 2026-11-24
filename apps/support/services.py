"""Public interface of the support app.

Other apps call only the functions defined here, never this app's models.
"""

from __future__ import annotations

from .models import Ticket

MAX_BODY_LENGTH = 5000


class TicketError(ValueError):
    """A ticket that cannot be filed as given; the message is safe to show."""


def _clean_body(body: str) -> str:
    body = (body or "").strip()
    if not body:
        raise TicketError("Write your message first.")
    if len(body) > MAX_BODY_LENGTH:
        raise TicketError(f"Keep the message under {MAX_BODY_LENGTH} characters.")
    return body


def _submitter(user_id: int | None, email: str | None) -> dict:
    """Exactly one of a signed-in user or a verified guest address files a ticket."""
    if (user_id is None) == (not email):
        raise TicketError("A ticket needs either a signed-in user or a verified email.")
    if user_id is not None:
        return {"submitted_by_id": user_id, "email": None}
    return {"submitted_by_id": None, "email": email.strip().lower()}


def submit_help(body: str, *, user_id: int | None = None, email: str | None = None) -> int:
    """File a help request (§6.3 Tickets, SRS FR 18). Returns the ticket id."""
    ticket = Ticket.objects.create(
        kind=Ticket.Kind.HELP, body=_clean_body(body), **_submitter(user_id, email)
    )
    return ticket.id


def submit_report(
    body: str, charity_id: int, *, user_id: int | None = None, email: str | None = None
) -> int:
    """File a report about one charity (§6.3 Tickets, SRS FR 19). Returns the ticket id.

    The caller has already checked that the charity exists; it is a FK, so a
    stale id fails here rather than filing a report about nothing.
    """
    if charity_id is None:
        raise TicketError("Choose the charity you are reporting.")
    ticket = Ticket.objects.create(
        kind=Ticket.Kind.REPORT,
        charity_id=charity_id,
        body=_clean_body(body),
        **_submitter(user_id, email),
    )
    return ticket.id
