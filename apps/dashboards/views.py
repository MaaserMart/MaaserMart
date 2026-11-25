"""Role dashboards (§6.2.1): the admin's, the rabbi's and the charity owner's so far."""

from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods

from apps.accounts import services as accounts
from apps.approvals import services as approvals
from apps.charities import services as charities

from .forms import HaskamaForm

# `?from=charity` sends the rabbi back to the charity page after saving. A
# fixed word, never a URL, so it cannot be turned into an open redirect.
FROM_CHARITY = "charity"


@require_GET
@login_required
def dashboard_view(request):
    """The nav's "Dashboard": the user's own dashboard, the chooser, or their application.

    Each dashboard checks the role again on every request, so typing another
    role's address gets a 404, whatever the nav showed.
    """
    return redirect(accounts.dashboard_for(request.user))


@require_GET
def owner_dashboard_view(request):
    """The charities this owner manages (§7.1.4). Approved charity owners only; else 404."""
    if not (request.user.is_authenticated and accounts.is_charity_owner(request.user.id)):
        raise Http404
    owned = []
    for charity_id in accounts.owned_charity_ids(request.user.id):
        name = charities.get_charity_name(charity_id)
        if name is not None:
            owned.append({"id": charity_id, "name": name})
    return render(request, "dashboards/owner.html", {"charities": owned})


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


def _require_rabbi(request):
    """404 for anyone but an approved rabbi (§6.2.9.3). A visitor costs no query."""
    if not (request.user.is_authenticated and accounts.is_rabbi(request.user.id)):
        raise Http404


@require_GET
def rabbi_dashboard_view(request):
    """The rabbi's own haskamos and an "Add a haskama" search (§7.1.5, §6.2.9.1).

    The search box asks this same view for results as the rabbi types (htmx
    sends `HX-Request`, and only the results list comes back). Without
    JavaScript, the box submits as a normal form and the whole page shows them.
    """
    _require_rabbi(request)
    term = request.GET.get("q", "")
    results = charities.search_charities(term)
    if request.headers.get("HX-Request"):
        return render(
            request, "dashboards/_charity_results.html", {"results": results, "term": term}
        )
    context = {
        "haskamas": charities.list_own_haskamas(request.user.id),
        "results": results,
        "term": term,
    }
    return render(request, "dashboards/rabbi.html", context)


@require_http_methods(["GET", "POST"])
def rabbi_haskama_view(request, charity_id):
    """Write a haskama for one charity, or edit the one already written (UC-06, 1a).

    The haskama is found by (this rabbi, this charity), never by its own id, so
    there is no id here to swap for another rabbi's. Every check passes before
    the write: logged in, the rabbi role, the form, the charity.
    """
    _require_rabbi(request)
    back_to_charity = request.GET.get("from") == FROM_CHARITY
    existing = charities.get_haskama(request.user.id, charity_id)
    if request.method == "POST":
        form = HaskamaForm(request.POST)
        valid = form.is_valid()
    else:
        initial = (
            {"verdict": existing.verdict, "importance": existing.importance, "body": existing.body}
            if existing
            else {}
        )
        form, valid = HaskamaForm(initial=initial), False
    name = existing.charity_name if existing else charities.get_charity_name(charity_id)
    if name is None:
        raise Http404
    if valid:
        outcome = charities.save_haskama(
            request.user.id,
            charity_id,
            form.cleaned_data["verdict"],
            form.cleaned_data["importance"],
            form.cleaned_data["body"],
        )
        refused = (charities.HaskamaOutcome.NOT_A_RABBI, charities.HaskamaOutcome.NO_SUCH_CHARITY)
        if outcome in refused:
            raise Http404  # Lost the role or the charity between the checks and the write.
        if back_to_charity:
            return redirect("charities:detail", charity_id=charity_id)
        return redirect("dashboards:rabbi")
    context = {
        "form": form,
        "charity_id": charity_id,
        "charity_name": name,
        "editing": existing is not None,
        "back_to_charity": back_to_charity,
        "action": reverse("dashboards:rabbi_haskama", args=[charity_id])
        + (f"?from={FROM_CHARITY}" if back_to_charity else ""),
    }
    return render(request, "dashboards/haskama_form.html", context)
