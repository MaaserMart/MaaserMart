"""Case-insensitive login through CaseInsensitiveModelBackend (D-032, D-YOSEF-accounts-login)."""

import pytest
from django.contrib.auth import authenticate
from django.contrib.auth.hashers import make_password
from django.db import connection
from django.test.utils import CaptureQueriesContext

from tests.factories import UserFactory
from tests.factories.accounts import DEFAULT_PASSWORD

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("typed", ["Yosef", "yosef", "YOSEF", "yOsEf"])
def test_any_case_of_the_username_logs_in(typed):
    user = UserFactory(username="Yosef")
    assert authenticate(username=typed, password=DEFAULT_PASSWORD) == user


@pytest.mark.parametrize(
    "typed",
    [
        "yoosef",  # extra letter
        "yose",  # missing letter
        "yosef1",  # extra digit
        " yosef",  # leading space
        "yosef ",  # trailing space
        "yos ef",  # space inside
        "yosеf",  # Cyrillic "е" that looks like a Latin "e"
        "",  # empty
        "y" * 10_000,  # absurdly long
        "' OR 1=1 --",  # SQL injection attempt
        "%",  # SQL wildcard
        "yos_f",  # SQL single-character wildcard
    ],
)
def test_a_username_that_only_looks_close_does_not_log_in(typed):
    UserFactory(username="Yosef")
    assert authenticate(username=typed, password=DEFAULT_PASSWORD) is None


def test_each_username_logs_in_to_its_own_account():
    yosef = UserFactory(username="Yosef")
    yosef2 = UserFactory(username="yosef2")
    assert authenticate(username="YOSEF", password=DEFAULT_PASSWORD) == yosef
    assert authenticate(username="YOSEF2", password=DEFAULT_PASSWORD) == yosef2


def test_right_username_with_another_users_password_fails():
    UserFactory(username="yosef")
    UserFactory(username="shaul", password=make_password("shauls-password"))
    assert authenticate(username="yosef", password="shauls-password") is None


def test_wrong_password_fails():
    UserFactory(username="yosef")
    assert authenticate(username="yosef", password="wrong") is None


def test_unknown_username_fails():
    assert authenticate(username="nobody", password=DEFAULT_PASSWORD) is None


def test_inactive_user_cannot_log_in():
    UserFactory(username="yosef", is_active=False)
    assert authenticate(username="yosef", password=DEFAULT_PASSWORD) is None


def test_missing_password_fails_without_a_query():
    UserFactory(username="yosef")
    with CaptureQueriesContext(connection) as queries:
        assert authenticate(username="yosef", password=None) is None
    assert len(queries) == 0


def test_lookup_is_one_query_on_lower_username():
    """LOWER(username) is what user_username_ci_uniq indexes; UPPER would scan the table."""
    UserFactory(username="yosef")
    with CaptureQueriesContext(connection) as queries:
        authenticate(username="Yosef", password=DEFAULT_PASSWORD)
    assert len(queries) == 1
    assert 'LOWER("accounts_user"."username")' in queries[0]["sql"]
