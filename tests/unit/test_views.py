"""Tests for the listing page."""

from django.test import TestCase
from django.urls import reverse

from apps.charities.models import Charity, Domain, Location


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

        self.assertIn("chip-divider", body)
        self.assertLess(body.index("Free loans"), body.index("chip-divider"))
        self.assertLess(body.index("chip-divider"), body.index("Lakewood"))

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
