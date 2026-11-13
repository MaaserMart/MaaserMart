"""Tests for the filter rules of §6.2.4 (D-045), using a stand-in repository.

Like the listing rules, these need no database: they pin what the service does
with a `CharityFilters` and what the URL parser accepts.
"""

from django.test import SimpleTestCase

from apps.charities.contracts import CharityCard
from apps.charities.filters import (
    MAX_STAR_RATING,
    MIN_STAR_RATING,
    CharityFilters,
    from_query,
    query_pairs,
    query_string,
    sidebar_groups,
)
from apps.charities.services import list_charities


class FakeRepository:
    """Records the filters it was handed and returns a fixed set."""

    def __init__(self) -> None:
        self.seen: list[CharityFilters] = []

    def page(self, offset, limit, filters) -> tuple[CharityCard, ...]:
        self.seen.append(filters)
        return ()

    def count(self, filters) -> int:
        self.seen.append(filters)
        return 0


class FiltersFromQueryTest(SimpleTestCase):
    """§6.2.4's parameter names are the app's public URL surface."""

    def test_no_parameters_means_no_filters(self) -> None:
        filters = from_query(_Query({}))

        self.assertEqual(filters, CharityFilters())
        self.assertTrue(filters.is_empty)

    def test_repeatable_parameters_collect_every_value(self) -> None:
        filters = from_query(_Query({"domain": ["2", "5"], "location": ["7"]}))

        self.assertEqual(filters.domains, (2, 5))
        self.assertEqual(filters.locations, (7,))

    def test_repeated_ids_are_kept_once(self) -> None:
        filters = from_query(_Query({"domain": ["2", "2", "5"]}))

        self.assertEqual(filters.domains, (2, 5))

    def test_numbers_are_read(self) -> None:
        filters = from_query(
            _Query(
                {
                    "min_rating": ["4"],
                    "min_reviews": ["2"],
                    "min_approving_haskamas": ["1"],
                    "max_disapproving_haskamas": ["0"],
                }
            )
        )

        self.assertEqual(filters.min_rating, 4)
        self.assertEqual(filters.min_reviews, 2)
        self.assertEqual(filters.min_approving_haskamas, 1)
        self.assertEqual(filters.max_disapproving_haskamas, 0)

    def test_zero_is_a_real_number(self) -> None:
        """0 means "no reviews" or "no disapprovals", not "unset" (D-045)."""
        filters = from_query(_Query({"min_reviews": ["0"], "max_disapproving_haskamas": ["0"]}))

        self.assertEqual(filters.min_reviews, 0)
        self.assertEqual(filters.max_disapproving_haskamas, 0)
        self.assertFalse(filters.is_empty)

    def test_junk_values_are_dropped_not_rejected(self) -> None:
        filters = from_query(
            _Query(
                {
                    "domain": ["abc", "0", "-3", ""],
                    "min_rating": ["lots"],
                    "min_reviews": [""],
                }
            )
        )

        self.assertEqual(filters.domains, ())
        self.assertIsNone(filters.min_rating)
        self.assertIsNone(filters.min_reviews)
        self.assertTrue(filters.is_empty)

    def test_unknown_parameters_are_ignored(self) -> None:
        filters = from_query(_Query({"sort": ["name"], "search": ["keren"]}))

        self.assertEqual(filters, CharityFilters())

    def test_active_count_counts_groups_and_values(self) -> None:
        filters = from_query(_Query({"domain": ["1"], "min_rating": ["4"]}))

        self.assertEqual(filters.active_count(), 2)


class FiltersQueryStringTest(SimpleTestCase):
    """A page link must repeat the filters it was made under."""

    def test_empty_filters_make_an_empty_string(self) -> None:
        self.assertEqual(query_string(CharityFilters()), "")

    def test_repeatable_and_numeric_groups_round_trip(self) -> None:
        filters = CharityFilters(domains=(1, 2), min_rating=4, min_reviews=0)

        self.assertEqual(query_string(filters), "domain=1&domain=2&min_rating=4&min_reviews=0")
        self.assertEqual(from_query(_Query(_parse(query_string(filters)))), filters)

    def test_pairs_keep_a_zero(self) -> None:
        self.assertIn(("min_reviews", 0), query_pairs(CharityFilters(min_reviews=0)))


