"""Page logic for the charities app."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from .repositories import DjangoCharityRepository
from .services import Page, list_charities


def _positive_int(raw: str | None) -> int | None:
    """Read an optional positive whole number, treating junk as absent."""
    if raw is None:
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    return value if value > 0 else None


def listing(request: HttpRequest) -> HttpResponse:
    """Render the paginated list of charities."""
    page: Page = list_charities(
        # published_only stays False until the admin approval queue publishes
        # charities; see D-042.
        repository=DjangoCharityRepository(published_only=False),
        page=_positive_int(request.GET.get("page")),
        page_size=_positive_int(request.GET.get("per_page")),
    )
    return render(request, "charities/listing.html", {"page": page})
