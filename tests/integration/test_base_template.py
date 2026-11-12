"""The base template and nav bar (design doc §7.2, D-026, D-029, D-037)."""

import re

import pytest

from tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def test_home_page_shows_nav_and_local_scripts(client):
    html = client.get("/").content.decode()

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
    html = client.get("/").content.decode()

    assert 'action="/accounts/logout/"' in html
    assert 'href="/accounts/login/"' not in html


def test_nav_is_pinned_to_the_top(client):
    html = client.get("/").content.decode()

    assert re.search(r"nav\s*\{[^}]*position:\s*sticky", html)
