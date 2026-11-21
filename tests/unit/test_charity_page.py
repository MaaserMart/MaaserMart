"""The charity page (§6.2.7, D-057) and the events it writes (audit M4)."""

import pytest
from django.urls import reverse
from django.utils.html import escape

from apps.accounts.models import RabbiProfile
from apps.charities.filters import CharityFilters
from apps.charities.models import Charity, Domain, Haskama, Link, Location, Review
from apps.charities.repositories import DjangoCharityRepository, DjangoFilterOptionsRepository
from apps.events.models import Event
from tests.factories import CharityFactory, UserFactory
from tests.factories.accounts import DEFAULT_PASSWORD

pytestmark = pytest.mark.django_db


@pytest.fixture
def populated_charity():
    charity = Charity.objects.create(
        name="Keren L'Dugma",
        tagline="Interest-free loans.",
        description="A gemach lending at no interest, Lakewood NJ.",
        image="charities/img/charity-01.svg",
    )
    domain = Domain.objects.create(name="Free loans")
    location = Location.objects.create(name="Lakewood", region="NJ", country="USA")
    charity.domains.add(domain)
    charity.locations.add(location)
    for kind, url in (
        (Link.Kind.WEBSITE_DONATE, "https://keren.example.org/donate"),
        (Link.Kind.WEBSITE_ABOUT, "https://keren.example.org/about"),
    ):
        Link.objects.create(charity=charity, kind=kind, url=url)
    reviewer = UserFactory(username="rivka")
    Review.objects.create(
        charity=charity,
        author=reviewer,
        rating=5,
        body="Excellent and quick service.",
    )
    rabbi = UserFactory(username="rabbi1")
    RabbiProfile.objects.create(user=rabbi, display_name="Yosef Cohen", title="Rabbi")
    Haskama.objects.create(
        rabbi_user=rabbi, charity=charity, verdict=Haskama.Verdict.APPROVE, importance=9
    )
    return charity


def test_the_page_shows_everything_the_doc_names(client, populated_charity):
    response = client.get(reverse("charities:detail", args=[populated_charity.id]))

    body = response.content.decode()
    for text in [
        "Keren L'Dugma",
        "Interest-free loans.",
        "A gemach lending at no interest",
        "Free loans",
        "Lakewood, NJ, USA",  # a location's full identity (D-045)
        "https://keren.example.org/donate",
        "5 out of 5",
        "rivka",
        "Excellent and quick service.",
        "Rabbi Yosef Cohen",
        "Approves",
        "Importance 9/10",
    ]:
        assert escape(text) in body, text


def test_an_unknown_charity_is_a_real_404(client):
    response = client.get(reverse("charities:detail", args=[999_999]))

    assert response.status_code == 404


def test_a_visit_is_recorded_as_a_view_event(client, populated_charity):
    client.get(reverse("charities:detail", args=[populated_charity.id]))

    event = Event.objects.get(charity=populated_charity, action=Event.Action.VIEW)
    assert event.user_id is None


def test_a_signed_in_visit_is_attributed(client, populated_charity, django_user_model):
    member = django_user_model.objects.create_user("member1", password=DEFAULT_PASSWORD)
    client.force_login(member)

    client.get(reverse("charities:detail", args=[populated_charity.id]))

    event = Event.objects.get(charity=populated_charity, action=Event.Action.VIEW)
    assert event.user_id == member.id


def test_clicking_a_link_counts_it_and_sends_the_visitor_on(client, populated_charity):
    link = populated_charity.links.get(kind=Link.Kind.WEBSITE_DONATE)

    response = client.get(reverse("charities:link", args=[populated_charity.id, link.id]))

    assert response.status_code == 302
    assert response["Location"] == link.url
    assert Event.objects.filter(
        charity=populated_charity, action=Event.Action.LINK_CLICK, link=link
    ).exists()


def test_a_link_with_an_unsafe_scheme_is_not_followed(client, populated_charity):
    link = Link.objects.create(
        charity=populated_charity, kind=Link.Kind.WEBSITE_CONTACT, url="javascript:alert(1)"
    )

    response = client.get(reverse("charities:link", args=[populated_charity.id, link.id]))

    assert response.status_code == 404
    assert not Event.objects.filter(link=link).exists()


def test_a_stray_redirect_request_records_no_event(client, populated_charity):
    response = client.get(reverse("charities:link", args=[populated_charity.id, 999_999]))

    assert response.status_code == 404
    assert Event.objects.count() == 0


def test_a_refused_visit_write_still_shows_the_charity(client, populated_charity, monkeypatch):
    """§6.2.7: "Failed writes do not fail the page."

    `record_event` refuses a reference that does not exist (audit B6), which a
    deleted account behind a live session is enough to cause. Losing the count
    must not cost the visitor the charity.
    """

    def refuse(*args, **kwargs):
        raise ValueError("Event refers to a row that does not exist")

    monkeypatch.setattr("apps.charities.views.record_event", refuse)

    response = client.get(reverse("charities:detail", args=[populated_charity.id]))

    assert response.status_code == 200
    assert escape("Keren L'Dugma") in response.content.decode()


def test_a_refused_click_write_still_sends_the_visitor_on(client, populated_charity, monkeypatch):
    """The same promise on the click route: the charity's own site is the point."""

    def refuse(*args, **kwargs):
        raise ValueError("Event refers to a row that does not exist")

    monkeypatch.setattr("apps.charities.views.record_event", refuse)
    link = populated_charity.links.get(kind=Link.Kind.WEBSITE_DONATE)

    response = client.get(reverse("charities:link", args=[populated_charity.id, link.id]))

    assert response.status_code == 302
    assert response["Location"] == link.url


def test_the_listing_card_links_to_the_charity_page(client, populated_charity):
    response = client.get(reverse("charities:listing"))

    body = response.content.decode()
    assert f'href="/charity/{populated_charity.id}/"' in body


class RabbiOptionsTest:
    """The Haskamos group reads its list from accounts (§6.2.4, M6, audit Q3)."""

    def test_the_filter_offers_every_rabbi_with_a_profile(self):
        rabbi = UserFactory(username="yosef")
        RabbiProfile.objects.create(user=rabbi, display_name="Yosef Cohen", title="Rabbi")

        options = DjangoFilterOptionsRepository().rabbis()

        assert len(options) == 1
        option = options[0]
        assert option.id == rabbi.id  # the *user* id, not the profile's (Q3)
        assert option.label == "Rabbi Yosef Cohen"

    def test_a_rabbi_without_a_profile_is_not_offered(self):
        UserFactory(username="not-a-rabbi")

        assert DjangoFilterOptionsRepository().rabbis() == ()

    def test_the_filters_s_feature_a_rabbi_who_can_endorse(self):
        charity = CharityFactory()
        rabbi = UserFactory(username="rabbi1")
        Haskama.objects.create(rabbi_user=rabbi, charity=charity, verdict=Haskama.Verdict.APPROVE)

        cards = DjangoCharityRepository().page(0, 10, CharityFilters(haskama_rabbis=(rabbi.id,)))

        assert [card.name for card in cards] == [charity.name]
