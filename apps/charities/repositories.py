"""Data access for the charity listing.

`CharityRepository` is the interface the rest of the app depends on.
`DjangoCharityRepository` is the single implementation that talks to Postgres.
Swapping the store later means adding an implementation, not editing callers.
"""

from __future__ import annotations

from typing import Protocol

from django.db.models import Avg, Count, F, OuterRef, Q, QuerySet
from django.db.models.functions import Coalesce

from apps.charities.contracts import CharityCard, DomainTag, LocationTag, ReviewSummary
from apps.charities.models import Charity, Haskama
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
        self, offset: int, limit: int, sort: CharitySort = DEFAULT_SORT
    ) -> tuple[CharityCard, ...]:
        """Return cards for the given window of the set, in the chosen order."""
        ...

    def count(self) -> int:
        """Return the total number of charities."""
        ...


class DjangoCharityRepository:
    """Reads charities from the project database.

    D-038 makes `is_visible` the public visibility switch: the listing reads it
    and never touches the approvals tables. Nothing publishes a charity yet
    (the admin approval queue is still to come), so every row is hidden and the
    listing would render empty. `published_only` is therefore off by default and
    the caller flips it when the queue starts publishing. See D-042.
    """

    # §6.2.5's mechanisms, and the annotated column each one orders by. The
    # annotation is added only when its mechanism is chosen, so a plain listing
    # page pays for no activity subquery (D-048).
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

    def _annotated(self, sort: CharitySort) -> QuerySet[Charity]:
        """Rows annotated with the numbers the cards show and the chosen sort reads.

        Review counts are distinct because the haskama sort joins a second
        collection; without it each review would be counted once per haskama.
        """
        rows = self._rows().annotate(
            review_count=Count("reviews", distinct=True),
            average_rating=Avg("reviews__rating"),
        )
        if sort.mechanism == HASKAMOS:
            rows = rows.annotate(
                approving_haskamas=Count(
                    "haskamas",
                    filter=Q(haskamas__verdict=Haskama.Verdict.APPROVE),
                    distinct=True,
                )
            )
        # EVENT is another app's table, so these expressions come from its
        # services.py; charities never imports the model (D-006).
        if sort.mechanism == POPULAR:
            rows = rows.annotate(event_count=events.event_count(OuterRef("pk")))
        if sort.mechanism == TRENDING:
            rows = rows.annotate(trending_score=events.trending_score(OuterRef("pk")))
        if sort.mechanism == UPDATED:
            rows = rows.annotate(
                last_changed=Coalesce(events.last_changed(OuterRef("pk")), F("created"))
            )
        return rows

    def page(
        self, offset: int, limit: int, sort: CharitySort = DEFAULT_SORT
    ) -> tuple[CharityCard, ...]:
        rows = self._ordered(self._annotated(sort), sort).prefetch_related("domains", "locations")[
            offset : offset + limit
        ]
        return tuple(self._to_card(row) for row in rows)

    def count(self) -> int:
        return self._rows().count()

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
            locations=tuple(LocationTag(name=loc.name) for loc in row.locations.all()),
            reviews=ReviewSummary(count=row.review_count, average=row.average_rating),
        )
