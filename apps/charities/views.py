"""Page logic for the charities app."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from .filters import from_query as read_filters
from .filters import keep_known_ids, requested_numbers
from .repositories import DjangoCharityRepository, DjangoFilterOptionsRepository
from .search import from_query as read_search
from .search import search_form
from .services import (
    Page,
    filter_form,
    list_charities,
    list_domains,
    list_locations,
    list_rabbis,
)
from .sorting import from_query as read_sort
from .sorting import sort_form


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
    """Render the paginated list of charities, searched, narrowed and ordered as chosen."""
    sort = read_sort(request.GET)
    search = read_search(request.GET)
    options_repository = DjangoFilterOptionsRepository()
    # Keyed by the list each group draws from, not by URL parameter.
    options = {
        "domains": list_domains(options_repository),
        "locations": list_locations(options_repository),
        "rabbis": list_rabbis(options_repository),
    }
    # A ticked id that names no row is not a filter (D-045), so the lists are
    # read before the filters are settled rather than after the page is counted.
    filters = keep_known_ids(read_filters(request.GET), options)
    page: Page = list_charities(
        # published_only stays False until the admin approval queue publishes
        # charities; see D-042.
        repository=DjangoCharityRepository(published_only=False),
        filters=filters,
        sort=sort,
        page=_positive_int(request.GET.get("page")),
        page_size=_positive_int(request.GET.get("page_size")),
        search=search,
    )
    form = filter_form(
        filters,
        options,
        # Passed so the sidebar can say when a value was clamped into range.
        requested=requested_numbers(request.GET),
    )
    return render(
        request,
        "charities/listing.html",
        {
            "page": page,
            "form": form,
            "sort_form": sort_form(sort),
            "search_form": search_form(search),
        },
    )
