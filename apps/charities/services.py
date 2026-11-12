"""Public interface of the charities app.

Other apps call only the functions defined here, never this app's models.
"""

from django.db import transaction

from apps.events.services import record_event

from .models import Charity


def publish_charity(charity_id, by_user_id=None):
    """Make a charity visible to the public. Approvals calls this once a charity is approved."""
    _set_visible(charity_id, True, by_user_id)


def hide_charity(charity_id, by_user_id=None):
    """Hide a charity from the public, for example to review it again after many reports."""
    _set_visible(charity_id, False, by_user_id)


def _set_visible(charity_id, visible, by_user_id):
    # Every change to a charity is recorded as a charity_updated EVENT (§6.1, D-039).
    with transaction.atomic():
        if not Charity.objects.filter(pk=charity_id).update(is_visible=visible):
            raise Charity.DoesNotExist(f"No charity with id {charity_id}")
        record_event(charity_id, "charity_updated", user_id=by_user_id)
