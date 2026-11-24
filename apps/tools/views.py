"""The maaser tools pages under /tools/ (§6.3.1, SRS FR 20–22, D-027, D-074).

Members only. Every account is a member (D-YOSEF-accounts-login), so signing in
is the check; tools depends on nothing (§6.1) and does not ask accounts.
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .services import (
    DONATION,
    INCOME,
    MAX_NOTE_LENGTH,
    TransactionError,
    add_transaction,
    delete_transaction,
    list_transactions,
    maaser_summary,
)

# Each ledger page's type, URL name and wording.
LEDGERS = {
    INCOME: {
        "url_name": "tools:income",
        "title": "Income",
        "noun": "income",
        "intro": "Record what you earn. A tenth of it is maaser.",
    },
    DONATION: {
        "url_name": "tools:donations",
        "title": "Donations",
        "noun": "donation",
        "intro": "Record what you give. It counts against the maaser you owe.",
    },
}


@login_required
def index(request: HttpRequest) -> HttpResponse:
    """The tools front page: what is owed now, and the way to each page."""
    return render(request, "tools/index.html", {"summary": maaser_summary(request.user.id)})


@login_required
def maaser(request: HttpRequest) -> HttpResponse:
    """The maaser calculator (FR 20): income / 10 − donations, never below zero."""
    return render(request, "tools/maaser.html", {"summary": maaser_summary(request.user.id)})


def _ledger(request: HttpRequest, type: str) -> HttpResponse:
    ledger = LEDGERS[type]
    error = None
    if request.method == "POST":
        try:
            add_transaction(
                request.user.id,
                type,
                request.POST.get("amount", ""),
                request.POST.get("date", ""),
                request.POST.get("note", ""),
            )
        except TransactionError as exc:
            error = str(exc)
        else:
            messages.success(request, f"Added the {ledger['noun']}.")
            # Post/redirect/get, so a refresh does not record it twice.
            return redirect(ledger["url_name"])
    entries = list_transactions(request.user.id, type)
    return render(
        request,
        "tools/ledger.html",
        {
            "ledger": ledger,
            "type": type,
            "entries": entries,
            "total": sum((entry.amount for entry in entries), start=0),
            "error": error,
            "form": request.POST if error else {},
            "today": timezone.localdate().isoformat(),
            "max_note_length": MAX_NOTE_LENGTH,
        },
        status=400 if error else 200,
    )


@login_required
def income(request: HttpRequest) -> HttpResponse:
    """Income history and the form to add to it (FR 21)."""
    return _ledger(request, INCOME)


@login_required
def donations(request: HttpRequest) -> HttpResponse:
    """Donation history and the form to add to it (FR 22)."""
    return _ledger(request, DONATION)


@login_required
@require_POST
def delete(request: HttpRequest, type: str, transaction_id: int) -> HttpResponse:
    """Remove one of the member's own entries and return to its page."""
    ledger = LEDGERS.get(type)
    if ledger is None or not delete_transaction(request.user.id, transaction_id):
        # Someone else's id looks the same as a missing one.
        raise Http404
    messages.success(request, f"Removed the {ledger['noun']}.")
    return redirect(ledger["url_name"])
