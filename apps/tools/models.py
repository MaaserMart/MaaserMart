"""Tables owned by tools (design doc §5.2.18)."""

from django.conf import settings
from django.db import models
from django.utils import timezone


class Transaction(models.Model):
    """§5.2.18 TRANSACTION: a member's income or donation, for maaser tracking."""

    class Type(models.TextChoices):
        INCOME = "income", "Income"
        DONATION = "donation", "Donation"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    type = models.CharField(max_length=16, choices=Type.choices)
    # A maaser ledger has no non-positive amounts: `0` contributes nothing and a
    # negative would invert income and donation (D-055).
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    # Required: a ledger line without a date cannot be ordered or totalled per
    # period, so an omitted date means today (D-055).
    date = models.DateField(default=timezone.localdate)
    charity = models.ForeignKey(
        "charities.Charity", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    note = models.CharField(max_length=500, null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["user", "type"], name="transaction_user_type")]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="transaction_amount_gt_0"
            ),
        ]
