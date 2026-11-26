"""Visitor addresses used for rate limits (D-078).

Behind Caddy, REMOTE_ADDR is the proxy and the visitor is the last entry in
X-Forwarded-For. The header is believed only from a trusted proxy, and an IPv6
visitor is keyed by their /64 because a household usually owns the whole range.
"""

from __future__ import annotations

import ipaddress

from django.conf import settings


def client_ip(request) -> str:
    remote = request.META.get("REMOTE_ADDR", "")
    if remote not in settings.TRUSTED_PROXY_IPS:
        return remote
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    last = forwarded.split(",")[-1].strip()
    try:
        return str(ipaddress.ip_address(last))
    except ValueError:
        return remote


def client_network(request) -> str:
    ip = client_ip(request)
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return ip
    if address.version == 6:
        return str(ipaddress.ip_network(f"{address}/64", strict=False))
    return ip
