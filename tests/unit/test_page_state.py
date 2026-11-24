"""The listing's whole URL state (audit S1, S7; D-068).

These pin the three things the collapse is for: one reading order, one writing
order, and one place that knows how the pieces join. A new part of the state
should break the structural test below — not silently leave a form able to drop
it.
"""

from dataclasses import fields, replace

from django.test import SimpleTestCase
from django.utils.datastructures import MultiValueDict

from apps.charities.filters import CharityFilters
from apps.charities.search import Search
from apps.charities.sorting import DEFAULT_SORT, RATING, CharitySort
from apps.charities.state import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    PARTS,
    SKIPPABLE,
    PageState,
)


def query(**values) -> MultiValueDict:
    """A `request.GET`-shaped query from plain lists."""
    return MultiValueDict(
        {key: value if isinstance(value, list) else [value] for key, value in values.items()}
    )


def busy_state() -> PageState:
    """A state with something in every part, which is where joins go wrong."""
    return PageState(
        search=Search(term="chesed", tagline=True),
        filters=CharityFilters(domains=(3,), min_rating=4),
        sort=CharitySort(mechanism=RATING, descending=True),
        page=2,
        page_size=10,
    )


class StructureTest(SimpleTestCase):
    def test_every_part_is_a_field_of_the_state(self) -> None:
        """A part that names no field would read and write nothing, silently."""
        names = {field.name for field in fields(PageState)}

        self.assertEqual({part.name for part in PARTS} - names, set())

    def test_the_skippable_names_are_the_parts(self) -> None:
        self.assertEqual(SKIPPABLE, tuple(part.name for part in PARTS))

    def test_the_slices_have_a_stated_order(self) -> None:
        """Search, filters, sort: the order a listing URL spells them (D-046)."""
        self.assertEqual(SKIPPABLE, ("search", "filters", "sort"))


class FromQueryTest(SimpleTestCase):
    def test_an_empty_address_is_the_default_view(self) -> None:
        state = PageState.from_query(query())

        self.assertEqual(state.search, Search())
        self.assertEqual(state.filters, CharityFilters())
        self.assertEqual(state.sort, DEFAULT_SORT)
        self.assertEqual(state.page, 1)
        self.assertEqual(state.page_size, DEFAULT_PAGE_SIZE)

    def test_every_part_is_read_through_its_own_module(self) -> None:
        state = PageState.from_query(
            query(q="chesed", domain="3", min_rating="4", sort="rating", direction="desc")
        )

        self.assertEqual(state.search, Search(term="chesed"))
        self.assertEqual(state.filters, CharityFilters(domains=(3,), min_rating=4))
        self.assertEqual(state.sort, CharitySort(mechanism=RATING, descending=True))

    def test_junk_in_the_window_is_ignored_not_fatal(self) -> None:
        """A junk window falls back to the default view, like a junk filter value."""
        state = PageState.from_query(query(page="nonsense", page_size="-4"))

        self.assertEqual(state.page, 1)
        self.assertEqual(state.page_size, DEFAULT_PAGE_SIZE)

    def test_an_enormous_page_size_is_capped(self) -> None:
        self.assertEqual(PageState.from_query(query(page_size="9999")).page_size, MAX_PAGE_SIZE)


class WritingTest(SimpleTestCase):
    def test_the_pairs_follow_the_stated_order(self) -> None:
        self.assertEqual(
            busy_state().pairs(),
            (
                ("q", "chesed"),
                ("tagline", "1"),
                ("domain", 3),
                ("min_rating", 4),
                ("sort", "rating"),
                ("direction", "desc"),
            ),
        )

    def test_the_window_goes_first(self) -> None:
        """Every page link spells the address the same way, so two links to the same
        listing are the same text (audit S7)."""
        self.assertEqual(
            busy_state().query_string(page=3, page_size=10),
            "page=3&page_size=10&q=chesed&tagline=1&domain=3&min_rating=4"
            "&sort=rating&direction=desc",
        )

    def test_skipping_a_part_drops_exactly_that_part(self) -> None:
        pairs = busy_state().pairs(skip=("filters",))

        self.assertIn(("q", "chesed"), pairs)
        self.assertNotIn(("domain", 3), pairs)
        self.assertIn(("sort", "rating"), pairs)

    def test_the_default_state_writes_no_parameters(self) -> None:
        self.assertEqual(PageState().query_string(), "")

    def test_an_address_read_back_is_the_same_state(self) -> None:
        state = busy_state()

        self.assertEqual(PageState.from_query(_parse(state.query_string())).pairs(), state.pairs())


class ClampOnConstructionTest(SimpleTestCase):
    def test_page_one_is_the_floor(self) -> None:
        self.assertEqual(PageState(page=0).page, 1)
        self.assertEqual(PageState(page=-3).page, 1)

    def test_page_size_is_bounded_both_ways(self) -> None:
        self.assertEqual(PageState(page_size=0).page_size, 1)
        self.assertEqual(PageState(page_size=10_000).page_size, MAX_PAGE_SIZE)


class ReplacedTest(SimpleTestCase):
    def test_replacing_a_part_keeps_the_rest(self) -> None:
        state = busy_state()

        changed = state.replaced(filters=CharityFilters())

        self.assertEqual(changed.filters, CharityFilters())
        self.assertEqual(changed.search, state.search)
        self.assertEqual(changed.page, state.page)

    def test_the_original_is_untouched(self) -> None:
        """Links are built from a state; building one must not change it."""
        state = busy_state()
        before = replace(state)

        state.with_page(7)
        state.replaced(filters=CharityFilters())

        self.assertEqual(state, before)


def _parse(query_string: str) -> MultiValueDict:
    from urllib.parse import parse_qs

    return MultiValueDict(parse_qs(query_string))
