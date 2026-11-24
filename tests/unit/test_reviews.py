"""Members can write and edit one review; everyone can read it."""

import pytest
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse

from apps.charities.models import Review
from apps.charities.services import get_user_review, save_review
from tests.factories import CharityFactory, UserFactory

pytestmark = pytest.mark.django_db


def test_guest_can_read_but_cannot_submit(client):
    charity = CharityFactory()
    reviewer = UserFactory()
    Review.objects.create(charity=charity, author=reviewer, rating=4, body="Helpful")
    page = reverse("charities:detail", args=[charity.id])
    response = client.get(page)
    assert b"Helpful" in response.content
    assert b"Log in to write a review" in response.content
    response = client.post(reverse("charities:review", args=[charity.id]), {"rating": 5})
    assert response.status_code == 302
    assert response.url.startswith("/accounts/login/?next=")
    assert Review.objects.count() == 1
    with pytest.raises(PermissionDenied):
        save_review(AnonymousUser(), charity.id, 5)


def test_submit_and_edit_review_updates_summary(client):
    charity = CharityFactory()
    member = UserFactory()
    client.force_login(member)
    url = reverse("charities:review", args=[charity.id])
    assert client.post(url, {"rating": 5, "body": "Excellent"}).status_code == 302
    review = Review.objects.get(charity=charity, author=member)
    page = client.get(reverse("charities:detail", args=[charity.id]))
    assert b"Edit your review" in page.content
    assert b"Excellent" in page.content
    assert b"5.0 out of 5" in page.content
    assert client.post(url, {"rating": 2, "body": ""}).status_code == 302
    review.refresh_from_db()
    assert (review.rating, review.body) == (2, "")
    assert Review.objects.filter(charity=charity, author=member).count() == 1
    page = client.get(reverse("charities:detail", args=[charity.id]))
    assert b"2.0 out of 5" in page.content
    assert b"(1 review" in page.content
    assert get_user_review(member, charity.id).id == review.id


@pytest.mark.parametrize("rating", ["", "0", "6", "3.5", "not a rating"])
def test_invalid_ratings_do_not_write(client, rating):
    charity = CharityFactory()
    member = UserFactory()
    client.force_login(member)
    response = client.post(reverse("charities:review", args=[charity.id]), {"rating": rating})
    assert response.status_code == 400
    assert not Review.objects.exists()
    assert b'role="alert"' in response.content


def test_review_cannot_overwrite_another_members_review(client):
    charity = CharityFactory()
    other = UserFactory()
    Review.objects.create(charity=charity, author=other, rating=1, body="First")
    client.force_login(UserFactory())
    client.post(reverse("charities:review", args=[charity.id]), {"rating": 5, "body": "Second"})
    assert list(
        Review.objects.filter(charity=charity).order_by("rating").values_list("body", flat=True)
    ) == ["First", "Second"]


def test_unknown_charity_and_invalid_service_input(client):
    member = UserFactory()
    client.force_login(member)
    assert client.post(reverse("charities:review", args=[999999]), {"rating": 5}).status_code == 404
    charity = CharityFactory()
    for rating in (0, 6, "5", True):
        with pytest.raises(ValidationError):
            save_review(member, charity.id, rating)
    assert not Review.objects.exists()


def test_rating_uses_required_radio_choices_and_preserves_saved_selection(client):
    from html.parser import HTMLParser

    class RadioInputs(HTMLParser):
        def __init__(self):
            super().__init__()
            self.inputs = []

        def handle_starttag(self, tag, attrs):
            attributes = dict(attrs)
            if tag == "input" and attributes.get("name") == "rating":
                self.inputs.append(attributes)

    charity = CharityFactory()
    member = UserFactory()
    Review.objects.create(charity=charity, author=member, rating=4)
    client.force_login(member)
    response = client.get(reverse("charities:detail", args=[charity.id]))
    html = response.content.decode()
    parser = RadioInputs()
    parser.feed(html)

    assert [item["value"] for item in parser.inputs] == ["1", "2", "3", "4", "5"]
    assert all(item["type"] == "radio" and "required" in item for item in parser.inputs)
    assert [item["value"] for item in parser.inputs if "checked" in item] == ["4"]
    assert all(f'for="{item["id"]}"' in html for item in parser.inputs)
    assert "Rating (required)" in html
    assert html.count('aria-hidden="true">★</span>') == 5


def test_missing_rating_error_is_associated_with_radio_group(client):
    charity = CharityFactory()
    client.force_login(UserFactory())
    response = client.post(reverse("charities:review", args=[charity.id]), {"body": "Text"})
    html = response.content.decode()
    assert response.status_code == 400
    assert 'aria-describedby="review-rating-errors"' in html
    assert 'id="review-rating-errors"' in html
    assert 'role="alert"' in html
    assert "Text" in html
