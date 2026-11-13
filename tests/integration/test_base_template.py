"""The base template and nav bar (design doc §7.2, D-026, D-029, D-037)."""

import re

import pytest
from django.conf import settings

from tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def test_root_redirects_to_the_charity_listing(client):
    """D-028: now that the listing exists, `/` redirects to it."""
    response = client.get("/")

    assert response.status_code == 302
    assert response.headers["Location"] == "/charity/"


def test_home_page_shows_nav_and_local_scripts(client):
    html = client.get("/charity/").content.decode()

    for path in [
        "/charity/",
        "/charity/add/",
        "/support/report/",
        "/tools/",
        "/dashboard/",
        "/support/help/",
        "/accounts/login/",
        "/accounts/signup/",
    ]:
        assert f'href="{path}"' in html
    assert "/static/vendor/htmx-2.0.4.min.js" in html
    assert "/static/vendor/alpinejs-3.14.8.min.js" in html
    assert "unpkg.com" not in html


def test_logged_in_nav_shows_logout_instead_of_login(client):
    client.force_login(UserFactory())
    html = client.get("/charity/").content.decode()

    assert 'action="/accounts/logout/"' in html
    assert 'href="/accounts/login/"' not in html


def test_nav_is_pinned_to_the_top():
    """D-037: the nav is sticky, so it stays visible while the page scrolls.

    The rule lives in the stylesheet the page loads, not in a literal inline
    <style> block, so this reads the CSS rather than the HTML.
    """
    css = (settings.BASE_DIR / "static" / "css" / "site.css").read_text(encoding="utf-8")

    assert re.search(r"\.nav\s*\{[^}]*position:\s*sticky", css)


def test_nav_is_a_full_width_bar_above_the_content(client):
    """The bar spans the viewport and sits before <main>, so it never crowds the page."""
    html = client.get("/charity/").content.decode()

    assert '<nav class="nav">' in html
    assert html.index('class="nav"') < html.index("<main>")
