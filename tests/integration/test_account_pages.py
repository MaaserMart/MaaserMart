"""Existing members can sign in safely and reach their dashboard."""

import pytest
from django.contrib.auth import SESSION_KEY

from tests.factories import RoleAssignmentFactory, UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def member():
    user = UserFactory(username="member")
    RoleAssignmentFactory(user=user)
    return user


def test_login_page_and_successful_case_insensitive_login(client, member):
    assert client.get("/accounts/login/").status_code == 200
    response = client.post("/accounts/login/", {"username": "MEMBER", "password": "password"})
    assert response.url == "/dashboard/"
    assert int(client.session[SESSION_KEY]) == member.pk


def test_failed_login_does_not_authenticate_and_shows_error(client, member):
    response = client.post("/accounts/login/", {"username": "member", "password": "wrong"})
    assert response.status_code == 200
    assert b"Wrong username or password" in response.content
    assert SESSION_KEY not in client.session


@pytest.mark.parametrize(
    ("next_url", "expected"),
    [("/tools/", "/tools/"), ("//evil.example/", "/dashboard/")],
)
def test_login_follows_only_safe_next(client, member, next_url, expected):
    response = client.post(
        "/accounts/login/", {"username": "member", "password": "password", "next": next_url}
    )
    assert response.url == expected


def test_logout_requires_post_and_ends_the_session(client, member):
    client.force_login(member)
    assert client.get("/accounts/logout/").status_code == 405
    assert int(client.session[SESSION_KEY]) == member.pk
    assert client.post("/accounts/logout/").url == "/"
    assert SESSION_KEY not in client.session


def test_chooser_only_shows_the_users_roles(client, member):
    RoleAssignmentFactory(user=member, role="rabbi")
    client.force_login(member)
    response = client.get("/accounts/choose-dashboard/")
    assert b"Member" in response.content
    assert b"Rabbi" in response.content
    assert b"Charity owner" not in response.content
