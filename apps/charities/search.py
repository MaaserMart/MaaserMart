"""The listing's search, as §6.2.6 defines it (D-054).

This is the one place that knows the doc's search parameter, the advanced options
it offers and how a typed term is matched. The view, the search bar, the page
links and the repository read a `Search` from here, so adding or renaming an
option is a change in this file and nowhere else.

`Search` is a value object rather than a bare string because the term and the
advanced options are read by three different places: the query is narrowed by
them (§6.2.6), the bar shows them back, and every other control on the page has
to carry them so that filtering or sorting does not silently drop the search.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlencode

# §6.2.6 names neither the search parameter nor the advanced ones; `q` is the
# conventional short search parameter, and the options are named for what they
# switch on (D-054).
TERM_PARAMETER = "q"

# A term longer than this is not a search anyone typed; it is dropped like a
# junk `page`, so an over-long URL cannot turn into a multi-megabyte ILIKE
# pattern over every row (audit B5). 100 characters is longer than any charity
# name in §5.2.9 (200) needs to be typed in full and far shorter than a request
# line Caddy would reject.
MAX_TERM_LENGTH = 100


@dataclass(frozen=True)
class Option:
    """One switch in the advanced panel: its URL parameter and where it is stored.

    One table for the two facts that must agree — the parameter the URL uses and
    the attribute on `Search` — so adding or renaming an option is one entry here.
    """

    parameter: str
    attribute: str
    label: str
    note: str = ""


# §6.2.6's advanced options ("like full words only, or searching in the tagline"),
# in the order the panel shows them. They are additions to the default search,
# which matches part of a word anywhere in the name (§6.2.2).
OPTIONS: tuple[Option, ...] = (
    Option(
        "whole_words",
        "whole_words",
        "Full words only",
        "Off matches part of a word.",
    ),
    Option(
        "tagline",
        "tagline",
        "Search the tagline too",
        "Off matches the name only.",
    ),
)


@dataclass(frozen=True)
class Search:
    """A typed term and the advanced options that shape how it is matched.

    An empty term searches for nothing: §6.2.6 has the listing show every charity
    until something is typed, so an empty search must not narrow the page. The
    options are meaningless without a term, so `is_empty` is decided by the term
    alone.
    """

    term: str = ""
    whole_words: bool = False
    tagline: bool = False

    @property
    def is_empty(self) -> bool:
        return not self.term

    @property
    def is_advanced(self) -> bool:
        """True when an advanced option is on, so the panel opens showing why."""
        return any(getattr(self, option.attribute) for option in OPTIONS)

    @property
    def fields(self) -> tuple[str, ...]:
        """The CHARITY columns the term is matched against.

        §6.2.2 says list_charities "searches the name column"; the tagline is
        only read when the reader asks for it (§6.2.6).
        """
        return ("name", "tagline") if self.tagline else ("name",)

    @property
    def lookup(self) -> str:
        """The Django lookup that matches the term, from the advanced options.

        Both are case-insensitive, which UC-03 requires. A whole-word match is a
        regular expression because a word boundary is not a `contains` test; the
        escaped term is matched as one contiguous piece of text, so a multi-word
        term has to appear as typed rather than as scattered words.
        """
        return "iregex" if self.whole_words else "icontains"

    @property
    def pattern(self) -> str:
        """The value `lookup` compares against: the term, bounded to whole words if asked."""
        if not self.whole_words:
            return self.term
        return rf"\y{re.escape(self.term)}\y"


def from_query(query) -> Search:
    """Read the term and the advanced options from a request query.

    A blank or whitespace-only term, and one that is only whitespace once
    normalised, is no search at all: the listing shows every charity, and the
    advanced options are dropped with it rather than left on with nothing to
    match. Runs of whitespace collapse to one space, so a doubled space in an
    address still matches the single space in the text. A term longer than
    `MAX_TERM_LENGTH` is treated the same way as a blank one: no search.
    """
    # A repeated `q` keeps the last value (the first is a real term too, but a
    # URL can only mean one); saying so here keeps the choice explicit (B9).
    terms = query.getlist(TERM_PARAMETER)
    term = " ".join((terms[-1] if terms else "").split())
    if not term or len(term) > MAX_TERM_LENGTH:
        return Search()
    values = {option.attribute: _switched_on(query.get(option.parameter)) for option in OPTIONS}
    return Search(term=term, **values)


def query_pairs(search: Search) -> tuple[tuple[str, str], ...]:
    """The search as (parameter, value) pairs, empty when nothing was typed.

    An absent search keeps a plain page link plain, and makes every URL that
    describes the same view spell it the same way — the same rule the sort and
    the filter groups follow (D-046, D-048).
    """
    if search.is_empty:
        return ()
    parts: list[tuple[str, str]] = [(TERM_PARAMETER, search.term)]
    for option in OPTIONS:
        if getattr(search, option.attribute):
            parts.append((option.parameter, "1"))
    return tuple(parts)


def query_string(search: Search) -> str:
    """The search as a query string, so a page link can repeat it."""
    return urlencode(query_pairs(search))


@dataclass(frozen=True)
class SearchOption:
    """One switch in the advanced panel, ready to render."""

    parameter: str
    label: str
    note: str
    checked: bool


@dataclass(frozen=True)
class SearchForm:
    """The search bar, ready to render.

    The bar carries the term back to the reader and the advanced switches in
    their current state. The parameter name and the three labels come from here
    too, so the template holds no search vocabulary at all.
    """

    term: str = ""
    options: tuple[SearchOption, ...] = ()
    is_advanced: bool = False
    parameter: str = TERM_PARAMETER
    label: str = "Search"
    placeholder: str = "Charity name"
    submit_label: str = "Search"
    advanced_label: str = "Advanced search"

    @property
    def is_active(self) -> bool:
        """True when a term is applied, which is what changes the empty message."""
        return bool(self.term)


def search_form(search: Search) -> SearchForm:
    """Assemble the search bar from the search the URL asked for."""
    return SearchForm(
        term=search.term,
        options=tuple(
            SearchOption(
                parameter=option.parameter,
                label=option.label,
                note=option.note,
                checked=getattr(search, option.attribute),
            )
            for option in OPTIONS
        ),
        is_advanced=search.is_advanced,
    )


def _switched_on(raw: str | None) -> bool:
    """Whether an advanced option is on, read as a checkbox-style flag.

    The bar sends `1`; `0`, `false`, `off` and `no` all mean off, so an address
    someone hand-edited cannot switch an option on by accident.
    """
    if raw is None:
        return False
    return raw.strip().lower() not in ("", "0", "false", "off", "no")