class SidebarGroupsTest(SimpleTestCase):
    def test_all_seven_groups_appear_in_the_doc_order(self) -> None:
        groups = sidebar_groups(CharityFilters(), {})

        self.assertEqual(
            [group.parameter for group in groups],
            [
                "domain",
                "location",
                "haskama_rabbis",
                "min_rating",
                "min_reviews",
                "min_approving_haskamas",
                "max_disapproving_haskamas",
            ],
        )

    def test_repeatable_groups_are_checkboxes_with_their_options(self) -> None:
        class Option:
            id = 3
            name = "Free loans"

        groups = sidebar_groups(CharityFilters(), {"domain": (Option(),)})

        domain = groups[0]
        self.assertEqual(domain.kind, "checkboxes")
        self.assertEqual([(o.id, o.label) for o in domain.options], [(3, "Free loans")])

    def test_selected_options_come_from_the_filters(self) -> None:
        class Option:
            id = 3
            name = "Free loans"

        groups = sidebar_groups(CharityFilters(domains=(3,)), {"domain": (Option(),)})

        self.assertEqual(groups[0].selected, (3,))

    def test_a_group_with_no_options_says_so(self) -> None:
        """D-045: the rabbi group is real but accounts cannot list rabbis yet."""
        groups = sidebar_groups(CharityFilters(), {})

        rabbis = next(group for group in groups if group.parameter == "haskama_rabbis")
        self.assertEqual(rabbis.options, ())
        self.assertTrue(rabbis.empty_note)

    def test_numbers_are_single_inputs_bounded_by_the_star_scale(self) -> None:
        groups = sidebar_groups(CharityFilters(min_rating=3), {})
        rating = next(group for group in groups if group.parameter == "min_rating")

        self.assertEqual(rating.kind, "number")
        self.assertEqual(rating.value, 3)
        self.assertEqual((rating.min, rating.max), (MIN_STAR_RATING, MAX_STAR_RATING))

    def test_a_location_option_is_labelled_by_its_full_identity(self) -> None:
        class Option:
            id = 1
            name = "Lakewood"
            region = "New Jersey"
            country = "USA"

            @property
            def label(self) -> str:
                return f"{self.name}, {self.region}, {self.country}"

        groups = sidebar_groups(CharityFilters(), {"location": (Option(),)})

        location = next(group for group in groups if group.parameter == "location")
        self.assertEqual(location.options[0].label, "Lakewood, New Jersey, USA")

    def test_an_empty_maximum_has_no_cap(self) -> None:
        groups = sidebar_groups(CharityFilters(), {})
        most = next(g for g in groups if g.parameter == "max_disapproving_haskamas")

        self.assertIsNone(most.value)
        self.assertTrue(most.none_note)


class ListCharitiesPassesFiltersTest(SimpleTestCase):
    def test_the_filters_reach_the_repository(self) -> None:
        repository = FakeRepository()
        filters = CharityFilters(domains=(4,), min_rating=3)

        page = list_charities(repository, filters=filters)

        self.assertEqual(repository.seen, [filters, filters])
        self.assertEqual(page.total, 0)

    def test_no_filters_pass_an_empty_filter_object(self) -> None:
        repository = FakeRepository()

        list_charities(repository)

        self.assertEqual(repository.seen[0], CharityFilters())


class _Query:
    """A stand-in for Django's QueryDict, with only the two methods used."""

    def __init__(self, data: dict[str, list[str]]) -> None:
        self._data = data

    def getlist(self, key: str) -> list[str]:
        return self._data.get(key, [])

    def get(self, key: str) -> str | None:
        values = self._data.get(key)
        return values[-1] if values else None


def _parse(query_string: str) -> dict[str, list[str]]:
    from urllib.parse import parse_qs

    return parse_qs(query_string)


class BlankNumberTest(SimpleTestCase):
    def test_a_blank_number_input_is_no_filter(self) -> None:
        """The sidebar submits every number input, so an empty one must not stick."""
        filters = from_query(_Query({"min_rating": [""], "min_reviews": [" "], "domain": ["3"]}))

        self.assertIsNone(filters.min_rating)
        self.assertIsNone(filters.min_reviews)
        self.assertEqual(query_string(filters), "domain=3")
