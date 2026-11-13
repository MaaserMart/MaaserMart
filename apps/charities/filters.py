"""The listing's filter groups, as §6.2.4 defines them (D-045).

`CharityFilters` is the one place that knows the doc's URL parameter names, which
groups repeat and which take one number. Everything else — the view, the sidebar
form, the repository — reads the groups from here, so adding or renaming a group
is a change in this file and nowhere else.

The value carries ids and numbers, never names: D-032 makes a location's name
alone ambiguous, and a name in a URL would break the moment a row is renamed.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from urllib.parse import urlencode

# §6.2.4 Filter: the seven groups, in the order the sidebar shows them.
# (parameter, repeatable?)
GROUPS: tuple[tuple[str, bool], ...] = (
    ("domain", True),
    ("location", True),
    ("haskama_rabbis", True),
    ("min_rating", False),
    ("min_reviews", False),
    ("min_approving_haskamas", False),
    ("max_disapproving_haskamas", False),
)

# §5.2.15 REVIEW.rating is 1–5, and D-044 prints the average out of 5.
MIN_STAR_RATING, MAX_STAR_RATING = 1, 5


@dataclass(frozen=True)
class CharityFilters:
    """Which charities the listing should keep. Empty means "every charity".

    Each tuple is one group: charities matching *any* value in it are kept (OR),
    and every non-empty group must match (AND), exactly as §6.2.4 states.
    """

    domains: tuple[int, ...] = ()
    locations: tuple[int, ...] = ()
    haskama_rabbis: tuple[int, ...] = ()
    min_rating: int | None = None
    min_reviews: int | None = None
    min_approving_haskamas: int | None = None
    max_disapproving_haskamas: int | None = None

    @property
    def is_empty(self) -> bool:
        """True when nothing is filtered, so the listing shows every charity.

        `0` is a real filter value (D-045), so each group is tested for being
        unset rather than for truthiness.
        """
        return all(getattr(self, group.name) in ((), None) for group in fields(self))

    def selected(self, name: str) -> tuple[int, ...]:
        """The ids ticked in a repeatable group; empty for the numeric groups."""
        group = next((g for g in GROUPS if g[0] == name), None)
        if group is None or not group[1]:
            return ()
        return getattr(self, _attr(name))

    def active_count(self) -> int:
        """How many groups narrow the listing, for the sidebar's summary line."""
        return sum(1 for group in GROUPS if getattr(self, _attr(group[0])) not in ((), None))


def _attr(parameter: str) -> str:
    """§6.2.4's parameter names are plural-free: `domain` reads `domains`."""
    return {
        "domain": "domains",
        "location": "locations",
        "haskama_rabbis": "haskama_rabbis",
    }.get(parameter, parameter)


def query_pairs(filters: CharityFilters) -> tuple[tuple[str, object], ...]:
    """The filter groups as (parameter, value) pairs, in the doc's order."""
    parts: list[tuple[str, object]] = []
    for parameter, repeatable in GROUPS:
        value = getattr(filters, _attr(parameter))
        if repeatable:
            parts.extend((parameter, item) for item in value)
        elif value is not None:
            parts.append((parameter, value))
    return tuple(parts)


def query_string(filters: CharityFilters) -> str:
    """The filter groups as a query string, so a page link can repeat them."""
    return urlencode(query_pairs(filters))


def from_query(query) -> CharityFilters:
    """Build filters from request query parameters, ignoring anything unusable.

    A value that names no row is not an error: it is dropped, which is the same
    treatment the listing already gives a junk `page`.
    """
    values: dict[str, tuple] = {}
    for parameter, repeatable in GROUPS:
        if repeatable:
            values[_attr(parameter)] = _token_ids(query.getlist(parameter))
        else:
            values[parameter] = _number(query.get(parameter))
    return CharityFilters(**values)


def _token_ids(raw_values) -> tuple[int, ...]:
    """Positive whole ids from repeated query values, in the order given, no repeats."""
    seen: list[int] = []
    for raw in raw_values:
        try:
            value = int(raw)
        except (TypeError, ValueError):
            continue
        if value > 0 and value not in seen:
            seen.append(value)
    return tuple(seen)


