"""Page logic for the charities app."""

from __future__ import annotations

import logging

from django.http import Http404, HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import render

from apps.events.services import record_event

from .filters import keep_known_ids, requested_numbers
from .repositories import DjangoCharityRepository, DjangoFilterOptionsRepository
from .search import search_form
from .services import (
    Page,
    filter_form,
    get_charity_page,
    get_link_url,
    list_charities,
    list_domains,
    list_locations,
    list_rabbis,
)
from .sorting import sort_form
from .state import PageState

logger = logging.getLogger(__name__)


def listing(request: HttpRequest) -> HttpResponse:
    """Render the paginated list of charities, searched, narrowed and ordered as chosen."""
    # The whole address as one value; every form below reads its slice of it (D-068).
    state = PageState.from_query(request.GET)
    options_repository = DjangoFilterOptionsRepository()
    # Keyed by the list each group draws from, not by URL parameter.
    options = {
        "domains": list_domains(options_repository),
        "locations": list_locations(options_repository),
        "rabbis": list_rabbis(options_repository),
    }
    # A ticked id that names no row is not a filter (D-045), so the lists are
    # read before the filters are settled rather than after the page is counted.
    state = state.replaced(filters=keep_known_ids(state.filters, options))
    page: Page = list_charities(
        # published_only stays False until the admin approval queue publishes
        # charities; see D-042.
        DjangoCharityRepository(published_only=False),
        state,
    )
    return render(
        request,
        "charities/listing.html",
        {
            "page": page,
            "form": filter_form(
                page.state.filters,
                options,
                # Passed so the sidebar can say when a value was clamped into range.
                requested=requested_numbers(request.GET),
            ),
            "sort_form": sort_form(page.state.sort),
            "search_form": search_form(page.state.search),
        },
    )


def _actor_id(request: HttpRequest) -> int | None:
    """The signed-in user's id, or None for a visitor (§5.2.17 allows both)."""
    return request.user.id if request.user.is_authenticated else None


def _count_visit(charity_id: int, action: str, **context) -> None:
    """Write one visit/click EVENT, and never let that write fail the page.

    §6.2.7 asks for exactly this: `record_event` is bookkeeping, so "Failed writes
    do not fail the page". `record_event` raises a `ValueError` when a reference
    does not exist (audit B6), and a visitor whose account was deleted mid-session
    is enough to trigger that — the charity is still there to show, and losing the
    count is cheaper than a 500.
    """
    try:
        record_event(charity_id, action, **context)
    except ValueError:
        logger.warning(
            "visit not counted: charity_id=%s action=%s context=%s",
            charity_id,
            action,
            context,
            exc_info=True,
        )


def detail(request: HttpRequest, charity_id: int) -> HttpResponse:
    """§6.2.7's charity page: everything known about one charity.

    The visit is recorded as a `view` EVENT (§5.2.21's visit count, §6.2.7's
    "writes events"), which is what makes the listing's popular and trending
    orders read real traffic instead of only seeded rows (audit M4).
    """
    charity = get_charity_page(
        # published_only stays False until the approval queue publishes
        # charities, for the same reason as the listing (D-042).
        DjangoCharityRepository(published_only=False),
        charity_id,
    )
    if charity is None:
        raise Http404("No charity with that id")
    _count_visit(charity_id, "view", user_id=_actor_id(request))
    return render(request, "charities/detail.html", {"charity": charity})


def link_redirect(request: HttpRequest, charity_id: int, link_id: int) -> HttpResponse:
    """Count a click on a charity's outbound link, then send the visitor there.

    §5.2.21 derives "link clicks" from EVENT, and §6.2.7 says the charity page
    writes events; without this, a click on a donate link is invisible (audit M4).
    """
    url = get_link_url(DjangoCharityRepository(published_only=False), charity_id, link_id)
    if url is None:
        raise Http404("No such link")
    _count_visit(charity_id, "link_click", link_id=link_id, user_id=_actor_id(request))
    return HttpResponseRedirect(url)
