"""The §6.2.6 search vocabulary and the URL it reads (D-054).

These need no database: the rules under test are which term and options a query
names, how a term is matched, and what the bar renders.
"""

from urllib.parse import urlencode

from django.http import QueryDict
from django.test import SimpleTestCase

from apps.charities.search import (
    OPTIONS,
    TERM_PARAMETER,
    Search,
    from_query,
    query_pairs,
    search_form,
)
from apps.charities.state import PageState


def query(params: dict) -> QueryDict:
    """A request query built from parameters, the way a form submission would."""
    return QueryDict(urlencode(params, doseq=True))


class SearchQueryTest(SimpleTestCase):
    def test_nothing_typed_is_no_search(self) -> None:
        """§6.2.6: with nothing typed the listing shows every charity."""
        self.assertEqual(from_query(QueryDict("")), Search())
        self.assertTrue(from_query(QueryDict("")).is_empty)

    def test_the_term_is_read_from_the_url(self) -> None:
        self.assertEqual(from_query(QueryDict("q=Chessed")).term, "Chessed")

    def test_a_blank_term_is_no_search(self) -> None:
        for raw in ["", "   ", "\t"]:
            with self.subTest(raw=raw):
                self.assertTrue(from_query(query({TERM_PARAMETER: raw})).is_empty)

    def test_surrounding_space_is_not_part_of_the_term(self) -> None:
        self.assertEqual(from_query(query({TERM_PARAMETER: "  chessed  "})).term, "chessed")

    def test_inner_whitespace_collapses_to_one_space(self) -> None:
        """A doubled space in an address still matches the single space in the text."""
        self.assertEqual(from_query(query({TERM_PARAMETER: "lev   chai"})).term, "lev chai")

    def test_an_advanced_option_is_off_unless_the_url_says_so(self) -> None:
        search = from_query(query({TERM_PARAMETER: "chessed"}))

        self.assertFalse(search.whole_words)
        self.assertFalse(search.tagline)

    def test_each_advanced_option_is_recognized(self) -> None:
        for option in OPTIONS:
            with self.subTest(option=option.parameter):
                search = from_query(query({TERM_PARAMETER: "chessed", option.parameter: "1"}))

                self.assertTrue(getattr(search, option.attribute))

    def test_an_option_saying_no_is_off(self) -> None:
        for raw in ["0", "false", "off", "no", ""]:
            with self.subTest(raw=raw):
                search = from_query(query({TERM_PARAMETER: "chessed", "tagline": raw}))

                self.assertFalse(search.tagline)

    def test_options_without_a_term_are_dropped(self) -> None:
        """They cannot narrow anything, so leaving them on would only mislead the bar."""
        self.assertEqual(from_query(query({"tagline": "1"})), Search())


class SearchMatchTest(SimpleTestCase):
    def test_the_default_searches_the_name_only(self) -> None:
        """§6.2.2 says list_charities searches the name column."""
        self.assertEqual(Search(term="chessed").fields, ("name",))

    def test_the_tagline_option_adds_the_tagline(self) -> None:
        self.assertEqual(Search(term="chessed", tagline=True).fields, ("name", "tagline"))

    def test_the_default_matches_part_of_a_word(self) -> None:
        search = Search(term="chess")

        self.assertEqual(search.lookup, "icontains")
        self.assertEqual(search.pattern, "chess")

    def test_whole_words_match_bounds_the_term(self) -> None:
        search = Search(term="chess", whole_words=True)

        self.assertEqual(search.lookup, "iregex")
        self.assertEqual(search.pattern, r"\ychess\y")

    def test_whole_words_escapes_a_regex_character_in_the_term(self) -> None:
        """A term is text, not a pattern: `(chai)` must match the characters."""
        search = Search(term="a.b", whole_words=True)

        self.assertIn(r"a\.b", search.pattern)

    def test_advanced_is_true_only_when_an_option_is_on(self) -> None:
        self.assertFalse(Search(term="chess").is_advanced)
        self.assertTrue(Search(term="chess", tagline=True).is_advanced)


class SearchQueryPairsTest(SimpleTestCase):
    def test_an_empty_search_adds_no_parameters(self) -> None:
        self.assertEqual(query_pairs(Search()), ())
        self.assertEqual(PageState(search=Search()).query_string(), "")

    def test_the_term_is_one_parameter(self) -> None:
        self.assertEqual(query_pairs(Search(term="chessed")), (("q", "chessed"),))

    def test_each_option_is_one_parameter(self) -> None:
        search = Search(term="chessed", whole_words=True, tagline=True)

        self.assertEqual(
            query_pairs(search),
            (("q", "chessed"), ("whole_words", "1"), ("tagline", "1")),
        )

    def test_a_query_survives_a_round_trip(self) -> None:
        search = Search(term="lev chai", whole_words=True, tagline=True)

        self.assertEqual(from_query(QueryDict(PageState(search=search).query_string())), search)


class SearchFormTest(SimpleTestCase):
    def test_the_bar_shows_the_term_and_the_submit_button(self) -> None:
        form = search_form(Search(term="Chessed"))

        self.assertEqual(form.term, "Chessed")
        self.assertEqual(form.parameter, "q")
        self.assertEqual(form.submit_label, "Search")
        self.assertTrue(form.is_active)

    def test_every_advanced_option_is_offered(self) -> None:
        form = search_form(Search())

        self.assertEqual(
            [option.parameter for option in form.options],
            [option.parameter for option in OPTIONS],
        )
        self.assertEqual(
            [option.label for option in form.options], [option.label for option in OPTIONS]
        )
        self.assertFalse(any(option.checked for option in form.options))

    def test_chosen_options_render_as_checked(self) -> None:
        form = search_form(Search(term="chessed", whole_words=True))

        checked = {option.parameter: option.checked for option in form.options}

        self.assertEqual(checked, {"whole_words": True, "tagline": False})
        self.assertTrue(form.is_advanced)

    def test_an_empty_search_is_not_active_so_the_empty_message_can_differ(self) -> None:
        self.assertFalse(search_form(Search()).is_active)


class SearchTermLimitsTest(SimpleTestCase):
    """A term past the cap is treated as no search (audit B5)."""

    def test_a_term_longer_than_the_cap_is_dropped(self) -> None:
        from apps.charities.search import MAX_TERM_LENGTH

        too_long = "a" * (MAX_TERM_LENGTH + 1)

        self.assertTrue(from_query(query({TERM_PARAMETER: too_long})).is_empty)

    def test_a_term_at_the_cap_is_kept(self) -> None:
        from apps.charities.search import MAX_TERM_LENGTH

        at_cap = "a" * MAX_TERM_LENGTH

        self.assertEqual(from_query(query({TERM_PARAMETER: at_cap})).term, at_cap)

    def test_a_repeated_term_uses_the_last_value(self) -> None:
        """`?q=a&q=b` is one term, and the choice is explicit (audit B9)."""
        parsed = from_query(QueryDict(f"{TERM_PARAMETER}=a&{TERM_PARAMETER}=b"))

        self.assertEqual(parsed.term, "b")
