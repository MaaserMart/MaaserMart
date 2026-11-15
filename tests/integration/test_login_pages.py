"""Local-only login pages (local/login-pages branch)."""

import pytest

from tests.factories import RoleAssignmentFactory, UserFactory
from tests.factories.accounts import DEFAULT_PASSWORD

pytestmark = pytest.mark.django_db


@pytest.fixture
def member():
    user = UserFactory(username="member1")
    RoleAssignmentFactory(user=user)
    return user


def test_logged_in_user_opening_login_is_sent_on(client, member):
    client.force_login(member)
    response = client.get("/accounts/login/")
    assert response.status_code == 302
    assert response.url == "/"


def test_logged_in_user_opening_login_follows_a_safe_next(client, member):
    client.force_login(member)
    response = client.get("/accounts/login/?next=/charity/12/")
    assert response.url == "/charity/12/"


def test_logged_in_user_stays_logged_in_after_opening_login(client, member):
    client.force_login(member)
    client.get("/accounts/login/")
    assert client.get("/accounts/choose-dashboard/").status_code == 200


def test_logged_out_visitor_sees_the_form(client):
    response = client.get("/accounts/login/")
    assert response.status_code == 200
    assert b'name="password"' in response.content


def test_logged_in_user_can_still_post_to_log_in_as_someone_else(client, member):
    other = UserFactory(username="shaul")
    client.force_login(member)
    response = client.post("/accounts/login/", {"username": "shaul", "password": DEFAULT_PASSWORD})
    assert response.status_code == 302
    assert int(client.session["_auth_user_id"]) == other.pk
