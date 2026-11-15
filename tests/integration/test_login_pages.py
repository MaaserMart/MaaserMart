"""Local-only login pages (local/login-pages branch)."""

from unittest import mock

import pytest
from django.contrib.auth import SESSION_KEY

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


# --- pinning each view's behaviour (review of the pages, S1) -----------------


def post_login(client, username="member1", password=DEFAULT_PASSWORD, **extra):
    return client.post("/accounts/login/", {"username": username, "password": password, **extra})


def test_right_password_redirects_and_logs_in(client, member):
    response = post_login(client)
    assert response.status_code == 302
    assert response.url == "/"
    assert int(client.session[SESSION_KEY]) == member.pk


def test_right_password_follows_next(client, member):
    response = post_login(client, next="/charity/12/")
    assert response.url == "/charity/12/"


@pytest.mark.parametrize("next_url", ["//evil.com/", "https://evil.com/", "/\\evil.com"])
def test_an_unsafe_next_goes_home_instead(client, member, next_url):
    assert post_login(client, next=next_url).url == "/"


def test_wrong_password_shows_the_message_and_does_not_log_in(client, member):
    response = post_login(client, password="wrong")
    assert response.status_code == 200
    assert b"Wrong username or password." in response.content
    assert SESSION_KEY not in client.session


def test_unknown_username_gets_the_same_answer_as_a_wrong_password(client, member):
    known = post_login(client, password="wrong")
    unknown = post_login(client, username="nobody", password="wrong")
    assert unknown.status_code == known.status_code
    assert b"Wrong username or password." in unknown.content


def test_wrong_password_keeps_the_typed_username(client, member):
    assert b'value="member1"' in post_login(client, password="wrong").content


def test_fifth_failure_shows_the_locked_message(client, member):
    for _ in range(4):
        post_login(client, password="wrong")
    response = post_login(client, password="wrong")
    assert b"locked for one hour" in response.content


def test_blank_fields_ask_for_both(client, member):
    response = post_login(client, password="")
    assert b"Enter your username and password." in response.content


def test_rate_limited_login_returns_429(client, member):
    with mock.patch("apps.accounts.login.take_token", return_value=False):
        response = post_login(client)
    assert response.status_code == 429
    assert SESSION_KEY not in client.session


def test_logout_logs_out_and_goes_home(client, member):
    client.force_login(member)
    response = client.post("/accounts/logout/")
    assert response.url == "/"
    assert SESSION_KEY not in client.session


def test_logout_by_get_is_refused_and_keeps_you_logged_in(client, member):
    client.force_login(member)
    assert client.get("/accounts/logout/").status_code == 405
    assert int(client.session[SESSION_KEY]) == member.pk


def test_chooser_sends_a_logged_out_visitor_to_login(client):
    response = client.get("/accounts/choose-dashboard/")
    assert response.status_code == 302
    assert response.url == "/accounts/login/?next=/accounts/choose-dashboard/"


def test_chooser_lists_only_my_roles(client, member):
    RoleAssignmentFactory(user=member, role="rabbi")
    RoleAssignmentFactory(user=UserFactory(), role="charity_owner")
    client.force_login(member)
    content = client.get("/accounts/choose-dashboard/").content
    assert b"Member" in content
    assert b"Rabbi" in content
    assert b"Charity owner" not in content


def test_chooser_labels_admin(client):
    admin = UserFactory(is_staff=True)
    RoleAssignmentFactory(user=admin)
    client.force_login(admin)
    content = client.get("/accounts/choose-dashboard/").content
    assert b"Member" in content
    assert b"Admin" in content
