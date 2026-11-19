"""Every §6.2.5 sort order, applied to real rows (D-048).

These live against Postgres because the thing under test is the ORDER BY the
repository builds: the count or date each mechanism reads, the direction, and
§6.2.5's alphabetical tiebreak. The doc asks for one white-box test per sort.
"""

from datetime import timedelta

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.charities.filters import CharityFilters
from apps.charities.models import Charity, Domain, Haskama, Review
from apps.charities.repositories import DjangoCharityRepository
from apps.charities.sorting import (
    ALPHABETICAL,
    DEFAULT_SORT,
    HASKAMOS,
    MECHANISMS,
    NEWEST,
    POPULAR,
    RATING,
    TRENDING,
    UPDATED,
    CharitySort,
)
from apps.events.models import Event
from tests.factories.accounts import UserFactory


def make_charity(name: str, *, created=None) -> Charity:
    """A charity, optionally with a known creation time.

    `auto_now_add` stamps the insert; the queryset update is the only way to
    give a test row a date in the past without sleeping.
    """
    charity = Charity.objects.create(name=name)
    if created is not None:
        Charity.objects.filter(pk=charity.pk).update(created=created)
        charity.refresh_from_db()
    return charity


def make_event(charity: Charity, *, days_ago: float = 0, action=Event.Action.VIEW) -> Event:
    event = Event.objects.create(charity=charity, action=action)
    Event.objects.filter(pk=event.pk).update(created=timezone.now() - timedelta(days=days_ago))
    return event


class SortTest(TestCase):
    def setUp(self) -> None:
        self.repository = DjangoCharityRepository()

    def names(self, sort: CharitySort) -> list[str]:
        return [card.name for card in self.repository.page(0, 20, sort=sort)]

    def sorted_names(self, mechanism, *, descending: bool) -> list[str]:
        return self.names(CharitySort(mechanism=mechanism, descending=descending))


class AlphabeticalSortTest(SortTest):
    def setUp(self) -> None:
        super().setUp()
        for name in ("Zohar Fund", "Adas Chessed", "Mercaz Tzedaka"):
            make_charity(name)

    def test_defaults_to_a_to_z(self) -> None:
        self.assertEqual(
            self.names(DEFAULT_SORT),
            ["Adas Chessed", "Mercaz Tzedaka", "Zohar Fund"],
        )

    def test_high_to_low_reverses_the_alphabet(self) -> None:
        self.assertEqual(
            self.sorted_names(ALPHABETICAL, descending=True),
            ["Zohar Fund", "Mercaz Tzedaka", "Adas Chessed"],
        )

    def test_equal_names_fall_back_to_the_row_id(self) -> None:
        """A tie needs a total order, or a page boundary can repeat a row."""
        first = make_charity("Same Name")
        second = make_charity("Same Name")

        cards = self.repository.page(0, 20, sort=DEFAULT_SORT)
        same_name = [card.id for card in cards if card.name == "Same Name"]

        self.assertEqual(same_name, [first.id, second.id])


