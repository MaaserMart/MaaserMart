"""The help and report pages (§6.2, SRS FR 18 and FR 19, D-072).

Both pages are one form posted back to itself. The button pressed names the
step (`action`): a guest sends a code, then types it, then submits; a signed-in
user only submits. Each re-render keeps what was typed, so a step never costs
the visitor their message.
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.validators import validate_email
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.charities.services import find_charities_by_name, get_charity_choice

from . import verification
from .services import (
    CLOSE,
    MAX_BODY_LENGTH,
    TicketError,
    get_tickets,
    resolve_ticket,
    submit_help,
    submit_report,
)


def _guest_step(request: HttpRequest, action: str) -> tuple[str | None, str | None]:
    """Run a guest's send-code or verify step. Returns (notice, error)."""
    if action == "send_code":
        email = request.POST.get("email", "").strip()
        try:
            validate_email(email)
        except ValidationError:
            return None, "Enter a valid email address."
        result = verification.start(request.session, email)
    else:
        result = verification.confirm(request.session, request.POST.get("code", ""))
    return (result.message, None) if result.ok else (None, result.message)


def _submitter(request: HttpRequest) -> dict:
    """Who files the ticket: the account, or the guest's verified address."""
    if request.user.is_authenticated:
        # The reply goes to the account's address as it is now (D-073).
        if not request.user.email:
            raise TicketError("Your account has no email address for the reply.")
        return {"user_id": request.user.id, "email": request.user.email}
    email = verification.verified_email(request.session)
    if not email:
        raise TicketError("Verify your email address first.")
    return {"email": email}


def _context(request: HttpRequest, **extra) -> dict:
    guest = not request.user.is_authenticated
    return {
        "guest": guest,
        "verified_email": verification.verified_email(request.session) if guest else None,
        "pending_email": verification.pending_email(request.session) if guest else None,
        "body": request.POST.get("body", ""),
        "max_body_length": MAX_BODY_LENGTH,
        **extra,
    }


def help_page(request: HttpRequest) -> HttpResponse:
    """Ask the site's admins for help (FR 18)."""
    notice = error = None
    if request.method == "POST":
        action = request.POST.get("action", "submit")
        if action in ("send_code", "verify") and not request.user.is_authenticated:
            notice, error = _guest_step(request, action)
        else:
            try:
                submit_help(request.POST.get("body", ""), **_submitter(request))
            except TicketError as exc:
                error = str(exc)
            else:
                return render(request, "support/sent.html", {"kind": "help"})
    return render(request, "support/help.html", _context(request, notice=notice, error=error))


def report_page(request: HttpRequest) -> HttpResponse:
    """Report a charity to the site's admins (FR 19).

    `?charity=<id>` (the charity page's "Report this charity" link) arrives with
    the charity chosen; otherwise the visitor searches by name and picks one.
    """
    data = request.POST if request.method == "POST" else request.GET
    charity = get_charity_choice(data.get("charity"))
    query = data.get("q", "").strip()
    notice = error = None
    if request.method == "POST":
        action = request.POST.get("action", "submit")
        if action == "search":
            charity = None
        elif action in ("send_code", "verify") and not request.user.is_authenticated:
            notice, error = _guest_step(request, action)
        elif charity is None:
            error = "Choose the charity you are reporting."
        else:
            try:
                submit_report(request.POST.get("body", ""), charity.id, **_submitter(request))
            except TicketError as exc:
                error = str(exc)
            else:
                return render(request, "support/sent.html", {"kind": "report", "charity": charity})
    matches = find_charities_by_name(query) if query and charity is None else ()
    return render(
        request,
        "support/report.html",
        _context(
            request,
            notice=notice,
            error=error,
            charity=charity,
            query=query,
            matches=matches,
        ),
    )


# --- Admin ticket queue (§7.3.10, D-073) ---------------------------------------


def _admin_only(request: HttpRequest) -> HttpResponse | None:
    """Send a visitor to log in, refuse a non-admin, let an admin through."""
    if not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path())
    if not getattr(request.user, "is_admin", False):
        raise PermissionDenied
    return None


def ticket_queue(request: HttpRequest) -> HttpResponse:
    """Every open ticket, with a reply box and a close button on each."""
    if (refusal := _admin_only(request)) is not None:
        return refusal
    return _render_queue(request)


@require_POST
def resolve(request: HttpRequest, ticket_id: int) -> HttpResponse:
    """Reply to or close one ticket, then return to the queue."""
    if (refusal := _admin_only(request)) is not None:
        return refusal
    action = request.POST.get("action", "")
    text = request.POST.get("text", "")
    try:
        resolve_ticket(ticket_id, request.user.id, text, action)
    except TicketError as exc:
        return _render_queue(request, failed=(ticket_id, str(exc), text), status=400)
    done = "closed" if action == CLOSE else "answered"
    messages.success(request, f"Ticket {ticket_id} {done}.")
    return redirect("support_admin:tickets")


def _render_queue(request: HttpRequest, failed=None, status=200) -> HttpResponse:
    failed_id, error, draft = failed or (None, None, "")
    return render(
        request,
        "support/ticket_queue.html",
        {
            "tickets": get_tickets(),
            "failed_id": failed_id,
            "error": error,
            "draft": draft,
            "max_body_length": MAX_BODY_LENGTH,
        },
        status=status,
    )
