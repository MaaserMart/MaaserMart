"""Charity visibility through the charities services (D-038, D-039)."""

import pytest

from apps.charities.models import Charity
from apps.charities.services import hide_charity, publish_charity, update_charity
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


def test_update_saves_fields_and_records_one_event():
    charity = CharityFactory()
    admin = UserFactory()

    update_charity(charity.id, by_user_id=admin.id, name="New Name", tagline="New tagline")

    charity.refresh_from_db()
    assert (charity.name, charity.tagline) == ("New Name", "New tagline")
    event = Event.objects.get(charity=charity, action=Event.Action.CHARITY_UPDATED)
    assert event.user_id == admin.id


def test_update_with_the_same_values_records_no_event():
    """A save that changes nothing is not a change (D-041's rule)."""
    charity = CharityFactory(name="Same Name")

    update_charity(charity.id, name="Same Name")

    assert not Event.objects.exists()


def test_update_only_saves_the_fields_it_changed():
    charity = CharityFactory(name="Old Name", tagline="Old tagline")

    update_charity(charity.id, name="New Name")

    charity.refresh_from_db()
    assert (charity.name, charity.tagline) == ("New Name", "Old tagline")


def test_update_cannot_change_visibility():
    """Visibility belongs to publish/hide, which are the audited switch (D-038)."""
    charity = CharityFactory()

    with pytest.raises(ValueError, match="is_visible"):
        update_charity(charity.id, is_visible=True)

    charity.refresh_from_db()
    assert charity.is_visible is False
    assert not Event.objects.exists()


def test_update_unknown_charity_raises_and_records_nothing():
    with pytest.raises(Charity.DoesNotExist):
        update_charity(999_999, name="New Name")
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


def test_a_cleared_field_is_stored_as_null_not_an_empty_string():
    """D-013: "absent" has one encoding in the schema (audit D5)."""
    charity = CharityFactory(description="Some text", tagline="A tagline", image=None)
    update_charity(charity.id, description="", tagline="   ", image="charities/img/charity-02.svg")
    charity.refresh_from_db()
    assert charity.description is None
    assert charity.tagline is None
    assert charity.image == "charities/img/charity-02.svg"


def test_a_static_path_is_an_acceptable_image():
    charity = CharityFactory()
    update_charity(charity.id, image="charities/img/charity-03.svg")
    charity.refresh_from_db()
    assert charity.image == "charities/img/charity-03.svg"


@pytest.mark.parametrize(
    "image",
    [
        "https://tracker.example/pixel.png",  # host not on the allowlist
        "javascript:alert(1)",
        "/etc/passwd",
        "../../secret.png",
        "charities/../../secret.png",
    ],
)
def test_an_unsafe_image_is_refused(image):
    """A card never renders a value the template cannot trust (audit B8)."""
    charity = CharityFactory()
    with pytest.raises(ValueError):
        update_charity(charity.id, image=image)
    charity.refresh_from_db()
    assert charity.image is None


@pytest.mark.django_db
def test_an_allowlisted_image_host_is_accepted(settings):
    settings.CHARITY_IMAGE_HOSTS = [".example.org"]
    charity = CharityFactory()

    update_charity(charity.id, image="https://img.example.org/charity.png")

    charity.refresh_from_db()
    assert charity.image == "https://img.example.org/charity.png"
