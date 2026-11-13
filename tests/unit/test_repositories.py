"""Tests for the Postgres-backed repository.

These need a database, unlike the rule tests, because the thing under test is
the mapping between rows and cards.
"""

from django.test import TestCase

from apps.charities.contracts import CharityCard
from apps.charities.models import Charity, Domain, Location
from apps.charities.repositories import DjangoCharityRepository


class DjangoCharityRepositoryTest(TestCase):
    def setUp(self) -> None:
        self.repository = DjangoCharityRepository()

    def test_returns_cards_in_name_order(self) -> None:
        for name in ["Zohar Fund", "Adas Chessed", "Mercaz Tzedaka"]:
            Charity.objects.create(name=name)

        cards = self.repository.page(offset=0, limit=10)

        self.assertEqual(
            [card.name for card in cards],
            ["Adas Chessed", "Mercaz Tzedaka", "Zohar Fund"],
        )
        self.assertIsInstance(cards[0], CharityCard)

    def test_maps_domains_and_locations(self) -> None:
        domain = Domain.objects.create(name="Free loans")
        location = Location.objects.create(name="Lakewood", region="NJ", country="USA")
        charity = Charity.objects.create(
            name="Keren L'Dugma", tagline="Interest-free loans.", image="a.svg"
        )
        charity.domains.add(domain)
        charity.locations.add(location)

        card = self.repository.page(offset=0, limit=1)[0]

        self.assertEqual(card.name, "Keren L'Dugma")
        self.assertEqual(card.tagline, "Interest-free loans.")
        self.assertEqual(card.image, "a.svg")
        self.assertEqual([d.name for d in card.domains], ["Free loans"])
        self.assertEqual([loc.name for loc in card.locations], ["Lakewood"])

    def test_window_skips_preceding_rows(self) -> None:
        for index in range(1, 6):
            Charity.objects.create(name=f"Charity {index:02d}")

        cards = self.repository.page(offset=2, limit=2)

        self.assertEqual([card.name for card in cards], ["Charity 03", "Charity 04"])

    def test_count_matches_rows(self) -> None:
        Charity.objects.create(name="Adas Chessed")

        self.assertEqual(self.repository.count(), 1)

    def test_card_does_not_leak_model_behaviour(self) -> None:
        Charity.objects.create(name="Adas Chessed")

        card = self.repository.page(offset=0, limit=1)[0]

        self.assertFalse(hasattr(card, "save"))
        self.assertFalse(hasattr(card, "objects"))

    def test_loads_relations_without_extra_queries(self) -> None:
        domain = Domain.objects.create(name="Free loans")
        location = Location.objects.create(name="Lakewood", region="NJ", country="USA")
        charity = Charity.objects.create(name="Keren L'Dugma")
        charity.domains.add(domain)
        charity.locations.add(location)

        with self.assertNumQueries(3):  # page, domains, locations
            cards = self.repository.page(offset=0, limit=10)

        self.assertEqual(cards[0].domains[0].name, "Free loans")


class PublishedOnlyTest(TestCase):
    """D-038 and D-042: `published_only` selects whether `is_visible` is read."""

    def setUp(self) -> None:
        Charity.objects.create(name="Hidden One")
        visible = Charity.objects.create(name="Visible One")
        visible.is_visible = True
        visible.save(update_fields=["is_visible"])

    def test_default_shows_every_charity(self) -> None:
        """D-042: with nothing publishing yet, the listing is not empty."""
        repository = DjangoCharityRepository()

        self.assertEqual([c.name for c in repository.page(0, 10)], ["Hidden One", "Visible One"])
        self.assertEqual(repository.count(), 2)

    def test_published_only_hides_unpublished_charities(self) -> None:
        """D-038: once publishing exists, only visible charities are listed."""
        repository = DjangoCharityRepository(published_only=True)

        self.assertEqual([c.name for c in repository.page(0, 10)], ["Visible One"])
        self.assertEqual(repository.count(), 1)
