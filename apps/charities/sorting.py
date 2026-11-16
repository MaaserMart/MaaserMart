"""The listing's sort orders, as §6.2.5 defines them (D-048).

This is the one place that knows the doc's `sort` and `direction` parameter
values, the order the dropdown offers, and which direction each mechanism starts
with. The view, the page links and the repository read a `CharitySort` from
here, so adding or renaming a mechanism is a change in this file and nowhere
else.

A mechanism is a value object rather than a bare string: the dropdown, the
direction buttons and the ORDER BY all need a mechanism's parts, and a typo in a
string would otherwise only show up as a silently unsorted listing.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode

SORT_PARAMETER = "sort"
DIRECTION_PARAMETER = "direction"

ASCENDING = "asc"
DESCENDING = "desc"
DIRECTIONS = (ASCENDING, DESCENDING)


@dataclass(frozen=True)
class Mechanism:
    """One choice in §6.2.5's dropdown.

    `descending_by_default` is the direction the mechanism starts in: A→Z for
    names, high→low for every count or date. `low_label` and `high_label` are
    what its two direction buttons say, so each order states the direction in
    its own terms: letters for names, counts for tallies, dates for time.
    """

    value: str
    label: str
    descending_by_default: bool = True
    low_label: str = "Low to high"
    high_label: str = "High to low"

    @property
    def default_direction(self) -> str:
        return DESCENDING if self.descending_by_default else ASCENDING


# §6.2.5's list, in the order the dropdown shows it. "Most popular" is the doc's
# name for the order by EVENT count; the direction labels say what each order
# means, so "high to low" is never asked of a date (D-048).
ALPHABETICAL = Mechanism(
    "alphabetical",
    "Name",
    descending_by_default=False,
    low_label="A to Z",
    high_label="Z to A",
)
TRENDING = Mechanism("trending", "Trending")
POPULAR = Mechanism("popular", "Most popular")
RATING = Mechanism("rating", "Highest rated", low_label="Lowest rated", high_label="Highest rated")
HASKAMOS = Mechanism("haskamos", "Most haskamos")
NEWEST = Mechanism(
    "newest", "Most recently added", low_label="Oldest first", high_label="Newest first"
)
UPDATED = Mechanism(
    "updated",
    "Most recently updated",
    low_label="Least recently changed",
    high_label="Most recently changed",
)

MECHANISMS: tuple[Mechanism, ...] = (
    ALPHABETICAL,
    TRENDING,
    POPULAR,
    RATING,
    HASKAMOS,
    NEWEST,
    UPDATED,
)

DEFAULT_MECHANISM = ALPHABETICAL


@dataclass(frozen=True)
class CharitySort:
    """A chosen mechanism and direction — §6.2.5's tuple of both.

    Both parts are required. A default direction here would contradict the
    mechanism's own default (`CharitySort(RATING)` would mean low to high), so
    the only place that fills a missing direction is `from_query`, which reads
    the mechanism's default. `descending` is a flag rather than the URL's word
    so the repository can read it directly and the template can compare it once.
    """

    mechanism: Mechanism
    descending: bool

    @property
    def is_default(self) -> bool:
        """True for alphabetical A→Z, the order a URL with no sort describes."""
        return self.mechanism == DEFAULT_MECHANISM and not self.descending

    @property
    def direction(self) -> str:
        return DESCENDING if self.descending else ASCENDING


DEFAULT_SORT = CharitySort(mechanism=DEFAULT_MECHANISM, descending=False)


def from_query(query) -> CharitySort:
    """Read `sort` and `direction` from a request query, as §6.2.5 states.

    An absent `sort` means alphabetical. A `sort` that names no mechanism makes
    the whole choice fall back to alphabetical A→Z: "when nothing recognizable
    is input ... it defaults to alphabetical a->z". A junk or absent
    `direction` keeps the mechanism and takes its default direction, the same
    treatment the filter groups give an unusable value.
    """
    raw_sort = query.get(SORT_PARAMETER)
    if raw_sort is None:
        mechanism = DEFAULT_MECHANISM
    else:
        mechanism = _mechanism(raw_sort)
        if mechanism is None:
            return DEFAULT_SORT

    raw_direction = query.get(DIRECTION_PARAMETER)
    direction = raw_direction if raw_direction in DIRECTIONS else mechanism.default_direction
    return CharitySort(mechanism=mechanism, descending=direction == DESCENDING)


def query_pairs(sort: CharitySort) -> tuple[tuple[str, str], ...]:
    """The sort as (parameter, value) pairs, empty for the default.

    Leaving the default out keeps a plain page link plain, and makes every URL
    that describes the same view spell it the same way.
    """
    if sort.is_default:
        return ()
    return (
        (SORT_PARAMETER, sort.mechanism.value),
        (DIRECTION_PARAMETER, sort.direction),
    )


def query_string(sort: CharitySort) -> str:
    """The sort as a query string, for a page link that must keep it."""
    return urlencode(query_pairs(sort))


def _mechanism(value: str) -> Mechanism | None:
    return next((mechanism for mechanism in MECHANISMS if mechanism.value == value), None)


@dataclass(frozen=True)
class SortOption:
    """One entry in the sort dropdown, already carrying its label."""

    value: str
    label: str


@dataclass(frozen=True)
class SortForm:
    """The sort control, ready to render.

    The dropdown carries `selected` and the two direction buttons carry their
    labels and which one is current. The parameter names and the direction
    values come from here too, so the template holds no sort vocabulary at all:
    renaming `sort`, `direction`, `asc` or `desc` is a change in this file only.
    """

    options: tuple[SortOption, ...]
    selected: str
    descending: bool
    low_label: str
    high_label: str
    parameter: str = SORT_PARAMETER
    direction_parameter: str = DIRECTION_PARAMETER
    ascending_value: str = ASCENDING
    descending_value: str = DESCENDING


def sort_form(sort: CharitySort) -> SortForm:
    """Assemble the dropdown and its direction buttons from the chosen sort."""
    return SortForm(
        options=tuple(SortOption(mechanism.value, mechanism.label) for mechanism in MECHANISMS),
        selected=sort.mechanism.value,
        descending=sort.descending,
        low_label=sort.mechanism.low_label,
        high_label=sort.mechanism.high_label,
    )
