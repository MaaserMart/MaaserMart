"""The admin approval queue (§6.2.13, §7.1.6). Admins only; anyone else gets 404."""

from django.contrib import messages
from django.http import Http404, HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from . import services

DECIDE_MESSAGES = {
    services.DecideOutcome.NOT_FOUND: "That request no longer exists.",
    services.DecideOutcome.ALREADY_DECIDED: "Another admin already decided that request.",
    services.DecideOutcome.NOT_DECIDABLE: "That kind of request can't be decided here yet.",
}


def _require_admin(request):
    """404, not 403, so the queue's address gives nothing away."""
    if not (request.user.is_authenticated and request.user.is_admin):
        raise Http404


@require_GET
def queue_view(request):
    _require_admin(request)
    return render(request, "approvals/queue.html", {"requests": services.get_requests()})


@require_POST
def decide_view(request, request_id):
    _require_admin(request)
    decision = request.POST.get("decision")
    if decision not in ("approve", "reject"):
        return HttpResponseBadRequest("Choose approve or reject.")
    outcome = services.decide_request(request_id, decision == "approve", request.user)
    if outcome is services.DecideOutcome.DONE:
        messages.success(request, "Approved." if decision == "approve" else "Rejected.")
    else:
        messages.error(request, DECIDE_MESSAGES[outcome])
    return redirect("approvals:queue")
