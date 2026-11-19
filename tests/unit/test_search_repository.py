"""§6.2.6 search, applied to real rows (D-054).

These live against Postgres because the thing under test is the `WHERE` the
repository builds: which column is read, whether the match is case-insensitive,
and what "full words only" and "search the tagline" actually do. The doc asks for
one white-box test with different strings and advanced options.
"""

from django.test import TestCase

from apps.charities.contracts import CharityCard
from apps.charities.filters import CharityFilters
from apps.charities.models import Charity, Domain
from apps.charities.repositories import DjangoCharityRepository
from apps.charities.search import Search


class SearchRepositoryTest(TestCase):
    def setUp(self) -> None:
        self.repository = DjangoCharityRepository()

    def cards(
        self, search: Search | None = None, filters: CharityFilters | None = None
    ) -> tuple[CharityCard, ...]:
        return self.repository.page(0, 20, filters=filters, search=search)

    def names(
        self, search: Search | None = None, filters: CharityFilters | None = None
    ) -> list[str]:
        return [card.name for card in self.cards(search, filters)]

    def test_an_empty_search_keeps_every_charity(self) -> None:
        Charity.objects.create(name="Adas Chessed")
        Charity.objects.create(name="Zohar Fund")

        self.assertEqual(self.names(Search()), ["Adas Chessed", "Zohar Fund"])
        self.assertEqual(self.names(), ["Adas Chessed", "Zohar Fund"])

    def test_the_name_is_matched_case_insensitively(self) -> None:
        """UC-03's implementation constraints: case-insensitive search."""
        Charity.objects.create(name="Lev Chessed")

        for term in ["chessed", "CHESSED", "CheSsed"]:
            with self.subTest(term=term):
                self.assertEqual(self.names(Search(term=term)), ["Lev Chessed"])

    def test_a_term_matches_part_of_a_word_by_default(self) -> None:
        Charity.objects.create(name="Lev Chessed")

        self.assertEqual(self.names(Search(term="chess")), ["Lev Chessed"])

    def test_a_term_that_matches_nothing_returns_nothing(self) -> None:
        Charity.objects.create(name="Lev Chessed")

        self.assertEqual(self.names(Search(term="zohar")), [])

    def test_whole_words_only_rejects_a_partial_word(self) -> None:
        Charity.objects.create(name="Lev Chessed")

        self.assertEqual(self.names(Search(term="chess", whole_words=True)), [])
        self.assertEqual(self.names(Search(term="Chessed", whole_words=True)), ["Lev Chessed"])

    def test_whole_words_matches_a_multi_word_term_as_typed(self) -> None:
        Charity.objects.create(name="Lev Chessed Fund")

        self.assertEqual(
            self.names(Search(term="Lev Chessed", whole_words=True)), ["Lev Chessed Fund"]
        )

    def test_whole_words_rejects_words_in_a_different_order(self) -> None:
        """The term is one contiguous piece of text, as typed (D-054)."""
        Charity.objects.create(name="Chessed Lev Fund")

        self.assertEqual(self.names(Search(term="Lev Chessed", whole_words=True)), [])

    def test_whole_words_treats_the_term_as_text_not_a_pattern(self) -> None:
        """A name with regex characters is still findable by those characters."""
        Charity.objects.create(name="A.B Fund")
        Charity.objects.create(name="AxB Fund")

        self.assertEqual(self.names(Search(term="a.b", whole_words=True)), ["A.B Fund"])

    def test_a_wildcard_in_the_term_is_text(self) -> None:
        """`%` and `_` are LIKE wildcards; a reader typing them means the characters."""
        Charity.objects.create(name="100% Chessed")
        Charity.objects.create(name="100x Chessed")
        Charity.objects.create(name="A_B Fund")
        Charity.objects.create(name="AxB Fund")

        self.assertEqual(self.names(Search(term="100%")), ["100% Chessed"])
        self.assertEqual(self.names(Search(term="a_b")), ["A_B Fund"])

    def test_the_tagline_is_not_searched_by_default(self) -> None:
        """§6.2.2: list_charities searches the name column."""
        Charity.objects.create(name="Adas Chessed", tagline="Interest-free loans")

        self.assertEqual(self.names(Search(term="interest")), [])

    def test_the_tagline_option_searches_the_name_and_the_tagline(self) -> None:
        Charity.objects.create(name="Adas Chessed", tagline="Interest-free loans")
        Charity.objects.create(name="Bikur Cholim", tagline="Hospital visits")

        self.assertEqual(self.names(Search(term="interest", tagline=True)), ["Adas Chessed"])
        self.assertEqual(self.names(Search(term="cholim", tagline=True)), ["Bikur Cholim"])

    def test_a_charity_matching_either_column_is_kept(self) -> None:
        """The two columns are OR-ed, so one matching column is enough."""
        Charity.objects.create(name="Chessed Fund", tagline="Chessed for all")

        self.assertEqual(self.names(Search(term="chessed", tagline=True)), ["Chessed Fund"])

    def test_the_search_combines_with_a_filter(self) -> None:
        """§6.2.6 keeps the filters on, so both narrow the same set (D-045's AND)."""
        food = Domain.objects.create(name="Food")
        chessed = Domain.objects.create(name="Chessed")
        first = Charity.objects.create(name="Chessed Food Bank")
        second = Charity.objects.create(name="Chessed Loans")
        first.domains.add(food)
        second.domains.add(chessed)

        found = self.names(Search(term="chessed"), CharityFilters(domains=(food.id,)))

        self.assertEqual(found, ["Chessed Food Bank"])

    def test_the_count_reads_the_search_too(self) -> None:
        """A total that ignored the term would page through rows the page does not show."""
        for index in range(1, 8):
            Charity.objects.create(name=f"Chessed {index}")

        self.assertEqual(self.repository.count(search=Search(term="chessed")), 7)
        self.assertEqual(self.repository.count(search=Search(term="chessed", whole_words=True)), 7)
        self.assertEqual(self.repository.count(search=Search(term="zohar")), 0)

    def test_a_searched_page_still_carries_every_card_value(self) -> None:
        """A searched page is an ordinary page: its cards print the same numbers."""
        charity = Charity.objects.create(name="Lev Chessed")

        cards = self.cards(Search(term="chessed"))

        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0].id, charity.id)
        self.assertEqual(cards[0].reviews.count, 0)
        self.assertEqual(cards[0].activity.events, 0)
