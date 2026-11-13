"""Public interface of the events app.

Other apps call only the functions defined here, never this app's models.
"""

from .models import Event


def record_event(charity_id, action, link_id=None, user_id=None):
    """Record one EVENT (§6.1). `action` must be one of Event.Action's values."""
    if action not in Event.Action.values:
        raise ValueError(f"Unknown event action {action!r}")
    Event.objects.create(charity_id=charity_id, action=action, link_id=link_id, user_id=user_id)
