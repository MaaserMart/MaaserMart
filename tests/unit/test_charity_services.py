"""Charity visibility through the charities services (D-038, D-039)."""

import pytest

from apps.charities.models import Charity
from apps.charities.services import hide_charity, publish_charity
from apps.events.models import Event
from tests.factories import CharityFactory, UserFactory

pytestmark = pytest.mark.django_db


def test_new_charity_is_hidden():
    assert CharityFactory().is_visible is False


def test_publish_makes_charity_visible():
    charity = CharityFactory()
    publish_charity(charity.id)
    charity.refresh_from_db()
    assert charity.is_visible is True


def test_hide_hides_a_published_charity_again():
    charity = CharityFactory()
    publish_charity(charity.id)
    hide_charity(charity.id)
    charity.refresh_from_db()
    assert charity.is_visible is False


def test_unknown_charity_raises():
    with pytest.raises(Charity.DoesNotExist):
        publish_charity(999_999)


@pytest.mark.parametrize("change", [publish_charity, hide_charity])
def test_each_change_records_who_changed_it(change):
    charity = CharityFactory()
    admin = UserFactory()
    if change is hide_charity:
        publish_charity(charity.id)

    change(charity.id, by_user_id=admin.id)

    event = Event.objects.filter(charity=charity).latest("id")
    assert event.action == Event.Action.CHARITY_UPDATED
    assert event.user_id == admin.id


def test_publish_then_hide_records_two_events():
    charity = CharityFactory()
    publish_charity(charity.id)
    hide_charity(charity.id)
    assert Event.objects.filter(charity=charity, action="charity_updated").count() == 2


def test_unknown_charity_records_no_event():
    with pytest.raises(Charity.DoesNotExist):
        hide_charity(999_999)
    assert not Event.objects.exists()


@pytest.mark.parametrize("change", [publish_charity, hide_charity])
def test_no_event_when_already_in_that_state(change):
    charity = CharityFactory()
    if change is hide_charity:
        publish_charity(charity.id)
    before = Event.objects.count()

    change(charity.id)
    change(charity.id)

    assert Event.objects.count() == before + 1
