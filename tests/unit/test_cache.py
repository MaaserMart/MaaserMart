"""The rate-limit cache is shared through PostgreSQL (D-YOSEF-shared-cache)."""

from datetime import timedelta
from unittest import mock

import pytest
from django.core.cache import caches
from django.core.cache.backends.db import DatabaseCache
from django.db import connection
from django.utils import timezone

pytestmark = pytest.mark.django_db

cache = caches["ratelimit"]


def stored_rows():
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM django_cache")
        return cursor.fetchone()[0]


def test_cache_is_the_database_cache():
    assert isinstance(caches["ratelimit"], DatabaseCache)


def test_a_value_is_stored_in_postgres_not_in_memory():
    assert stored_rows() == 0
    cache.set("login-fails:yosef", 3, timeout=60)
    assert stored_rows() == 1
    assert cache.get("login-fails:yosef") == 3


def test_a_missing_key_returns_nothing():
    assert cache.get("login-fails:nobody") is None


def test_one_key_does_not_return_another_keys_value():
    cache.set("login-fails:yosef", 3, timeout=60)
    assert cache.get("login-fails:Yosef") is None
    assert cache.get("login-fails:yosef2") is None


def test_a_value_is_gone_after_its_timeout():
    cache.set("login-fails:yosef", 3, timeout=60)
    later = timezone.now() + timedelta(seconds=61)
    with mock.patch("django.core.cache.backends.db.tz_now", return_value=later):
        assert cache.get("login-fails:yosef") is None


def test_a_value_is_still_there_before_its_timeout():
    cache.set("login-fails:yosef", 3, timeout=60)
    later = timezone.now() + timedelta(seconds=59)
    with mock.patch("django.core.cache.backends.db.tz_now", return_value=later):
        assert cache.get("login-fails:yosef") == 3
