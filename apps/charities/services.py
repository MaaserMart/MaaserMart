"""Public interface of the charities app.

Other apps call only the functions defined here, never this app's models.
"""

import logging
from dataclasses import dataclass
from urllib.parse import urlsplit

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.events.services import record_event

from .contracts import CharityCard, CharityPage, DomainOption, LocationOption, RabbiOption
from .filters import CharityFilters, FilterForm, sidebar_groups
from .models import Charity, Review
from .repositories import (
    CharityRepository,
    DjangoCharityRepository,
    DjangoFilterOptionsRepository,
    FilterOptionsRepository,
)
from .search import Search
from .sorting import MECHANISMS, RATING, CharitySort
from .state import MAX_PAGE_SIZE, PageState, page_count

logger = logging.getLogger(__name__)

# The charity fields a save may change. `is_visible` stays out: it changes only
# through publish/hide, so a caller cannot flip visibility by passing it here.
EDITABLE_FIELDS = ("name", "tagline", "description", "image")

# Fields whose "absent" value is NULL, not "" (D-013, audit D5). A form submits
# an empty string for a cleared box, and storing it would give one meaning two
# encodings, so both entry points normalise before the row is written.
NULLABLE_FIELDS = ("tagline", "description", "image")

IMAGE_SCHEMES = ("http", "https")


def validate_image(value: str | None) -> str | None:
    """Return an image value the card can render, or refuse it (audit B8).

    Two shapes are allowed: a repo-relative path under `static/` (what D-043's
    seed writes) and an absolute http(s) URL on a host listed in
    `settings.CHARITY_IMAGE_HOSTS`. Anything else is refused at write time, so
    the template never has to guess and a card never loads an arbitrary
    third-party image or a path that escapes `static/`.
    """
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    parts = urlsplit(value)
    if parts.scheme:
        if parts.scheme.lower() not in IMAGE_SCHEMES or not parts.netloc:
            raise ValueError(f"Charity image must be an http(s) URL or a static path: {value!r}")
        if not _image_host_allowed(parts.hostname or ""):
            raise ValueError(
                f"Charity image host {parts.hostname!r} is not in CHARITY_IMAGE_HOSTS: {value!r}"
            )
        return value
    if value.startswith(("/", "\\")) or ".." in value.split("/"):
        raise ValueError(f"Charity image must not leave static/: {value!r}")
    if ":" in value:
        raise ValueError(f"Charity image is neither a URL nor a path: {value!r}")
    return value


def _image_host_allowed(hostname: str) -> bool:
    """Whether `hostname` is on the configured image allowlist.

    An entry starting with "." allows any subdomain (".example.com"). An empty
    list allows no external image at all, which is the safe default.
    """
    hostname = hostname.lower()
    hosts = [host.lower() for host in getattr(settings, "CHARITY_IMAGE_HOSTS", ())]
    return any(
        hostname == host or (host.startswith(".") and hostname.endswith(host)) for host in hosts
    )


def _clean_value(field: str, value):
    """Normalise one field value at the entry point: trim, and "" becomes NULL."""
    if isinstance(value, str):
        value = value.strip()
        if field in NULLABLE_FIELDS and not value:
            return None
    if field == "image":
        return validate_image(value)
    return value


def publish_charity(charity_id, by_user_id=None):
    """Make a charity visible to the public. Approvals calls this once a charity is approved."""
    _set_visible(charity_id, True, by_user_id)


def hide_charity(charity_id, by_user_id=None):
    """Hide a charity from the public, for example to review it again after many reports."""
    _set_visible(charity_id, False, by_user_id)


