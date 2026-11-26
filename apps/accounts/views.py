"""Login, logout, member signup and the dashboard chooser (§6.2.1, §6.2.2)."""

from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from common.verification import CODE_LENGTH, MAX_CODE_TRIES

from . import signup
from .login import LoginResult, attempt_login, dashboard_url, redirect_after_login
from .models import RoleAssignment
from .services import ADMIN, find_role

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


@require_http_methods(["GET", "POST"])
def signup_view(request):
    if request.user.is_authenticated:
        # Already a member: signing up again isn't a path (D-033).
        return redirect(redirect_after_login(request, request.user))
    form = signup.SignupForm(request.POST or None)
    context = {"form": form, "next": _next(request)}
    if request.method == "POST":
        result = signup.start_signup(request, form, next_url=_next(request))
        if result is signup.SignupResult.CODE_SENT:
            return redirect("accounts:signup_verify")
        context["error"] = SIGNUP_MESSAGES.get(result)
        status = 429 if result is signup.SignupResult.RATE_LIMITED else 200
        return render(request, "accounts/signup.html", context, status=status)
    return render(request, "accounts/signup.html", context)


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
            if result is signup.SignupResult.RATE_LIMITED:
                status = 429
            if result in (signup.SignupResult.OUT_OF_TRIES, signup.SignupResult.TAKEN):
                form = signup.SignupForm(initial={"username": pending["username"]})
                context = {"form": form, "error": SIGNUP_MESSAGES[result], "next": pending["next"]}
                return render(request, "accounts/signup.html", context)
            error = SIGNUP_MESSAGES.get(result)
    context = {
        "email": signup.masked_email(pending["email"]),
        "next": pending["next"],
        "error": error,
        "notice": notice,
        "tries_left": signup.tries_left(request),
        "code_length": CODE_LENGTH,
        "max_tries": MAX_CODE_TRIES,
    }
    return render(request, "accounts/signup_verify.html", context, status=status)
