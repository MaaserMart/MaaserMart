"""Public interface of the tools app (§6.1: income and donation CRUD, maaser calculation).

Other apps call only the functions defined here, never this app's models. Every
function takes the member's user id and touches only that member's rows, so a
caller cannot read or delete someone else's ledger by passing a row id.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.db.models import Sum
from django.utils import timezone

from .models import Transaction

INCOME = Transaction.Type.INCOME
DONATION = Transaction.Type.DONATION

# The column is Decimal(12, 2): anything at or above this cannot be stored.
MAX_AMOUNT = Decimal("9999999999.99")
MAX_NOTE_LENGTH = 500
MAASER_RATE = Decimal("0.10")
CENT = Decimal("0.01")


class TransactionError(ValueError):
    """An entry that cannot be saved as given; the message is safe to show."""


@dataclass(frozen=True)
class Entry:
    """One ledger line as the tools pages show it."""

    id: int
    type: str
    amount: Decimal
    date: datetime.date
    note: str


@dataclass(frozen=True)
class MaaserSummary:
    """The calculator's answer (§6.4 Maaser Calculator) and the totals behind it."""

    income: Decimal
    donations: Decimal
    # One tenth of income, to the cent.
    due: Decimal
    # due − donations, clamped at zero: maaser cannot be given before the fact (§6.3).
    owed: Decimal
    # What donations exceed `due` by. Shown, never subtracted from future income.
    given_beyond: Decimal


def _clean_amount(raw) -> Decimal:
    try:
        amount = Decimal(str(raw).strip().replace(",", ""))
    except (InvalidOperation, AttributeError):
        raise TransactionError("Enter the amount as a number, like 1250.00.") from None
    if not amount.is_finite():
        raise TransactionError("Enter the amount as a number, like 1250.00.")
    if amount != amount.quantize(CENT):
        raise TransactionError("Amounts go to the cent at most.")
    if amount <= 0:
        # The table refuses it too (D-055); this is the readable version.
        raise TransactionError("The amount must be more than zero.")
    if amount > MAX_AMOUNT:
        raise TransactionError("That amount is too large.")
    return amount


def _clean_date(raw) -> datetime.date:
    if raw in (None, ""):
        return timezone.localdate()
    if isinstance(raw, datetime.date):
        date = raw
    else:
        try:
            date = datetime.date.fromisoformat(str(raw).strip())
        except ValueError:
            raise TransactionError("Enter the date as YYYY-MM-DD.") from None
    if date > timezone.localdate():
        raise TransactionError("The date cannot be in the future.")
    return date


def add_transaction(user_id: int, type: str, amount, date=None, note: str = "") -> int:
    """Record one income or donation for a member. Returns the new row's id.

    `date` defaults to today (D-055). Future dates are refused: the ledger is
    what already happened, and a future donation would lower maaser owed today.
    """
    if type not in (INCOME, DONATION):
        raise TransactionError("Choose income or donation.")
    note = (note or "").strip()
    if len(note) > MAX_NOTE_LENGTH:
        raise TransactionError(f"Keep the note under {MAX_NOTE_LENGTH} characters.")
    row = Transaction.objects.create(
        user_id=user_id,
        type=type,
        amount=_clean_amount(amount),
        date=_clean_date(date),
        note=note or None,
    )
    return row.id


def list_transactions(user_id: int, type: str) -> list[Entry]:
    """A member's income or donations, newest first."""
    rows = Transaction.objects.filter(user_id=user_id, type=type).order_by("-date", "-id")
    return [
        Entry(id=row.id, type=row.type, amount=row.amount, date=row.date, note=row.note or "")
        for row in rows
    ]


def delete_transaction(user_id: int, transaction_id: int) -> bool:
    """Remove one of the member's own entries. False when there was none to remove."""
    deleted, _ = Transaction.objects.filter(user_id=user_id, pk=transaction_id).delete()
    return bool(deleted)


def maaser_summary(user_id: int) -> MaaserSummary:
    """income / 10 − donations for one member, never below zero (§6.4, §6.3).

    All of a member's amounts are taken to be in one currency (§6.3.1).
    """
    totals = {
        row["type"]: row["total"]
        for row in Transaction.objects.filter(user_id=user_id)
        .values("type")
        .annotate(total=Sum("amount"))
        .order_by()
    }
    income = totals.get(INCOME) or Decimal("0.00")
    donations = totals.get(DONATION) or Decimal("0.00")
    due = (income * MAASER_RATE).quantize(CENT, rounding=ROUND_HALF_UP)
    balance = due - donations
    zero = Decimal("0.00")
    return MaaserSummary(
        income=income,
        donations=donations,
        due=due,
        owed=max(balance, zero),
        given_beyond=max(-balance, zero),
    )


def maaser_owed(user_id: int) -> Decimal:
    """Just the amount still owed, for callers such as the member dashboard."""
    return maaser_summary(user_id).owed
