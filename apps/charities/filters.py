"""The listing's filter groups, as §6.2.4 defines them (D-045).

`CharityFilters` is the one place that knows the doc's URL parameter names, which
groups repeat and which take one number. Everything else — the view, the sidebar
form, the repository — reads the groups from here, so adding or renaming a group
is a change in this file and nowhere else.

The value carries ids and numbers, never names: D-032 makes a location's name
alone ambiguous, and a name in a URL would break the moment a row is renamed.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, replace
from urllib.parse import urlencode


@dataclass(frozen=True)
class Group:
    """One of §6.2.4's filter groups: its URL parameter and where it is stored.

    One table for all three facts that must agree — the parameter the URL uses,
    the attribute on `CharityFilters`, and whether the group repeats — so adding
    or renaming a group is a single entry here.
    """

    parameter: str
    attribute: str
    repeatable: bool


# §6.2.4 Filter: the seven groups, in the order the sidebar shows them. The
# parameter names are the doc's, verbatim, including its singular
# `haskama_rabbi` (D-046).
GROUPS: tuple[Group, ...] = (
    Group("domain", "domains", repeatable=True),
    Group("location", "locations", repeatable=True),
    Group("haskama_rabbi", "haskama_rabbis", repeatable=True),
    Group("min_rating", "min_rating", repeatable=False),
    Group("min_reviews", "min_reviews", repeatable=False),
    Group("min_approving_haskamas", "min_approving_haskamas", repeatable=False),
    Group("max_disapproving_haskamas", "max_disapproving_haskamas", repeatable=False),
)

# The parameter a repeatable group's option list is looked up under.
OPTION_SOURCES: dict[str, str] = {
    "domain": "domains",
    "location": "locations",
    "haskama_rabbi": "rabbis",
}

# §5.2.15 REVIEW.rating is 1–5, and D-044 prints the average out of 5.
MIN_STAR_RATING, MAX_STAR_RATING = 1, 5

# The bounds each numeric group's value is held inside, so a value is never
# carried off the scale it means. `None` is "no bound in that direction". One
# table for every group: the clamp and the note that explains it read the same
# entry, so a new bounded group cannot print another group's sentence (audit B4).
CLAMPS: dict[str, tuple[int, None] | tuple[int, int] | tuple[None, int]] = {
    "min_rating": (MIN_STAR_RATING, MAX_STAR_RATING),
    "min_reviews": (0, None),
    "min_approving_haskamas": (0, None),
    "max_disapproving_haskamas": (0, None),
}


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

    def selected(self, parameter: str) -> tuple[int, ...]:
        """The ids ticked in a repeatable group; empty for the numeric groups."""
        group = next((g for g in GROUPS if g.parameter == parameter), None)
        if group is None or not group.repeatable:
            return ()
        return getattr(self, group.attribute)

    def active_count(self) -> int:
        """How many groups narrow the listing, for the sidebar's summary line."""
        return sum(1 for group in GROUPS if getattr(self, group.attribute) not in ((), None))


def query_pairs(filters: CharityFilters) -> tuple[tuple[str, object], ...]:
    """The filter groups as (parameter, value) pairs, in the doc's order."""
    parts: list[tuple[str, object]] = []
    for group in GROUPS:
        value = getattr(filters, group.attribute)
        if group.repeatable:
            parts.extend((group.parameter, item) for item in value)
        elif value is not None:
            parts.append((group.parameter, value))
    return tuple(parts)


def query_string(filters: CharityFilters) -> str:
    """The filter groups as a query string, so a page link can repeat them."""
    return urlencode(query_pairs(filters))


def from_query(query) -> CharityFilters:
    """Build filters from request query parameters, ignoring anything unusable.

    A value that names no row is not an error: it is dropped, which is the same
    treatment the listing already gives a junk `page`. `min_rating` is the one
    exception: it is clamped to the star scale rather than dropped, so a shared
    `?min_rating=99` still means "the highest rating".
    """
    values: dict[str, tuple] = {}
    for group in GROUPS:
        if group.repeatable:
            values[group.attribute] = _token_ids(query.getlist(group.parameter))
        else:
            values[group.attribute] = clamp_number(
                group.parameter, _number(query.get(group.parameter))
            )
    return CharityFilters(**values)


def keep_known_ids(filters: CharityFilters, options: dict[str, tuple]) -> CharityFilters:
    """Drop ticked ids that name no row, so a stale address filters nothing.

    D-045: "A raw value that names no row is ignored rather than rejected." The
    option lists are the authority — an id the sidebar does not offer is not a
    filter, and keeping it would empty the page with no box the reader could
    untick. `options` is keyed as `OPTION_SOURCES` names it (`domains`,
    `locations`, `rabbis`), so this runs after the lists are read and before
    anything counts or links a page.
    """
    changes: dict[str, tuple[int, ...]] = {}
    for group in GROUPS:
        if not group.repeatable:
            continue
        chosen = getattr(filters, group.attribute)
        if not chosen:
            continue
        known = {option.id for option in options.get(OPTION_SOURCES[group.parameter], ())}
        kept = tuple(value for value in chosen if value in known)
        if kept != chosen:
            changes[group.attribute] = kept
    return replace(filters, **changes) if changes else filters


