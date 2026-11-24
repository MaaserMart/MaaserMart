"""Private member dashboard and actions on the current member's activity."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from apps.charities.services import charity_names, history_links
from apps.events.services import get_history, hide_all_history, hide_history, record_event
from apps.recommendations.services import recommend_for
from apps.tools.services import maaser_summary


@login_required
@never_cache
@require_GET
def dashboard(request: HttpRequest) -> HttpResponse:
    history = get_history(request.user.id)
    names = charity_names(item.charity_id for item in history)
    links = history_links(item.link_id for item in history if item.link_id is not None)
    return render(
        request,
        "dashboards/dashboard.html",
        {
            "history": [
                (
                    item,
                    names.get(item.charity_id, "Charity"),
                    links.get((item.charity_id, item.link_id)),
                )
                for item in history
            ],
            "recommendations": recommend_for(request.user.id),
            "summary": maaser_summary(request.user.id),
        },
    )


@login_required
@require_POST
def hide(request: HttpRequest, event_id: int) -> HttpResponse:
    if not hide_history(request.user.id, event_id):
        raise Http404
    messages.success(request, "Activity hidden from your history.")
    return redirect("dashboards:dashboard")


@login_required
@require_POST
def clear_history(request: HttpRequest) -> HttpResponse:
    hide_all_history(request.user.id)
    messages.success(request, "Your history was cleared.")
    return redirect("dashboards:dashboard")


@login_required
@require_POST
def reject(request: HttpRequest, charity_id: int) -> HttpResponse:
    # Only a recommendation currently offered to this member may be rejected.
    if charity_id not in {item.id for item in recommend_for(request.user.id)}:
        raise Http404
    record_event(charity_id, "reject", user_id=request.user.id)
    messages.success(request, "Recommendation removed.")
    return redirect("dashboards:dashboard")
