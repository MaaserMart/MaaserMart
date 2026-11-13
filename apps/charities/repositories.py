"""Data access for the charity listing.

`CharityRepository` is the interface the rest of the app depends on.
`DjangoCharityRepository` is the single implementation that talks to Postgres.
Swapping the store later means adding an implementation, not editing callers.
"""

from __future__ import annotations

from typing import Protocol

from django.db.models import QuerySet

from apps.charities.contracts import CharityCard, DomainTag, LocationTag
from apps.charities.models import Charity


class CharityRepository(Protocol):
    """Read access to charities, in the terms the listing needs."""

    def page(self, offset: int, limit: int) -> tuple[CharityCard, ...]:
        """Return cards for the given window, ordered by name."""
        ...

    def count(self) -> int:
        """Return the total number of charities."""
        ...


class DjangoCharityRepository:
    """Reads charities from the project database.

    D-038 makes `is_visible` the public visibility switch: the listing reads it
    and never touches the approvals tables. Nothing publishes a charity yet
    (the admin approval queue is still to come), so every row is hidden and a
    filtered listing would render empty. `published_only` is therefore off by
    default and the caller flips it when the queue starts publishing. See
    D-042.
    """

    def __init__(self, *, published_only: bool = False) -> None:
        self.published_only = published_only

    def _rows(self) -> QuerySet[Charity]:
        """The charities the listing may show."""
        rows = Charity.objects.all()
        if self.published_only:
            rows = rows.filter(is_visible=True)
        return rows

    def page(self, offset: int, limit: int) -> tuple[CharityCard, ...]:
        rows = (
            self._rows()
            .prefetch_related("domains", "locations")
            .order_by("name")[offset : offset + limit]
        )
        return tuple(self._to_card(row) for row in rows)

    def count(self) -> int:
        return self._rows().count()

    @staticmethod
    def _to_card(row: Charity) -> CharityCard:
        return CharityCard(
            id=row.id,
            name=row.name,
            tagline=row.tagline,
            image=row.image,
            domains=tuple(DomainTag(name=d.name) for d in row.domains.all()),
            locations=tuple(LocationTag(name=loc.name) for loc in row.locations.all()),
        )
