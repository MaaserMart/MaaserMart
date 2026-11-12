"""Tables owned by approvals (design doc §5.2.5-5.2.8)."""

import uuid

from django.conf import settings
from django.db import models


class ApprovalRequest(models.Model):
    """§5.2.5 APPROVAL_REQUEST: every request an admin decides. Rejected ones are kept."""

    class Kind(models.TextChoices):
        NEW_CHARITY = "new_charity", "New charity"
        OWNER_CLAIM = "owner_claim", "Owner claim"
        EDIT = "edit", "Edit"
        RABBI = "rabbi", "Rabbi"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        REJECTED = "rejected", "Rejected"
        APPROVED = "approved", "Approved"

    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    kind = models.CharField(max_length=16, choices=Kind.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    submitted_at = models.DateTimeField(auto_now_add=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    batch_id = models.UUIDField(default=uuid.uuid4)

    class Meta:
        indexes = [
            models.Index(fields=["status", "submitted_at"], name="approval_status_submitted"),
        ]

    def __str__(self):
        return f"{self.kind} #{self.pk} ({self.status})"


class NewCharityRequest(models.Model):
    """§5.2.6 NEW_CHARITY_REQUEST."""

    approval_request = models.OneToOneField(
        ApprovalRequest, on_delete=models.CASCADE, related_name="new_charity"
    )
    charity = models.ForeignKey("charities.Charity", on_delete=models.PROTECT, related_name="+")


class OwnerClaimRequest(models.Model):
    """§5.2.7 OWNER_CLAIM_REQUEST."""

    approval_request = models.OneToOneField(
        ApprovalRequest, on_delete=models.CASCADE, related_name="owner_claim"
    )
    charity = models.ForeignKey("charities.Charity", on_delete=models.PROTECT, related_name="+")


class EditRequest(models.Model):
    """§5.2.8 EDIT_REQUEST: one proposed field change to a charity or a rabbi profile."""

    class TargetType(models.TextChoices):
        CHARITY = "charity", "Charity"
        PROFILE = "profile", "Profile"

    class Field(models.TextChoices):
        NAME = "name", "Name"
        DESCRIPTION = "description", "Description"
        TAGLINE = "tagline", "Tagline"
        IMAGE = "image", "Image"
        LOCATION = "location", "Location"
        WEBSITE_DONATE = "website_donate", "Donate page"
        WEBSITE_ABOUT = "website_about", "About page"
        WEBSITE_CONTACT = "website_contact", "Contact page"
        TITLE = "title", "Title"

    approval_request = models.OneToOneField(
        ApprovalRequest, on_delete=models.CASCADE, related_name="edit"
    )
    # Nullable because a profile edit has no charity; see the check constraint below.
    charity = models.ForeignKey(
        "charities.Charity", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name="+"
    )
    target_type = models.CharField(max_length=16, choices=TargetType.choices)
    field = models.CharField(max_length=32, choices=Field.choices)
    old_value = models.TextField(null=True, blank=True)
    new_value = models.TextField()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(target_type="charity", charity__isnull=False)
                    | models.Q(target_type="profile", user__isnull=False)
                ),
                name="edit_request_target_present",
            ),
        ]