class RatingSortTest(SortTest):
    """`rating` is D-044's average, not the review count (D-048)."""

    def setUp(self) -> None:
        super().setUp()
        self.top = make_charity("Alpha")
        self.mid = make_charity("Beta")
        self.low = make_charity("Gamma")
        self.unrated = make_charity("Delta")
        # Alpha 5.0, Beta 4.5, Gamma 3.0. Delta has no reviews, so no average.
        # One review per member per charity (D-055), so each rating gets its own author.
        for charity, ratings in ((self.top, (5,)), (self.mid, (4, 5)), (self.low, (3,))):
            for rating in ratings:
                Review.objects.create(charity=charity, author=UserFactory(), rating=rating)

    def test_high_to_low_is_the_default(self) -> None:
        self.assertEqual(
            self.sorted_names(RATING, descending=True),
            ["Alpha", "Beta", "Gamma", "Delta"],
        )

    def test_low_to_high_puts_the_unrated_charity_last_too(self) -> None:
        """No reviews is no rating, not a low rating (D-045, D-048)."""
        self.assertEqual(
            self.sorted_names(RATING, descending=False),
            ["Gamma", "Beta", "Alpha", "Delta"],
        )

    def test_a_tie_breaks_alphabetically_in_both_directions(self) -> None:
        make_charity("Echo")
        Review.objects.create(
            charity=Charity.objects.get(name="Echo"), author=UserFactory(), rating=5
        )

        descending = self.sorted_names(RATING, descending=True)
        ascending = self.sorted_names(RATING, descending=False)

        # The tiebreak is A→Z in both directions, not reversed with the order.
        self.assertEqual(descending[:2], ["Alpha", "Echo"])
        self.assertEqual(ascending[-3:], ["Alpha", "Echo", "Delta"])


class HaskamaCountSortTest(SortTest):
    """Only approving haskamas raise a charity (D-048)."""

    def setUp(self) -> None:
        super().setUp()
        self.alpha = make_charity("Alpha")
        self.beta = make_charity("Beta")
        self.gamma = make_charity("Gamma")
        for charity in (self.alpha, self.alpha, self.beta):
            Haskama.objects.create(
                rabbi_user=UserFactory(), charity=charity, verdict=Haskama.Verdict.APPROVE
            )
        Haskama.objects.create(
            rabbi_user=UserFactory(),
            charity=self.beta,
            verdict=Haskama.Verdict.DISAPPROVE,
        )

    def test_high_to_low_counts_approvals(self) -> None:
        self.assertEqual(
            self.sorted_names(HASKAMOS, descending=True),
            ["Alpha", "Beta", "Gamma"],
        )

    def test_low_to_high_starts_with_no_approvals(self) -> None:
        self.assertEqual(
            self.sorted_names(HASKAMOS, descending=False),
            ["Gamma", "Beta", "Alpha"],
        )

    def test_the_join_does_not_list_a_charity_once_per_haskama(self) -> None:
        self.assertEqual(len(self.repository.page(0, 20, sort=CharitySort(HASKAMOS, True))), 3)

    def test_the_haskama_order_does_not_change_the_review_summary(self) -> None:
        """A sort must not multiply the review aggregate it shares a query with."""
        for charity, rating in ((self.alpha, 5), (self.alpha, 3), (self.beta, 4)):
            Review.objects.create(charity=charity, author=UserFactory(), rating=rating)

        cards = {
            card.name: card
            for card in self.repository.page(0, 20, sort=CharitySort(HASKAMOS, True))
        }

        self.assertEqual((cards["Alpha"].reviews.count, cards["Alpha"].reviews.average), (2, 4.0))
        self.assertEqual((cards["Beta"].reviews.count, cards["Beta"].reviews.average), (1, 4.0))


class PopularSortTest(SortTest):
    """`popular` counts every EVENT action (D-048)."""

    def setUp(self) -> None:
        super().setUp()
        self.alpha = make_charity("Alpha")
        self.beta = make_charity("Beta")
        self.gamma = make_charity("Gamma")
        for action in (Event.Action.VIEW, Event.Action.LINK_CLICK, Event.Action.CHARITY_UPDATED):
            make_event(self.alpha, action=action)
        make_event(self.beta, action=Event.Action.REJECT)

    def test_high_to_low_orders_by_total_events(self) -> None:
        self.assertEqual(
            self.sorted_names(POPULAR, descending=True),
            ["Alpha", "Beta", "Gamma"],
        )

    def test_low_to_high_orders_by_fewest_events(self) -> None:
        self.assertEqual(
            self.sorted_names(POPULAR, descending=False),
            ["Gamma", "Beta", "Alpha"],
        )

    def test_a_charity_is_listed_once_however_many_events_it_has(self) -> None:
        self.assertEqual(
            len(self.repository.page(0, 10, sort=CharitySort(mechanism=POPULAR, descending=True))),
            3,
        )


