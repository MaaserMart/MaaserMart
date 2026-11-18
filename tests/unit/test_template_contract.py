"""Contract tests between the listing template and the values it receives.

Django templates fail silently: an attribute that does not exist renders as an
empty string, so a template that iterates the wrong attribute produces a page
with missing content and no error. These tests pin the contract that the
template relies on, so that renaming or reshaping a value breaks a test rather
than quietly emptying the page.
"""

from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.charities.contracts import (
    ActivitySummary,
    CharityCard,
    DomainTag,
    LocationTag,
    ReviewSummary,
)
from apps.charities.models import Charity, Domain, Haskama, Location, Review
from apps.events.models import Event
from tests.factories.accounts import UserFactory
from tests.support.css import declarations


class FilterSidebarCssTest(TestCase):
    """D-047: the panel is bounded to the viewport and scrolls on its own.

    Like the nav's sticky rule, this reads the stylesheet the page loads: a
    deleted `max-height` or `overflow-y` would otherwise only show up by eye.
    """

    def test_the_sidebar_is_bounded_and_scrolls(self) -> None:
        """Resolved the way a browser would (audit T2), not just searched for."""
        css = (settings.BASE_DIR / "static" / "css" / "site.css").read_text(encoding="utf-8")
        rule = declarations(css, ".listing__sidebar")

        self.assertIn("max-height", rule)
        self.assertEqual(rule.get("overflow-y"), "auto")
        # A later `position: static` would break the scroll claim; a regex on the
        # first matching block would not notice.
        self.assertEqual(rule.get("position"), "sticky")

    def test_the_sidebar_class_is_on_the_page(self) -> None:
        """The rule above only matters if an element carries the class."""
        body = self.client.get(reverse("charities:listing")).content.decode()

        self.assertIn('class="listing__sidebar"', body)


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
        charity = Charity.objects.create(name="Keren L'Dugma")
        for rating in (4, 5):
            Review.objects.create(charity=charity, author=UserFactory(), rating=rating)

        body = self._render_single_charity()

        self.assertIn("4.5 out of 5", body)
        self.assertIn("2 reviews", body)

    def test_activity_values_render_on_every_card(self) -> None:
        """D-051: every order shows the numbers it sorts by, including zero counts."""
        charity = Charity.objects.create(name="Keren L'Dugma")
        for _ in range(2):
            Event.objects.create(charity=charity, action=Event.Action.VIEW)
        Haskama.objects.create(
            rabbi_user=UserFactory(), charity=charity, verdict=Haskama.Verdict.APPROVE
        )

        body = self._render_single_charity()

        self.assertIn("2 events", body)
        self.assertIn("1 haskama", body)
        self.assertIn("Last changed", body)

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
        .reviews.average, and .activity's three values. If a card stops
        exposing one of those, or exposes a manager instead of a sequence, this
        fails loudly.
        """
        card = CharityCard(
            id=1,
            name="Keren L'Dugma",
            tagline="t",
            image="i.svg",
            domains=(DomainTag(name="Free loans"),),
            locations=(LocationTag(name="Lakewood", region="NJ", country="USA"),),
            reviews=ReviewSummary(count=2, average=4.5),
            activity=ActivitySummary(events=7, approving_haskamas=3, last_changed=timezone.now()),
        )

        for attribute in (
            "name",
            "tagline",
            "image",
            "domains",
            "locations",
            "reviews",
            "activity",
        ):
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
        self.assertIn("Highest rated", counted)
        self.assertIn("Lowest rated", counted)

    def test_the_sort_form_repeats_the_active_filters(self) -> None:
        """Sorting must not drop the sidebar's choices (D-045, D-048)."""
        domain = Domain.objects.create(name="Free loans")

        body = self.client.get(self.url, {"domain": domain.id}).content.decode()

        self.assertIn(f'name="domain" value="{domain.id}"', self._sort_form(body))

    def test_the_dropdown_applies_its_choice_when_it_changes(self) -> None:
        """The labels must never describe the mechanism that is no longer chosen (D-053)."""
        body = self.client.get(self.url).content.decode()
        form = self._sort_form(body)

        self.assertIn("data-sort-form", form)
        # The behaviour lives in the script, not in an inline handler that a
        # Content-Security-Policy would have to allow.
        self.assertNotIn("onchange=", form)
        self.assertIn('<script src="', body)
        self.assertIn("js/sort.js", body)

    def test_enter_in_the_dropdown_takes_the_same_path_as_a_change(self) -> None:
        """Both listeners submit with no submitter, so the default direction wins.

        There is no browser here to press the key, so the check is on the script
        the page loads: losing either listener would bring back the asc-first
        implicit submit.
        """
        script = (settings.BASE_DIR / "static" / "js" / "sort.js").read_text(encoding="utf-8")

        self.assertIn('addEventListener("change"', script)
        self.assertIn('addEventListener("keydown"', script)
        self.assertIn('event.key === "Enter"', script)
        self.assertIn("form.submit()", script)


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
