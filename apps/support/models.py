"""Tables owned by support (design doc §5.2.19)."""

from django.conf import settings
from django.db import models


class Ticket(models.Model):
    """§5.2.19 TICKET: help requests and charity reports."""

    class Kind(models.TextChoices):
        HELP = "help", "Help"
        REPORT = "report", "Report"

    class Status(models.TextChoices):
        RESPONDED = "responded", "Responded"
        NOT_RESPONDED = "not_responded", "Not responded"
        CLOSED = "closed", "Closed"

    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    kind = models.CharField(max_length=16, choices=Kind.choices)
    charity = models.ForeignKey(
        "charities.Charity", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    # A guest's verified address, where the reply goes (§6.3 Tickets). Empty for a
    # signed-in user, whose reply goes to the account's address (D-072).
    email = models.EmailField(null=True, blank=True)
    body = models.TextField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.NOT_RESPONDED)
    responded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    # The admin's answer, as emailed to the submitter (§6.3 Tickets, D-072).
    response = models.TextField(null=True, blank=True)
    responded = models.DateTimeField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    closed = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["status", "created"], name="ticket_status_created")]