def update_charity(charity_id, by_user_id=None, **changes):
    """Save field changes to a charity, recording one `charity_updated` EVENT.

    Every save of a charity goes through here or `_set_visible` (D-052), so the
    "most recently updated" order and §5.2.21's derived date cannot go stale.
    Only `EDITABLE_FIELDS` are accepted; anything else is a programming error,
    not a value to ignore. A call that changes nothing writes nothing and
    records no event (D-041's rule for an unchanged state).
    """
    unknown = set(changes) - set(EDITABLE_FIELDS)
    if unknown:
        logger.error(
            "update_charity refused for charity %s: unknown fields %s", charity_id, sorted(unknown)
        )
        raise ValueError(f"Not an editable charity field: {', '.join(sorted(unknown))}")
    changes = {field: _clean_value(field, value) for field, value in changes.items()}
    with transaction.atomic():
        charity = Charity.objects.select_for_update().filter(pk=charity_id).first()
        if charity is None:
            raise Charity.DoesNotExist(f"No charity with id {charity_id}")
        changed = [field for field, value in changes.items() if getattr(charity, field) != value]
        if not changed:
            return
        for field in changed:
            setattr(charity, field, changes[field])
        charity.save(update_fields=changed)
        # Every change to a charity is recorded as a charity_updated EVENT (§6.1, D-039).
        record_event(charity_id, "charity_updated", user_id=by_user_id)


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
# The rules below are the listing's: filters, order, page clamping, page sizes.
# They know nothing about where the rows come from; the repository is injected.


@dataclass(frozen=True)
class Page:
    """One page of results, plus the state and the links needed to move around it.

    The search, the filters and the order belong to the result set, not to one
    page: every link the page builds repeats all three, or moving to page 2 would
    silently drop a filter. That whole address is `Page.state` — one value,
    instead of the three pair-bundles this class used to concatenate by hand
    (audit S1, S7; D-068).
    """

    items: tuple[CharityCard, ...]
    total: int
    state: PageState = PageState()

    @property
    def number(self) -> int:
        """Which page of the result set this is, already clamped to a real one."""
        return self.state.page

    @property
    def page_size(self) -> int:
        return self.state.page_size

    @property
    def sort(self) -> CharitySort:
        return self.state.sort

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
        return self.state.query_string(page=number, page_size=min(self.page_size, MAX_PAGE_SIZE))

    @property
    def previous_query(self) -> str:
        return self.query(self.number - 1)

    @property
    def next_query(self) -> str:
        return self.query(self.number + 1)

    @property
    def can_jump_to_first(self) -> bool:
        """Whether the first page is far enough to warrant a jump link (P5)."""
        return self.number > 3

    @property
    def can_jump_to_last(self) -> bool:
        """Whether the last page is far enough to warrant a jump link (P5)."""
        return self.page_count - self.number > 2

    @property
    def first_query(self) -> str:
        """The first page of this same result set, for a jump link (audit P5)."""
        return self.query(1)

    @property
    def last_query(self) -> str:
        """The last page of this same result set, for a jump link (audit P5)."""
        return self.query(self.page_count)

    @property
    def clear_filters_query(self) -> str:
        """The page with its size, search and order kept, but no filters (§6.2.4)."""
        return self.state.replaced(filters=CharityFilters()).query_string(page_size=self.page_size)

    def numbers(self, window: int = 2) -> list[tuple[int, str]]:
        """(page number, query string) pairs to render as links."""
        first = max(1, self.number - window)
        last = min(self.page_count, self.number + window)
        return [(n, self.query(n)) for n in range(first, last + 1)]


def list_charities(repository: CharityRepository, state: PageState | None = None) -> Page:
    """Return the page of charities the state describes.

    §6.2.6: the search is a term plus the advanced options that shape it, and it
    narrows the same set the filters do rather than starting a new one, so the
    two combine. §6.2.6 also shows page 1 of a search, which the view gets by not
    passing a `page` when the term changes; an explicit page in the URL is still
    honoured so a shared link keeps its whole state (UC-03). §6.2.5's sort change
    and §6.2.4's filter change work the same way.
    """
    state = state or PageState()
    # One query answers the page and its total (see `page_and_count`), so a row
    # inserted between two statements cannot make a charity repeat or vanish
    # across a page boundary (audit B3).
    items, total = repository.page_and_count(
        offset=(state.page - 1) * state.page_size,
        limit=state.page_size,
        filters=state.filters,
        sort=state.sort,
        search=state.search,
    )
    count = page_count(total, state.page_size)
    if state.page > count:
        # The requested page was past the end: the state is answered with the
        # last real page, and only when there are rows is a second read needed.
        state = state.with_page(count)
        if total:
            items = repository.page(
                offset=(count - 1) * state.page_size,
                limit=state.page_size,
                filters=state.filters,
                sort=state.sort,
                search=state.search,
            )
    return Page(items=items, total=total, state=state)


