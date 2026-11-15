"""Per-client rate limiting with a token bucket (D-YOSEF-accounts-login).

A bucket holds `capacity` tokens and gains one every `refill_seconds`. Each
request spends one; with none left the request is refused. Buckets live in the
shared cache (D-YOSEF-shared-cache), so every Gunicorn worker sees the same count.
"""

import hashlib
import ipaddress
import time

from django.conf import settings
from django.core.cache import cache


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


def client_ip(request):
    """The visitor's IP address.

    Behind Caddy, REMOTE_ADDR is Caddy's own address and the visitor's is the
    last entry Caddy appended to X-Forwarded-For. The header is believed only
    when the request comes from a trusted proxy; anyone else could send a fake
    one to get a fresh bucket on every request.
    """
    remote = request.META.get("REMOTE_ADDR", "")
    if remote not in settings.TRUSTED_PROXY_IPS:
        return remote
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    last = forwarded.split(",")[-1].strip()
    try:
        return str(ipaddress.ip_address(last))
    except ValueError:
        return remote