class TrendingSortTest(SortTest):
    """§6.4.3 with non-overlapping buckets: days 1–7 count 3, days 8–30 count 2 (D-050)."""

    def setUp(self) -> None:
        super().setUp()
        newest_plus_old = make_charity("Alpha")
        make_event(newest_plus_old, days_ago=1)
        make_event(newest_plus_old, days_ago=20)
        only_old = make_charity("Beta")
        for _ in range(3):
            make_event(only_old, days_ago=20)
        fresh = make_charity("Gamma")
        make_event(fresh, days_ago=1)
        make_charity("Delta")
        outside = make_charity("Epsilon")
        make_event(outside, days_ago=40)

    def test_high_to_low_uses_both_windows(self) -> None:
        # A week event is worth 3, not 5: Beta 3×2 = 6 beats Alpha 3 + 2 = 5.
        # Gamma 3; Delta and Epsilon 0.
        self.assertEqual(
            self.sorted_names(TRENDING, descending=True),
            ["Beta", "Alpha", "Gamma", "Delta", "Epsilon"],
        )

    def test_low_to_high_reverses_the_score(self) -> None:
        self.assertEqual(
            self.sorted_names(TRENDING, descending=False),
            ["Delta", "Epsilon", "Gamma", "Alpha", "Beta"],
        )


class TrendingBucketTest(SortTest):
    """The week and month buckets do not overlap (D-050)."""

    def test_a_week_old_event_is_not_also_counted_in_the_month(self) -> None:
        """One event is worth 3, not 5, at the week boundary."""
        week_only = make_charity("Week Only")
        make_event(week_only, days_ago=6)
        month_only = make_charity("Month Only")
        for _ in range(2):
            make_event(month_only, days_ago=10)

        # Week Only 1 × 3 = 3; Month Only 2 × 2 = 4. The literal double count
        # would put Week Only's single event at 5 and reverse this order.
        self.assertEqual(
            self.sorted_names(TRENDING, descending=True),
            ["Month Only", "Week Only"],
        )


class NewestSortTest(SortTest):
    """`newest` is CHARITY.created (D-017, D-048)."""

    def setUp(self) -> None:
        super().setUp()
        now = timezone.now()
        make_charity("Alpha", created=now - timedelta(days=3))
        make_charity("Beta", created=now - timedelta(days=2))
        make_charity("Gamma", created=now - timedelta(days=1))

    def test_high_to_low_is_newest_first(self) -> None:
        self.assertEqual(
            self.sorted_names(NEWEST, descending=True),
            ["Gamma", "Beta", "Alpha"],
        )

    def test_low_to_high_is_oldest_first(self) -> None:
        self.assertEqual(
            self.sorted_names(NEWEST, descending=False),
            ["Alpha", "Beta", "Gamma"],
        )


class UpdatedSortTest(SortTest):
    """`updated` is the latest charity_updated EVENT, else CHARITY.created (D-048)."""

    def setUp(self) -> None:
        super().setUp()
        now = timezone.now()
        alpha = make_charity("Alpha", created=now - timedelta(days=10))
        make_event(alpha, days_ago=3, action=Event.Action.CHARITY_UPDATED)
        # A newer view is not a change to the charity and must not win.
        make_event(alpha, days_ago=0.01, action=Event.Action.VIEW)
        beta = make_charity("Beta", created=now - timedelta(days=20))
        make_event(beta, days_ago=1, action=Event.Action.CHARITY_UPDATED)
        make_charity("Gamma", created=now - timedelta(days=5))

    def test_high_to_low_uses_the_last_change(self) -> None:
        # Beta changed 1 day ago, Alpha 3 days ago, Gamma never (created 5 days ago).
        self.assertEqual(
            self.sorted_names(UPDATED, descending=True),
            ["Beta", "Alpha", "Gamma"],
        )

    def test_low_to_high_puts_the_oldest_change_first(self) -> None:
        self.assertEqual(
            self.sorted_names(UPDATED, descending=False),
            ["Gamma", "Alpha", "Beta"],
        )


