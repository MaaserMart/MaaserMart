"""Page logic for the charities app."""

from __future__ import annotations

import logging

from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.db import DatabaseError
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect, render, resolve_url
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.events.services import record_event

from .filters import keep_known_ids, requested_numbers
from .forms import ReviewForm
from .repositories import DjangoCharityRepository, DjangoFilterOptionsRepository
from .search import search_form
from .services import (
    Page,
    filter_form,
    get_charity_page,
    get_link_url,
    get_user_review,
    list_charities,
    list_domains,
    list_locations,
    list_rabbis,
    save_review,
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
    count is cheaper than a 500. Database write failures are likewise logged
    without preventing the page or redirect from being served.
    """
    try:
        record_event(charity_id, action, **context)
    except (ValueError, DatabaseError):
        logger.warning(
            "visit not counted: charity_id=%s action=%s context=%s",
            charity_id,
            action,
            context,
            exc_info=True,
        )


def _charity_page(charity_id: int):
    """Use the same publication policy for reading and submitting a review."""
    charity = get_charity_page(DjangoCharityRepository(published_only=False), charity_id)
    if charity is None:
        raise Http404("No charity with that id")
    return charity


def _review_context(request: HttpRequest, charity, form=None):
    review = get_user_review(request.user, charity.id) if request.user.is_authenticated else None
    if form is None and request.user.is_authenticated:
        form = ReviewForm(
            initial={"rating": review.rating, "body": review.body} if review else None
        )
    return {
        "charity": charity,
        "review_form": form,
        "own_review": review,
        "login_url": resolve_url(settings.LOGIN_URL),
    }


def detail(request: HttpRequest, charity_id: int) -> HttpResponse:
    """§6.2.7's charity page: everything known about one charity.

    The visit is recorded as a `view` EVENT (§5.2.21's visit count, §6.2.7's
    "writes events"), which is what makes the listing's popular and trending
    orders read real traffic instead of only seeded rows (audit M4).
    """
    charity = _charity_page(charity_id)
    _count_visit(charity_id, "view", user_id=_actor_id(request))
    return render(request, "charities/detail.html", _review_context(request, charity))


@require_POST
def review(request: HttpRequest, charity_id: int) -> HttpResponse:
    """Save one review per member and charity; a subsequent submission edits it."""
    detail_url = reverse("charities:detail", args=[charity_id])
    if not request.user.is_authenticated:
        return redirect_to_login(detail_url)
    charity = _charity_page(charity_id)
    form = ReviewForm(request.POST)
    if not form.is_valid():
        return render(
            request, "charities/detail.html", _review_context(request, charity, form), status=400
        )
    save_review(request.user, charity_id, **form.cleaned_data)
    return redirect(f"{detail_url}#reviews-heading")


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
