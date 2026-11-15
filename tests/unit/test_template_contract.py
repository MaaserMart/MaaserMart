"""Contract tests between the listing template and the values it receives.

Django templates fail silently: an attribute that does not exist renders as an
empty string, so a template that iterates the wrong attribute produces a page
with missing content and no error. These tests pin the contract that the
template relies on, so that renaming or reshaping a value breaks a test rather
than quietly emptying the page.
"""

from django.test import TestCase
from django.urls import reverse

from apps.charities.contracts import CharityCard, DomainTag, LocationTag, ReviewSummary
from apps.charities.models import Charity, Domain, Location, Review
from tests.factories.accounts import UserFactory


class ListingTemplateContractTest(TestCase):
    """Every field the template renders must appear in the output."""

    def setUp(self) -> None:
        self.url = reverse("charities:listing")

    def _render_single_charity(self) -> str:
        return self.client.get(self.url).content.decode()

    def test_every_card_field_reaches_the_page(self) -> None:
        domain = Domain.objects.create(name="Free loans")
        location = Location.objects.create(name="Lakewood", region="NJ", country="USA")
        charity = Charity.objects.create(
            name="Keren L'Dugma",
            tagline="Interest-free loans.",
            image="charities/img/charity-01.svg",
        )
        charity.domains.add(domain)
        charity.locations.add(location)

        body = self._render_single_charity()

        self.assertIn("Keren L&#x27;Dugma", body)
        self.assertIn("Interest-free loans.", body)
        self.assertIn("charity-01.svg", body)

    def test_domain_names_render(self) -> None:
        domain = Domain.objects.create(name="Free loans")
        charity = Charity.objects.create(name="Keren L'Dugma")
        charity.domains.add(domain)

        body = self._render_single_charity()

        self.assertIn("Free loans", body)

    def test_location_names_render(self) -> None:
        location = Location.objects.create(name="Lakewood", region="NJ", country="USA")
        charity = Charity.objects.create(name="Keren L'Dugma")
        charity.locations.add(location)

        body = self._render_single_charity()

        self.assertIn("Lakewood", body)

    def test_review_summary_renders(self) -> None:
        author = UserFactory()
        charity = Charity.objects.create(name="Keren L'Dugma")
        for rating in (4, 5):
            Review.objects.create(charity=charity, author=author, rating=rating)

        body = self._render_single_charity()

        self.assertIn("4.5 out of 5", body)
        self.assertIn("2 reviews", body)

    def test_charity_without_reviews_says_so(self) -> None:
        """The empty state stands in for the rating, rather than showing 0 out of 5."""
        Charity.objects.create(name="Keren L'Dugma")

        body = self._render_single_charity()

        self.assertIn("No reviews yet", body)
        self.assertNotIn("out of 5", body)

    def test_card_type_has_the_attributes_the_template_uses(self) -> None:
        """Guards the shape the template iterates over.

        The template reads .name, .tagline, .image, .domains, .locations and
        each tag's .name, plus .reviews.count and .reviews.average. If a card
        stops exposing one of those, or exposes a manager instead of a
        sequence, this fails loudly.
        """
        card = CharityCard(
            id=1,
            name="Keren L'Dugma",
            tagline="t",
            image="i.svg",
            domains=(DomainTag(name="Free loans"),),
            locations=(LocationTag(name="Lakewood"),),
            reviews=ReviewSummary(count=2, average=4.5),
        )

        for attribute in ("name", "tagline", "image", "domains", "locations", "reviews"):
            self.assertTrue(hasattr(card, attribute), attribute)

        # The template iterates these directly, so they must be iterable and
        # must not be ORM managers left over from the old contract.
        self.assertEqual(list(card.domains)[0].name, "Free loans")
        self.assertEqual(list(card.locations)[0].name, "Lakewood")
        self.assertFalse(hasattr(card.domains, "all"))
        self.assertEqual(card.reviews.count, 2)
        self.assertEqual(card.reviews.average, 4.5)

    def test_empty_relations_do_not_render_a_divider(self) -> None:
        Charity.objects.create(name="Keren L'Dugma")

        body = self._render_single_charity()

        self.assertNotIn("chip-divider", body)


class SortControlContractTest(TestCase):
    """The sort partial reads only fields `SortForm` guarantees (D-048).

    Django templates fail silently, so an option list or direction label that
    stops reaching the page would leave a working-looking control that does
    nothing. These pin the shape the partial depends on.
    """

    def setUp(self) -> None:
        self.url = reverse("charities:listing")

    def _sort_form(self, body: str) -> str:
        start = body.index('<form class="sort"')
        return body[start : body.index("</form>", start)]

    def test_every_mechanism_reaches_the_dropdown(self) -> None:
        body = self.client.get(self.url).content.decode()
        form = self._sort_form(body)

        for value in (
            "alphabetical",
            "trending",
            "popular",
            "rating",
            "haskamos",
            "newest",
            "updated",
        ):
            with self.subTest(value=value):
                self.assertIn(f'<option value="{value}"', form)

    def test_the_direction_labels_come_from_the_chosen_mechanism(self) -> None:
        alphabetical = self._sort_form(
            self.client.get(self.url, {"direction": "desc"}).content.decode()
        )
        counted = self._sort_form(self.client.get(self.url, {"sort": "rating"}).content.decode())

        self.assertIn("Z to A", alphabetical)
        self.assertIn("High to low", counted)
        self.assertIn("Low to high", counted)
