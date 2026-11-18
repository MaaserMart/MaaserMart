"""Tests for the listing rules, using a stand-in repository.

These need no database: the rules under test depend only on the repository
interface, which is exactly the point of keeping them separate.
"""

from django.test import SimpleTestCase
from django.utils import timezone

from apps.charities.contracts import (
    ActivitySummary,
    CharityCard,
    DomainTag,
    LocationTag,
    ReviewSummary,
)
from apps.charities.filters import CharityFilters
from apps.charities.search import Search
from apps.charities.services import Page, list_charities
from apps.charities.sorting import DEFAULT_SORT, RATING, CharitySort
from apps.charities.state import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, PageState, clamp_page_size


def card(name: str) -> CharityCard:
    return CharityCard(
        id=abs(hash(name)) % 100_000,
        name=name,
        tagline="",
        image="",
        domains=(DomainTag(name="Free loans"),),
        locations=(LocationTag(name="Lakewood", region="NJ", country="USA"),),
        reviews=ReviewSummary(count=0, average=None),
        activity=ActivitySummary(events=0, approving_haskamas=0, last_changed=timezone.now()),
    )


class FakeCharityRepository:
    """An in-memory repository: the interface, nothing more."""

    def __init__(self, names: list[str]) -> None:
        self._cards = tuple(card(name) for name in sorted(names))
        self.requested_sort = None
        self.requested_search = None

    def page(
        self,
        offset: int,
        limit: int,
        filters: CharityFilters | None = None,
        sort: CharitySort = DEFAULT_SORT,
        search: Search | None = None,
    ) -> tuple[CharityCard, ...]:
        self.requested_sort = sort
        self.requested_search = search
        return self._cards[offset : offset + limit]

    def count(self, filters: CharityFilters | None = None, search: Search | None = None) -> int:
        return len(self._cards)

    def page_and_count(
        self,
        offset: int,
        limit: int,
        filters: CharityFilters | None = None,
        sort: CharitySort = DEFAULT_SORT,
        search: Search | None = None,
    ) -> tuple[tuple[CharityCard, ...], int]:
        self.requested_sort = sort
        self.requested_search = search
        return self._cards[offset : offset + limit], len(self._cards)


class ListCharitiesDefaultTest(SimpleTestCase):
    """The default run, as named in the Charity List tracer bullet."""

    def test_returns_every_charity_alphabetically(self) -> None:
        repository = FakeCharityRepository(["Zohar Fund", "Adas Chessed", "Mercaz Tzedaka"])

        page = list_charities(repository)

        self.assertEqual(
            [charity.name for charity in page.items],
            ["Adas Chessed", "Mercaz Tzedaka", "Zohar Fund"],
        )
        self.assertEqual(page.total, 3)

    def test_reports_no_charities_when_none_exist(self) -> None:
        page = list_charities(FakeCharityRepository([]))

        self.assertEqual(page.items, ())
        self.assertEqual(page.total, 0)


class ListCharitiesPaginationTest(SimpleTestCase):
    def setUp(self) -> None:
        self.repository = FakeCharityRepository([f"Charity {index:02d}" for index in range(1, 26)])

    def test_default_page_size_is_used(self) -> None:
        page = list_charities(self.repository)

        self.assertEqual(page.page_size, DEFAULT_PAGE_SIZE)
        self.assertEqual(len(page.items), DEFAULT_PAGE_SIZE)
        self.assertEqual(page.total, 25)

    def test_second_page_continues_the_ordering(self) -> None:
        page = list_charities(self.repository, PageState(page=2, page_size=10))

        self.assertEqual(page.items[0].name, "Charity 11")
        self.assertEqual(len(page.items), 10)
        self.assertTrue(page.has_previous)
        self.assertTrue(page.has_next)

    def test_last_page_may_be_partial(self) -> None:
        page = list_charities(self.repository, PageState(page=3, page_size=10))

        self.assertEqual(len(page.items), 5)
        self.assertTrue(page.has_previous)
        self.assertFalse(page.has_next)

    def test_first_page_has_no_previous(self) -> None:
        page = list_charities(self.repository, PageState(page=1, page_size=10))

        self.assertFalse(page.has_previous)
        self.assertTrue(page.has_next)

    def test_page_below_one_is_clamped_to_the_first_page(self) -> None:
        self.assertEqual(list_charities(self.repository, PageState(page=0, page_size=10)).number, 1)
        self.assertEqual(
            list_charities(self.repository, PageState(page=-5, page_size=10)).number, 1
        )

    def test_absent_page_defaults_to_the_first_page(self) -> None:
        self.assertEqual(list_charities(self.repository, PageState(page_size=10)).number, 1)

    def test_page_past_the_end_is_clamped_to_the_last_page(self) -> None:
        self.assertEqual(
            list_charities(self.repository, PageState(page=99, page_size=10)).number, 3
        )

    def test_empty_result_still_reports_page_one(self) -> None:
        page = list_charities(FakeCharityRepository([]), PageState(page=4, page_size=10))

        self.assertEqual(page.number, 1)
        self.assertEqual(page.total, 0)


class ListCharitiesSortTest(SimpleTestCase):
    def test_the_default_sort_is_alphabetical(self) -> None:
        repository = FakeCharityRepository(["Zohar Fund"])

        page = list_charities(repository)

        self.assertEqual(repository.requested_sort, DEFAULT_SORT)
        self.assertEqual(page.sort, DEFAULT_SORT)

    def test_the_chosen_sort_reaches_the_repository(self) -> None:
        repository = FakeCharityRepository(["Zohar Fund"])
        sort = CharitySort(mechanism=RATING, descending=True)

        page = list_charities(repository, PageState(sort=sort))

        self.assertEqual(repository.requested_sort, sort)
        self.assertEqual(page.sort, sort)


