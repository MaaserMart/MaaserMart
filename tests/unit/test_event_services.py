"""The events app's public interface (§6.1)."""

import pytest

from apps.events.models import Event
from apps.events.services import record_event
from tests.factories import CharityFactory

pytestmark = pytest.mark.django_db


def test_record_event_stores_the_event():
    charity = CharityFactory()
    record_event(charity.id, "view")
    assert Event.objects.get().action == Event.Action.VIEW


def test_record_event_rejects_an_unknown_action():
    charity = CharityFactory()
    with pytest.raises(ValueError, match="charity_updatd"):
        record_event(charity.id, "charity_updatd")
    assert not Event.objects.exists()
