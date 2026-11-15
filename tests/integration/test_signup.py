"""Member signup with an emailed code (§6.2.2, D-YOSEF-member-signup)."""

import re
from unittest import mock

import pytest
from django.contrib.auth import SESSION_KEY
from django.contrib.auth.hashers import check_password
from django.core import mail
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.accounts import signup
from apps.accounts.models import RoleAssignment, User
from apps.accounts.services import SignupOutcome, submit_member_signup
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db

SIGNUP = "/accounts/signup/"
VERIFY = "/accounts/signup/verify/"
GOOD = {
    "username": "sarah_k",
    "email": "sarah@example.com",
    "password": "a-long-pass-42",
    "agree": "on",
}


def form(**changes):
    data = {**GOOD, **changes}
    return {k: v for k, v in data.items() if v is not None}


def sent_code():
    return re.search(r"\d{6}", mail.outbox[-1].body).group()


def wrong(code):
    """A code one digit off from the right one."""
    return code[:-1] + str((int(code[-1]) + 1) % 10)


@pytest.fixture
def clock():
    """Control the signup clock: clock.now is seconds since the epoch."""

    class Clock:
        now = 1_000_000.0

    with mock.patch.object(signup, "_now", lambda: Clock.now):
        yield Clock


@pytest.fixture
def started(client):
    """A visitor who filled in step 1; returns the emailed code."""
    assert client.post(SIGNUP, GOOD).status_code == 302
    return sent_code()


# --- the happy path ----------------------------------------------------------


def test_step_one_emails_a_code_and_goes_to_the_code_page(client):
    response = client.post(SIGNUP, GOOD)
    assert response.status_code == 302
    assert response.url == VERIFY
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["sarah@example.com"]
    assert re.fullmatch(r"\d{6}", sent_code())


def test_step_one_creates_no_account_yet(client):
    client.post(SIGNUP, GOOD)
    assert not User.objects.filter(username="sarah_k").exists()


def test_right_code_creates_a_member_and_logs_them_in(client, started):
    response = client.post(VERIFY, {"code": started})
    user = User.objects.get(username="sarah_k")
    assert response.status_code == 302
    assert client.session[SESSION_KEY] == str(user.pk)
    assert list(user.role_assignments.values_list("role", flat=True)) == ["member"]
    assert user.email == "sarah@example.com"
    assert user.check_password("a-long-pass-42")


def test_after_signup_the_member_goes_where_login_would(client, started):
    assert client.post(VERIFY, {"code": started}).url == "/"


def test_a_safe_next_is_followed_after_signup(client):
    client.post(SIGNUP, form(next="/charity/12/"))
    response = client.post(VERIFY, {"code": sent_code(), "next": "/charity/12/"})
    assert response.url == "/charity/12/"


def test_an_unsafe_next_is_ignored_after_signup(client):
    client.post(SIGNUP, form(next="https://evil.com/"))
    response = client.post(VERIFY, {"code": sent_code(), "next": "https://evil.com/"})
    assert response.url == "/"


@pytest.mark.parametrize("typed", ["{c}", "{a} {b}", "{a}-{b}", " {c} "])
def test_spaces_and_a_dash_in_the_code_are_fine(client, started, typed):
    code = typed.format(c=started, a=started[:3], b=started[3:])
    assert client.post(VERIFY, {"code": code}).status_code == 302
    assert User.objects.filter(username="sarah_k").exists()


def test_the_page_shows_where_the_code_went_but_not_the_whole_address(client, started):
    page = client.get(VERIFY).content.decode()
    assert "s***@example.com" in page
    assert "sarah@example.com" not in page


def test_the_code_is_never_sent_to_the_browser(client, started):
    assert started not in client.get(VERIFY).content.decode()


def test_the_password_is_never_kept_in_the_session(client, started):
    pending = client.session[signup.SESSION_KEY]
    assert "a-long-pass-42" not in str(pending)
    assert check_password("a-long-pass-42", pending["password_hash"])


# --- step 1: what should be refused ------------------------------------------


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"username": ""}, "username"),
        ({"email": ""}, "email"),
        ({"password": ""}, "password"),
        ({"agree": None}, "agree"),
        ({"email": "sarah@"}, "email"),
        ({"username": "sarah k"}, "username"),  # spaces aren't allowed
        ({"username": "x" * 151}, "username"),
        ({"password": "short1"}, "password"),  # under 8 characters
        ({"password": "password123"}, "password"),  # common
        ({"password": "83920174"}, "password"),  # all digits
        ({"password": "sarah_k1"}, "password"),  # too close to the username
    ],
)
def test_a_bad_form_is_refused_and_sends_nothing(client, changes, field):
    response = client.post(SIGNUP, form(**changes))
    assert response.status_code == 200
    assert field in response.context["form"].errors
    assert mail.outbox == []
    assert signup.SESSION_KEY not in client.session


