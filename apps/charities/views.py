"""Page logic for the charities app."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from .filters import from_query, requested_numbers
from .repositories import DjangoCharityRepository, DjangoFilterOptionsRepository
from .services import (
    Page,
    filter_form,
    list_charities,
    list_domains,
    list_locations,
    list_rabbis,
)


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
    """Render the paginated list of charities, narrowed by the sidebar's filters."""
    filters = from_query(request.GET)
    options_repository = DjangoFilterOptionsRepository()
    page: Page = list_charities(
        # published_only stays False until the admin approval queue publishes
        # charities; see D-042.
        repository=DjangoCharityRepository(published_only=False),
        page=_positive_int(request.GET.get("page")),
        page_size=_positive_int(request.GET.get("page_size")),
        filters=filters,
    )
    form = filter_form(
        filters,
        {
            # Keyed by the list each group draws from, not by URL parameter.
            "domains": list_domains(options_repository),
            "locations": list_locations(options_repository),
            "rabbis": list_rabbis(options_repository),
        },
        # Passed so the sidebar can say when a value was clamped into range.
        requested=requested_numbers(request.GET),
    )
    return render(request, "charities/listing.html", {"page": page, "form": form})
