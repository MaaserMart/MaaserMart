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
class CharityCard:
    """What the listing shows for one charity."""

    id: int
    name: str
    tagline: str
    image: str
    domains: tuple[DomainTag, ...]
    locations: tuple[LocationTag, ...]
