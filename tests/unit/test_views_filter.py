"""Black-box page contracts: domain, location and rabbi filters.

Split out of tests/unit/test_views.py (audit T3): one file per page feature, so
a reader finds the test for a behaviour without scanning 750 lines and feature
branches stop colliding on one file. The module docstring of test_views.py lists
what is where.
"""

import re

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.charities.models import Charity, Domain, Location, Review


class ListingFilterPageTest(TestCase):
    """Black-box: a visitor picks filters in the sidebar and the results narrow (§6.2.4)."""

    def setUp(self) -> None:
        self.url = reverse("charities:listing")
        self.food = Domain.objects.create(name="Food Security")
        self.education = Domain.objects.create(name="Education")
        self.pantry = Charity.objects.create(name="Pantry")
        self.school = Charity.objects.create(name="School")
        self.pantry.domains.add(self.food)
        self.school.domains.add(self.education)

    def test_the_sidebar_offers_every_domain_and_location(self) -> None:
        Location.objects.create(name="Lakewood", region="New Jersey", country="USA")

        response = self.client.get(self.url)

        self.assertContains(response, 'name="domain"')
        self.assertContains(response, "Food Security")
        self.assertContains(response, "Education")
        # A location is offered by its full identity, never its name alone (D-045).
        self.assertContains(response, "Lakewood, New Jersey, USA")

    def test_a_chosen_domain_narrows_the_results(self) -> None:
        response = self.client.get(self.url, {"domain": [self.food.id]})

        self.assertContains(response, "Pantry")
        self.assertNotContains(response, "School")

    def test_two_domains_are_or(self) -> None:
        response = self.client.get(self.url, {"domain": [self.food.id, self.education.id]})

        self.assertContains(response, "Pantry")
        self.assertContains(response, "School")

    def test_a_chosen_box_stays_ticked(self) -> None:
        response = self.client.get(self.url, {"domain": [self.food.id]})
        box = re.search(
            rf'name="domain"\s*value="{self.food.id}"\s*checked', response.content.decode()
        )

        self.assertIsNotNone(box, "the chosen domain should render ticked")

    def test_filters_and_numbers_are_and(self) -> None:
        author = User.objects.create_user(username="reviewer", password="x")
        Review.objects.create(charity=self.pantry, author=author, rating=5)
        Review.objects.create(charity=self.school, author=author, rating=1)

        response = self.client.get(
            self.url, {"domain": [self.food.id, self.education.id], "min_rating": 4}
        )

        self.assertContains(response, "Pantry")
        self.assertNotContains(response, "School")

    def test_no_match_says_so(self) -> None:
        response = self.client.get(self.url, {"min_rating": 5})

        self.assertContains(response, "No charities match those filters.")
        self.assertNotContains(response, "No charities found.")

    def test_an_empty_listing_still_says_no_charities_found(self) -> None:
        Charity.objects.all().delete()

        response = self.client.get(self.url)

        self.assertContains(response, "No charities found.")

    def test_the_filter_form_has_no_page_field_so_apply_starts_at_page_one(self) -> None:
        """§6.2.4: setting a filter returns page 1. The sidebar form sends no
        `page`, so a fresh Apply always lands on page 1; a URL with an explicit
        page keeps it, because UC-03 stores the whole view state in the URL."""
        for index in range(1, 26):
            Charity.objects.create(name=f"Charity {index:02d}")

        response = self.client.get(self.url, {"page": 3, "page_size": 5})

        form = response.content.decode()
        form = form[form.index('<form class="filters"') : form.index("</form>")]
        self.assertNotIn('name="page"', form)

    def test_a_shared_url_keeps_its_page_and_filters(self) -> None:
        for index in range(1, 26):
            charity = Charity.objects.create(name=f"Charity {index:02d}")
            charity.domains.add(self.food)

        response = self.client.get(self.url, {"page": 2, "page_size": 5, "domain": self.food.id})

        self.assertEqual(response.context["page"].number, 2)

    def test_page_links_keep_the_filters(self) -> None:
        for index in range(1, 26):
            charity = Charity.objects.create(name=f"Charity {index:02d}")
            charity.domains.add(self.food)

        response = self.client.get(self.url, {"domain": [self.food.id], "page_size": 5})

        self.assertContains(response, f"page=2&amp;page_size=5&amp;domain={self.food.id}")

    def test_page_size_form_keeps_the_filters(self) -> None:
        response = self.client.get(self.url, {"domain": [self.food.id]})

        self.assertContains(response, f'<input type="hidden" name="domain" value="{self.food.id}">')

    def test_a_sort_does_not_drop_the_active_filter(self) -> None:
        author = User.objects.create_user(username="sort-filter-reviewer", password="x")
        Review.objects.create(charity=self.pantry, author=author, rating=1)
        Review.objects.create(charity=self.school, author=author, rating=5)

        response = self.client.get(
            self.url, {"domain": [self.food.id], "sort": "rating", "direction": "desc"}
        )

        self.assertEqual([card.name for card in response.context["page"].items], ["Pantry"])
        self.assertContains(response, f'<input type="hidden" name="domain" value="{self.food.id}">')

    def test_applying_filters_keeps_the_sort(self) -> None:
        response = self.client.get(
            self.url, {"domain": [self.food.id], "sort": "rating", "direction": "desc"}
        )
        body = response.content.decode()
        form = body[body.index('<form class="filters"') :]
        form = form[: form.index("</form>")]

        self.assertIn('name="sort" value="rating"', form)
        self.assertIn('name="direction" value="desc"', form)

    def test_clearing_filters_keeps_the_sort(self) -> None:
        response = self.client.get(
            self.url, {"domain": [self.food.id], "sort": "rating", "direction": "desc"}
        )

        link = re.search(r'<a class="filters__clear" href="([^"]+)"', response.content.decode())

        self.assertIsNotNone(link)
        self.assertIn("sort=rating", link.group(1))
        self.assertIn("direction=desc", link.group(1))
        self.assertNotIn("domain=", link.group(1))

    def test_page_links_keep_the_filters_and_the_sort(self) -> None:
        for index in range(1, 26):
            charity = Charity.objects.create(name=f"Charity {index:02d}")
            charity.domains.add(self.food)

        response = self.client.get(
            self.url,
            {
                "domain": [self.food.id],
                "sort": "rating",
                "direction": "desc",
                "page_size": 5,
            },
        )

        self.assertContains(
            response,
            f"page=2&amp;page_size=5&amp;domain={self.food.id}&amp;sort=rating&amp;direction=desc",
        )

    def test_the_jump_form_keeps_the_filters_and_the_sort(self) -> None:
        for index in range(1, 26):
            charity = Charity.objects.create(name=f"Charity {index:02d}")
            charity.domains.add(self.food)

        response = self.client.get(
            self.url,
            {
                "domain": [self.food.id],
                "sort": "rating",
                "direction": "desc",
                "page_size": 5,
            },
        )
        body = response.content.decode()
        jump = body[body.index('<form class="jump"') :]
        jump = jump[: jump.index("</form>")]

        self.assertIn(f'name="domain" value="{self.food.id}"', jump)
        self.assertIn('name="sort" value="rating"', jump)
        self.assertIn('name="direction" value="desc"', jump)

    def test_clear_filters_link_appears_only_when_filtering(self) -> None:
        self.assertNotContains(self.client.get(self.url), "Clear filters")
        self.assertContains(self.client.get(self.url, {"domain": [self.food.id]}), "Clear filters")

    def test_a_junk_filter_value_is_ignored(self) -> None:
        response = self.client.get(self.url, {"domain": "nonsense"})

        self.assertContains(response, "Pantry")
        self.assertContains(response, "School")

    def test_a_domain_id_that_names_no_row_is_ignored(self) -> None:
        """D-045: a value naming no row is ignored, not a filter that matches nothing."""
        response = self.client.get(self.url, {"domain": 999999})

        self.assertContains(response, "Pantry")
        self.assertContains(response, "School")
        self.assertNotContains(response, "group on")

    def test_a_stale_id_does_not_override_a_real_one(self) -> None:
        response = self.client.get(self.url, {"domain": [999999, self.food.id]})

        self.assertContains(response, "Pantry")
        self.assertNotContains(response, "School")

    def test_a_rabbi_id_cannot_filter_while_the_group_offers_nothing(self) -> None:
        response = self.client.get(self.url, {"haskama_rabbi": 4})

        self.assertContains(response, "Pantry")
        self.assertContains(response, "School")

    def test_the_sidebar_is_on_the_page_for_every_visitor(self) -> None:
        """Filtering needs no account (§6.2.4 Permissions)."""
        response = self.client.get(self.url)

        self.assertContains(response, 'class="listing__sidebar"')
        self.assertContains(response, "Apply filters")
