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


def test_editing_a_charity_records_an_event(client, admin_user):
    """D-052: an admin edit is a save too, so it moves "most recently updated"."""
    charity = CharityFactory(name="Old Name")

    response = client.post(f"{CHANGELIST}{charity.id}/change/", {"name": "New Name"})

    assert response.status_code == 302
    charity.refresh_from_db()
    assert charity.name == "New Name"
    event = Event.objects.get(charity=charity, action=Event.Action.CHARITY_UPDATED)
    assert event.user_id == admin_user.id


def test_editing_without_a_change_records_no_event(client, admin_user):
    fields = {
        "name": "Old Name",
        "tagline": "Old tagline",
        "description": "Old description",
        "image": "charities/img/charity-01.svg",
    }
    charity = CharityFactory(**fields)

    client.post(f"{CHANGELIST}{charity.id}/change/", fields)

    assert not Event.objects.filter(charity=charity, action=Event.Action.CHARITY_UPDATED).exists()


def test_publish_and_hide_actions_go_through_the_services(client, admin_user):
    charity = CharityFactory()

    client.post(CHANGELIST, {"action": "publish", "_selected_action": [charity.id]})
    assert Charity.objects.get(id=charity.id).is_visible is True

    client.post(CHANGELIST, {"action": "hide", "_selected_action": [charity.id]})
    assert Charity.objects.get(id=charity.id).is_visible is False

    events = Event.objects.filter(charity=charity, action=Event.Action.CHARITY_UPDATED)
    assert list(events.values_list("user_id", flat=True)) == [admin_user.id, admin_user.id]


def test_an_admin_added_charity_is_published(client, admin_user):
    """D-038: an admin who adds a charity creates it already approved (audit B7)."""
    response = client.post(
        f"{CHANGELIST}add/",
        {"name": "Brand New Fund", "tagline": "", "description": "", "image": ""},
    )

    assert response.status_code == 302
    charity = Charity.objects.get(name="Brand New Fund")
    assert charity.is_visible is True
    assert Event.objects.filter(charity=charity, action=Event.Action.CHARITY_UPDATED).exists()


def test_an_admin_changed_field_the_service_cannot_apply_is_an_error(admin_user):
    """A changed field outside EDITABLE_FIELDS must not be silently dropped (B2)."""
    from types import SimpleNamespace

    from django.contrib import admin as django_admin

    from apps.charities.admin import CharityAdmin, CharityAdminUnappliedFieldError

    charity = CharityFactory()
    request = SimpleNamespace(user=admin_user)

    class Form:
        changed_data = ["name", "slug"]
        cleaned_data = {"name": "New Name", "slug": "new-name"}

    with pytest.raises(CharityAdminUnappliedFieldError, match="slug"):
        CharityAdmin(Charity, django_admin.site).save_model(request, charity, Form(), change=True)
