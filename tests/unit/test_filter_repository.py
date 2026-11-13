"""The §6.2.4 filter groups, applied to real rows by DjangoCharityRepository.

These live against Postgres because the thing under test is how the filters
become one query — the OR within a group, the AND between groups, and the counts
a card shows next to the numbers a filter compares.
"""

from django.http import QueryDict
from django.test import TestCase

from apps.charities.filters import CharityFilters, from_query
from apps.charities.models import Charity, Domain, Haskama, Location, Review
from apps.charities.repositories import DjangoCharityRepository
from tests.factories.accounts import UserFactory


class DomainFilterTest(TestCase):
    def setUp(self) -> None:
        self.a = Charity.objects.create(name="Alpha")
        self.b = Charity.objects.create(name="Beta")
        self.general = Domain.objects.create(name="General")
        self.food = Domain.objects.create(name="Food Security")
        self.a.domains.add(self.general, self.food)
        self.b.domains.add(self.general)

    def test_a_domain_selects_charities_in_it(self) -> None:
        cards = self._page(CharityFilters(domains=(self.food.id,)))

        self.assertEqual([card.name for card in cards], ["Alpha"])

    def test_domains_are_or(self) -> None:
        """Two domains together match a charity in either one (§6.2.4)."""
        cards = self._page(CharityFilters(domains=(self.food.id, self.b.domains.first().id)))

        self.assertEqual({card.name for card in cards}, {"Alpha", "Beta"})

    def test_two_domains_on_one_charity_count_once(self) -> None:
        cards = self._page(CharityFilters(domains=(self.general.id, self.food.id)))

        self.assertEqual([card.name for card in cards], ["Alpha", "Beta"])
        self.assertEqual(
            DjangoCharityRepository().count(
                CharityFilters(domains=(self.general.id, self.food.id))
            ),
            2,
        )

    def _page(self, filters):
        return DjangoCharityRepository().page(0, 10, filters)


class LocationFilterTest(TestCase):
    def test_a_location_selects_and_is_distinct(self) -> None:
        charity = Charity.objects.create(name="Alpha")
        first = Location.objects.create(name="Lakewood", region="NJ", country="USA")
        second = Location.objects.create(name="Monsey", region="NY", country="USA")
        charity.locations.add(first, second)

        cards = DjangoCharityRepository().page(0, 10, CharityFilters(locations=(first.id,)))

        self.assertEqual([card.name for card in cards], ["Alpha"])

    def test_locations_are_or(self) -> None:
        charity = Charity.objects.create(name="Alpha")
        first = Location.objects.create(name="Lakewood", region="NJ", country="USA")
        second = Location.objects.create(name="Monsey", region="NY", country="USA")
        charity.locations.add(first, second)

        cards = DjangoCharityRepository().page(0, 10, CharityFilters(locations=(second.id,)))

        self.assertEqual([card.name for card in cards], ["Alpha"])


class HaskamaRabbiFilterTest(TestCase):
    def test_a_rabbi_selects_charities_they_endorsed(self) -> None:
        charity = Charity.objects.create(name="Alpha")
        other = Charity.objects.create(name="Beta")
        rabbi = UserFactory()
        other_rabbi = UserFactory()
        Haskama.objects.create(rabbi_user=rabbi, charity=charity, verdict=Haskama.Verdict.APPROVE)
        Haskama.objects.create(
            rabbi_user=other_rabbi, charity=other, verdict=Haskama.Verdict.APPROVE
        )

        cards = DjangoCharityRepository().page(0, 10, CharityFilters(haskama_rabbis=(rabbi.id,)))

        self.assertEqual([card.name for card in cards], ["Alpha"])

    def test_rabbis_are_or(self) -> None:
        charity = Charity.objects.create(name="Alpha")
        other = Charity.objects.create(name="Beta")
        first = UserFactory()
        second = UserFactory()
        Haskama.objects.create(rabbi_user=first, charity=charity, verdict=Haskama.Verdict.APPROVE)
        Haskama.objects.create(rabbi_user=second, charity=other, verdict=Haskama.Verdict.APPROVE)

        cards = DjangoCharityRepository().page(
            0, 10, CharityFilters(haskama_rabbis=(first.id, second.id))
        )

        self.assertEqual({card.name for card in cards}, {"Alpha", "Beta"})

    def test_a_disapproving_haskama_still_counts_as_endorsement(self) -> None:
        """The group matches any haskama, approve or disapprove (D-045)."""
        charity = Charity.objects.create(name="Alpha")
        rabbi = UserFactory()
        Haskama.objects.create(
            rabbi_user=rabbi, charity=charity, verdict=Haskama.Verdict.DISAPPROVE
        )

        cards = DjangoCharityRepository().page(0, 10, CharityFilters(haskama_rabbis=(rabbi.id,)))

        self.assertEqual([card.name for card in cards], ["Alpha"])


