"""The listing's whole URL state, in one value (audit S1, S7; D-068).

A listing page is described entirely by its address: a search term, a set of
ticked filters, an order, and which page of the results is on screen. Those four
things used to be read, written and re-printed separately — three modules each
with their own `from_query`, `query_pairs` and `query_string`, `Page` gluing
three pair-bundles together in a hand-written order, and three template partials
that every form had to remember to include.

`PageState` is that whole address as one immutable value. The three feature
modules still own their own *rules* (clamping, mechanism pairing, term matching);
this module owns the **plumbing that joins them** — one list of parts, one
reading order, one writing order, one string.

Adding a fourth kind of state is one entry in `PARTS` plus a field here.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any
from urllib.parse import urlencode

from .filters import CharityFilters
from .filters import from_query as filters_from_query
from .filters import query_pairs as filter_pairs
from .search import Search
from .search import from_query as search_from_query
from .search import query_pairs as search_pairs
from .sorting import DEFAULT_SORT, CharitySort
from .sorting import from_query as sort_from_query
from .sorting import query_pairs as sort_pairs

# Page sizes: the URL asks, these bound the answer. They live here because a
# page size is part of the address, not a rule of the query.
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

# The parameter names of the window, as opposed to the result set.
PAGE_PARAMETER = "page"
PAGE_SIZE_PARAMETER = "page_size"


def clamp_page_size(requested: int | None) -> int:
    """Bound a requested page size to a range the server is willing to serve."""
    if requested is None:
        return DEFAULT_PAGE_SIZE
    return max(1, min(requested, MAX_PAGE_SIZE))


def page_count(total: int, page_size: int) -> int:
    """Pages needed for `total` rows; at least one, so a page always exists."""
    return max(1, -(-total // page_size))


def _positive_int(raw: str | None) -> int | None:
    """Read an optional positive whole number, treating junk as absent."""
    if raw is None:
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


@dataclass(frozen=True)
class Part:
    """One slice of the address: how to read it from a URL and how to write it back.

    `name` is the spelling the templates use to leave a slice out — the form that
    owns the filters prints them itself, so it includes the state with
    `skip="filters"`. It is also the field name on `PageState`, so a part cannot
    be added without saying where it is stored.
    """

    name: str
    read: Callable[[Any], Any]
    write: Callable[[Any], tuple[tuple[str, object], ...]]


# The result set, in the order a URL spells it. One table, so the reading order
# and the writing order cannot drift apart (audit S7).
PARTS: tuple[Part, ...] = (
    Part("search", search_from_query, search_pairs),
    Part("filters", filters_from_query, filter_pairs),
    Part("sort", sort_from_query, sort_pairs),
)

# What a form can leave out of the hidden fields, by name.
SKIPPABLE = tuple(part.name for part in PARTS)


@dataclass(frozen=True)
class PageState:
    """Everything the listing's address says: the result set plus the window.

    Immutable, because a page link is "the same state, one page over" — building
    a link must not be able to change the state it was built from. `page` and
    `page_size` are the window onto the result set; `search`, `filters` and
    `sort` describe the set itself.

    `page_size` and `page` are clamped on construction, so an out-of-range value
    cannot leak in from a hand-written URL or a stray call: the state a caller
    holds is always a state the server is willing to serve.
    """

    search: Search = Search()
    filters: CharityFilters = CharityFilters()
    sort: CharitySort = DEFAULT_SORT
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE

    def __post_init__(self) -> None:
        object.__setattr__(self, "page", max(1, self.page))
        object.__setattr__(self, "page_size", clamp_page_size(self.page_size))

    @classmethod
    def from_query(cls, query) -> PageState:
        """Read a request's query parameters into the whole state.

        Every part is read through its own module's `from_query`, so the "a junk
        value is ignored, not an error" rule is stated once per feature rather
        than once per caller.
        """
        values = {part.name: part.read(query) for part in PARTS}
        return cls(
            **values,
            page=_positive_int(query.get(PAGE_PARAMETER)) or 1,
            page_size=clamp_page_size(_positive_int(query.get(PAGE_SIZE_PARAMETER))),
        )

    def replaced(self, **changes) -> PageState:
        """A copy with some parts replaced — the way code changes state."""
        return replace(self, **changes)

    def with_page(self, number: int) -> PageState:
        """The same result set, on another page."""
        return replace(self, page=number)

    def groups(self) -> tuple[tuple[str, tuple[tuple[str, object], ...]], ...]:
        """(part name, its parameter pairs), in the order a URL spells them."""
        return tuple((part.name, part.write(getattr(self, part.name))) for part in PARTS)

    def pairs(self, skip: tuple[str, ...] = ()) -> tuple[tuple[str, object], ...]:
        """The result set's pairs, minus any part the caller is writing itself."""
        return tuple(pair for name, pairs in self.groups() if name not in skip for pair in pairs)

    def query_string(self, skip: tuple[str, ...] = (), **window: int) -> str:
        """This state as a query string, with an optional page/page_size window.

        The window goes first and the result set after it, in the one order
        `PARTS` states — the order every link on the page therefore spells the
        same way, so two addresses that describe the same listing are identical
        text (audit S7).
        """
        pairs = tuple(window.items()) + self.pairs(skip=skip)
        return urlencode(pairs)