# --- Charity page ------------------------------------------------------------
# §6.2.7's page shows one charity in full. It is read through the repository so
# the page and the listing cards compute the same derived values (D-044, D-051).


def get_charity_page(repository: CharityRepository, charity_id: int) -> CharityPage | None:
    """One charity in full, or None when no row has that id."""
    return repository.detail(charity_id)


def get_link_url(repository: CharityRepository, charity_id: int, link_id: int) -> str | None:
    """The safe target of one of a charity's links, or None."""
    return repository.link_url(charity_id, link_id)


def get_user_review(user, charity_id: int) -> Review | None:
    """Return the member's existing review, if any, for editing."""
    if not user.is_authenticated:
        raise PermissionDenied
    return Review.objects.filter(author=user, charity_id=charity_id).first()


def save_review(user, charity_id: int, rating: int, body: str = "") -> None:
    """Create or replace the member's review; the database enforces uniqueness.

    Every account is a member (D-074). Validate here as well as on the form,
    since callers of this service do not necessarily use the web form.
    """
    if not user.is_authenticated:
        raise PermissionDenied
    if isinstance(rating, bool) or not isinstance(rating, int) or not 1 <= rating <= 5:
        raise ValidationError("Choose a rating from 1 to 5.")
    Review.objects.update_or_create(
        author=user, charity_id=charity_id, defaults={"rating": rating, "body": body or ""}
    )


# --- Lookups for other apps ---------------------------------------------------
# Small reads other apps need without a whole listing page: support's report form
# picks a charity by name (D-072). They return `CharityChoice`, never a model row.


@dataclass(frozen=True)
class CharityChoice:
    """A charity as a pick list shows it: its id and its name."""

    id: int
    name: str


CHARITY_LOOKUP_LIMIT = 10


def find_charities_by_name(
    term: str, limit: int = CHARITY_LOOKUP_LIMIT
) -> tuple[CharityChoice, ...]:
    """Charities whose name contains `term`, case-insensitively, A to Z.

    An empty or blank term matches nothing, so a pick list never dumps the table.
    """
    term = (term or "").strip()
    if not term:
        return ()
    limit = max(1, min(limit, CHARITY_LOOKUP_LIMIT))
    rows = Charity.objects.filter(name__icontains=term).only("id", "name").order_by("name", "id")
    return tuple(CharityChoice(id=row.id, name=row.name) for row in rows[:limit])


def get_charity_choice(charity_id) -> CharityChoice | None:
    """One charity's id and name, or None when no row has that id."""
    try:
        charity_id = int(charity_id)
    except (TypeError, ValueError):
        return None
    row = Charity.objects.filter(pk=charity_id).only("id", "name").first()
    return None if row is None else CharityChoice(id=row.id, name=row.name)


def get_charity_choices(charity_ids) -> dict[int, CharityChoice]:
    """Id and name for each existing charity among `charity_ids`, keyed by id."""
    ids = {int(i) for i in charity_ids if i is not None}
    if not ids:
        return {}
    rows = Charity.objects.filter(pk__in=ids).only("id", "name")
    return {row.id: CharityChoice(id=row.id, name=row.name) for row in rows}


