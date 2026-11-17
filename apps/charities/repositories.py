"""Data access for the charity listing.

`CharityRepository` is the interface the rest of the app depends on.
`DjangoCharityRepository` is the single implementation that talks to Postgres.
Swapping the store later means adding an implementation, not editing callers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlsplit

from django.core.cache import cache
from django.db.models import (
    Avg,
    Count,
    Exists,
    Expression,
    F,
    IntegerField,
    OuterRef,
    Q,
    QuerySet,
    Subquery,
    Value,
    Window,
)
from django.db.models.functions import Coalesce

from apps.accounts import services as accounts
from apps.charities.contracts import (
    ActivitySummary,
    CharityCard,
    CharityLink,
    CharityPage,
    DomainOption,
    DomainTag,
    HaskamaEntry,
    LocationOption,
    LocationTag,
    RabbiOption,
    ReviewEntry,
    ReviewSummary,
)
from apps.charities.filters import CharityFilters
from apps.charities.models import (
    Charity,
    CharityDomain,
    CharityLocation,
    Domain,
    Haskama,
    Link,
    Location,
)
from apps.charities.search import Search
from apps.charities.sorting import (
    ALPHABETICAL,
    DEFAULT_SORT,
    HASKAMOS,
    NEWEST,
    POPULAR,
    RATING,
    TRENDING,
    UPDATED,
    CharitySort,
    Mechanism,
)
from apps.events import services as events

# §5.2.14's three link kinds, in the words the charity page offers them.
LINK_LABELS = {
    Link.Kind.WEBSITE_DONATE: "Donate",
    Link.Kind.WEBSITE_ABOUT: "About",
    Link.Kind.WEBSITE_CONTACT: "Contact",
}


def _rabbi_label(user_id: int, rabbis: dict, members: dict) -> str:
    """A rabbi's public identity, falling back to the account name."""
    identity = rabbis.get(user_id)
    return identity.label if identity else members.get(user_id, "A rabbi")


@dataclass(frozen=True)
class OrderKey:
    """How one sort mechanism becomes an ORDER BY.

    `column` is the annotated value the mechanism orders by. `tiebreak` follows
    the primary order and is never reversed, which is what makes a result set
    with equal values total and pageable. `nulls_last` marks a value where NULL
    means "none" rather than "low" (D-048).
    """

    column: str
    tiebreak: tuple[str, ...] = ("name", "pk")
    nulls_last: bool = False


def _search_condition(search: Search | None) -> Q | None:
    """§6.2.6's term as one condition, or None when nothing was typed.

    The term is matched against the columns `search.fields` names, OR-ed
    together, so a charity whose tagline matches is a match even when its name
    does not. An empty search is not a condition at all: the listing is then
    unfiltered, which is what the page shows before anything is typed.
    """
    if search is None or search.is_empty:
        return None
    condition = Q()
    for field in search.fields:
        condition |= Q(**{f"{field}__{search.lookup}": search.pattern})
    return condition


class CharityRepository(Protocol):
    """Read access to charities, in the terms the listing needs."""

    def page(
        self,
        offset: int,
        limit: int,
        filters: CharityFilters | None = None,
        sort: CharitySort = DEFAULT_SORT,
        search: Search | None = None,
    ) -> tuple[CharityCard, ...]:
        """Return cards for the given window of the filtered set, in the chosen order."""
        ...

    def count(self, filters: CharityFilters | None = None, search: Search | None = None) -> int:
        """Return how many charities the filters and the search keep."""
        ...

    def page_and_count(
        self,
        offset: int,
        limit: int,
        filters: CharityFilters | None = None,
        sort: CharitySort = DEFAULT_SORT,
        search: Search | None = None,
    ) -> tuple[tuple[CharityCard, ...], int]:
        """Return a page and the total it came from, read as one snapshot."""
        ...

    def detail(self, charity_id: int) -> CharityPage | None:
        """Return everything the charity page shows for one charity, or None."""
        ...

    def link_url(self, charity_id: int, link_id: int) -> str | None:
        """Return the outbound URL of one of a charity's links, or None."""
        ...