@pytest.mark.parametrize("taken", ["sarah_k", "Sarah_K", "SARAH_K"])
def test_a_taken_username_in_any_capitals_is_refused(client, taken):
    UserFactory(username=taken)
    response = client.post(SIGNUP, GOOD)
    assert response.context["form"].errors["username"] == ["That username is taken."]
    assert mail.outbox == []


@pytest.mark.parametrize("free", ["sarah_kk", "sara_k", "sarahk"])
def test_a_near_miss_username_is_free(client, free):
    UserFactory(username="sarah_k")
    assert client.post(SIGNUP, form(username=free)).status_code == 302


@pytest.mark.parametrize("taken", ["sarah@example.com", "Sarah@Example.COM"])
def test_a_taken_email_in_any_capitals_is_refused(client, taken):
    UserFactory(email=taken)
    response = client.post(SIGNUP, GOOD)
    assert "already has an account" in response.context["form"].errors["email"][0]
    assert mail.outbox == []


def test_a_near_miss_email_is_free(client):
    UserFactory(email="sarah@example.co")
    assert client.post(SIGNUP, GOOD).status_code == 302


def test_every_field_problem_is_shown_at_once(client):
    UserFactory(username="sarah_k", email="sarah@example.com")
    errors = client.post(SIGNUP, GOOD).context["form"].errors
    assert set(errors) == {"username", "email"}


def test_a_bad_form_never_reaches_the_database(client):
    """Checks up front, cheapest first: a field error stops before any query."""
    client.get(SIGNUP)  # warm the session
    with CaptureQueriesContext(connection) as queries:
        client.post(SIGNUP, form(agree=None))
    assert not any('"accounts_user"' in q["sql"] for q in queries)


def test_username_lookup_uses_the_index(client):
    with CaptureQueriesContext(connection) as queries:
        client.post(SIGNUP, GOOD)
    user_sql = [q["sql"] for q in queries if 'FROM "accounts_user"' in q["sql"]]
    assert user_sql
    assert all("LOWER(" in sql and "UPPER(" not in sql for sql in user_sql)


def test_logged_in_user_opening_signup_is_sent_on(client):
    client.force_login(UserFactory())
    assert client.get(SIGNUP).status_code == 302
    assert client.post(SIGNUP, GOOD).status_code == 302
    assert mail.outbox == []


# --- step 1: limits ------------------------------------------------------------


def test_fifth_signup_from_one_network_is_allowed_and_sixth_is_refused(client):
    for n in range(5):
        response = client.post(SIGNUP, form(username=f"user_n{n}", email=f"n{n}@example.com"))
        assert response.status_code == 302
    response = client.post(SIGNUP, form(username="user_n5", email="n5@example.com"))
    assert response.status_code == 429
    assert len(mail.outbox) == 5


def test_rate_limit_comes_before_any_other_check(client):
    with mock.patch.object(signup, "take_token", return_value=False):
        with CaptureQueriesContext(connection) as queries:
            response = client.post(SIGNUP, form(agree=None))
    assert response.status_code == 429
    assert not any('"accounts_user"' in q["sql"] for q in queries)


def test_third_email_to_one_address_is_sent_and_fourth_is_refused(client):
    for _ in range(3):
        client.post(SIGNUP, GOOD)
    assert len(mail.outbox) == 3
    response = client.post(SIGNUP, GOOD)
    assert response.status_code == 200
    assert "3 codes" in response.context["error"]
    assert len(mail.outbox) == 3


def test_the_email_limit_ignores_capitals(client):
    for _ in range(3):
        client.post(SIGNUP, GOOD)
    client.post(SIGNUP, form(email="SARAH@example.com"))
    assert len(mail.outbox) == 3


def test_a_bad_form_does_not_spend_an_email(client):
    for _ in range(3):
        client.post(SIGNUP, form(agree=None))
    assert client.post(SIGNUP, GOOD).status_code == 302


# --- step 2: what should be refused ------------------------------------------


def test_a_code_one_digit_off_is_refused(client, started):
    response = client.post(VERIFY, {"code": wrong(started)})
    assert response.status_code == 200
    assert "isn't right" in response.context["error"]
    assert not User.objects.filter(username="sarah_k").exists()
    assert SESSION_KEY not in client.session


@pytest.mark.parametrize("code", ["", "12345", "1234567", "abcdef"])
def test_a_malformed_code_is_refused(client, started, code):
    client.post(VERIFY, {"code": code})
    assert not User.objects.filter(username="sarah_k").exists()


