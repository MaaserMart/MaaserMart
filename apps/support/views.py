"""The help and report pages (§6.2, SRS FR 18 and FR 19, D-072).

Both pages are one form posted back to itself. The button pressed names the
step (`action`): a guest sends a code, then types it, then submits; a signed-in
user only submits. Each re-render keeps what was typed, so a step never costs
the visitor their message.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from apps.charities.services import find_charities_by_name, get_charity_choice
from common.clients import client_network

from . import verification
from .services import MAX_BODY_LENGTH, TicketError, submit_help, submit_report


def _guest_step(request: HttpRequest, action: str) -> tuple[str | None, str | None]:
    """Run a guest's send-code or verify step. Returns (notice, error)."""
    network = client_network(request)
    if action == "send_code":
        email = request.POST.get("email", "").strip()
        try:
            validate_email(email)
        except ValidationError:
            return None, "Enter a valid email address."
        result = verification.start(request.session, email, network)
    else:
        result = verification.confirm(request.session, request.POST.get("code", ""), network)
    return (result.message, None) if result.ok else (None, result.message)


def _submitter(request: HttpRequest) -> dict:
    """Who files the ticket: the account, or the guest's verified address."""
    if request.user.is_authenticated:
        return {"user_id": request.user.id}
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
