"""Per-client rate limiting with a token bucket (D-YOSEF-accounts-login).

A bucket holds `capacity` tokens and gains one every `refill_seconds`. Each
request spends one; with none left the request is refused. Buckets live in the
shared cache (D-YOSEF-shared-cache), so every Gunicorn worker sees the same count.
The visitor's address comes from `common.clients`, shared with support (D-078).
"""

import hashlib
import time

from django.core.cache import cache

from common.clients import client_ip, client_network

__all__ = ["client_ip", "client_network", "take_token"]


def _now():
    return time.time()


def take_token(key, capacity, refill_seconds):
    """Spend one token from the bucket `key`. Return False if it is empty."""
    cache_key = "ratelimit:" + hashlib.sha256(key.encode()).hexdigest()
    now = _now()
    tokens, last = cache.get(cache_key, (capacity, now))
    tokens = min(capacity, tokens + (now - last) / refill_seconds)
    allowed = tokens >= 1
    if allowed:
        tokens -= 1
    # Not atomic: two requests at the same instant may both spend the same token.
    # An idle bucket refills completely in capacity * refill_seconds, so the entry
    # can expire then; a missing entry means a full bucket.
    cache.set(cache_key, (tokens, now), timeout=int(capacity * refill_seconds) + 1)
    return allowed