class DjangoCharityRepository:
    """Reads charities from the project database.

    D-038 makes `is_visible` the public visibility switch: the listing reads it
    and never touches the approvals tables. Nothing publishes a charity yet
    (the admin approval queue is still to come), so every row is hidden and a
    filtered listing would render empty. `published_only` is therefore off by
    default and the caller flips it when the queue starts publishing. See
    D-042.

    Filtering and ordering both happen here and only here: the repository turns
    the doc's groups (§6.2.4) and orders (§6.2.5) into one query, so the values
    the cards show, the filters compare and the sort reads are computed by the
    same annotations and cannot disagree (D-045, D-048).
    """

    # §6.2.5's mechanisms mapped to their ORDER BY. Every card shows the event
    # count and last-change date, so the page query always has those two
    # annotations; only trending adds a third (D-051).
    ORDER_KEYS: dict[Mechanism, OrderKey] = {
        ALPHABETICAL: OrderKey("name", tiebreak=("pk",)),
        TRENDING: OrderKey("trending_score"),
        POPULAR: OrderKey("event_count"),
        RATING: OrderKey("average_rating", nulls_last=True),
        HASKAMOS: OrderKey("approving_haskamas"),
        NEWEST: OrderKey("created"),
        UPDATED: OrderKey("last_changed"),
    }

    def __init__(self, *, published_only: bool = False) -> None:
        self.published_only = published_only

    def _rows(self) -> QuerySet[Charity]:
        """The charities the listing may show."""
        rows = Charity.objects.all()
        if self.published_only:
            rows = rows.filter(is_visible=True)
        return rows

    def _annotated(
        self, *, reviews: bool, approving: bool = False, disapproving: bool = False
    ) -> QuerySet[Charity]:
        """Rows annotated with the numbers the cards and the filters read.

        The counts are over all of a charity's rows, not just published ones:
        while D-042 lists unpublished charities, the filters treat them the same.
        A value is added only when a card shows it or a filter compares it, so
        the pagination count does not aggregate rows it never reads. A haskama
        count comes from a subquery, so it never multiplies the rows the review
        aggregate sees (D-045, D-048).
        """
        rows = self._rows()
        if reviews:
            rows = rows.annotate(
                review_count=Count("reviews"),
                average_rating=Avg("reviews__rating"),
            )
        if approving:
            rows = rows.annotate(approving_haskamas=self._haskama_count(Haskama.Verdict.APPROVE))
        if disapproving:
            rows = rows.annotate(
                disapproving_haskamas=self._haskama_count(Haskama.Verdict.DISAPPROVE)
            )
        return rows

    @staticmethod
    def _haskama_count(verdict: str) -> Expression:
        """How many of a charity's haskamas carry `verdict`, as a count expression.

        HASKAMA is this app's table, so the subquery is read here rather than
        through another app's services. Coalescing to 0 keeps "no haskamas" a
        countable zero instead of NULL, which no filter or order can compare.
        """
        return Coalesce(
            Subquery(
                Haskama.objects.filter(charity=OuterRef("pk"), verdict=verdict)
                .order_by()
                .values("charity")
                .annotate(total=Count("pk"))
                .values("total"),
                output_field=IntegerField(),
            ),
            Value(0),
            output_field=IntegerField(),
        )

    def page(
        self,
        offset: int,
        limit: int,
        filters: CharityFilters | None = None,
        sort: CharitySort = DEFAULT_SORT,
        search: Search | None = None,
    ) -> tuple[CharityCard, ...]:
        rows = self._narrowed(filters, sort=sort, search=search, reviews=True)
        rows = self._with_activity_values(rows, sort)
        rows = self._ordered(rows, sort)
        rows = rows.prefetch_related("domains", "locations")[offset : offset + limit]
        return tuple(self._to_card(row) for row in rows)

    def count(self, filters: CharityFilters | None = None, search: Search | None = None) -> int:
        return self._narrowed(filters, search=search).count()

    def link_url(self, charity_id: int, link_id: int) -> str | None:
        """The target of one of a charity's links, only if it is an http(s) URL.

        A link row written outside the form path could hold any scheme, so the
        redirect view asks for a safe target rather than trusting `URLField`.
        """
        url = (
            Link.objects.filter(charity_id=charity_id, pk=link_id)
            .values_list("url", flat=True)
            .first()
        )
        if url is None or urlsplit(url).scheme.lower() not in ("http", "https"):
            return None
        return url

    def detail(self, charity_id: int) -> CharityPage | None:
        """Everything §6.2.7's charity page shows for one charity, or None.

        The counts (reviews, haskamas, events) are the same annotations the
        listing uses, so the page and the card cannot disagree. Author and
        rabbi names come from accounts' services, never from its tables (D-006).
        """
        rows = self._annotated(reviews=True, approving=True, disapproving=True)
        if self.published_only:
            rows = rows.filter(is_visible=True)
        row = self._with_activity_values(rows, DEFAULT_SORT).filter(pk=charity_id).first()
        if row is None:
            return None
        reviews = tuple(row.reviews.order_by("-created", "-id"))
        haskamas = tuple(row.haskamas.order_by("-updated", "-id"))
        members = accounts.usernames(
            [review.author_id for review in reviews]
            + [haskama.rabbi_user_id for haskama in haskamas]
        )
        rabbis = accounts.rabbi_identities(haskama.rabbi_user_id for haskama in haskamas)
        return CharityPage(
            id=row.id,
            name=row.name,
            tagline=row.tagline,
            description=row.description,
            image=row.image,
            domains=tuple(DomainTag(name=domain.name) for domain in row.domains.all()),
            locations=tuple(
                LocationTag(name=loc.name, region=loc.region, country=loc.country)
                for loc in row.locations.all()
            ),
            links=tuple(
                CharityLink(
                    id=link.id,
                    kind=link.kind,
                    label=LINK_LABELS.get(link.kind, link.get_kind_display()),
                    url=link.url,
                )
                for link in row.links.order_by("kind")
            ),
            reviews=tuple(
                ReviewEntry(
                    # A deleted account leaves the review; it is shown as anonymous.
                    author=members.get(review.author_id, "A member"),
                    rating=review.rating,
                    body=review.body,
                    created=review.created,
                )
                for review in reviews
            ),
            review_summary=ReviewSummary(count=row.review_count, average=row.average_rating),
            haskamas=tuple(
                HaskamaEntry(
                    rabbi=_rabbi_label(haskama.rabbi_user_id, rabbis, members),
                    approving=haskama.verdict == Haskama.Verdict.APPROVE,
                    importance=haskama.importance,
                    body=haskama.body or "",
                    updated=haskama.updated,
                )
                for haskama in haskamas
            ),
            approving_haskamas=row.approving_haskamas,
            disapproving_haskamas=row.disapproving_haskamas,
            activity=ActivitySummary(
                events=row.event_count,
                approving_haskamas=row.approving_haskamas,
                last_changed=row.last_changed,
            ),
            is_visible=row.is_visible,
        )

    def page_and_count(
        self,
        offset: int,
        limit: int,
        filters: CharityFilters | None = None,
        sort: CharitySort = DEFAULT_SORT,
        search: Search | None = None,
    ) -> tuple[tuple[CharityCard, ...], int]:
        """Return a page and its total from one read, so both see one snapshot.

        The total is a window count over the same query, so a row written
        between the count and the page (which used to be two statements) cannot
        make a charity repeat on page 2 or be skipped entirely (audit B3). Only
        an out-of-range page, which returns no rows and so has no window to read
        the total from, falls back to a count.
        """
        rows = self._narrowed(filters, sort=sort, search=search, reviews=True)
        rows = self._with_activity_values(rows, sort)
        rows = self._ordered(rows.annotate(total=Window(Count("pk"))), sort)
        window = list(rows.prefetch_related("domains", "locations")[offset : offset + limit])
        if not window:
            # Past the end: the caller still needs the total to clamp the page.
            return (), self.count(filters, search=search)
        return tuple(self._to_card(row) for row in window), window[0].total

    def _narrowed(
        self,
        filters: CharityFilters | None,
        *,
        sort: CharitySort | None = None,
        search: Search | None = None,
        reviews: bool = False,
    ) -> QuerySet[Charity]:
        """Apply §6.2.4's groups and §6.2.6's search: OR inside a group, AND between them.

        A repeatable group is one EXISTS, not a join: a charity with three
        matching domains is still one row, so no DISTINCT is needed and the
        review count cannot be multiplied by a filter. A derived value is
        annotated only when a card, a filter or the chosen order reads it.
        """
        filters = filters or CharityFilters()
        needs_reviews = reviews or filters.min_rating is not None or filters.min_reviews is not None
        # A page passes `reviews=True`, and its cards all show the approving
        # count (D-051); the pagination count reads none of it.
        needs_approving = (
            reviews
            or (sort is not None and sort.mechanism == HASKAMOS)
            or filters.min_approving_haskamas is not None
        )
        rows = self._annotated(
            reviews=needs_reviews,
            approving=needs_approving,
            disapproving=filters.max_disapproving_haskamas is not None,
        )
        if filters.domains:
            rows = rows.filter(
                Exists(
                    CharityDomain.objects.filter(charity=OuterRef("pk"), domain__in=filters.domains)
                )
            )
        if filters.locations:
            rows = rows.filter(
                Exists(
                    CharityLocation.objects.filter(
                        charity=OuterRef("pk"), location__in=filters.locations
                    )
                )
            )
        if filters.haskama_rabbis:
            rows = rows.filter(
                Exists(
                    Haskama.objects.filter(
                        charity=OuterRef("pk"), rabbi_user__in=filters.haskama_rabbis
                    )
                )
            )
        if filters.min_rating is not None:
            # The scale is stars (D-045), and `from_query` has already clamped the
            # value into it, so this compares like with like. No reviews means no
            # average, and a charity with no average cannot clear a minimum rating.
            rows = rows.filter(review_count__gt=0, average_rating__gte=filters.min_rating)
        if filters.min_reviews is not None:
            rows = rows.filter(review_count__gte=filters.min_reviews)
        if filters.min_approving_haskamas is not None:
            rows = rows.filter(approving_haskamas__gte=filters.min_approving_haskamas)
        if filters.max_disapproving_haskamas is not None:
            rows = rows.filter(disapproving_haskamas__lte=filters.max_disapproving_haskamas)
        condition = _search_condition(search)
        if condition is not None:
            rows = rows.filter(condition)
        return rows

    @staticmethod
    def _with_activity_values(rows: QuerySet[Charity], sort: CharitySort) -> QuerySet[Charity]:
        """Annotate the EVENT-derived values the cards show and the chosen order reads.

        Every card shows the event count and last-change date (D-051), so those
        two are always added; trending is the only order that needs a third.
        The haskama count is not added here: `_narrowed` already knows it is
        needed for this page (or for a haskama filter or order), and reusing
        that one annotation keeps the query from counting the same rows twice.
        EVENT is another app's table, so these expressions come from its
        services.py; charities never imports the model (D-006).
        """
        rows = rows.annotate(
            event_count=events.event_count(OuterRef("pk")),
            last_changed=Coalesce(events.last_changed(OuterRef("pk")), F("created")),
        )
        if sort.mechanism == TRENDING:
            return rows.annotate(trending_score=events.trending_score(OuterRef("pk")))
        return rows

    @classmethod
    def _ordered(cls, rows: QuerySet[Charity], sort: CharitySort) -> QuerySet[Charity]:
        """Order by the chosen mechanism, then by §6.2.5's alphabetical tiebreak.

        The tiebreak is always A→Z, even when the primary order is descending;
        the id makes the order total, so paging cannot repeat or skip a row.
        A rating of `None` is no rating, not a low one, so those rows stay last
        in both directions (D-048).
        """
        key = cls.ORDER_KEYS[sort.mechanism]
        primary = F(key.column)
        # Django wants None, not False, when NULLS LAST is not requested.
        nulls_last = True if key.nulls_last else None
        ordered = (
            primary.desc(nulls_last=nulls_last)
            if sort.descending
            else primary.asc(nulls_last=nulls_last)
        )
        return rows.order_by(ordered, *key.tiebreak)

    @staticmethod
    def _to_card(row: Charity) -> CharityCard:
        return CharityCard(
            id=row.id,
            name=row.name,
            tagline=row.tagline,
            image=row.image,
            domains=tuple(DomainTag(name=d.name) for d in row.domains.all()),
            locations=tuple(
                LocationTag(name=loc.name, region=loc.region, country=loc.country)
                for loc in row.locations.all()
            ),
            reviews=ReviewSummary(count=row.review_count, average=row.average_rating),
            activity=ActivitySummary(
                events=row.event_count,
                approving_haskamas=row.approving_haskamas,
                last_changed=row.last_changed,
            ),
        )


