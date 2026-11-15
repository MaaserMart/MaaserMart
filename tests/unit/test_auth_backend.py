"""Case-insensitive login through CaseInsensitiveModelBackend (D-032, D-YOSEF-accounts-login)."""

import pytest
from django.contrib.auth import authenticate
from django.db import connection
from django.test.utils import CaptureQueriesContext

from tests.factories import UserFactory
from tests.factories.accounts import DEFAULT_PASSWORD

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("typed", ["Yosef", "yosef", "YOSEF", "yOsEf"])
def test_any_case_of_the_username_logs_in(typed):
    user = UserFactory(username="Yosef")
    assert authenticate(username=typed, password=DEFAULT_PASSWORD) == user


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
