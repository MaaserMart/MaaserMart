"""Public interface of the charities app.

Other apps call only the functions defined here, never this app's models.
"""

from dataclasses import dataclass
from urllib.parse import urlencode

from django.db import transaction

from apps.events.services import record_event

from .contracts import CharityCard
from .models import Charity
from .repositories import CharityRepository
from .sorting import DEFAULT_SORT, CharitySort
from .sorting import query_pairs as sort_query_pairs
from .sorting import query_string as sort_query_string


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

    `sort` is part of the result set, not of one page: every link the page
    builds repeats it, or moving to page 2 would silently reorder the list.
    """

    items: tuple[CharityCard, ...]
    total: int
    number: int
    page_size: int
    sort: CharitySort = DEFAULT_SORT

    @property
    def page_count(self) -> int:
        return page_count(self.total, self.page_size)

    @property
    def has_previous(self) -> bool:
        return self.number > 1

    @property
    def has_next(self) -> bool:
        return self.number < self.page_count

    @property
    def sort_pairs(self) -> tuple[tuple[str, str], ...]:
        """The sort as hidden-input pairs; empty for the default order."""
        return sort_query_pairs(self.sort)

    def query(self, number: int) -> str:
        """Query string for another page of this same result set."""
        query = urlencode({"page": number, "page_size": self.page_size})
        sort = sort_query_string(self.sort)
        return f"{query}&{sort}" if sort else query

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
    sort: CharitySort = DEFAULT_SORT,
    page: int | None = 1,
    page_size: int | None = None,
) -> Page:
    """Return one page of charities, ordered by `sort`.

    §6.2.5: choosing an order shows page 1, which the view gets by not passing a
    `page` for a sort change; an explicit page in the URL is still honoured so a
    shared link keeps its whole state (UC-03).
    """
    page_size = clamp_page_size(page_size)
    total = repository.count()
    count = page_count(total, page_size)
    number = max(1, min(page or 1, count))
    offset = (number - 1) * page_size

    return Page(
        items=repository.page(offset=offset, limit=page_size, sort=sort),
        total=total,
        number=number,
        page_size=page_size,
        sort=sort,
    )
