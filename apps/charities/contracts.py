"""Read models for the charity listing.

These are plain values, deliberately free of any database or ORM behaviour, so
that the listing logic and the templates cannot depend on how the rows were
fetched.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class DomainTag:
    name: str


@dataclass(frozen=True)
class LocationTag:
    """A location as it is shown: name alone is not unique (D-032, D-045)."""

    name: str
    region: str
    country: str

    @property
    def label(self) -> str:
        """The full identity, identical to what the filter offers as one choice."""
        return f"{self.name}, {self.region}, {self.country}"


@dataclass(frozen=True)
class ReviewSummary:
    """A charity's reviews, as the listing shows them (§5.2.15, §5.3).

    `average` is None when there are no reviews, so a card with no reviews
    cannot be mistaken for one rated 0. §5.3 derives both values from REVIEW
    rows; nothing is stored.
    """

    count: int
    average: float | None


@dataclass(frozen=True)
class ActivitySummary:
    """The activity values the card shows, and four sort orders read (D-051).

    `last_changed` falls back to CHARITY.created, so it is always a date: a
    charity no one has edited yet was last changed when it was added.
    """

    events: int
    approving_haskamas: int
    last_changed: datetime


@dataclass(frozen=True)
class CharityCard:
    """What the listing shows for one charity."""

    id: int
    name: str
    tagline: str
    image: str
    domains: tuple[DomainTag, ...]
    locations: tuple[LocationTag, ...]
    reviews: ReviewSummary
    activity: ActivitySummary


@dataclass(frozen=True)
class DomainOption:
    """One choice in the Domain filter group (§6.2.4)."""

    id: int
    name: str


@dataclass(frozen=True)
class LocationOption:
    """One choice in the Location filter group, labelled by its full identity (D-045)."""

    id: int
    name: str
    region: str
    country: str

    @property
    def label(self) -> str:
        return f"{self.name}, {self.region}, {self.country}"


@dataclass(frozen=True)
class RabbiOption:
    """One choice in the Haskamos filter group, a rabbi's public identity (§6.2.4, D-045).

    `id` is the **user** id, not the profile's: HASKAMA stores `rabbi_user`,
    which is what the filter compares against. The two parts of the identity
    come from RABBI_PROFILE (§5.2.3); `title` is optional there, so the label
    has to cope with its absence.
    """

    id: int
    display_name: str
    title: str | None

    @property
    def label(self) -> str:
        return f"{self.title} {self.display_name}" if self.title else self.display_name


@dataclass(frozen=True)
class CharityLink:
    """One of a charity's outbound links (§5.2.14), with the label the page shows."""

    id: int
    kind: str
    label: str
    url: str


@dataclass(frozen=True)
class ReviewEntry:
    """One review as the charity page shows it (§5.2.15)."""

    author: str
    rating: int
    body: str
    created: datetime


@dataclass(frozen=True)
class HaskamaEntry:
    """One rabbi's endorsement as the charity page shows it (§5.2.16)."""

    rabbi: str
    approving: bool
    importance: int | None
    body: str
    updated: datetime


@dataclass(frozen=True)
class CharityPage:
    """Everything §6.2.7's charity page shows, read in one place.

    ``image`` is the stored value (a path or an allowed URL), never a rendered
    `src`; the template turns it into one through `image_src` (D-056).
    """

    id: int
    name: str
    tagline: str | None
    description: str | None
    image: str | None
    domains: tuple[DomainTag, ...]
    locations: tuple[LocationTag, ...]
    links: tuple[CharityLink, ...]
    reviews: tuple[ReviewEntry, ...]
    review_summary: ReviewSummary
    haskamas: tuple[HaskamaEntry, ...]
    approving_haskamas: int
    disapproving_haskamas: int
    activity: ActivitySummary
    is_visible: bool
