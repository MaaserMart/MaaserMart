"""Tables owned by events (design doc §5.2.17). Other apps are referenced by string only."""

from django.conf import settings
from django.db import models


class Event(models.Model):
    """§5.2.17 EVENT: page views, link clicks and charity changes."""

    class Action(models.TextChoices):
        VIEW = "view", "View"
        LINK_CLICK = "link_click", "Link click"
        REJECT = "reject", "Reject"
        CHARITY_UPDATED = "charity_updated", "Charity updated"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    charity = models.ForeignKey("charities.Charity", on_delete=models.PROTECT, related_name="+")
    # Index on link_id (§5.2.20) is the FK index.
    link = models.ForeignKey(
        "charities.Link", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    action = models.CharField(max_length=32, choices=Action.choices)
    hidden_by_user = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["charity", "action", "created"], name="event_charity_action_created"
            ),
            models.Index(fields=["user", "created"], name="event_user_created"),
        ]
