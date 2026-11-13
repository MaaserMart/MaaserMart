"""Data access for the charity listing.

`CharityRepository` is the interface the rest of the app depends on.
`DjangoCharityRepository` is the single implementation that talks to Postgres.
Swapping the store later means adding an implementation, not editing callers.
"""

from __future__ import annotations

from typing import Protocol

from django.db.models import Avg, Count, Q, QuerySet

from apps.charities.contracts import (
    CharityCard,
    DomainOption,
    DomainTag,
    LocationOption,
    LocationTag,
    RabbiOption,
    ReviewSummary,
)
from apps.charities.filters import (
    MAX_STAR_RATING,
    MIN_STAR_RATING,
    CharityFilters,
)
from apps.charities.models import Charity, Domain, Haskama, Location


class CharityRepository(Protocol):
    """Read access to charities, in the terms the listing needs."""

    def page(self, offset: int, limit: int, filters: CharityFilters) -> tuple[CharityCard, ...]:
        """Return cards for the given window of the filtered set, ordered by name."""
        ...

    def count(self, filters: CharityFilters) -> int:
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

    Filtering happens here and only here: the repository turns the doc's groups
    (§6.2.4) into one query, so the counts on a card and the values the filters
    compare are computed by the same annotations and cannot disagree (D-045).
    """

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

    def page(self, offset: int, limit: int, filters: CharityFilters) -> tuple[CharityCard, ...]:
        rows = (
            self._narrowed(filters)
            .prefetch_related("domains", "locations")
            .order_by("name")[offset : offset + limit]
        )
        return tuple(self._to_card(row) for row in rows)

    def count(self, filters: CharityFilters) -> int:
        return self._narrowed(filters).count()

    def _narrowed(self, filters: CharityFilters) -> QuerySet[Charity]:
        """Apply §6.2.4's groups: OR inside a group, AND between groups."""
        rows = self._counted()
        if filters.domains:
            rows = rows.filter(domains__in=filters.domains)
        if filters.locations:
            rows = rows.filter(locations__in=filters.locations)
        if filters.haskama_rabbis:
            rows = rows.filter(haskamas__rabbi_user__in=filters.haskama_rabbis)
        if filters.min_rating is not None and (
            MIN_STAR_RATING <= filters.min_rating <= MAX_STAR_RATING
        ):
            # The scale is stars (D-045). No reviews means no average, and a
            # charity with no average cannot clear a minimum rating. A value off
            # the scale is not saturating: it is unusable, so it filters nothing,
            # like every other unusable value the URL parser lets through.
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
