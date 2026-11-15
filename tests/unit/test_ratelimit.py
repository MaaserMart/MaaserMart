"""Token-bucket rate limit and the client IP behind Caddy (D-YOSEF-accounts-login)."""

import time
from unittest import mock

import pytest
from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory

from apps.accounts.login import LoginResult, attempt_login, is_locked_out
from apps.accounts.ratelimit import client_ip, take_token
from tests.factories import UserFactory
from tests.factories.accounts import DEFAULT_PASSWORD

pytestmark = pytest.mark.django_db

CADDY = "127.0.0.1"
STRANGER = "203.0.113.9"


class Clock:
    """A clock the test moves by hand."""

    def __init__(self):
        self.now = time.time()

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


@pytest.fixture
def clock():
    c = Clock()
    with mock.patch("apps.accounts.ratelimit._now", c):
        yield c


def spend(n, key="k"):
    return [take_token(key, 20, 3) for _ in range(n)]


def request_from(remote, forwarded=None):
    meta = {"REMOTE_ADDR": remote}
    if forwarded is not None:
        meta["HTTP_X_FORWARDED_FOR"] = forwarded
    request = RequestFactory().post("/accounts/login/", **meta)
    request.session = SessionStore()
    return request


# --- the bucket: allowed -----------------------------------------------------


def test_a_burst_of_twenty_is_allowed(clock):
    assert spend(20) == [True] * 20


def test_one_more_is_allowed_after_three_seconds(clock):
    spend(20)
    clock.advance(3)
    assert spend(1) == [True]


def test_an_idle_minute_refills_the_whole_bucket(clock):
    spend(20)
    clock.advance(60)
    assert spend(20) == [True] * 20


def test_each_key_has_its_own_bucket(clock):
    spend(20, key="a")
    assert spend(1, key="b") == [True]


# --- the bucket: refused -----------------------------------------------------


def test_the_twenty_first_in_a_burst_is_refused(clock):
    assert spend(21) == [True] * 20 + [False]


def test_not_yet_refilled_just_before_three_seconds(clock):
    spend(20)
    clock.advance(2.9)
    assert spend(1) == [False]


def test_a_long_wait_never_fills_past_twenty(clock):
    clock.advance(3600)
    assert spend(21) == [True] * 20 + [False]


def test_refused_requests_do_not_earn_extra_tokens(clock):
    spend(20)
    for _ in range(10):
        clock.advance(0.25)
        spend(1)
    clock.advance(0.51)  # just over 3 seconds since the bucket emptied
    assert spend(2) == [True, False]


# --- client IP: believed -----------------------------------------------------


def test_direct_request_uses_its_own_address():
    assert client_ip(request_from(STRANGER)) == STRANGER


def test_through_caddy_the_forwarded_address_is_used():
    assert client_ip(request_from(CADDY, "198.51.100.7")) == "198.51.100.7"


def test_through_caddy_the_last_forwarded_entry_wins():
    """Earlier entries came from the visitor and can be made up; Caddy adds the last."""
    assert client_ip(request_from(CADDY, "6.6.6.6, 198.51.100.7")) == "198.51.100.7"


def test_ipv6_through_caddy():
    assert client_ip(request_from("::1", "2001:db8::1")) == "2001:db8::1"


# --- client IP: not believed -------------------------------------------------


def test_a_forwarded_header_from_a_stranger_is_ignored():
    assert client_ip(request_from(STRANGER, "198.51.100.7")) == STRANGER


def test_through_caddy_without_a_header_uses_caddys_address():
    assert client_ip(request_from(CADDY)) == CADDY


def test_through_caddy_a_garbage_header_is_ignored():
    assert client_ip(request_from(CADDY, "not-an-ip")) == CADDY


# --- inside attempt_login ----------------------------------------------------


def login_from(ip, password=DEFAULT_PASSWORD, username="yosef"):
    result, _ = attempt_login(request_from(CADDY, ip), username, password)
    return result


def test_the_twenty_first_login_from_one_ip_is_refused_without_a_password_check(clock):
    UserFactory(username="yosef")
    for _ in range(20):
        login_from("198.51.100.7")
    with mock.patch("apps.accounts.login.authenticate") as authenticate:
        assert login_from("198.51.100.7") is LoginResult.RATE_LIMITED
    authenticate.assert_not_called()


def test_another_ip_can_still_log_in(clock):
    UserFactory(username="yosef")
    for _ in range(20):
        login_from("198.51.100.7")
    assert login_from("198.51.100.8") is LoginResult.OK


def test_refused_requests_do_not_count_toward_the_lockout(clock):
    UserFactory(username="yosef")
    for _ in range(20):
        login_from("198.51.100.7", password="wrong", username="other")
    for _ in range(10):
        login_from("198.51.100.7", password="wrong")
    assert is_locked_out("yosef") is False


def test_blank_input_does_not_spend_a_token(clock):
    UserFactory(username="yosef")
    for _ in range(30):
        login_from("198.51.100.7", password="")
    assert login_from("198.51.100.7") is LoginResult.OK
