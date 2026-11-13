"""Tests for the listing rules, using a stand-in repository.

These need no database: the rules under test depend only on the repository
interface, which is exactly the point of keeping them separate.
"""

from django.test import SimpleTestCase

from apps.charities.contracts import CharityCard, DomainTag, LocationTag, ReviewSummary
from apps.charities.filters import CharityFilters
from apps.charities.services import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    Page,
    clamp_page_size,
    list_charities,
)


def card(name: str) -> CharityCard:
    return CharityCard(
        id=abs(hash(name)) % 100_000,
        name=name,
        tagline="",
        image="",
        domains=(DomainTag(name="Free loans"),),
        locations=(LocationTag(name="Lakewood", region="NJ", country="USA"),),
        reviews=ReviewSummary(count=0, average=None),
    )


class FakeCharityRepository:
    """An in-memory repository: the interface, nothing more."""

    def __init__(self, names: list[str]) -> None:
        self._cards = tuple(card(name) for name in sorted(names))

    def page(
        self, offset: int, limit: int, filters: CharityFilters | None = None
    ) -> tuple[CharityCard, ...]:
        return self._cards[offset : offset + limit]

    def count(self, filters: CharityFilters | None = None) -> int:
        return len(self._cards)


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
        page = list_charities(self.repository, page=2, page_size=10)

        self.assertEqual(page.items[0].name, "Charity 11")
        self.assertEqual(len(page.items), 10)
        self.assertTrue(page.has_previous)
        self.assertTrue(page.has_next)

    def test_last_page_may_be_partial(self) -> None:
        page = list_charities(self.repository, page=3, page_size=10)

        self.assertEqual(len(page.items), 5)
        self.assertTrue(page.has_previous)
        self.assertFalse(page.has_next)

    def test_first_page_has_no_previous(self) -> None:
        page = list_charities(self.repository, page=1, page_size=10)

        self.assertFalse(page.has_previous)
        self.assertTrue(page.has_next)

    def test_page_below_one_is_clamped_to_the_first_page(self) -> None:
        self.assertEqual(list_charities(self.repository, page=0, page_size=10).number, 1)
        self.assertEqual(list_charities(self.repository, page=-5, page_size=10).number, 1)

    def test_absent_page_defaults_to_the_first_page(self) -> None:
        self.assertEqual(list_charities(self.repository, page=None, page_size=10).number, 1)

    def test_page_past_the_end_is_clamped_to_the_last_page(self) -> None:
        self.assertEqual(list_charities(self.repository, page=99, page_size=10).number, 3)

    def test_empty_result_still_reports_page_one(self) -> None:
        page = list_charities(FakeCharityRepository([]), page=4, page_size=10)

        self.assertEqual(page.number, 1)
        self.assertEqual(page.total, 0)


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
        page = Page(items=(), total=30, number=1, page_size=10)

        self.assertEqual(page.next_query, "page=2&page_size=10")

    def test_previous_query_carries_page_and_size(self) -> None:
        page = Page(items=(), total=30, number=3, page_size=10)

        self.assertEqual(page.previous_query, "page=2&page_size=10")

    def test_page_count_rounds_up(self) -> None:
        self.assertEqual(Page(items=(), total=31, number=1, page_size=10).page_count, 4)

    def test_page_count_is_one_when_empty(self) -> None:
        self.assertEqual(Page(items=(), total=0, number=1, page_size=10).page_count, 1)

    def test_numbers_window_around_the_current_page(self) -> None:
        page = Page(items=(), total=200, number=10, page_size=10)

        self.assertEqual([number for number, _ in page.numbers()], [8, 9, 10, 11, 12])

    def test_numbers_window_is_clipped_at_the_start(self) -> None:
        page = Page(items=(), total=200, number=1, page_size=10)

        self.assertEqual([number for number, _ in page.numbers()], [1, 2, 3])

    def test_numbers_window_is_clipped_at_the_end(self) -> None:
        page = Page(items=(), total=200, number=20, page_size=10)

        self.assertEqual([number for number, _ in page.numbers()], [18, 19, 20])

    def test_numbers_carry_a_usable_query_string(self) -> None:
        page = Page(items=(), total=30, number=1, page_size=10)

        self.assertEqual(page.numbers()[1], (2, "page=2&page_size=10"))
