"""Member dashboard: private activity, recommendation actions, and navigation."""

import pytest
from django.urls import reverse

from apps.events.models import Event
from tests.factories import UserFactory
from tests.factories.charities import CharityFactory, LinkFactory

pytestmark = pytest.mark.django_db


def test_dashboard_requires_login(client):
    response = client.get(reverse("dashboards:dashboard"))
    assert response.status_code == 302
    assert response.url.startswith("/accounts/login/")


def test_dashboard_displays_only_own_history_and_maaser(client):
    member, other = UserFactory(), UserFactory()
    own, private = CharityFactory(name="Own activity"), CharityFactory(name="Other activity")
    Event.objects.create(user=member, charity=own, action="view")
    Event.objects.create(user=other, charity=private, action="view")
    client.force_login(member)
    response = client.get(reverse("dashboards:dashboard"))
    assert response.status_code == 200
    assert "Own activity" in response.content.decode()
    assert "Other activity" not in response.content.decode()
    assert "Maaser owed" in response.content.decode()
    assert "no-store" in response.headers["Cache-Control"]


def test_history_actions_are_scoped_and_post_only(client):
    member, other = UserFactory(), UserFactory()
    charity = CharityFactory()
    own = Event.objects.create(user=member, charity=charity, action="view")
    theirs = Event.objects.create(user=other, charity=charity, action="link_click")
    client.force_login(member)
    assert client.get(reverse("dashboards:hide", args=[own.id])).status_code == 405
    assert client.post(reverse("dashboards:hide", args=[theirs.id])).status_code == 404
    assert client.post(reverse("dashboards:hide", args=[own.id])).status_code == 302
    own.refresh_from_db()
    assert own.hidden_by_user
    next_event = Event.objects.create(user=member, charity=charity, action="link_click")
    assert client.post(reverse("dashboards:clear-history")).status_code == 302
    next_event.refresh_from_db()
    theirs.refresh_from_db()
    assert next_event.hidden_by_user and not theirs.hidden_by_user


def test_reject_requires_an_offered_recommendation(client, monkeypatch):
    member = UserFactory()
    charity = CharityFactory()
    client.force_login(member)
    url = reverse("dashboards:reject", args=[charity.id])
    assert client.get(url).status_code == 405
    monkeypatch.setattr("apps.dashboards.views.recommend_for", lambda user_id: ())
    assert client.post(url).status_code == 404
    from types import SimpleNamespace

    monkeypatch.setattr(
        "apps.dashboards.views.recommend_for", lambda user_id: (SimpleNamespace(id=charity.id),)
    )
    assert client.post(url).status_code == 302
    assert Event.objects.filter(user=member, charity=charity, action="reject").exists()


def test_history_identifies_outgoing_links_and_handles_deleted_or_unsafe_links(client):
    member = UserFactory()
    charity = CharityFactory(name="Helpful charity")
    donate = LinkFactory(charity=charity, kind="website_donate", url="https://example.org/donate")
    deleted = LinkFactory(charity=charity, kind="website_about", url="https://example.org/about")
    unsafe = LinkFactory(charity=charity, kind="website_contact", url="javascript:alert(1)")
    for link in (donate, deleted, unsafe):
        Event.objects.create(user=member, charity=charity, link=link, action="link_click")
    deleted.delete()
    client.force_login(member)

    html = client.get(reverse("dashboards:dashboard")).content.decode()

    assert "Donate page" in html
    assert "https://example.org/donate" in html
    assert reverse("charities:link", args=[charity.id, donate.id]) in html
    assert html.count("Clicked a link (no longer available)") == 2
    assert "javascript:alert" not in html


def test_browsing_recommendation_rejection_and_history_through_real_routes(client, settings):
    """A member's actual visits drive recommendations and can be hidden."""
    settings.RECOMMENDATIONS_MIN_HISTORY = 1
    member = UserFactory()
    charity = CharityFactory(name="Community charity", is_visible=True)
    link = LinkFactory(charity=charity, url="https://example.org/donate")
    client.force_login(member)

    assert client.get(reverse("charities:detail", args=[charity.id])).status_code == 200
    assert client.get(reverse("charities:link", args=[charity.id, link.id])).url == link.url
    visit = Event.objects.get(user=member, charity=charity, action="view")
    click = Event.objects.get(user=member, charity=charity, action="link_click")
    dashboard_url = reverse("dashboards:dashboard")
    html = client.get(dashboard_url).content.decode()
    reject_url = reverse("dashboards:reject", args=[charity.id])
    assert reject_url in html
    assert "https://example.org/donate" in html

    assert client.post(reject_url).status_code == 302
    assert Event.objects.filter(user=member, charity=charity, action="reject").exists()
    assert reject_url not in client.get(dashboard_url).content.decode()

    assert client.post(reverse("dashboards:hide", args=[click.id])).status_code == 302
    click.refresh_from_db()
    visit.refresh_from_db()
    assert click.hidden_by_user and not visit.hidden_by_user
    assert "https://example.org/donate" not in client.get(dashboard_url).content.decode()
    assert client.post(reverse("dashboards:clear-history")).status_code == 302
    visit.refresh_from_db()
    assert visit.hidden_by_user
    assert "Your charity activity will appear here" in client.get(dashboard_url).content.decode()
