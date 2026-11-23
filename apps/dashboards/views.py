"""Role dashboards (§6.2.1). Only the admin's exists so far."""

from django.contrib import admin
from django.http import Http404
from django.shortcuts import render
from django.views.decorators.http import require_GET

from apps.approvals import services as approvals


@require_GET
def admin_dashboard_view(request):
    """Links to the approval queue and Django admin (§6.2.13.1). Admins only; else 404."""
    if not (request.user.is_authenticated and request.user.is_admin):
        raise Http404
    context = {
        # Django admin's header, nav and styles, so the dashboard looks like the rest of it.
        **admin.site.each_context(request),
        "title": "Admin dashboard",
        "pending_count": approvals.pending_count(),
    }
    return render(request, "dashboards/admin.html", context)
