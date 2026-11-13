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
        each tag's .name (and .label for a location), plus .reviews.count and
        .reviews.average. If a card
        stops exposing one of those, or exposes a manager instead of a
        sequence, this fails loudly.
        """
        card = CharityCard(
            id=1,
            name="Keren L'Dugma",
            tagline="t",
            image="i.svg",
            domains=(DomainTag(name="Free loans"),),
            locations=(LocationTag(name="Lakewood", region="NJ", country="USA"),),
            reviews=ReviewSummary(count=2, average=4.5),
        )

        for attribute in ("name", "tagline", "image", "domains", "locations", "reviews"):
            self.assertTrue(hasattr(card, attribute), attribute)

        # The template iterates these directly, so they must be iterable and
        # must not be ORM managers left over from the old contract.
        self.assertEqual(list(card.domains)[0].name, "Free loans")
        self.assertEqual(list(card.locations)[0].label, "Lakewood, NJ, USA")
        self.assertFalse(hasattr(card.domains, "all"))
        self.assertEqual(card.reviews.count, 2)
        self.assertEqual(card.reviews.average, 4.5)

    def test_empty_relations_do_not_render_a_divider(self) -> None:
        Charity.objects.create(name="Keren L'Dugma")

        body = self._render_single_charity()

        self.assertNotIn("chip-divider", body)


class FilterSidebarContractTest(TestCase):
    """The sidebar template reads only fields `FilterForm` guarantees (D-045).

    Django templates fail silently, so a group that loses its `legend` or
    `kind` would render an empty panel with no error. These pin the contract.
    """

    def setUp(self) -> None:
        self.url = reverse("charities:listing")

    def test_every_group_renders_a_legend(self) -> None:
        body = self.client.get(self.url).content.decode()

        for legend in [
            "Domains",
            "Locations",
            "Haskamos",
            "Rating",
            "Reviews",
            "Approving haskamos",
            "Disapproving haskamos",
        ]:
            self.assertIn(legend, body)

    def test_checkbox_groups_render_inputs_named_by_their_parameter(self) -> None:
        Domain.objects.create(name="Free loans")
        Location.objects.create(name="Lakewood", region="NJ", country="USA")

        body = self.client.get(self.url).content.decode()

        self.assertIn('type="checkbox"', body)
        self.assertIn('name="domain"', body)
        self.assertIn('name="location"', body)

    def test_number_groups_render_one_bounded_input_each(self) -> None:
        body = self.client.get(self.url).content.decode()

        self.assertIn('name="min_rating"', body)
        self.assertIn('min="1"', body)
        self.assertIn('max="5"', body)
        self.assertIn('name="max_disapproving_haskamas"', body)

    def test_the_form_is_a_get(self) -> None:
        """Filters live in the URL, so the form must not post (UC-03)."""
        body = self.client.get(self.url).content.decode()

        self.assertIn('<form class="filters" method="get"', body)

    def test_no_template_comment_leaks_into_the_page(self) -> None:
        body = self.client.get(self.url).content.decode()

        self.assertNotIn("{#", body)
        self.assertNotIn("{%", body)
