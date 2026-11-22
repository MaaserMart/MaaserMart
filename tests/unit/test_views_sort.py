"""Black-box page contracts: ordering by name, rating, activity and recency.

Split out of tests/unit/test_views.py (audit T3): one file per page feature, so
a reader finds the test for a behaviour without scanning 750 lines and feature
branches stop colliding on one file. The module docstring of test_views.py lists
what is where.
"""

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.charities.models import Charity, Review
from apps.charities.sorting import DEFAULT_SORT


class ListingSortPageTest(TestCase):
    """Black-box: a visitor picks an order and the listing follows it (§6.2.5)."""

    def setUp(self) -> None:
        self.url = reverse("charities:listing")

    def test_the_sort_control_offers_every_mechanism(self) -> None:
        body = self.client.get(self.url).content.decode()

        for value, label in [
            ("alphabetical", "Name"),
            ("trending", "Trending"),
            ("popular", "Most popular"),
            ("rating", "Highest rated"),
            ("haskamos", "Most haskamos"),
            ("newest", "Most recently added"),
            ("updated", "Most recently updated"),
        ]:
            with self.subTest(value=value):
                self.assertIn(f'<option value="{value}"', body)
                self.assertIn(label, body)

        self.assertIn('class="sort__select"', body)
        self.assertIn('id="sort"', body)
        self.assertIn('name="sort"', body)
        self.assertIn('name="direction"', body)

    def test_name_a_to_z_is_the_default_state(self) -> None:
        body = self.client.get(self.url).content.decode()

        self.assertIn('<option value="alphabetical" selected>Name</option>', body)
        self.assertIn("A to Z", body)
        self.assertIn("Z to A", body)

    def test_the_current_direction_is_marked_once(self) -> None:
        body = self.client.get(self.url).content.decode()
        sort_form = body[
            body.index('<form class="sort"') : body.index(
                "</form>", body.index('<form class="sort"')
            )
        ]

        self.assertEqual(sort_form.count('aria-current="true"'), 1)

    def test_a_chosen_sort_reorders_the_page(self) -> None:
        author = User.objects.create_user(username="sort-reviewer", password="x")
        low = Charity.objects.create(name="Alpha")
        high = Charity.objects.create(name="Zeta")
        Review.objects.create(charity=low, author=author, rating=2)
        Review.objects.create(charity=high, author=author, rating=5)

        response = self.client.get(self.url, {"sort": "rating", "direction": "desc"})

        self.assertEqual(
            [charity.name for charity in response.context["page"].items], ["Zeta", "Alpha"]
        )

    def test_a_mechanism_starts_high_to_low(self) -> None:
        author = User.objects.create_user(username="sort-reviewer", password="x")
        low = Charity.objects.create(name="Alpha")
        high = Charity.objects.create(name="Zeta")
        Review.objects.create(charity=low, author=author, rating=2)
        Review.objects.create(charity=high, author=author, rating=5)

        response = self.client.get(self.url, {"sort": "rating"})

        self.assertEqual(response.context["page"].sort.direction, "desc")
        self.assertEqual(response.context["page"].items[0].name, "Zeta")

    def test_low_to_high_reverses_the_page(self) -> None:
        author = User.objects.create_user(username="sort-reviewer", password="x")
        low = Charity.objects.create(name="Alpha")
        high = Charity.objects.create(name="Zeta")
        Review.objects.create(charity=low, author=author, rating=2)
        Review.objects.create(charity=high, author=author, rating=5)

        response = self.client.get(self.url, {"sort": "rating", "direction": "asc"})

        self.assertEqual(
            [charity.name for charity in response.context["page"].items], ["Alpha", "Zeta"]
        )

    def test_an_unrecognized_sort_falls_back_to_the_default(self) -> None:
        Charity.objects.create(name="Adas Chessed")

        response = self.client.get(self.url, {"sort": "sideways", "direction": "desc"})

        self.assertEqual(response.context["page"].sort, DEFAULT_SORT)
        self.assertIn('<option value="alphabetical" selected>', response.content.decode())

    def test_the_sort_form_sends_no_page_so_a_new_order_starts_at_page_one(self) -> None:
        """§6.2.5: the reader is shown page 1 of the new order."""
        body = self.client.get(self.url, {"page": 2, "page_size": 2}).content.decode()
        sort_form = body[
            body.index('<form class="sort"') : body.index(
                "</form>", body.index('<form class="sort"')
            )
        ]

        self.assertNotIn('name="page"', sort_form)

    def test_pagination_links_keep_the_sort(self) -> None:
        for index in range(1, 4):
            Charity.objects.create(name=f"Charity {index:02d}")

        response = self.client.get(
            self.url, {"sort": "rating", "direction": "desc", "page_size": 2}
        )

        self.assertContains(
            response,
            "page=2&amp;page_size=2&amp;sort=rating&amp;direction=desc",
        )

    def test_the_page_size_form_keeps_the_sort(self) -> None:
        Charity.objects.create(name="Adas Chessed")

        response = self.client.get(self.url, {"sort": "rating", "direction": "desc"})

        self.assertContains(response, '<input type="hidden" name="sort" value="rating">')
        self.assertContains(response, '<input type="hidden" name="direction" value="desc">')

    def test_the_jump_form_keeps_the_sort(self) -> None:
        for index in range(1, 4):
            Charity.objects.create(name=f"Charity {index:02d}")

        body = self.client.get(self.url, {"sort": "newest", "page_size": 2}).content.decode()
        jump_form = body[body.index('<form class="jump"') :]
        jump_form = jump_form[: jump_form.index("</form>")]

        self.assertIn('name="sort" value="newest"', jump_form)
        self.assertIn('name="direction" value="desc"', jump_form)
