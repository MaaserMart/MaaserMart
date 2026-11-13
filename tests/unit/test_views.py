"""Tests for the listing page."""

import re

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.charities.models import Charity, Domain, Location, Review


class ListingPageTest(TestCase):
    def setUp(self) -> None:
        self.url = reverse("charities:listing")

    def test_lists_charity_details(self) -> None:
        domain = Domain.objects.create(name="Free loans")
        location = Location.objects.create(name="Lakewood", region="NJ", country="USA")
        charity = Charity.objects.create(name="Keren L'Dugma", tagline="Interest-free loans.")
        charity.domains.add(domain)
        charity.locations.add(location)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Keren L&#x27;Dugma")
        self.assertContains(response, "Interest-free loans.")
        self.assertContains(response, "Free loans")
        self.assertContains(response, "Lakewood")

    def test_empty_listing_explains_itself(self) -> None:
        response = self.client.get(self.url)

        self.assertContains(response, "No charities found.")

    def test_charity_without_tagline_still_renders(self) -> None:
        Charity.objects.create(name="Adas Chessed")

        response = self.client.get(self.url)

        self.assertContains(response, "Adas Chessed")

    def test_root_redirects_to_the_listing(self) -> None:
        response = self.client.get("/")

        self.assertRedirects(response, self.url)

    def test_page_parameter_selects_a_page(self) -> None:
        for index in range(1, 26):
            Charity.objects.create(name=f"Charity {index:02d}")

        response = self.client.get(self.url, {"page": 2, "page_size": 10})

        self.assertContains(response, "Charity 11")
        self.assertNotContains(response, "Charity 01")

    def test_nonsense_page_parameter_falls_back_to_the_first_page(self) -> None:
        Charity.objects.create(name="Adas Chessed")

        response = self.client.get(self.url, {"page": "abc", "page_size": "lots"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Adas Chessed")

    def test_page_size_is_capped(self) -> None:
        Charity.objects.create(name="Adas Chessed")

        response = self.client.get(self.url, {"page_size": 99999})

        self.assertEqual(response.context["page"].page_size, 100)

    def test_pagination_links_appear_only_when_needed(self) -> None:
        Charity.objects.create(name="Adas Chessed")

        response = self.client.get(self.url)

        self.assertNotContains(response, "Pagination")

    def test_page_numbers_are_linked(self) -> None:
        for index in range(1, 26):
            Charity.objects.create(name=f"Charity {index:02d}")

        response = self.client.get(self.url, {"page_size": 10})

        self.assertContains(response, 'href="?page=2&amp;page_size=10"')
        self.assertContains(response, 'aria-current="page"')

    def test_page_size_input_shows_the_current_size(self) -> None:
        Charity.objects.create(name="Adas Chessed")

        response = self.client.get(self.url, {"page_size": 50})

        self.assertContains(response, 'id="page-size"')
        self.assertContains(response, 'value="50"')

    def test_page_size_accepts_an_arbitrary_number(self) -> None:
        for index in range(1, 13):
            Charity.objects.create(name=f"Charity {index:02d}")

        response = self.client.get(self.url, {"page_size": 7})

        self.assertEqual(len(response.context["page"].items), 7)

    def test_jump_form_is_present(self) -> None:
        for index in range(1, 26):
            Charity.objects.create(name=f"Charity {index:02d}")

        response = self.client.get(self.url, {"page_size": 10})

        self.assertContains(response, 'id="jump-page"')

    def test_divider_sits_between_domain_and_location_chips(self) -> None:
        domain = Domain.objects.create(name="Free loans")
        location = Location.objects.create(name="Lakewood", region="NJ", country="USA")
        charity = Charity.objects.create(name="Keren L'Dugma")
        charity.domains.add(domain)
        charity.locations.add(location)

        response = self.client.get(self.url)
        body = response.content.decode()

        # Locations are labelled with their full identity (D-045). The sidebar
        # offers the same strings, so look inside the card only.
        card = body[body.index("charity-card") :]
        card = card[: card.index("</a>")]
        self.assertIn("chip-divider", card)
        chip_divider = card.index('class="chip-divider"')
        self.assertLess(card.index("Free loans"), chip_divider)
        self.assertLess(chip_divider, card.index("Lakewood, NJ, USA"))

    def test_no_divider_when_a_charity_has_no_domains(self) -> None:
        location = Location.objects.create(name="Lakewood", region="NJ", country="USA")
        charity = Charity.objects.create(name="Keren L'Dugma")
        charity.locations.add(location)

        response = self.client.get(self.url)

        self.assertNotContains(response, "chip-divider")

    def test_image_is_served_from_static(self) -> None:
        Charity.objects.create(name="Keren L'Dugma", image="charities/img/charity-01.svg")

        response = self.client.get(self.url)

        self.assertContains(response, "/static/charities/img/charity-01.svg")

    def test_absolute_image_url_is_not_wrapped_in_static(self) -> None:
        # Seed data stores a full URL (D-024); {% static %} would mangle it into a 404.
        Charity.objects.create(name="Keren L'Dugma", image="https://placehold.co/600x400.png")

        response = self.client.get(self.url)

        self.assertContains(response, 'src="https://placehold.co/600x400.png"')
        self.assertNotContains(response, "/static/https")

    def test_next_link_is_html_escaped(self) -> None:
        for index in range(1, 4):
            Charity.objects.create(name=f"Charity {index:02d}")

        response = self.client.get(self.url, {"page_size": 2})

        self.assertContains(response, "?page=2&amp;page_size=2")
        self.assertNotContains(response, "?page=2&amp;amp;page_size=2")

    def test_first_page_has_next_but_no_previous_link(self) -> None:
        for index in range(1, 4):
            Charity.objects.create(name=f"Charity {index:02d}")

        response = self.client.get(self.url, {"page_size": 2})

        self.assertContains(response, "Next")
        self.assertContains(response, 'aria-disabled="true">&larr; Prev</span>')
        self.assertNotContains(response, 'rel="prev"')

    def test_last_page_has_previous_but_no_next_link(self) -> None:
        for index in range(1, 4):
            Charity.objects.create(name=f"Charity {index:02d}")

        response = self.client.get(self.url, {"page": 2, "page_size": 2})

        self.assertContains(response, "Prev")
        self.assertContains(response, 'aria-disabled="true">Next &rarr;</span>')
        self.assertNotContains(response, 'rel="next"')


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

    def test_clear_filters_link_appears_only_when_filtering(self) -> None:
        self.assertNotContains(self.client.get(self.url), "Clear filters")
        self.assertContains(self.client.get(self.url, {"domain": [self.food.id]}), "Clear filters")

    def test_a_junk_filter_value_is_ignored(self) -> None:
        response = self.client.get(self.url, {"domain": "nonsense"})

        self.assertContains(response, "Pantry")
        self.assertContains(response, "School")

    def test_the_sidebar_is_on_the_page_for_every_visitor(self) -> None:
        """Filtering needs no account (§6.2.4 Permissions)."""
        response = self.client.get(self.url)

        self.assertContains(response, 'class="listing__sidebar"')
        self.assertContains(response, "Apply filters")


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