class FilterOptionsRepository(Protocol):
    """The sidebar's option lists, as the page-building code sees them.

    The listing never touches Domain and Location rows directly; it asks for
    their options. This protocol is what the services accept (S5), so a page
    that only reads options can be served anything that provides them — a
    cache, a read replica, or, as here, the shared list tables.
    """

    def domains(self) -> tuple[DomainOption, ...]:
        """Every domain, in the order the sidebar offers them."""
        ...

    def locations(self) -> tuple[LocationOption, ...]:
        """Every location, in the order the sidebar offers them."""
        ...

    def rabbis(self) -> tuple[RabbiOption, ...]:
        """Every rabbi the filters can select, in the order the sidebar offers them."""
        ...


class DjangoFilterOptionsRepository:
    """The sidebar's choices: the domains, locations and rabbis one can filter by.

    Options come from the shared lists rather than from the charities currently
    matching, so ticking one option cannot make the others disappear under the
    user's cursor. Domains and locations that no charity uses are still offered,
    because the domain and location lists are managed on their own (§5.2.10–11).

    The domain and location lists are cached for a minute (audit P1): on a real
    directory they run to thousands of rows and were being read in full on every
    listing request. A minute is short enough that a new domain or location
    appears while the admin is working, and long enough that a busy page stops
    paying for it per request. Rabbis, being people, are never cached.
    """

    # How long an option list stays fresh. Short: options change rarely and the
    # cost of staleness is a checkbox appearing a minute late.
    OPTIONS_TTL = 60

    def _cached_options(self, key: str, load) -> tuple:
        options = cache.get(key)
        if options is None:
            options = tuple(load())
            cache.set(key, options, self.OPTIONS_TTL)
        return options

    def domains(self) -> tuple[DomainOption, ...]:
        return self._cached_options(
            "filter-options:domains",
            lambda: (
                DomainOption(id=row.id, name=row.name) for row in Domain.objects.order_by("name")
            ),
        )

    def locations(self) -> tuple[LocationOption, ...]:
        return self._cached_options(
            "filter-options:locations",
            lambda: (
                LocationOption(id=row.id, name=row.name, region=row.region, country=row.country)
                for row in Location.objects.order_by("name", "region", "country")
            ),
        )

    def rabbis(self) -> tuple[RabbiOption, ...]:
        """The rabbis the Haskamos group offers (§6.2.4, D-045).

        A rabbi's public identity lives in accounts (§6.1), so this asks its
        service rather than reading RABBI_PROFILE. The ids are user ids, which
        is what HASKAMA stores and the filter compares (audit Q3).
        """
        return tuple(
            RabbiOption(id=rabbi.user_id, display_name=rabbi.display_name, title=rabbi.title)
            for rabbi in accounts.search_rabbis()
        )
