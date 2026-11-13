"""The listing's filter groups, as §6.2.4 defines them (D-045).

`CharityFilters` is the one place that knows the doc's URL parameter names, which
groups repeat and which take one number. Everything else — the view, the sidebar
form, the repository — reads the groups from here, so adding or renaming a group
is a change in this file and nowhere else.

The value carries ids and numbers, never names: D-032 makes a location's name
alone ambiguous, and a name in a URL would break the moment a row is renamed.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields

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
        """True when nothing is filtered, so the listing shows every charity."""
        return not any(getattr(self, group.name) for group in fields(self))

    def selected(self, name: str) -> tuple[int, ...]:
        """The ids ticked in a repeatable group; empty for the numeric groups."""
        group = next((g for g in GROUPS if g[0] == name), None)
        if group is None or not group[1]:
            return ()
        return getattr(self, _attr(name))

    def active_count(self) -> int:
        """How many groups narrow the listing, for the sidebar's summary line."""
        return sum(1 for group in GROUPS if getattr(self, _attr(group[0])))


def _attr(parameter: str) -> str:
    """§6.2.4's parameter names are plural-free: `domain` reads `domains`."""
    return {
        "domain": "domains",
        "location": "locations",
        "haskama_rabbis": "haskama_rabbis",
    }.get(parameter, parameter)


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
    """An optional whole number; junk is treated as absent."""
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class FilterForm:
    """The sidebar's groups with their options, ready to render (D-045).

    `options` maps a repeatable group's parameter name to its choices;
    `values` maps every parameter name to what the URL asked for.
    """

    filters: CharityFilters
    options: dict[str, tuple] = field(default_factory=dict)

    @property
    def is_active(self) -> bool:
        return not self.filters.is_empty