def _number(raw: str | None) -> int | None:
    """An optional whole number; a blank input and junk both mean "absent".

    The sidebar always submits every number input, so an unticked group arrives
    as an empty string. Treating that as no filter keeps a submitted URL as clean
    as a hand-written one.
    """
    if raw is None or raw.strip() == "":
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class FilterForm:
    """The sidebar, ready to render (D-045).

    `groups` is the doc's order, each with its options or its single input;
    `filters` is what the URL asked for, so the sidebar shows the live state.
    """

    filters: CharityFilters
    groups: tuple[FilterGroup, ...] = ()

    @property
    def is_active(self) -> bool:
        return not self.filters.is_empty


@dataclass(frozen=True)
class FilterOption:
    """One tickable choice, already carrying the label it is shown with."""

    id: int
    label: str


@dataclass(frozen=True)
class FilterGroup:
    """One group in the sidebar, ready to render as checkboxes or one number input.

    `kind` is "checkboxes" or "number". A number group carries the bounds its
    input accepts (`min`, `max`, may be None) and a `label` for the input; a
    checkbox group carries `options` and the `selected` ids from the URL.
    """

    parameter: str
    legend: str
    kind: str
    options: tuple[FilterOption, ...] = ()
    selected: tuple[int, ...] = ()
    value: int | None = None
    label: str = ""
    min: int | None = None
    max: int | None = None
    empty_note: str = ""
    none_note: str = ""


# The legends and input labels, in the doc's order (§6.2.4). Kept beside the
# groups so a new group cannot be added without saying what it is called.
LEGENDS: dict[str, str] = {
    "domain": "Domains",
    "location": "Locations",
    "haskama_rabbis": "Haskamos",
    "min_rating": "Rating",
    "min_reviews": "Reviews",
    "min_approving_haskamas": "Approving haskamos",
    "max_disapproving_haskamas": "Disapproving haskamos",
}

NUMBER_LABELS: dict[str, str] = {
    "min_rating": "stars or more",
    "min_reviews": "reviews or more",
    "min_approving_haskamas": "at least",
    "max_disapproving_haskamas": "at most",
}

NONE_NOTES: dict[str, str] = {
    "max_disapproving_haskamas": "Leave blank for no limit.",
}

EMPTY_NOTES: dict[str, str] = {
    # D-045: the group is real but its options come from accounts, which has no
    # rabbi search yet. Saying so beats an empty box that looks broken.
    "haskama_rabbis": "Rabbi search is not available yet.",
}


def sidebar_groups(filters: CharityFilters, options: dict[str, tuple]) -> tuple[FilterGroup, ...]:
    """Build the sidebar's groups from the URL's filters and the option lists."""
    groups: list[FilterGroup] = []
    for parameter, repeatable in GROUPS:
        if repeatable:
            choices = tuple(
                FilterOption(id=option.id, label=_option_label(option))
                for option in options.get(parameter, ())
            )
            groups.append(
                FilterGroup(
                    parameter=parameter,
                    legend=LEGENDS[parameter],
                    kind="checkboxes",
                    options=choices,
                    selected=filters.selected(parameter),
                    empty_note=EMPTY_NOTES.get(parameter, "Nothing to choose from."),
                )
            )
            continue
        groups.append(
            FilterGroup(
                parameter=parameter,
                legend=LEGENDS[parameter],
                kind="number",
                value=getattr(filters, parameter),
                label=NUMBER_LABELS[parameter],
                min=MIN_STAR_RATING if parameter == "min_rating" else 0,
                max=MAX_STAR_RATING if parameter == "min_rating" else None,
                none_note=NONE_NOTES.get(parameter, ""),
            )
        )
    return tuple(groups)


def _option_label(option) -> str:
    """A location states its full identity; anything else has one name (D-045)."""
    return getattr(option, "label", None) or getattr(option, "name", str(option.id))
