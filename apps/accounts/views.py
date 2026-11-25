"""Login, logout, signup, role requests and the dashboard chooser (§6.2.1, §6.2.2)."""

from django.conf import settings
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import NoReverseMatch, reverse
from django.views.decorators.http import require_http_methods, require_POST

from apps.approvals import services as approvals
from apps.charities import services as charities

from . import signup
from .forms import RabbiApplicationForm
from .login import LoginResult, attempt_login, dashboard_url, redirect_after_login
from .models import RoleAssignment
from .services import ADMIN, find_role, is_applicant

MESSAGES = {
    LoginResult.MISSING_CREDENTIALS: "Enter your username and password.",
    LoginResult.WRONG_CREDENTIALS: "Wrong username or password.",
    LoginResult.LOCKED_OUT: "Too many failed tries. This account is locked for one hour.",
    LoginResult.RATE_LIMITED: "Too many tries from your connection. Wait a minute and try again.",
}


def role_label(role):
    return "Admin" if role == ADMIN else RoleAssignment.Role(role).label


@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.method == "GET" and request.user.is_authenticated:
        # Already logged in: skip the form and go where a fresh login would.
        return redirect(redirect_after_login(request, request.user))
    next_url = request.POST.get("next") or request.GET.get("next", "")
    context = {"next": next_url, "username": ""}
    if request.method == "POST":
        username = request.POST.get("username", "")
        result, user = attempt_login(request, username, request.POST.get("password", ""))
        if result is LoginResult.OK:
            return redirect(redirect_after_login(request, user))
        context.update(username=username, error=MESSAGES[result])
        status = 429 if result is LoginResult.RATE_LIMITED else 200
        return render(request, "accounts/login.html", context, status=status)
    return render(request, "accounts/login.html", context)


@require_POST
def logout_view(request):
    logout(request)
    return redirect("home")


@login_required
def choose_dashboard_view(request):
    choices = [(role_label(role), dashboard_url(role)) for role in find_role(request.user)]
    return render(request, "accounts/choose_dashboard.html", {"choices": choices})


SIGNUP_MESSAGES = {
    signup.SignupResult.RATE_LIMITED: "Too many tries from your connection. Try again later.",
    signup.SignupResult.TOO_MANY_EMAILS: (
        "We've sent this address 3 codes in the last hour. Wait a little and try again."
    ),
    signup.SignupResult.EXPIRED: "That code has expired. Send a new one.",
    signup.SignupResult.WRONG_CODE: "That code isn't right.",
    signup.SignupResult.OUT_OF_TRIES: "Too many wrong codes. Start again.",
    signup.SignupResult.TAKEN: (
        "Someone took that username or email while your code was on its way. Start again."
    ),
}


def _next(request):
    return request.POST.get("next") or request.GET.get("next", "")


# Each signup page: its form and template. Both continue at the same code page.
SIGNUP_PAGES = {
    "member": (signup.SignupForm, "accounts/signup.html"),
    "rabbi": (signup.SignupForm, "accounts/rabbi_signup.html"),
    "owner": (signup.SignupForm, "accounts/owner_signup.html"),
}

# Where each kind of applicant goes after the code, to fill in the application.
APPLICATION_PAGES = {
    "rabbi": "accounts:rabbi_application",
    "owner": "accounts:owner_application",
}


def _signup_page(request, kind):
    if request.user.is_authenticated:
        # Already has an account: signing up again isn't a path (D-033). A rabbi
        # signs up with a different email (D-YOSEF-rabbi-signup).
        return redirect(redirect_after_login(request, request.user))
    form_class, template = SIGNUP_PAGES[kind]
    form = form_class(request.POST or None)
    context = {"form": form, "next": _next(request)}
    if request.method == "POST":
        applying_for = None if kind == "member" else kind
        result = signup.start_signup(
            request, form, next_url=_next(request), applying_for=applying_for
        )
        if result is signup.SignupResult.CODE_SENT:
            return redirect("accounts:signup_verify")
        context["error"] = SIGNUP_MESSAGES.get(result)
        status = 429 if result is signup.SignupResult.RATE_LIMITED else 200
        return render(request, template, context, status=status)
    return render(request, template, context)


@require_http_methods(["GET", "POST"])
def signup_view(request):
    return _signup_page(request, "member")


@require_http_methods(["GET", "POST"])
def rabbi_signup_view(request):
    return _signup_page(request, "rabbi")


@require_http_methods(["GET", "POST"])
def owner_signup_view(request):
    return _signup_page(request, "owner")


