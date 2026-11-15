"""attempt_login and the 5-tries, 1-hour lockout (§6.2.1.8, D-YOSEF-accounts-login)."""

from contextlib import contextmanager
from datetime import timedelta
from unittest import mock

import pytest
from django.contrib.auth import SESSION_KEY
from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory
from django.utils import timezone

from apps.accounts.login import LoginResult, attempt_login, is_locked_out
from tests.factories import UserFactory
from tests.factories.accounts import DEFAULT_PASSWORD

pytestmark = pytest.mark.django_db

OK = LoginResult.OK
WRONG = LoginResult.WRONG_CREDENTIALS
LOCKED = LoginResult.LOCKED_OUT


def new_request():
    request = RequestFactory().post("/accounts/login/")
    request.session = SessionStore()
    return request


def try_login(username, password=DEFAULT_PASSWORD, request=None):
    result, _user = attempt_login(request or new_request(), username, password)
    return result


def fail(username, times):
    return [try_login(username, "wrong") for _ in range(times)]


@contextmanager
def minutes_from_now(minutes):
    """Move the cache's clocks ahead: tz_now() decides expiry, time.time() sets it."""
    later = timezone.now() + timedelta(minutes=minutes)
    with (
        mock.patch("django.core.cache.backends.db.tz_now", return_value=later),
        mock.patch("time.time", return_value=later.timestamp()),
    ):
        yield


@pytest.fixture
def yosef():
    return UserFactory(username="Yosef")


# --- what should log in ------------------------------------------------------


def test_right_password_logs_in_and_starts_a_session(yosef):
    request = new_request()
    result, user = attempt_login(request, "yosef", DEFAULT_PASSWORD)
    assert result is OK
    assert user == yosef
    assert request.session[SESSION_KEY] == str(yosef.pk)


def test_four_failures_then_the_right_password_still_logs_in(yosef):
    assert fail("yosef", 4) == [WRONG] * 4
    assert try_login("yosef") is OK


def test_a_success_resets_the_count(yosef):
    fail("yosef", 4)
    try_login("yosef")
    assert fail("yosef", 4) == [WRONG] * 4
    assert try_login("yosef") is OK


def test_the_lock_ends_after_an_hour(yosef):
    fail("yosef", 5)
    with minutes_from_now(61):
        assert try_login("yosef") is OK


def test_failures_older_than_an_hour_are_forgotten(yosef):
    fail("yosef", 4)
    with minutes_from_now(61):
        assert fail("yosef", 1) == [WRONG]
        assert try_login("yosef") is OK


def test_a_count_that_expires_mid_update_restarts_at_one(yosef):
    with mock.patch("apps.accounts.login.cache.incr", side_effect=ValueError):
        assert fail("yosef", 1) == [WRONG]
    assert fail("yosef", 3) == [WRONG] * 3
    assert try_login("yosef") is OK


def test_one_users_lock_does_not_lock_another_user(yosef):
    UserFactory(username="shaul")
    fail("yosef", 5)
    assert try_login("shaul") is OK


# --- what should NOT log in --------------------------------------------------


def test_the_first_four_failures_only_say_wrong_credentials(yosef):
    assert fail("yosef", 4) == [WRONG] * 4
    assert is_locked_out("yosef") is False


def test_the_fifth_failure_locks_and_says_so(yosef):
    assert fail("yosef", 5) == [WRONG] * 4 + [LOCKED]
    assert is_locked_out("yosef") is True


def test_while_locked_the_right_password_is_refused(yosef):
    fail("yosef", 5)
    request = new_request()
    result, user = attempt_login(request, "yosef", DEFAULT_PASSWORD)
    assert (result, user) == (LOCKED, None)
    assert SESSION_KEY not in request.session


def test_while_locked_the_password_is_never_checked(yosef):
    fail("yosef", 5)
    with mock.patch("apps.accounts.login.authenticate") as authenticate:
        try_login("yosef")
    authenticate.assert_not_called()


def test_still_locked_just_before_the_hour_is_up(yosef):
    fail("yosef", 5)
    with minutes_from_now(59):
        assert try_login("yosef") is LOCKED


def test_changing_the_case_does_not_reset_the_count(yosef):
    for typed in ["yosef", "Yosef", "YOSEF", "yOsEf"]:
        try_login(typed, "wrong")
    assert try_login("YoSeF", "wrong") is LOCKED
    assert try_login("yosef") is LOCKED


def test_wrong_password_does_not_start_a_session(yosef):
    request = new_request()
    attempt_login(request, "yosef", "wrong")
    assert SESSION_KEY not in request.session


def test_an_unknown_username_is_counted_the_same_way():
    """Otherwise "never locks" would reveal that the username doesn't exist."""
    assert fail("nobody", 5) == [WRONG] * 4 + [LOCKED]


def test_a_huge_username_is_counted_without_crashing():
    assert fail("y" * 10_000, 5) == [WRONG] * 4 + [LOCKED]