class MinRatingFilterTest(TestCase):
    def setUp(self) -> None:
        self.rated = Charity.objects.create(name="Rated")
        self.unrated = Charity.objects.create(name="Unrated")
        author = UserFactory()
        for rating in (5, 4):
            Review.objects.create(charity=self.rated, author=author, rating=rating)

    def test_filters_by_average_star_rating(self) -> None:
        cards = self._page(min_rating=4)

        self.assertEqual([card.name for card in cards], ["Rated"])

    def test_a_charity_with_no_reviews_has_no_average_and_does_not_match(self) -> None:
        cards = self._page(min_rating=1)

        self.assertEqual([card.name for card in cards], ["Rated"])

    def test_lower_bound_is_inclusive(self) -> None:
        """The average is 4.5, so 4 keeps the charity and 5 does not."""
        self.assertEqual([c.name for c in self._page(min_rating=4)], ["Rated"])
        self.assertEqual([c.name for c in self._page(min_rating=5)], [])

    def test_cards_show_the_same_average_the_filter_uses(self) -> None:
        card = self._page(min_rating=4)[0]

        self.assertEqual(card.reviews.average, 4.5)
        self.assertEqual(card.reviews.count, 2)

    def _page(self, min_rating):
        return DjangoCharityRepository().page(0, 10, CharityFilters(min_rating=min_rating))


class MinReviewsFilterTest(TestCase):
    def test_counts_reviews(self) -> None:
        busy = Charity.objects.create(name="Busy")
        Charity.objects.create(name="Quiet")
        author = UserFactory()
        Review.objects.create(charity=busy, author=author, rating=5)
        Review.objects.create(charity=busy, author=author, rating=3)

        cards = DjangoCharityRepository().page(0, 10, CharityFilters(min_reviews=2))

        self.assertEqual([card.name for card in cards], ["Busy"])

    def test_zero_matches_even_a_charity_with_no_reviews(self) -> None:
        """D-045: 0 is a real lower bound, not "unset"."""
        Charity.objects.create(name="Quiet")

        cards = DjangoCharityRepository().page(0, 10, CharityFilters(min_reviews=0))

        self.assertEqual([card.name for card in cards], ["Quiet"])


class HaskamaCountFilterTest(TestCase):
    def test_min_approving_haskamas_counts_approve_verdicts(self) -> None:
        charity = Charity.objects.create(name="Approved")
        other = Charity.objects.create(name="Other")
        first = UserFactory()
        second = UserFactory()
        Haskama.objects.create(rabbi_user=first, charity=charity, verdict=Haskama.Verdict.APPROVE)
        Haskama.objects.create(rabbi_user=second, charity=charity, verdict=Haskama.Verdict.APPROVE)
        Haskama.objects.create(rabbi_user=first, charity=other, verdict=Haskama.Verdict.APPROVE)

        cards = DjangoCharityRepository().page(0, 10, CharityFilters(min_approving_haskamas=2))

        self.assertEqual([card.name for card in cards], ["Approved"])

    def test_max_disapproving_haskamas_counts_disapprove_verdicts(self) -> None:
        charity = Charity.objects.create(name="Approved")
        other = Charity.objects.create(name="Disputed")
        first = UserFactory()
        second = UserFactory()
        Haskama.objects.create(rabbi_user=first, charity=other, verdict=Haskama.Verdict.DISAPPROVE)
        Haskama.objects.create(rabbi_user=second, charity=other, verdict=Haskama.Verdict.DISAPPROVE)
        Haskama.objects.create(rabbi_user=first, charity=charity, verdict=Haskama.Verdict.APPROVE)

        cards = DjangoCharityRepository().page(0, 10, CharityFilters(max_disapproving_haskamas=1))

        self.assertEqual([card.name for card in cards], ["Approved"])

    def test_zero_disapproving_haskamas_means_none_at_all(self) -> None:
        Charity.objects.create(name="Clean")
        disputed = Charity.objects.create(name="Disputed")
        rabbi = UserFactory()
        Haskama.objects.create(
            rabbi_user=rabbi, charity=disputed, verdict=Haskama.Verdict.DISAPPROVE
        )

        cards = DjangoCharityRepository().page(0, 10, CharityFilters(max_disapproving_haskamas=0))

        self.assertEqual([card.name for card in cards], ["Clean"])


