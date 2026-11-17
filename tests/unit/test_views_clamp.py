"""Black-box page contracts: out-of-range numbers being clamped visibly (D-046).

Split out of tests/unit/test_views.py (audit T3): one file per page feature, so
a reader finds the test for a behaviour without scanning 750 lines and feature
branches stop colliding on one file. The module docstring of test_views.py lists
what is where.
"""

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.charities.models import Charity, Review


class RatingClampOnThePageTest(TestCase):
    """D-046: an off-scale min_rating is clamped, and the page says so."""

    def setUp(self) -> None:
        self.url = reverse("charities:listing")
        self.charity = Charity.objects.create(name="Keren L'Dugma")
        author = User.objects.create_user(username="reviewer2", password="x")
        Review.objects.create(charity=self.charity, author=author, rating=5)

    def test_an_over_scale_rating_is_clamped_and_explained(self) -> None:
        response = self.client.get(self.url, {"min_rating": 99})
        body = response.content.decode()

        self.assertEqual(response.context["page"].total, 1)
        self.assertContains(response, "Kept between 1 and 5; using 5.")
        # the sidebar shows the value actually applied, not the one asked for
        self.assertRegex(body, r'name="min_rating"[\s\S]{0,200}?value="5"')

    def test_an_under_scale_rating_is_clamped_and_explained(self) -> None:
        response = self.client.get(self.url, {"min_rating": 0})

        self.assertContains(response, "Kept between 1 and 5; using 1.")

    def test_an_in_range_rating_has_no_note(self) -> None:
        response = self.client.get(self.url, {"min_rating": 4})

        self.assertNotContains(response, "Kept between")
