"""Charity visibility through the charities services (D-038)."""

import pytest

from apps.charities.models import Charity
from apps.charities.services import hide_charity, publish_charity
from tests.factories import CharityFactory

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