class CombinedFiltersTest(TestCase):
    def test_groups_are_and(self) -> None:
        """A domain AND a rating must both hold (§6.2.4)."""
        food = Domain.objects.create(name="Food Security")
        in_food = Charity.objects.create(name="In food")
        also_in_food = Charity.objects.create(name="In food, poorly rated")
        in_food.domains.add(food)
        also_in_food.domains.add(food)
        author = UserFactory()
        Review.objects.create(charity=in_food, author=author, rating=5)
        Review.objects.create(charity=also_in_food, author=author, rating=2)

        cards = DjangoCharityRepository().page(
            0, 10, CharityFilters(domains=(food.id,), min_rating=4)
        )

        self.assertEqual([card.name for card in cards], ["In food"])

    def test_the_counts_are_recomputed_together(self) -> None:
        food = Domain.objects.create(name="Food Security")
        charity = Charity.objects.create(name="Alpha")
        other = Charity.objects.create(name="Beta")
        charity.domains.add(food)
        author = UserFactory()
        for rating in (5, 5):
            Review.objects.create(charity=charity, author=author, rating=rating)
        Review.objects.create(charity=other, author=author, rating=5)

        cards = DjangoCharityRepository().page(
            0, 10, CharityFilters(domains=(food.id,), min_rating=5, min_reviews=2)
        )

        self.assertEqual([card.name for card in cards], ["Alpha"])


class CountRespectsFiltersTest(TestCase):
    def test_count_matches_the_filtered_set(self) -> None:
        food = Domain.objects.create(name="Food Security")
        charity = Charity.objects.create(name="Alpha")
        other = Charity.objects.create(name="Beta")
        charity.domains.add(food)
        other.domains.add(food)

        repository = DjangoCharityRepository()
        filters = CharityFilters(domains=(food.id,))
        self.assertEqual(repository.count(filters), 2)
        self.assertEqual(repository.count(CharityFilters(domains=(food.id, 999999))), 2)


class FilterOptionsRepositoryTest(TestCase):
    def test_domains_and_locations_come_from_the_shared_lists(self) -> None:
        from apps.charities.repositories import DjangoFilterOptionsRepository

        domain = Domain.objects.create(name="Education")
        Location.objects.create(name="Lakewood", region="NJ", country="USA")

        options = DjangoFilterOptionsRepository()

        self.assertEqual([(o.id, o.name) for o in options.domains()], [(domain.id, "Education")])
        self.assertEqual([o.label for o in options.locations()], ["Lakewood, NJ, USA"])

    def test_rabbis_are_empty_until_accounts_can_list_them(self) -> None:
        from apps.charities.repositories import DjangoFilterOptionsRepository

        self.assertEqual(DjangoFilterOptionsRepository().rabbis(), ())


class RatingClampTest(TestCase):
    """D-046: min_rating is clamped into the 1-5 scale, and the clamp is visible.

    The repository compares what it is given; the clamp happens where the URL is
    read, so these tests exercise `from_query` and the sidebar's correction note.
    """

    def setUp(self) -> None:
        self.rated = Charity.objects.create(name="Rated")
        self.unrated = Charity.objects.create(name="Unrated")
        author = UserFactory()
        Review.objects.create(charity=self.rated, author=author, rating=5)

    def test_from_query_clamps_above_the_scale_to_five(self) -> None:
        filters = from_query(QueryDict("min_rating=99"))

        self.assertEqual(filters.min_rating, 5)
        cards = DjangoCharityRepository().page(0, 10, filters)
        self.assertEqual([c.name for c in cards], ["Rated"])

    def test_from_query_clamps_below_the_scale_to_one(self) -> None:
        filters = from_query(QueryDict("min_rating=0"))

        self.assertEqual(filters.min_rating, 1)
        # min_rating=1 still excludes the unreviewed charity: it has no average.
        cards = DjangoCharityRepository().page(0, 10, filters)
        self.assertEqual([c.name for c in cards], ["Rated"])

    def test_inside_the_scale_is_untouched(self) -> None:
        self.assertEqual(from_query(QueryDict("min_rating=4")).min_rating, 4)


class ScrollableOptionListTest(TestCase):
    """D-046: the repeatable groups' options scroll instead of unrolling."""

    def test_options_are_wrapped_in_a_scrollable_panel(self) -> None:
        from django.test import Client

        body = Client().get("/charity/").content.decode()

        self.assertIn('class="filters__options"', body)
        self.assertIn("tabindex", body)
