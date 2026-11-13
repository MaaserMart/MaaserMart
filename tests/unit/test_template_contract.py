"""Contract tests between the listing template and the values it receives.

Django templates fail silently: an attribute that does not exist renders as an
empty string, so a template that iterates the wrong attribute produces a page
with missing content and no error. These tests pin the contract that the
template relies on, so that renaming or reshaping a value breaks a test rather
than quietly emptying the page.
"""

from django.test import TestCase
from django.urls import reverse

from apps.charities.contracts import CharityCard, DomainTag, LocationTag
from apps.charities.models import Charity, Domain, Location


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

    def test_card_type_has_the_attributes_the_template_uses(self) -> None:
        """Guards the shape the template iterates over.

        The template reads .name, .tagline, .image, .domains, .locations and
        each tag's .name. If a card stops exposing one of those, or exposes a
        manager instead of a sequence, this fails loudly.
        """
        card = CharityCard(
            id=1,
            name="Keren L'Dugma",
            tagline="t",
            image="i.svg",
            domains=(DomainTag(name="Free loans"),),
            locations=(LocationTag(name="Lakewood"),),
        )

        for attribute in ("name", "tagline", "image", "domains", "locations"):
            self.assertTrue(hasattr(card, attribute), attribute)

        # The template iterates these directly, so they must be iterable and
        # must not be ORM managers left over from the old contract.
        self.assertEqual(list(card.domains)[0].name, "Free loans")
        self.assertEqual(list(card.locations)[0].name, "Lakewood")
        self.assertFalse(hasattr(card.domains, "all"))

    def test_empty_relations_do_not_render_a_divider(self) -> None:
        Charity.objects.create(name="Keren L'Dugma")

        body = self._render_single_charity()

        self.assertNotIn("chip-divider", body)
