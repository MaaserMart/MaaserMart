"""Data access for the charity listing.

`CharityRepository` is the interface the rest of the app depends on.
`DjangoCharityRepository` is the single implementation that talks to Postgres.
Swapping the store later means adding an implementation, not editing callers.
"""

from __future__ import annotations

from typing import Protocol

from django.db.models import Avg, Count, F, OuterRef, Q, QuerySet
from django.db.models.functions import Coalesce

from apps.charities.contracts import (
    CharityCard,
    DomainOption,
    DomainTag,
    LocationOption,
    LocationTag,
    RabbiOption,
    ReviewSummary,
)
from apps.charities.filters import CharityFilters
from apps.charities.models import Charity, Domain, Haskama, Location
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


class CharityRepository(Protocol):
    """Read access to charities, in the terms the listing needs."""

    def page(
        self,
        offset: int,
        limit: int,
        filters: CharityFilters | None = None,
        sort: CharitySort = DEFAULT_SORT,
    ) -> tuple[CharityCard, ...]:
        """Return cards for the given window of the filtered set, in the chosen order."""
        ...

    def count(self, filters: CharityFilters | None = None) -> int:
        """Return how many charities the filters keep."""
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

    # §6.2.5's mechanisms, and the annotated column each one orders by. The
    # event annotations are added only when their mechanism is chosen, so a
    # plain listing page pays for no activity subquery (D-048).
    ORDER_COLUMNS: dict[Mechanism, str] = {
        ALPHABETICAL: "name",
        TRENDING: "trending_score",
        POPULAR: "event_count",
        RATING: "average_rating",
        HASKAMOS: "approving_haskamas",
        NEWEST: "created",
        UPDATED: "last_changed",
    }

    def __init__(self, *, published_only: bool = False) -> None:
        self.published_only = published_only

    def _rows(self) -> QuerySet[Charity]:
        """The charities the listing may show."""
        rows = Charity.objects.all()
        if self.published_only:
            rows = rows.filter(is_visible=True)
        return rows

    def _counted(self) -> QuerySet[Charity]:
        """Rows annotated with the review and haskama numbers the filters read.

        The counts are over all of a charity's rows, not just published ones:
        while D-042 lists unpublished charities, the filters treat them the same.
        The distinct counts keep one review or haskama from being counted once
        per row a joining filter adds (D-045).
        """
        return self._rows().annotate(
            review_count=Count("reviews", distinct=True),
            average_rating=Avg("reviews__rating"),
            approving_haskamas=Count(
                "haskamas", filter=Q(haskamas__verdict=Haskama.Verdict.APPROVE), distinct=True
            ),
            disapproving_haskamas=Count(
                "haskamas", filter=Q(haskamas__verdict=Haskama.Verdict.DISAPPROVE), distinct=True
            ),
        )

    def page(
        self,
        offset: int,
        limit: int,
        filters: CharityFilters | None = None,
        sort: CharitySort = DEFAULT_SORT,
    ) -> tuple[CharityCard, ...]:
        rows = self._ordered(self._with_sort_values(self._narrowed(filters), sort), sort)
        rows = rows.prefetch_related("domains", "locations")[offset : offset + limit]
        return tuple(self._to_card(row) for row in rows)

    def count(self, filters: CharityFilters | None = None) -> int:
        return self._narrowed(filters).count()

    def _narrowed(self, filters: CharityFilters | None) -> QuerySet[Charity]:
        """Apply §6.2.4's groups: OR inside a group, AND between groups."""
        filters = filters or CharityFilters()
        rows = self._counted()
        if filters.domains:
            rows = rows.filter(domains__in=filters.domains)
        if filters.locations:
            rows = rows.filter(locations__in=filters.locations)
        if filters.haskama_rabbis:
            rows = rows.filter(haskamas__rabbi_user__in=filters.haskama_rabbis)
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
        return rows.distinct() if self._joins_rows(filters) else rows

    @staticmethod
    def _joins_rows(filters: CharityFilters) -> bool:
        """True when a filter multiplies rows, so DISTINCT is needed to count charities."""
        return bool(filters.domains or filters.locations or filters.haskama_rabbis)

    @staticmethod
    def _with_sort_values(rows: QuerySet[Charity], sort: CharitySort) -> QuerySet[Charity]:
        """Annotate the activity value the chosen order reads, if it has one.

        The haskama count is already on the rows because the sidebar filters by
        it, so the sort reuses that annotation rather than joining HASKAMA a
        second time. EVENT is another app's table, so those expressions come
        from its services.py; charities never imports the model (D-006).
        """
        if sort.mechanism == POPULAR:
            return rows.annotate(event_count=events.event_count(OuterRef("pk")))
        if sort.mechanism == TRENDING:
            return rows.annotate(trending_score=events.trending_score(OuterRef("pk")))
        if sort.mechanism == UPDATED:
            return rows.annotate(
                last_changed=Coalesce(events.last_changed(OuterRef("pk")), F("created"))
            )
        return rows

    @classmethod
    def _ordered(cls, rows: QuerySet[Charity], sort: CharitySort) -> QuerySet[Charity]:
        """Order by the chosen mechanism, then by §6.2.5's alphabetical tiebreak.

        The tiebreak is always A→Z, even when the primary order is descending;
        the id makes the order total, so paging cannot repeat or skip a row.
        A rating of `None` is no rating, not a low one, so those rows stay last
        in both directions (D-048).
        """
        column = cls.ORDER_COLUMNS[sort.mechanism]
        if column == "name":
            primary = F("name").desc() if sort.descending else F("name").asc()
            return rows.order_by(primary, "pk")
        if column == "average_rating":
            primary = (
                F(column).desc(nulls_last=True)
                if sort.descending
                else F(column).asc(nulls_last=True)
            )
            return rows.order_by(primary, "name", "pk")
        primary = F(column).desc() if sort.descending else F(column).asc()
        return rows.order_by(primary, "name", "pk")

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
        )


class DjangoFilterOptionsRepository:
    """The sidebar's choices: the domains, locations and rabbis one can filter by.

    Options come from the shared lists rather than from the charities currently
    matching, so ticking one option cannot make the others disappear under the
    user's cursor. Domains and locations that no charity uses are still offered,
    because the domain and location lists are managed on their own (§5.2.10–11).
    """

    def domains(self) -> tuple[DomainOption, ...]:
        return tuple(
            DomainOption(id=row.id, name=row.name) for row in Domain.objects.order_by("name")
        )

    def locations(self) -> tuple[LocationOption, ...]:
        rows = Location.objects.order_by("name", "region", "country")
        return tuple(
            LocationOption(id=row.id, name=row.name, region=row.region, country=row.country)
            for row in rows
        )

    def rabbis(self) -> tuple[RabbiOption, ...]:
        """Empty for now: the rabbi list belongs to accounts (§6.1, D-045).

        `HASKAMA` is read in its real shape, but a rabbi's public identity comes
        from `accounts.services.search_rabbis`, which does not exist yet. When it
        lands, this method returns its results and no other code changes.
        """
        return ()
