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
from apps.charities import services as charities

from .models import ApprovalRequest, OwnerClaimRequest

Kind = ApprovalRequest.Kind
Status = ApprovalRequest.Status

# The kinds an admin can approve or reject from the queue so far.
DECIDABLE_KINDS = {Kind.RABBI, Kind.OWNER_CLAIM}

# The role each kind of application asks for, in the words the applicant sees.
ROLE_WORDS = {Kind.RABBI: "rabbi", Kind.OWNER_CLAIM: "charity owner"}


def role_words(kind):
    return ROLE_WORDS.get(kind) or Kind(kind).label.lower()


def decision_email(kind, approved):
    """The subject and body of the email that tells the applicant the decision."""
    role = role_words(kind)
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
    ALREADY_APPLIED = "already_applied"  # One application per account, whatever its outcome.
    ALREADY_GRANTED = "already_granted"
    NO_SUCH_CHARITY = "no_such_charity"


class DecideOutcome(enum.Enum):
    DONE = "done"
    DONE_EMAIL_FAILED = "done_email_failed"  # Decided and saved; the email didn't queue.
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
        if _has_applied(user):
            return SubmitOutcome.ALREADY_APPLIED
        accounts.save_rabbi_profile(user.pk, display_name, title)
        ApprovalRequest.objects.create(submitted_by=user, kind=Kind.RABBI, batch_id=uuid.uuid4())
    return SubmitOutcome.SUBMITTED


def submit_owner_claim(user, charity_id):
    """Ask to own a charity already in the database (§6.2.2.5).

    Saves a pending request and which charity it is for. The user owns nothing
    until an admin approves (D-YOSEF-owner-signup).
    """
    with transaction.atomic():
        _lock_requests_of(user.pk)
        if accounts.CHARITY_OWNER in accounts.find_role(user):
            return SubmitOutcome.ALREADY_GRANTED
        if _has_applied(user):
            return SubmitOutcome.ALREADY_APPLIED
        if charities.get_charity_name(charity_id) is None:
            return SubmitOutcome.NO_SUCH_CHARITY
        request = ApprovalRequest.objects.create(
            submitted_by=user, kind=Kind.OWNER_CLAIM, batch_id=uuid.uuid4()
        )
        OwnerClaimRequest.objects.create(approval_request=request, charity_id=charity_id)
    return SubmitOutcome.SUBMITTED


def _has_applied(user):
    """One application per account, of any kind and whatever its outcome."""
    return ApprovalRequest.objects.filter(submitted_by=user).exists()


def latest_application(user):
    """The user's latest request as (role in words, status), e.g. ("rabbi", "pending").

    None if the user never applied.
    """
    row = (
        ApprovalRequest.objects.filter(submitted_by=user)
        .order_by("-submitted_at", "-id")
        .values_list("kind", "status")
        .first()
    )
    if row is None:
        return None
    kind, status = row
    return role_words(kind), status


def pending_count():
    return ApprovalRequest.objects.filter(status=Status.PENDING).count()


def get_requests():
    """Every pending request for the admin queue, oldest first (§6.2.13.5)."""
    requests = list(
        ApprovalRequest.objects.filter(status=Status.PENDING)
        .select_related("owner_claim")
        .order_by("submitted_at", "id")
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
        elif r.kind == Kind.OWNER_CLAIM and hasattr(r, "owner_claim"):
            # One query per claim; the queue is short (a bulk lookup can come later).
            charity_id = r.owner_claim.charity_id
            detail = f"Claims {charities.get_charity_name(charity_id)} (#{charity_id})"
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
    # Filled by the on_commit callback. It runs before we return only when this
    # atomic block is the outermost transaction (no ATOMIC_REQUESTS, no caller's
    # atomic); otherwise it runs later and a failed email still reports DONE.
    emailed = []
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
            if approve and request.kind == Kind.OWNER_CLAIM:
                claim = OwnerClaimRequest.objects.get(approval_request=request)
                accounts.add_charity_owner(user_id, claim.charity_id)
            subject, message = decision_email(request.kind, approve)
            # Only once the decision is saved, so a rolled-back decision sends nothing.
            transaction.on_commit(
                lambda: emailed.append(accounts.notify_user(user_id, subject, message))
            )
    if emailed == [False]:
        return DecideOutcome.DONE_EMAIL_FAILED
    return DecideOutcome.DONE
