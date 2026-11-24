"""The base template and nav bar (design doc §7.2, D-026, D-029, D-037, audit B1, A3)."""

import re

import pytest
from django.conf import settings

from tests.factories import UserFactory
from tests.support.css import value

pytestmark = pytest.mark.django_db


def test_root_redirects_to_the_charity_listing(client):
    """D-028: now that the listing exists, `/` redirects to it."""
    response = client.get("/")

    assert response.status_code == 302
    assert response.headers["Location"] == "/charity/"


def test_every_nav_link_answers(client):
    """The nav promises nothing that 404s (audit B1): each nav href must resolve."""
    html = client.get("/charity/").content.decode()
    nav = html[html.index('class="nav"') :]
    nav = nav[: nav.index("</nav>")]
    hrefs = re.findall(r'href="(/[^"]+)"', nav)

    assert hrefs  # the nav is not empty
    for path in hrefs:
        response = client.get(path)
        assert response.status_code in (200, 302), path


def test_home_page_shows_nav_and_local_scripts(client):
    html = client.get("/charity/").content.decode()

    assert 'href="/charity/"' in html
    # A route with no pattern yet is not advertised at all (B1).
    assert 'href="/dashboard/"' not in html
    assert 'href="/accounts/login/"' not in html
    assert "/static/vendor/htmx-2.0.4.min.js" in html
    assert "/static/vendor/alpinejs-3.14.8.min.js" in html
    assert "unpkg.com" not in html


def test_logged_in_nav_shows_no_login_or_signup(client):
    """D-033: logged in, the auth links are gone (the logout POST is unshipped)."""
    client.force_login(UserFactory())
    html = client.get("/charity/").content.decode()

    assert 'href="/accounts/login/"' not in html
    assert 'href="/accounts/signup/"' not in html
    assert 'action="/accounts/logout/"' not in html  # no pattern yet, so no form


def test_nav_is_pinned_to_the_top():
    """D-037: the nav is sticky, so it stays visible while the page scrolls.

    The rule lives in the stylesheet the page loads, not in an inline <style>
    block, so this resolves the property for `.nav` the way a browser would
    (audit T2): a later block overriding `position` would fail this test, where
    a regex for the declaration would pass.
    """
    css = (settings.BASE_DIR / "static" / "css" / "site.css").read_text(encoding="utf-8")

    assert value(css, ".nav", "position") == "sticky"


def test_nav_is_a_full_width_bar_above_the_content(client):
    """The bar spans the viewport and sits before <main>, so it never crowds the page."""
    html = client.get("/charity/").content.decode()

    assert '<nav class="nav"' in html
    assert html.index('class="nav"') < html.index('<main id="main"')


def test_the_skip_link_is_the_first_thing_for_a_keyboard_user(client):
    """A3: 'Skip to content' targets <main> and comes before the nav in source order."""
    html = client.get("/charity/").content.decode()

    assert 'class="skip-link" href="#main"' in html
    assert 'id="main"' in html
    assert html.index("skip-link") < html.index('<nav class="nav"')


def test_the_main_nav_has_a_landmark_label(client):
    html = client.get("/charity/").content.decode()

    assert '<nav class="nav" aria-label="Main">' in html


def test_a_404_serves_the_friendly_template(client):
    response = client.get("/no/such/page/")

    assert response.status_code == 404
    assert "Page not found" in response.content.decode()
