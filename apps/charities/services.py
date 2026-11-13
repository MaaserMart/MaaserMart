"""Public interface of the charities app.

Other apps call only the functions defined here, never this app's models.
"""

from dataclasses import dataclass
from urllib.parse import urlencode

from django.db import transaction

from apps.events.services import record_event

from .contracts import CharityCard, DomainOption, LocationOption, RabbiOption
from .filters import CharityFilters, FilterForm, query_pairs, query_string, sidebar_groups
from .models import Charity
from .repositories import CharityRepository


def publish_charity(charity_id, by_user_id=None):
    """Make a charity visible to the public. Approvals calls this once a charity is approved."""
    _set_visible(charity_id, True, by_user_id)


def hide_charity(charity_id, by_user_id=None):
    """Hide a charity from the public, for example to review it again after many reports."""
    _set_visible(charity_id, False, by_user_id)


def _set_visible(charity_id, visible, by_user_id):
    with transaction.atomic():
        charity = Charity.objects.select_for_update().filter(pk=charity_id).first()
        if charity is None:
            raise Charity.DoesNotExist(f"No charity with id {charity_id}")
        if charity.is_visible == visible:
            return  # Already in that state: no change, so no event (D-041).
        charity.is_visible = visible
        charity.save(update_fields=["is_visible"])
        # Every change to a charity is recorded as a charity_updated EVENT (§6.1, D-039).
        record_event(charity_id, "charity_updated", user_id=by_user_id)


# --- Listing -----------------------------------------------------------------
# The rules below are the listing's: order, page clamping, page sizes. They know
# nothing about where the rows come from; the repository is injected.

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def page_count(total: int, page_size: int) -> int:
    """Pages needed for `total` rows; at least one, so a page always exists."""
    return max(1, -(-total // page_size))


@dataclass(frozen=True)
class Page:
    """One page of results, plus the links needed to move between pages.

    `filters_query` is the query string a page link must repeat so the reader
    keeps the filters they chose; empty when nothing is filtered.
    """

    items: tuple[CharityCard, ...]
    total: int
    number: int
    page_size: int
    filters_query: str = ""
    # The same filters as (name, value) pairs, for replaying them as hidden inputs.
    filter_pairs: tuple[tuple[str, object], ...] = ()

    @property
    def page_count(self) -> int:
        return page_count(self.total, self.page_size)

    @property
    def has_previous(self) -> bool:
        return self.number > 1

    @property
    def has_next(self) -> bool:
        return self.number < self.page_count

    def query(self, number: int) -> str:
        """Query string for another page of this same result set."""
        parts = {"page": number, "page_size": min(self.page_size, MAX_PAGE_SIZE)}
        if self.filters_query:
            return f"{urlencode(parts)}&{self.filters_query}"
        return urlencode(parts)

    @property
    def previous_query(self) -> str:
        return self.query(self.number - 1)

    @property
    def next_query(self) -> str:
        return self.query(self.number + 1)

    def numbers(self, window: int = 2) -> list[tuple[int, str]]:
        """(page number, query string) pairs to render as links."""
        first = max(1, self.number - window)
        last = min(self.page_count, self.number + window)
        return [(n, self.query(n)) for n in range(first, last + 1)]


def clamp_page_size(requested: int | None) -> int:
    """Bound a requested page size to a range the server is willing to serve."""
    if requested is None:
        return DEFAULT_PAGE_SIZE
    return max(1, min(requested, MAX_PAGE_SIZE))


def list_charities(
    repository: CharityRepository,
    page: int | None = 1,
    page_size: int | None = None,
    filters: CharityFilters | None = None,
) -> Page:
    """Return one page of the charities `filters` keep, alphabetically by name."""
    filters = filters or CharityFilters()
    page_size = clamp_page_size(page_size)
    total = repository.count(filters)
    count = page_count(total, page_size)
    number = max(1, min(page or 1, count))
    offset = (number - 1) * page_size

    return Page(
        items=repository.page(offset=offset, limit=page_size, filters=filters),
        total=total,
        number=number,
        page_size=page_size,
        filters_query=query_string(filters),
        filter_pairs=query_pairs(filters),
    )


# --- Filter sidebar ----------------------------------------------------------
# The sidebar is data: a `FilterForm` holds the groups with their options, so the
# template can render checkboxes and number inputs without knowing which group
# repeats or what the parameter is called. The option lists are read through the
# repository so the view could swap the source without changing this function.


def list_domains(repository) -> tuple[DomainOption, ...]:
    """The Domain filter group's choices (§5.2.11)."""
    return repository.domains()


def list_locations(repository) -> tuple[LocationOption, ...]:
    """The Location filter group's choices (§5.2.10, D-045)."""
    return repository.locations()


def list_rabbis(repository) -> tuple[RabbiOption, ...]:
    """The Haskamos filter group's choices (§6.1, D-045)."""
    return repository.rabbis()


def filter_form(
    filters: CharityFilters,
    options: dict[str, tuple],
    requested: dict[str, int | None] | None = None,
) -> FilterForm:
    """Assemble the sidebar from the chosen filters and the option lists."""
    return FilterForm(filters=filters, groups=sidebar_groups(filters, options, requested or {}))
