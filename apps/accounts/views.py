"""Plain login, logout and chooser pages. Local only, for trying login in a browser."""

from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from .login import (
    DASHBOARD_URL_NAMES,
    LoginResult,
    _url_or_home,
    attempt_login,
    redirect_after_login,
)
from .services import find_role

MESSAGES = {
    LoginResult.MISSING_CREDENTIALS: "Enter your username and password.",
    LoginResult.WRONG_CREDENTIALS: "Wrong username or password.",
    LoginResult.LOCKED_OUT: "Too many failed tries. This account is locked for one hour.",
    LoginResult.RATE_LIMITED: "Too many tries from your connection. Wait a minute and try again.",
}

ROLE_LABELS = {
    "member": "Member",
    "rabbi": "Rabbi",
    "charity_owner": "Charity owner",
    "technical_supporter": "Technical supporter",
    "admin": "Admin",
}


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
    choices = [
        (ROLE_LABELS[role], _url_or_home(DASHBOARD_URL_NAMES[role]))
        for role in find_role(request.user)
    ]
    return render(request, "accounts/choose_dashboard.html", {"choices": choices})
