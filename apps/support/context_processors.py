"""The nav bar's links, so the template cannot advertise a page that 404s.

The nav is the site's promise about where a visitor can go (D-026 fixes the
paths; D-009 groups them by app). Each entry below names a URL *pattern*, not a
string, so the nav appears the day the page lands and disappears if a route is
renamed — the failure mode the audit found was eight hand-written hrefs of which
seven answered 404 (B1, S4, A1).

This lives in support because §6.1 lets support depend on nothing and the nav
belongs to no single app; `reverse()` needs no dependency at all.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.urls import NoReverseMatch, reverse


@dataclass(frozen=True)
class NavDestination:
    """One link in the nav, already resolved to a path."""

    label: str
    url: str


# §7.2's nav, in the order the bar shows it (D-026, D-027). The account links
# are separate because they change with the session (D-033).
NAV_DESTINATIONS: tuple[tuple[str, str], ...] = (
    ("charities:listing", "Charities"),
    ("charities:add", "Request a charity"),
    ("support:report", "Report a charity"),
    ("tools:index", "Maaser tools"),
    ("dashboards:dashboard", "Dashboard"),
    ("support:help", "Help"),
)

LOGIN_URL_NAME = "accounts:login"
SIGNUP_URL_NAME = "accounts:signup"
LOGOUT_URL_NAME = "accounts:logout"


def _url_of(name: str) -> str | None:
    """The path of a URL pattern, or None while that page does not exist."""
    try:
        return reverse(name)
    except NoReverseMatch:
        return None


def nav(request) -> dict:
    """The nav's destinations for this request.

    A page that has not shipped yet contributes no link at all, rather than a
    link to a 404. The bar is then short, which is honest: the alternative was
    eight destinations and seven dead ends.
    """
    destinations = [
        NavDestination(label=label, url=url)
        for name, label in NAV_DESTINATIONS
        if (url := _url_of(name)) is not None
    ]
    return {
        "nav": {
            "destinations": destinations,
            "login_url": _url_of(LOGIN_URL_NAME),
            "signup_url": _url_of(SIGNUP_URL_NAME),
            "logout_url": _url_of(LOGOUT_URL_NAME),
        }
    }
