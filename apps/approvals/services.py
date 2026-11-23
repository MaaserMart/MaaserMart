"""Public interface of the approvals app.

Other apps call only the functions defined here, never this app's models.
"""

import enum
import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime

from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone

from apps.accounts import services as accounts

from .models import ApprovalRequest

Kind = ApprovalRequest.Kind
Status = ApprovalRequest.Status

# The kinds an admin can approve or reject from the queue so far.
DECIDABLE_KINDS = {Kind.RABBI}


def decision_email(kind, approved):
    """The subject and body of the email that tells the applicant the decision."""
    role = Kind(kind).label.lower()
    if approved:
        return (
            f"Your MaaserMart {role} account is approved",
            f"Your {role} application was approved. You can now log in to MaaserMart.",
        )
    return f"Your MaaserMart {role} application", rejected_message(role)


def rejected_message(role):
    return (
        f"Your {role} application wasn't approved. If you think this is a mistake, "
        f"please email {settings.SUPPORT_EMAIL}."
    )


class SubmitOutcome(enum.Enum):
    SUBMITTED = "submitted"
    ALREADY_PENDING = "already_pending"
    ALREADY_GRANTED = "already_granted"


class DecideOutcome(enum.Enum):
    DONE = "done"
    NOT_FOUND = "not_found"
    ALREADY_DECIDED = "already_decided"  # Another admin got there first (§6.2.13.8).
    NOT_DECIDABLE = "not_decidable"  # A kind the queue can't decide yet.


@dataclass(frozen=True)
class QueueItem:
    id: int
    kind: str
    kind_label: str
    submitted_at: datetime
    batch_id: uuid.UUID
    username: str | None  # None when the account was deleted.
    email: str | None
    detail: str
    decidable: bool


def _lock_requests_of(user_id):
    """Make one user's submissions take turns, so two clicks can't both pass the checks.

    Held until the transaction ends.
    """
    key = f"approvals:user:{user_id}".encode()
    lock_id = int.from_bytes(hashlib.sha256(key).digest()[:8], "big", signed=True)
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [lock_id])


def submit_rabbi_request(user, display_name, title):
    """Ask to become a rabbi (§6.2.2.5). Saves the name and title and a pending request."""
    with transaction.atomic():
        _lock_requests_of(user.pk)
        if accounts.RABBI in accounts.find_role(user):
            return SubmitOutcome.ALREADY_GRANTED
        if has_pending(user, Kind.RABBI):
            return SubmitOutcome.ALREADY_PENDING
        accounts.save_rabbi_profile(user.pk, display_name, title)
        ApprovalRequest.objects.create(submitted_by=user, kind=Kind.RABBI, batch_id=uuid.uuid4())
    return SubmitOutcome.SUBMITTED


def pending_kinds(user):
    """The labels of a user's pending requests, oldest first, e.g. ["Rabbi"]."""
    kinds = (
        ApprovalRequest.objects.filter(submitted_by=user, status=Status.PENDING)
        .order_by("submitted_at", "id")
        .values_list("kind", flat=True)
    )
    return [Kind(kind).label for kind in kinds]


def has_pending(user, kind):
    """Whether the user already has a pending request of this kind, e.g. "rabbi"."""
    return ApprovalRequest.objects.filter(
        submitted_by=user, kind=kind, status=Status.PENDING
    ).exists()


def latest_application_status(user):
    """The status of the user's latest request ("pending", "rejected"...), or None."""
    return (
        ApprovalRequest.objects.filter(submitted_by=user)
        .order_by("-submitted_at", "-id")
        .values_list("status", flat=True)
        .first()
    )


def latest_application_label(user):
    """The role the user's latest request asks for, in words, e.g. "rabbi"."""
    kind = (
        ApprovalRequest.objects.filter(submitted_by=user)
        .order_by("-submitted_at", "-id")
        .values_list("kind", flat=True)
        .first()
    )
    return Kind(kind).label.lower() if kind else "account"


def pending_count():
    return ApprovalRequest.objects.filter(status=Status.PENDING).count()


def get_requests():
    """Every pending request for the admin queue, oldest first (§6.2.13.5)."""
    requests = list(
        ApprovalRequest.objects.filter(status=Status.PENDING).order_by("submitted_at", "id")
    )
    user_ids = [r.submitted_by_id for r in requests if r.submitted_by_id]
    names = accounts.usernames(user_ids)
    addresses = accounts.emails(user_ids)
    rabbis = accounts.rabbi_identities(
        r.submitted_by_id for r in requests if r.kind == Kind.RABBI and r.submitted_by_id
    )
    items = []
    for r in requests:
        detail = ""
        if r.kind == Kind.RABBI and r.submitted_by_id in rabbis:
            detail = rabbis[r.submitted_by_id].label
        items.append(
            QueueItem(
                id=r.pk,
                kind=r.kind,
                kind_label=Kind(r.kind).label,
                submitted_at=r.submitted_at,
                batch_id=r.batch_id,
                username=names.get(r.submitted_by_id),
                email=addresses.get(r.submitted_by_id),
                detail=detail,
                decidable=r.kind in DECIDABLE_KINDS,
            )
        )
    return items


def decide_request(request_id, approve, admin_user):
    """Approve or reject one request, and email the person who sent it (§6.2.13.5)."""
    with transaction.atomic():
        # The row lock makes a second admin wait, then see it is already decided.
        request = ApprovalRequest.objects.select_for_update().filter(pk=request_id).first()
        if request is None:
            return DecideOutcome.NOT_FOUND
        if request.status != Status.PENDING:
            return DecideOutcome.ALREADY_DECIDED
        if request.kind not in DECIDABLE_KINDS:
            return DecideOutcome.NOT_DECIDABLE
        request.status = Status.APPROVED if approve else Status.REJECTED
        request.decided_by = admin_user
        request.decided_at = timezone.now()
        request.save(update_fields=["status", "decided_by", "decided_at"])
        user_id = request.submitted_by_id
        if user_id is not None:
            if approve and request.kind == Kind.RABBI:
                accounts.grant_role(user_id, accounts.RABBI)
            subject, message = decision_email(request.kind, approve)
            # Only once the decision is saved, so a rolled-back decision sends nothing.
            transaction.on_commit(lambda: accounts.notify_user(user_id, subject, message))
    return DecideOutcome.DONE
