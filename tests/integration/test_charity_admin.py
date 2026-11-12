"""Django admin changes charity visibility only through the services (D-038, D-039)."""

import pytest
from django.contrib.auth import get_user_model

from apps.charities.models import Charity
from apps.events.models import Event
from tests.factories import CharityFactory

pytestmark = pytest.mark.django_db

CHANGELIST = "/django-admin/charities/charity/"


@pytest.fixture
def admin_user(client):
    user = get_user_model().objects.create_superuser("boss", "boss@example.com", "pw")
    client.force_login(user)
    return user


def test_visibility_is_not_editable_on_the_change_form(client, admin_user):
    charity = CharityFactory()
    html = client.get(f"{CHANGELIST}{charity.id}/change/").content.decode()
    assert 'name="is_visible"' not in html


def test_publish_and_hide_actions_go_through_the_services(client, admin_user):
    charity = CharityFactory()

    client.post(CHANGELIST, {"action": "publish", "_selected_action": [charity.id]})
    assert Charity.objects.get(id=charity.id).is_visible is True

    client.post(CHANGELIST, {"action": "hide", "_selected_action": [charity.id]})
    assert Charity.objects.get(id=charity.id).is_visible is False

    events = Event.objects.filter(charity=charity, action=Event.Action.CHARITY_UPDATED)
    assert list(events.values_list("user_id", flat=True)) == [admin_user.id, admin_user.id]
