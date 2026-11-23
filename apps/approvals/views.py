"""The admin approval queue (§6.2.13, §7.1.6). Admins only; anyone else gets 404."""

from django.contrib import admin, messages
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
    context = {
        # Django admin's header, nav and styles, so the queue looks like the rest of it.
        **admin.site.each_context(request),
        "title": "Approval queue",
        "requests": services.get_requests(),
    }
    return render(request, "approvals/queue.html", context)


@require_POST
def decide_view(request, request_id):
    _require_admin(request)
    decision = request.POST.get("decision")
    if decision not in ("approve", "reject"):
        return HttpResponseBadRequest("Choose approve or reject.")
    outcome = services.decide_request(request_id, decision == "approve", request.user)
    done = "Approved." if decision == "approve" else "Rejected."
    if outcome is services.DecideOutcome.DONE:
        messages.success(request, done)
    elif outcome is services.DecideOutcome.DONE_EMAIL_FAILED:
        messages.warning(request, f"{done} The email to the applicant didn't send; write to them.")
    else:
        messages.error(request, DECIDE_MESSAGES[outcome])
    return redirect("approvals:queue")