@require_http_methods(["GET", "POST"])
def signup_verify_view(request):
    pending = signup.pending_signup(request)
    if pending is None:
        if request.user.is_authenticated:
            return redirect(redirect_after_login(request, request.user))
        return redirect("accounts:signup")
    error = None
    notice = None
    status = 200
    if request.method == "POST":
        if "resend" in request.POST:
            result = signup.resend_code(request)
            notice = "We sent a new code." if result is signup.SignupResult.CODE_SENT else None
            error = SIGNUP_MESSAGES.get(result)
        else:
            result, user = signup.verify_signup(request, request.POST.get("code", ""))
            if result is signup.SignupResult.OK:
                return redirect(redirect_after_login(request, user))
            if result is signup.SignupResult.APPLICANT:
                return redirect(APPLICATION_PAGES[pending["applying_for"]])
            if result is signup.SignupResult.RATE_LIMITED:
                status = 429
            if result in (signup.SignupResult.OUT_OF_TRIES, signup.SignupResult.TAKEN):
                kind = pending.get("applying_for") or "member"
                form_class, template = SIGNUP_PAGES[kind]
                form = form_class(initial={"username": pending["username"]})
                context = {"form": form, "error": SIGNUP_MESSAGES[result], "next": pending["next"]}
                return render(request, template, context)
            error = SIGNUP_MESSAGES.get(result)
    context = {
        "email": signup.masked_email(pending["email"]),
        "next": pending["next"],
        "error": error,
        "notice": notice,
        "tries_left": signup.tries_left(request),
        "code_length": signup.CODE_LENGTH,
        "max_tries": signup.MAX_CODE_TRIES,
    }
    return render(request, "accounts/signup_verify.html", context, status=status)


def _applicant_or_redirect(request):
    """None for an applicant (rabbi or owner); else where to send them.

    A member, an approved rabbi or owner, or a staff user has nothing to apply for here.
    """
    if not is_applicant(request.user):
        return redirect(redirect_after_login(request, request.user))
    return None


@login_required
@require_http_methods(["GET", "POST"])
def rabbi_application_view(request):
    """The rabbi's details for the admin. The user is the one logged in, never from the URL."""
    elsewhere = _applicant_or_redirect(request)
    if elsewhere:
        return elsewhere
    if approvals.latest_application(request.user) is not None:
        return redirect("accounts:pending")  # Already sent: one application per account.
    form = RabbiApplicationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        approvals.submit_rabbi_request(
            request.user, form.cleaned_data["display_name"], form.cleaned_data["title"]
        )
        return redirect("accounts:pending")
    return render(request, "accounts/rabbi_application.html", {"form": form})


def _add_charity_url():
    """Where "Add a charity" goes, or None while that page isn't built (D-YOSEF-owner-signup)."""
    try:
        return reverse("charities:add")
    except NoReverseMatch:
        return None


CLAIM_ERRORS = {
    approvals.SubmitOutcome.NO_SUCH_CHARITY: "That charity isn't in MaaserMart. Search again.",
}


@login_required
@require_http_methods(["GET", "POST"])
def owner_application_view(request):
    """Find your charity and claim it (§6.2.2.1). The claimant is the one logged in.

    The search box asks this same view for results as the applicant types (htmx
    sends `HX-Request`, and only the results come back). Without JavaScript it
    submits as a normal form and the whole page shows them.
    """
    elsewhere = _applicant_or_redirect(request)
    if elsewhere:
        return elsewhere
    if approvals.latest_application(request.user) is not None:
        return redirect("accounts:pending")  # Already sent: one application per account.
    error = None
    status = 200
    if request.method == "POST":
        try:
            charity_id = int(request.POST.get("charity_id", ""))
        except ValueError:
            charity_id = None
        if charity_id is not None:
            outcome = approvals.submit_owner_claim(request.user, charity_id)
            if outcome is not approvals.SubmitOutcome.NO_SUCH_CHARITY:
                return redirect("accounts:pending")
        error = CLAIM_ERRORS[approvals.SubmitOutcome.NO_SUCH_CHARITY]
        status = 400
    term = request.GET.get("q", "")
    results = charities.search_charities(term)
    context = {"results": results, "term": term}
    if request.headers.get("HX-Request"):
        return render(request, "accounts/_owner_charity_results.html", context)
    context.update(error=error, add_charity_url=_add_charity_url())
    return render(request, "accounts/owner_application.html", context, status=status)


@login_required
def pending_view(request):
    """An applicant's only page: the state of the application."""
    elsewhere = _applicant_or_redirect(request)
    if elsewhere:
        return elsewhere
    application = approvals.latest_application(request.user)
    if application is None:
        # Nothing sent yet, e.g. logged out before applying. Which one isn't
        # stored until the application is, so the applicant picks.
        return render(request, "accounts/choose_application.html")
    role, status = application
    context = {"role": role, "status": status}
    if status == approvals.Status.REJECTED:
        context["message"] = approvals.rejected_message(role)
    elif status == approvals.Status.APPROVED:
        # Approved, yet the account holds no role (e.g. the role was removed later).
        context["message"] = (
            f"Your {role} application was approved, but your account isn't set up yet. "
            f"Please email {settings.SUPPORT_EMAIL}."
        )
    return render(request, "accounts/pending.html", context)