class FilteredSortTest(SortTest):
    """A filter chooses the set and a sort orders it, in the same query (D-045, D-048)."""

    def test_a_filter_and_a_sort_narrow_and_order_together(self) -> None:
        food = Domain.objects.create(name="Food")
        education = Domain.objects.create(name="Education")
        alpha = make_charity("Alpha")
        alpha.domains.add(food)
        zeta = make_charity("Zeta")
        zeta.domains.add(education)
        make_event(alpha)
        make_event(zeta)
        make_event(zeta)

        cards = self.repository.page(
            0,
            20,
            CharityFilters(domains=(food.id,)),
            CharitySort(mechanism=POPULAR, descending=True),
        )

        self.assertEqual([card.name for card in cards], ["Alpha"])

    def test_a_repeatable_filter_keeps_the_review_count_exact(self) -> None:
        """Two matching domains must not turn two reviews into four (D-045)."""
        first = Domain.objects.create(name="Food")
        second = Domain.objects.create(name="Education")
        charity = make_charity("Alpha")
        charity.domains.add(first, second)
        for rating in (5, 3):
            Review.objects.create(charity=charity, author=UserFactory(), rating=rating)

        filters = CharityFilters(domains=(first.id,))
        cards = self.repository.page(0, 20, filters)

        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0].reviews.count, 2)
        self.assertEqual(cards[0].reviews.average, 4.0)
        self.assertEqual(self.repository.count(filters), 1)

    def test_a_haskama_rabbi_filter_cannot_multiply_the_page(self) -> None:
        """A repeatable filter is one EXISTS, not a join (D-045)."""
        charity = make_charity("Alpha")
        rabbis = [UserFactory(), UserFactory()]
        for rabbi in rabbis:
            Haskama.objects.create(
                rabbi_user=rabbi, charity=charity, verdict=Haskama.Verdict.APPROVE
            )

        cards = self.repository.page(
            0, 20, CharityFilters(haskama_rabbis=tuple(r.id for r in rabbis))
        )

        self.assertEqual([card.name for card in cards], ["Alpha"])


class SortCountTest(SortTest):
    def test_the_total_does_not_depend_on_the_order(self) -> None:
        for name in ("Alpha", "Beta"):
            make_charity(name)

        for mechanism in MECHANISMS:
            with self.subTest(mechanism=mechanism.value):
                sort = CharitySort(mechanism=mechanism, descending=True)
                self.assertEqual(self.repository.count(), 2)
                self.assertEqual(len(self.repository.page(0, 20, sort=sort)), 2)

    def test_every_mechanism_has_an_order_key(self) -> None:
        """Adding a mechanism without an ORDER BY fails here, not on the page."""
        self.assertEqual(set(DjangoCharityRepository.ORDER_KEYS), set(MECHANISMS))

    def test_the_total_does_not_aggregate_reviews(self) -> None:
        """The count only needs the number of matching charities (D-045)."""
        make_charity("Alpha")

        with CaptureQueriesContext(connection) as queries:
            self.assertEqual(self.repository.count(), 1)

        self.assertNotIn("charities_review", queries.captured_queries[0]["sql"])

    def test_activity_and_haskama_sorts_do_not_add_a_query_per_charity(self) -> None:
        charity = make_charity("Alpha")
        make_event(charity)

        for mechanism in (POPULAR, TRENDING, UPDATED, HASKAMOS):
            with self.subTest(mechanism=mechanism.value):
                with self.assertNumQueries(3):  # page, domains, locations
                    self.repository.page(
                        0, 10, sort=CharitySort(mechanism=mechanism, descending=True)
                    )
