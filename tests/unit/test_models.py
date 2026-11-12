"""Database constraints that the schema relies on (design doc §5.2, D-014, D-019)."""

import pytest
from django.db import IntegrityError

from apps.approvals.models import ApprovalRequest, EditRequest
from tests.factories import (
    ApprovalRequestFactory,
    CharityFactory,
    LocationFactory,
    ReviewFactory,
    UserFactory,
)

pytestmark = pytest.mark.django_db


def test_email_is_unique_ignoring_case():
    UserFactory(email="sara@example.com")
    with pytest.raises(IntegrityError):
        UserFactory(email="Sara@Example.com")


def test_username_is_unique_ignoring_case():
    UserFactory(username="sara")
    with pytest.raises(IntegrityError):
        UserFactory(username="SARA")


@pytest.mark.parametrize("rating", [0, 6])
def test_review_rating_must_be_1_to_5(rating):
    with pytest.raises(IntegrityError):
        ReviewFactory(rating=rating)


def test_charity_edit_request_needs_a_charity():
    with pytest.raises(IntegrityError):
        EditRequest.objects.create(
            approval_request=ApprovalRequestFactory(),
            target_type=EditRequest.TargetType.CHARITY,
            field=EditRequest.Field.NAME,
            new_value="New name",
        )


def test_profile_edit_request_needs_no_charity():
    user = UserFactory()
    EditRequest.objects.create(
        approval_request=ApprovalRequestFactory(submitted_by=user),
        target_type=EditRequest.TargetType.PROFILE,
        user=user,
        field=EditRequest.Field.TITLE,
        new_value="Rav",
    )


def test_location_is_unique():
    LocationFactory(name="Lakewood", region="New Jersey", country="USA")
    with pytest.raises(IntegrityError):
        LocationFactory(name="Lakewood", region="New Jersey", country="USA")


def test_charity_created_is_set_automatically():
    assert CharityFactory().created is not None


def test_approval_request_needs_an_explicit_batch_id():
    with pytest.raises(IntegrityError):
        ApprovalRequest.objects.create(kind=ApprovalRequest.Kind.RABBI)