def test_the_fourth_wrong_try_still_leaves_one_more(client, started):
    for _ in range(4):
        client.post(VERIFY, {"code": wrong(started)})
    assert client.post(VERIFY, {"code": started}).status_code == 302
    assert User.objects.filter(username="sarah_k").exists()


def test_the_fifth_wrong_try_throws_the_code_away(client, started):
    for _ in range(5):
        response = client.post(VERIFY, {"code": wrong(started)})
    assert "Start again" in response.context["error"]
    assert signup.SESSION_KEY not in client.session
    # Even the right code is now useless.
    assert client.post(VERIFY, {"code": started}).url == SIGNUP
    assert not User.objects.filter(username="sarah_k").exists()


def test_the_code_works_at_fourteen_minutes(client, clock):
    client.post(SIGNUP, GOOD)
    clock.now += 14 * 60
    assert client.post(VERIFY, {"code": sent_code()}).status_code == 302


def test_the_code_fails_at_sixteen_minutes(client, clock):
    client.post(SIGNUP, GOOD)
    clock.now += 16 * 60
    response = client.post(VERIFY, {"code": sent_code()})
    assert "expired" in response.context["error"]
    assert not User.objects.filter(username="sarah_k").exists()


def test_the_code_page_without_a_signup_goes_back_to_step_one(client):
    assert client.get(VERIFY).url == SIGNUP
    assert client.post(VERIFY, {"code": "123456"}).url == SIGNUP


def test_another_browser_cannot_use_my_code(client, started):
    """The code is tied to the session that asked for it."""
    from django.test import Client

    other = Client()
    assert other.post(VERIFY, {"code": started}).url == SIGNUP
    assert not User.objects.filter(username="sarah_k").exists()


def test_someone_taking_the_username_while_the_code_is_out(client, started):
    UserFactory(username="SARAH_K")
    response = client.post(VERIFY, {"code": started})
    assert "Start again" in response.context["error"]
    assert User.objects.filter(username__iexact="sarah_k").count() == 1
    assert SESSION_KEY not in client.session


# --- step 2: a new code ----------------------------------------------------------


def test_a_new_code_replaces_the_old_one(client, started):
    client.post(VERIFY, {"resend": "1"})
    new = sent_code()
    assert len(mail.outbox) == 2
    if new != started:
        client.post(VERIFY, {"code": started})
        assert not User.objects.filter(username="sarah_k").exists()
    assert client.post(VERIFY, {"code": new}).status_code == 302


def test_a_new_code_resets_the_tries_and_the_clock(client, started, clock):
    for _ in range(4):
        client.post(VERIFY, {"code": wrong(started)})
    clock.now += 14 * 60
    client.post(VERIFY, {"resend": "1"})
    clock.now += 14 * 60
    for _ in range(4):
        client.post(VERIFY, {"code": wrong(sent_code())})
    assert client.post(VERIFY, {"code": sent_code()}).status_code == 302


def test_new_codes_count_toward_three_emails_an_hour(client, started):
    client.post(VERIFY, {"resend": "1"})
    client.post(VERIFY, {"resend": "1"})
    response = client.post(VERIFY, {"resend": "1"})
    assert len(mail.outbox) == 3
    assert "3 codes" in response.context["error"]


# --- the service ----------------------------------------------------------------


def test_service_creates_user_and_member_role_together():
    outcome, user = submit_member_signup("dov", "dov@example.com", "hash")
    assert outcome is SignupOutcome.CREATED
    assert RoleAssignment.objects.filter(user=user, role="member").exists()


def test_service_reports_a_taken_username_and_writes_nothing():
    UserFactory(username="DOV", email="someone@example.com")
    outcome, user = submit_member_signup("dov", "dov@example.com", "hash")
    assert (outcome, user) == (SignupOutcome.USERNAME_TAKEN, None)
    assert not User.objects.filter(email="dov@example.com").exists()


def test_service_reports_a_taken_email_and_writes_nothing():
    UserFactory(email="DOV@example.com")
    outcome, _ = submit_member_signup("dov", "dov@example.com", "hash")
    assert outcome is SignupOutcome.EMAIL_TAKEN
    assert not User.objects.filter(username="dov").exists()


def test_service_leaves_no_user_if_the_role_cannot_be_written():
    with mock.patch.object(RoleAssignment.objects, "create", side_effect=RuntimeError):
        with pytest.raises(RuntimeError):
            submit_member_signup("dov", "dov@example.com", "hash")
    assert not User.objects.filter(username="dov").exists()


# --- small helpers -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("email", "shown"),
    [("sarah@example.com", "s***@example.com"), ("a@b.co", "a***@b.co")],
)
def test_masked_email(email, shown):
    assert signup.masked_email(email) == shown