# --- Filter sidebar ----------------------------------------------------------
# The sidebar is data: a `FilterForm` holds the groups with their options, so the
# template can render checkboxes and number inputs without knowing which group
# repeats or what the parameter is called. The option lists are read through the
# repository so the view could swap the source without changing this function.


def list_domains(repository: FilterOptionsRepository) -> tuple[DomainOption, ...]:
    """The Domain filter group's choices (§5.2.11)."""
    return repository.domains()


def list_locations(repository: FilterOptionsRepository) -> tuple[LocationOption, ...]:
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


# --- Lookups for the chatbot ---------------------------------------------------
# The chatbot's model asks for charities through these read-only calls (D-076).
# They read the same repository as the listing and the charity page, so the
# chatbot sees exactly what a visitor can see, and they return the same
# contracts, never model rows.

CHAT_RESULT_LIMIT = 5


def _matching_ids(options, wanted: str) -> tuple[int, ...] | None:
    """Ids of the options whose label contains `wanted`; None when nothing is asked."""
    wanted = (wanted or "").strip().lower()
    if not wanted:
        return None
    return tuple(o.id for o in options if wanted in getattr(o, "label", o.name).lower())


def search_charities(
    term: str = "",
    *,
    domain: str = "",
    location: str = "",
    sort: str = RATING.value,
    limit: int = CHAT_RESULT_LIMIT,
) -> tuple[CharityCard, ...]:
    """Up to `limit` charities matching a name, a domain and a location, best first.

    `domain` and `location` are matched by name, case-insensitively, against the
    filter options; one that matches no option yields no charities rather than
    being ignored. `sort` is a §6.2.5 mechanism value; an unknown one means
    highest rated.
    """
    options = DjangoFilterOptionsRepository()
    domains = _matching_ids(options.domains(), domain)
    locations = _matching_ids(options.locations(), location)
    if domains == () or locations == ():
        return ()
    mechanism = next((m for m in MECHANISMS if m.value == sort), RATING)
    # published_only follows the listing's view until D-042 flips it.
    return DjangoCharityRepository(published_only=False).page(
        offset=0,
        limit=max(1, min(limit, CHAT_RESULT_LIMIT)),
        filters=CharityFilters(domains=domains or (), locations=locations or ()),
        sort=CharitySort(mechanism, mechanism.descending_by_default),
        search=Search(term=(term or "").strip()),
    )


def get_charity(charity_id) -> CharityPage | None:
    """One charity in full, as its page shows it, or None."""
    try:
        charity_id = int(charity_id)
    except (TypeError, ValueError):
        return None
    return DjangoCharityRepository(published_only=False).detail(charity_id)


def domain_names() -> tuple[str, ...]:
    """Every domain's name, as the Domain filter offers them."""
    return tuple(o.name for o in DjangoFilterOptionsRepository().domains())


@dataclass(frozen=True)
class RecommendationCharity:
    """The public fields and classification needed by recommendations."""

    id: int
    name: str
    tagline: str | None
    is_visible: bool
    domain_ids: frozenset[int]
    location_ids: frozenset[int]


def recommendation_charities(history_ids) -> tuple[RecommendationCharity, ...]:
    """Published candidates plus historical charities needed to calculate signals.

    An unpublished charity may still contribute to a member's past preferences,
    but is never itself a recommendation.
    """
    from django.db.models import Q

    rows = Charity.objects.filter(Q(is_visible=True) | Q(pk__in=history_ids)).prefetch_related(
        "domains", "locations"
    )
    return tuple(
        RecommendationCharity(
            id=row.pk,
            name=row.name,
            tagline=row.tagline,
            is_visible=row.is_visible,
            domain_ids=frozenset(domain.pk for domain in row.domains.all()),
            location_ids=frozenset(location.pk for location in row.locations.all()),
        )
        for row in rows
    )


def charity_names(charity_ids) -> dict[int, str]:
    """Resolve charity IDs for history without exposing another app's models."""
    return dict(Charity.objects.filter(pk__in=charity_ids).values_list("pk", "name"))
