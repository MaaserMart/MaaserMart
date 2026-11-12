"""Public interface of the charities app.

Other apps call only the functions defined here, never this app's models.
"""

from .models import Charity


def publish_charity(charity_id):
    """Make a charity visible to the public. Approvals calls this once a charity is approved."""
    _set_visible(charity_id, True)


def hide_charity(charity_id):
    """Hide a charity from the public, for example to review it again after many reports."""
    _set_visible(charity_id, False)


def _set_visible(charity_id, visible):
    if not Charity.objects.filter(pk=charity_id).update(is_visible=visible):
        raise Charity.DoesNotExist(f"No charity with id {charity_id}")
