"""Tables owned by tools (design doc §5.2.18)."""

from django.conf import settings
from django.db import models


class Transaction(models.Model):
    """§5.2.18 TRANSACTION: a member's income or donation, for maaser tracking."""

    class Type(models.TextChoices):
        INCOME = "income", "Income"
        DONATION = "donation", "Donation"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    type = models.CharField(max_length=16, choices=Type.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField(null=True, blank=True)
    charity = models.ForeignKey(
        "charities.Charity", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    note = models.CharField(max_length=500, null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["user", "type"], name="transaction_user_type")]
