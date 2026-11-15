"""The §6.2.5 sort vocabulary and the URL it reads (D-048).

These need no database: the rules under test are which mechanism a query names,
which direction it starts in, and what the control renders.
"""

from django.http import QueryDict
from django.test import SimpleTestCase

from apps.charities.sorting import (
    ALPHABETICAL,
    ASCENDING,
    DEFAULT_SORT,
    DESCENDING,
    DIRECTION_PARAMETER,
    HASKAMOS,
    MECHANISMS,
    NEWEST,
    POPULAR,
    RATING,
    SORT_PARAMETER,
    TRENDING,
    UPDATED,
    CharitySort,
    from_query,
    query_pairs,
    query_string,
    sort_form,
)


class SortQueryTest(SimpleTestCase):
    def test_nothing_in_the_url_is_alphabetical_a_to_z(self) -> None:
        """§6.2.5: no recognizable input defaults to alphabetical a->z."""
        self.assertEqual(from_query(QueryDict("")), DEFAULT_SORT)
        self.assertEqual(DEFAULT_SORT.mechanism, ALPHABETICAL)
        self.assertFalse(DEFAULT_SORT.descending)
        self.assertEqual(DEFAULT_SORT.direction, "asc")

    def test_a_sort_that_names_no_mechanism_falls_back_to_alphabetical(self) -> None:
        self.assertEqual(from_query(QueryDict("sort=sideways&direction=desc")), DEFAULT_SORT)

    def test_each_mechanism_is_recognized(self) -> None:
        for mechanism in MECHANISMS:
            with self.subTest(mechanism=mechanism.value):
                sort = from_query(QueryDict(f"sort={mechanism.value}"))

                self.assertEqual(sort.mechanism, mechanism)

    def test_a_mechanism_starts_in_its_default_direction(self) -> None:
        self.assertFalse(from_query(QueryDict("sort=alphabetical")).descending)
        for mechanism in MECHANISMS[1:]:
            with self.subTest(mechanism=mechanism.value):
                self.assertTrue(from_query(QueryDict(f"sort={mechanism.value}")).descending)

    def test_an_explicit_direction_overrides_the_default(self) -> None:
        sort = from_query(QueryDict("sort=rating&direction=asc"))

        self.assertEqual(sort.mechanism, RATING)
        self.assertFalse(sort.descending)
        self.assertEqual(sort.direction, "asc")

    def test_a_junk_direction_keeps_the_mechanisms_default(self) -> None:
        sort = from_query(QueryDict("sort=rating&direction=sideways"))

        self.assertEqual(sort.mechanism, RATING)
        self.assertTrue(sort.descending)

    def test_direction_alone_reverses_alphabetical_order(self) -> None:
        """Direction is its own control, so `?direction=desc` is Z→A."""
        sort = from_query(QueryDict("direction=desc"))

        self.assertEqual(sort.mechanism, ALPHABETICAL)
        self.assertTrue(sort.descending)

    def test_an_empty_sort_value_is_not_recognized(self) -> None:
        self.assertEqual(from_query(QueryDict("sort=&direction=desc")), DEFAULT_SORT)


class SortUrlTest(SimpleTestCase):
    def test_the_default_adds_no_parameters(self) -> None:
        self.assertEqual(query_pairs(DEFAULT_SORT), ())
        self.assertEqual(query_string(DEFAULT_SORT), "")

    def test_an_explicit_default_is_spelled_as_the_default(self) -> None:
        """`alphabetical` ascending and no sort at all are the same view."""
        self.assertEqual(query_pairs(CharitySort(mechanism=ALPHABETICAL, descending=False)), ())

    def test_a_chosen_sort_carries_both_parameters(self) -> None:
        sort = CharitySort(mechanism=RATING, descending=True)

        self.assertEqual(query_pairs(sort), (("sort", "rating"), ("direction", "desc")))
        self.assertEqual(query_string(sort), "sort=rating&direction=desc")

    def test_reversed_alphabetical_is_not_the_default(self) -> None:
        sort = CharitySort(mechanism=ALPHABETICAL, descending=True)

        self.assertEqual(query_pairs(sort), (("sort", "alphabetical"), ("direction", "desc")))


class SortFormTest(SimpleTestCase):
    def test_the_dropdown_offers_every_mechanism_in_doc_order(self) -> None:
        form = sort_form(DEFAULT_SORT)

        self.assertEqual([option.value for option in form.options], [m.value for m in MECHANISMS])
        self.assertEqual(form.selected, ALPHABETICAL.value)
        self.assertFalse(form.descending)

    def test_the_selected_mechanism_and_direction_are_carried(self) -> None:
        form = sort_form(CharitySort(mechanism=UPDATED, descending=False))

        self.assertEqual(form.selected, UPDATED.value)
        self.assertFalse(form.descending)

    def test_the_form_carries_the_url_vocabulary(self) -> None:
        """The template must not repeat `sort`, `direction`, `asc` or `desc`."""
        form = sort_form(DEFAULT_SORT)

        self.assertEqual(form.parameter, SORT_PARAMETER)
        self.assertEqual(form.direction_parameter, DIRECTION_PARAMETER)
        self.assertEqual(form.ascending_value, ASCENDING)
        self.assertEqual(form.descending_value, DESCENDING)

    def test_alphabetical_uses_letter_labels(self) -> None:
        form = sort_form(DEFAULT_SORT)

        self.assertEqual((form.low_label, form.high_label), ("A to Z", "Z to A"))

    def test_each_order_words_its_directions_in_its_own_terms(self) -> None:
        expected = {
            TRENDING: ("Low to high", "High to low"),
            POPULAR: ("Low to high", "High to low"),
            RATING: ("Lowest rated", "Highest rated"),
            HASKAMOS: ("Low to high", "High to low"),
            NEWEST: ("Oldest first", "Newest first"),
            UPDATED: ("Least recently changed", "Most recently changed"),
        }

        for mechanism, labels in expected.items():
            with self.subTest(mechanism=mechanism.value):
                form = sort_form(CharitySort(mechanism=mechanism, descending=True))

                self.assertEqual((form.low_label, form.high_label), labels)