def clamp_number(parameter: str, value: int | None) -> int | None:
    """Hold one numeric group inside the bounds its meaning allows (D-046, audit B4).

    Clamping happens once, at the edge where the URL is read, so everything
    downstream — the query, the sidebar's input, the page links — sees the same
    number. `?min_rating=99` therefore means "5 stars or more" and the sidebar
    shows that 5, rather than the reader silently getting something else. Each
    group's bounds come from `CLAMPS`, so the rating's star scale is the rating's
    own rule and a negative review count becomes zero instead of "everyone".
    """
    if value is None:
        return None
    low, high = CLAMPS.get(parameter, (None, None))
    if low is not None:
        value = max(low, value)
    if high is not None:
        value = min(high, value)
    return value


def clamp_rating(rating: int | None) -> int | None:
    """Hold `min_rating` inside the star scale (D-046)."""
    return clamp_number("min_rating", rating)


def requested_numbers(query) -> dict[str, int | None]:
    """The numeric groups exactly as the URL asked, before any clamping."""
    numbers: dict[str, int | None] = {}
    for group in GROUPS:
        if not group.repeatable:
            numbers[group.parameter] = _number(query.get(group.parameter))
    return numbers


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
    # True when this group narrows the listing. A chosen `0` is a real filter, so
    # the template needs this rather than testing `value` for truthiness.
    is_set: bool = False
    label: str = ""
    min: int | None = None
    max: int | None = None
    empty_note: str = ""
    none_note: str = ""
    # Set when the value shown is not the one the URL asked for, so the reader is
    # told the filter they got, not left to guess.
    adjusted_note: str = ""


# The legends and input labels, in the doc's order (§6.2.4). Kept beside the
# groups so a new group cannot be added without saying what it is called.
# Keyed by §6.2.4's parameter names, in the doc's order.
LEGENDS: dict[str, str] = {
    "domain": "Domains",
    "location": "Locations",
    "haskama_rabbi": "Haskamos",
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

# No group has special text today: the rabbi list now comes from
# accounts.services.search_rabbis (D-058), so an empty group is just empty.
EMPTY_NOTES: dict[str, str] = {}


def sidebar_groups(
    filters: CharityFilters,
    options: dict[str, tuple],
    requested: dict[str, int | None] | None = None,
) -> tuple[FilterGroup, ...]:
    """Build the sidebar's groups from the URL's filters and the option lists.

    `options` is keyed by what a group draws its choices from (`domains`,
    `locations`, `rabbis`), not by URL parameter, so the view does not have to
    know which parameter asks for which list. `requested` holds the raw numbers
    the URL asked for, so a clamped value can be called out.
    """
    requested = requested or {}
    groups: list[FilterGroup] = []
    for group in GROUPS:
        parameter = group.parameter
        if group.repeatable:
            choices = tuple(
                FilterOption(id=option.id, label=_option_label(option))
                for option in options.get(OPTION_SOURCES[parameter], ())
            )
            groups.append(
                FilterGroup(
                    parameter=parameter,
                    legend=LEGENDS[parameter],
                    kind="checkboxes",
                    options=choices,
                    selected=filters.selected(parameter),
                    is_set=bool(filters.selected(parameter)),
                    empty_note=EMPTY_NOTES.get(parameter, "Nothing to choose from."),
                )
            )
            continue
        value = getattr(filters, group.attribute)
        groups.append(
            FilterGroup(
                parameter=parameter,
                legend=LEGENDS[parameter],
                kind="number",
                value=value,
                is_set=value is not None,
                label=NUMBER_LABELS[parameter],
                min=CLAMPS.get(parameter, (None, None))[0],
                max=CLAMPS.get(parameter, (None, None))[1],
                none_note=NONE_NOTES.get(parameter, ""),
                adjusted_note=_adjusted_note(parameter, requested, value),
            )
        )
    return tuple(groups)


def _adjusted_note(parameter: str, requested: dict[str, int | None], value: int | None) -> str:
    """Say so when the URL asked for a value the sidebar is not showing.

    The sentence is built from that group's own bounds, so it names the rule
    that was applied ("between 1 and 5" for the star scale, "0 or more" for a
    count) rather than always describing the rating group (audit B4).
    """
    asked = requested.get(parameter)
    if asked is None or asked == value:
        return ""
    low, high = CLAMPS.get(parameter, (None, None))
    if low is not None and high is not None:
        return f"Kept between {low} and {high}; using {value}."
    if low is not None:
        return f"Kept at {low} or more; using {value}."
    if high is not None:
        return f"Kept at {high} or less; using {value}."
    return ""


def _option_label(option) -> str:
    """A location states its full identity; anything else has one name (D-045)."""
    return getattr(option, "label", None) or getattr(option, "name", str(option.id))
