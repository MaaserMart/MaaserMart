"""Read models for the charity listing.

These are plain values, deliberately free of any database or ORM behaviour, so
that the listing logic and the templates cannot depend on how the rows were
fetched.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DomainTag:
    name: str


@dataclass(frozen=True)
class LocationTag:
    name: str


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
class CharityCard:
    """What the listing shows for one charity."""

    id: int
    name: str
    tagline: str
    image: str
    domains: tuple[DomainTag, ...]
    locations: tuple[LocationTag, ...]
    reviews: ReviewSummary
