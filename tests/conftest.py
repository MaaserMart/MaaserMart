"""Test-wide fixtures."""

import pytest


@pytest.fixture(autouse=True)
def _empty_cache():
    """Every test starts with a cold options cache.

    The filter option lists are cached for a minute (audit P1); without this, a
    domain created in one test would be invisible to the next because the cache
    outlives the transaction, and a test that never touches the cache would run
    on another test's leftovers.
    """
    from django.core.cache import caches

    caches["options"].clear()
    yield
    caches["options"].clear()
