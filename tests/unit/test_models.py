"""Database constraints that the schema relies on (design doc §5.2, D-014, D-019)."""

import pytest
from django.db import IntegrityError
from django.utils import timezone

from apps.approvals.models import ApprovalRequest, EditRequest
from apps.charities.models import Charity
from apps.tools.models import Transaction
from tests.factories import (
    ApprovalRequestFactory,
    CharityFactory,
    LinkFactory,
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


def test_one_link_per_kind_per_charity():
    link = LinkFactory(kind="website_donate")
    LinkFactory(charity=link.charity, kind="website_about")
    with pytest.raises(IntegrityError):
        LinkFactory(charity=link.charity, kind="website_donate")


def test_one_review_per_member_per_charity():
    """§8.6, UC-05: a member reviews a charity once (D-055)."""
    review = ReviewFactory()
    with pytest.raises(IntegrityError):
        ReviewFactory(charity=review.charity, author=review.author)


def test_a_member_may_review_several_charities():
    author = UserFactory()
    ReviewFactory(author=author)
    ReviewFactory(author=author)


@pytest.mark.parametrize("amount", [0, -5])
def test_transaction_amount_must_be_positive(amount):
    """A maaser ledger line is a real amount of money (D-055)."""
    with pytest.raises(IntegrityError):
        Transaction.objects.create(user=UserFactory(), type=Transaction.Type.INCOME, amount=amount)


def test_transaction_date_defaults_to_today():
    transaction = Transaction.objects.create(
        user=UserFactory(), type=Transaction.Type.INCOME, amount="100.00"
    )
    assert transaction.date == timezone.localdate()


def test_the_listing_columns_are_indexed():
    """The default and `newest` orders sort by columns nothing else indexes (D-055)."""
    indexed = {",".join(index.fields) for index in Charity._meta.indexes}
    assert {"name,id", "created"} <= indexed


def test_pending_requests_can_be_read_by_batch():
    indexed = {",".join(index.fields) for index in ApprovalRequest._meta.indexes}
    assert "batch_id,status" in indexed