class ListCharitiesSearchTest(SimpleTestCase):
    """§6.2.6: the search is one more narrowing of the same result set."""

    def test_no_search_is_an_empty_search(self) -> None:
        repository = FakeCharityRepository(["Zohar Fund"])

        page = list_charities(repository)

        self.assertEqual(repository.requested_search, Search())
        self.assertEqual(page.state.search, Search())

    def test_the_search_reaches_the_repository(self) -> None:
        repository = FakeCharityRepository(["Zohar Fund"])
        search = Search(term="zohar", tagline=True)

        list_charities(repository, PageState(search=search))

        self.assertEqual(repository.requested_search, search)

    def test_the_search_is_replayed_by_every_page_link(self) -> None:
        """A page of a search is still that search (§6.2.6), so links must carry it."""
        repository = FakeCharityRepository([f"Charity {index:02d}" for index in range(1, 6)])

        page = list_charities(repository, PageState(search=Search(term="chessed"), page_size=2))

        self.assertEqual(page.state.search, Search(term="chessed"))
        self.assertIn("q=chessed", page.next_query)
        self.assertIn("q=chessed", page.previous_query)
        self.assertIn("q=chessed", page.clear_filters_query)


class ClampPageSizeTest(SimpleTestCase):
    def test_absent_size_falls_back_to_the_default(self) -> None:
        self.assertEqual(clamp_page_size(None), DEFAULT_PAGE_SIZE)

    def test_size_is_capped(self) -> None:
        self.assertEqual(clamp_page_size(10_000), MAX_PAGE_SIZE)

    def test_size_is_at_least_one(self) -> None:
        self.assertEqual(clamp_page_size(0), 1)
        self.assertEqual(clamp_page_size(-3), 1)

    def test_size_within_range_is_kept(self) -> None:
        self.assertEqual(clamp_page_size(35), 35)


class PageQueryTest(SimpleTestCase):
    """The page builds its own links, so the template holds no URL logic."""

    def test_next_query_carries_page_and_size(self) -> None:
        page = Page(items=(), total=30, state=PageState(page=1, page_size=10))

        self.assertEqual(page.next_query, "page=2&page_size=10")

    def test_previous_query_carries_page_and_size(self) -> None:
        page = Page(items=(), total=30, state=PageState(page=3, page_size=10))

        self.assertEqual(page.previous_query, "page=2&page_size=10")

    def test_page_count_rounds_up(self) -> None:
        page = Page(items=(), total=31, state=PageState(page=1, page_size=10))

        self.assertEqual(page.page_count, 4)

    def test_page_count_is_one_when_empty(self) -> None:
        page = Page(items=(), total=0, state=PageState(page=1, page_size=10))

        self.assertEqual(page.page_count, 1)

    def test_numbers_window_around_the_current_page(self) -> None:
        page = Page(items=(), total=200, state=PageState(page=10, page_size=10))

        self.assertEqual([number for number, _ in page.numbers()], [8, 9, 10, 11, 12])

    def test_numbers_window_is_clipped_at_the_start(self) -> None:
        page = Page(items=(), total=200, state=PageState(page=1, page_size=10))

        self.assertEqual([number for number, _ in page.numbers()], [1, 2, 3])

    def test_numbers_window_is_clipped_at_the_end(self) -> None:
        page = Page(items=(), total=200, state=PageState(page=20, page_size=10))

        self.assertEqual([number for number, _ in page.numbers()], [18, 19, 20])

    def test_numbers_carry_a_usable_query_string(self) -> None:
        page = Page(items=(), total=30, state=PageState(page=1, page_size=10))

        self.assertEqual(page.numbers()[1], (2, "page=2&page_size=10"))

    def test_the_default_sort_adds_nothing_to_the_query(self) -> None:
        page = Page(items=(), total=30, state=PageState(page=1, page_size=10))

        self.assertEqual(page.state.pairs(), ())

    def test_next_query_keeps_a_chosen_sort(self) -> None:
        """§6.2.5: moving to another page must not reorder the list."""
        chosen = CharitySort(mechanism=RATING, descending=True)
        page = Page(items=(), total=30, state=PageState(page=1, page_size=10, sort=chosen))

        self.assertEqual(page.next_query, "page=2&page_size=10&sort=rating&direction=desc")
        self.assertEqual(page.state.sort, chosen)

    def test_next_query_keeps_the_filters_and_the_sort(self) -> None:
        """A page link must replay the whole result set (D-045, D-048)."""
        page = Page(
            items=(),
            total=30,
            state=PageState(
                page=1,
                page_size=10,
                sort=CharitySort(mechanism=RATING, descending=True),
                filters=CharityFilters(domains=(3,), min_rating=4),
            ),
        )

        self.assertEqual(
            page.next_query,
            "page=2&page_size=10&domain=3&min_rating=4&sort=rating&direction=desc",
        )

    def test_clearing_filters_keeps_the_page_size_and_sort(self) -> None:
        page = Page(
            items=(),
            total=30,
            state=PageState(
                page=3,
                page_size=10,
                sort=CharitySort(mechanism=RATING, descending=True),
                filters=CharityFilters(domains=(3,)),
            ),
        )

        self.assertEqual(page.clear_filters_query, "page_size=10&sort=rating&direction=desc")

    def test_clearing_filters_on_the_default_view_adds_nothing_extra(self) -> None:
        self.assertEqual(
            Page(items=(), total=30, state=PageState(page=1, page_size=10)).clear_filters_query,
            "page_size=10",
        )
