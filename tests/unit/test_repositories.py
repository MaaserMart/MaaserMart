"""Tests for the Postgres-backed repository.

These need a database, unlike the rule tests, because the thing under test is
the mapping between rows and cards.
"""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.charities.contracts import CharityCard, ReviewSummary
from apps.charities.filters import CharityFilters
from apps.charities.models import Charity, Domain, Haskama, Location, Review
from apps.charities.repositories import DjangoCharityRepository
from apps.events.models import Event
from tests.factories.accounts import UserFactory


class DjangoCharityRepositoryTest(TestCase):
    def setUp(self) -> None:
        self.repository = DjangoCharityRepository()
        self.no_filters = CharityFilters()

    def test_returns_cards_in_name_order(self) -> None:
        for name in ["Zohar Fund", "Adas Chessed", "Mercaz Tzedaka"]:
            Charity.objects.create(name=name)

        cards = self.repository.page(filters=self.no_filters, offset=0, limit=10)

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

        card = self.repository.page(filters=self.no_filters, offset=0, limit=1)[0]

        self.assertEqual(card.name, "Keren L'Dugma")
        self.assertEqual(card.tagline, "Interest-free loans.")
        self.assertEqual(card.image, "a.svg")
        self.assertEqual([d.name for d in card.domains], ["Free loans"])
        self.assertEqual([loc.label for loc in card.locations], ["Lakewood, NJ, USA"])

    def test_window_skips_preceding_rows(self) -> None:
        for index in range(1, 6):
            Charity.objects.create(name=f"Charity {index:02d}")

        cards = self.repository.page(filters=self.no_filters, offset=2, limit=2)

        self.assertEqual([card.name for card in cards], ["Charity 03", "Charity 04"])

    def test_count_matches_rows(self) -> None:
        Charity.objects.create(name="Adas Chessed")

        self.assertEqual(self.repository.count(self.no_filters), 1)

    def test_card_does_not_leak_model_behaviour(self) -> None:
        Charity.objects.create(name="Adas Chessed")

        card = self.repository.page(filters=self.no_filters, offset=0, limit=1)[0]

        self.assertFalse(hasattr(card, "save"))
        self.assertFalse(hasattr(card, "objects"))

    def test_loads_relations_without_extra_queries(self) -> None:
        domain = Domain.objects.create(name="Free loans")
        location = Location.objects.create(name="Lakewood", region="NJ", country="USA")
        charity = Charity.objects.create(name="Keren L'Dugma")
        charity.domains.add(domain)
        charity.locations.add(location)

        with self.assertNumQueries(3):  # page, domains, locations
            cards = self.repository.page(filters=self.no_filters, offset=0, limit=10)

        self.assertEqual(cards[0].domains[0].name, "Free loans")

    def test_maps_review_average_and_count(self) -> None:
        """§5.3: the average rating is derived from the reviews, not stored."""
        charity = Charity.objects.create(name="Keren L'Dugma")
        for rating in (2, 4, 5):
            # One review per member per charity (D-055), so each rating has its own author.
            Review.objects.create(charity=charity, author=UserFactory(), rating=rating)

        card = self.repository.page(filters=self.no_filters, offset=0, limit=1)[0]

        self.assertEqual(card.reviews.count, 3)
        self.assertAlmostEqual(card.reviews.average, 11 / 3)

    def test_charity_without_reviews_has_no_average(self) -> None:
        Charity.objects.create(name="Keren L'Dugma")

        card = self.repository.page(filters=self.no_filters, offset=0, limit=1)[0]

        self.assertEqual(card.reviews, ReviewSummary(count=0, average=None))

    def test_maps_activity_values(self) -> None:
        """D-051: every card carries the counts and date the activity orders read."""
        charity = Charity.objects.create(name="Keren L'Dugma")
        for _ in range(2):
            Event.objects.create(charity=charity, action=Event.Action.VIEW)
        Haskama.objects.create(
            rabbi_user=UserFactory(), charity=charity, verdict=Haskama.Verdict.APPROVE
        )
        Haskama.objects.create(
            rabbi_user=UserFactory(), charity=charity, verdict=Haskama.Verdict.DISAPPROVE
        )

        card = self.repository.page(filters=self.no_filters, offset=0, limit=1)[0]

        self.assertEqual(card.activity.events, 2)
        self.assertEqual(card.activity.approving_haskamas, 1)
        # No charity_updated event yet, so the charity's own creation is its last change.
        self.assertEqual(card.activity.last_changed, charity.created)

    def test_last_changed_is_the_latest_charity_update(self) -> None:
        charity = Charity.objects.create(name="Keren L'Dugma")
        event = Event.objects.create(charity=charity, action=Event.Action.CHARITY_UPDATED)
        stamp = timezone.now() + timedelta(days=1)
        Event.objects.filter(pk=event.pk).update(created=stamp)

        card = self.repository.page(filters=self.no_filters, offset=0, limit=1)[0]

        self.assertEqual(card.activity.last_changed, stamp)

    def test_reviews_do_not_add_queries_per_charity(self) -> None:
        author = UserFactory()
        for index in range(1, 4):
            charity = Charity.objects.create(name=f"Charity {index:02d}")
            Review.objects.create(charity=charity, author=author, rating=5)

        with self.assertNumQueries(3):  # page and the two prefetches
            self.repository.page(filters=self.no_filters, offset=0, limit=10)


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

        self.assertEqual(
            [c.name for c in repository.page(0, 10, CharityFilters())],
            ["Hidden One", "Visible One"],
        )
        self.assertEqual(repository.count(CharityFilters()), 2)

    def test_published_only_hides_unpublished_charities(self) -> None:
        """D-038: once publishing exists, only visible charities are listed."""
        repository = DjangoCharityRepository(published_only=True)

        self.assertEqual(
            [c.name for c in repository.page(0, 10, CharityFilters())], ["Visible One"]
        )
        self.assertEqual(repository.count(CharityFilters()), 1)


class PageAndCountTest(TestCase):
    """The page and its total come from one read, so they see one snapshot (audit B3)."""

    def setUp(self) -> None:
        self.repository = DjangoCharityRepository()
        for index in range(1, 31):
            Charity.objects.create(name=f"Charity {index:02d}")

    def test_reports_the_page_and_its_total(self) -> None:
        cards, total = self.repository.page_and_count(offset=10, limit=10)

        self.assertEqual(total, 30)
        self.assertEqual([card.name for card in cards][0], "Charity 11")
        self.assertEqual(len(cards), 10)

    def test_the_page_costs_one_query_plus_the_prefetches(self) -> None:
        with self.assertNumQueries(3):  # page, domains, locations
            self.repository.page_and_count(offset=0, limit=10)

    def test_a_window_past_the_end_still_reports_the_total(self) -> None:
        cards, total = self.repository.page_and_count(offset=500, limit=10)

        self.assertEqual(cards, ())
        self.assertEqual(total, 30)
