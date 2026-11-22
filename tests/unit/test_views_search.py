"""Black-box page contracts: the tracer-bullet search (D-050).

Split out of tests/unit/test_views.py (audit T3): one file per page feature, so
a reader finds the test for a behaviour without scanning 750 lines and feature
branches stop colliding on one file. The module docstring of test_views.py lists
what is where.
"""

from django.test import TestCase
from django.urls import reverse

from apps.charities.models import Charity, Domain


class ListingSearchPageTest(TestCase):
    """Black-box: §6.2.6's search bar, end to end through the page."""

    def setUp(self) -> None:
        self.url = reverse("charities:listing")
        self.food = Domain.objects.create(name="Food")

    def form(self, response, marker: str) -> str:
        """The HTML of one form on the page, so a test can look inside it."""
        body = response.content.decode()
        start = body.index(marker)
        return body[start : body.index("</form>", start)]

    def test_the_search_bar_is_on_the_page_for_every_visitor(self) -> None:
        body = self.client.get(self.url).content.decode()

        self.assertIn('role="search"', body)
        self.assertIn('name="q"', body)
        self.assertIn('type="search"', body)
        self.assertIn(">Search</button>", body)

    def test_every_advanced_option_is_offered(self) -> None:
        body = self.client.get(self.url).content.decode()

        self.assertIn("Advanced search", body)
        self.assertIn('name="whole_words"', body)
        self.assertIn("Full words only", body)
        self.assertIn('name="tagline"', body)
        self.assertIn("Search the tagline too", body)

    def test_a_typed_term_narrows_the_page(self) -> None:
        Charity.objects.create(name="Lev Chessed")
        Charity.objects.create(name="Zohar Fund")

        response = self.client.get(self.url, {"q": "chessed"})

        self.assertEqual([card.name for card in response.context["page"].items], ["Lev Chessed"])
        self.assertEqual(response.context["page"].total, 1)

    def test_the_term_stays_in_the_box(self) -> None:
        response = self.client.get(self.url, {"q": "Lev Chessed"})

        self.assertContains(response, 'value="Lev Chessed"')

    def test_the_search_form_sends_no_page_so_a_search_starts_at_page_one(self) -> None:
        """§6.2.6: page 1 of the search is shown."""
        for index in range(1, 26):
            Charity.objects.create(name=f"Chessed {index:02d}")

        response = self.client.get(self.url, {"page": 3, "page_size": 5, "q": "chessed"})

        self.assertNotIn('name="page"', self.form(response, '<form class="search"'))

    def test_a_shared_url_keeps_its_page_and_search(self) -> None:
        for index in range(1, 26):
            Charity.objects.create(name=f"Chessed {index:02d}")

        response = self.client.get(self.url, {"page": 2, "page_size": 5, "q": "chessed"})

        self.assertEqual(response.context["page"].number, 2)

    def test_pagination_links_keep_the_search(self) -> None:
        for index in range(1, 4):
            Charity.objects.create(name=f"Chessed {index:02d}")

        response = self.client.get(self.url, {"q": "chessed", "page_size": 2})

        self.assertContains(response, "q=chessed")

    def test_the_page_size_form_keeps_the_search(self) -> None:
        Charity.objects.create(name="Adas Chessed")

        response = self.client.get(self.url, {"q": "chessed"})

        self.assertContains(response, '<input type="hidden" name="q" value="chessed">')

    def test_the_sort_form_keeps_the_search(self) -> None:
        response = self.client.get(self.url, {"q": "chessed"})

        self.assertIn('name="q" value="chessed"', self.form(response, '<form class="sort"'))

    def test_the_filter_form_keeps_the_search(self) -> None:
        response = self.client.get(self.url, {"q": "chessed"})

        self.assertIn('name="q" value="chessed"', self.form(response, '<form class="filters"'))

    def test_the_jump_form_keeps_the_search(self) -> None:
        for index in range(1, 4):
            Charity.objects.create(name=f"Chessed {index:02d}")

        response = self.client.get(self.url, {"q": "chessed", "page_size": 2})

        self.assertIn('name="q" value="chessed"', self.form(response, '<form class="jump"'))

    def test_the_search_and_a_filter_narrow_together(self) -> None:
        """§6.2.6 keeps the filters on, so a search does not clear them."""
        clothing = Domain.objects.create(name="Clothing")
        fed = Charity.objects.create(name="Chessed Kitchen")
        clad = Charity.objects.create(name="Chessed Closet")
        fed.domains.add(self.food)
        clad.domains.add(clothing)

        response = self.client.get(self.url, {"q": "chessed", "domain": self.food.id})

        self.assertEqual(
            [card.name for card in response.context["page"].items], ["Chessed Kitchen"]
        )

    def test_clearing_filters_keeps_the_search(self) -> None:
        Charity.objects.create(name="Adas Chessed")

        response = self.client.get(self.url, {"q": "chessed", "domain": self.food.id})

        self.assertContains(response, "Clear filters")
        self.assertIn("q=chessed", response.context["page"].clear_filters_query)

    def test_an_empty_result_says_the_search_found_nothing(self) -> None:
        Charity.objects.create(name="Adas Chessed")

        response = self.client.get(self.url, {"q": "zohar"})

        self.assertContains(response, "No charities match that search.")

    def test_an_empty_result_names_both_the_search_and_the_filters(self) -> None:
        Charity.objects.create(name="Adas Chessed")

        response = self.client.get(self.url, {"q": "zohar", "domain": self.food.id})

        self.assertContains(response, "No charities match that search and those filters.")

    def test_an_empty_database_still_says_no_charities_found(self) -> None:
        response = self.client.get(self.url)

        self.assertContains(response, "No charities found.")

    def test_a_whole_word_search_is_applied(self) -> None:
        Charity.objects.create(name="Chessed Gemach")
        Charity.objects.create(name="Chess Club")

        response = self.client.get(self.url, {"q": "chess", "whole_words": "1"})

        self.assertEqual([card.name for card in response.context["page"].items], ["Chess Club"])
        # the option is shown back to the reader, and its panel is open
        self.assertRegex(response.content.decode(), r'name="whole_words"[\s\S]{0,40}?checked')
        self.assertContains(response, '<details class="search__advanced" open>')

    def test_a_tagline_search_is_applied(self) -> None:
        Charity.objects.create(name="Adas Chessed", tagline="Interest-free loans")

        without = self.client.get(self.url, {"q": "interest"})
        with_tagline = self.client.get(self.url, {"q": "interest", "tagline": "1"})

        self.assertEqual(without.context["page"].total, 0)
        self.assertEqual(with_tagline.context["page"].total, 1)

    def test_a_blank_term_searches_for_nothing(self) -> None:
        Charity.objects.create(name="Adas Chessed")
        Charity.objects.create(name="Zohar Fund")

        response = self.client.get(self.url, {"q": "  "})

        self.assertEqual(response.context["page"].total, 2)
        self.assertNotContains(response, "No charities match that search.")
