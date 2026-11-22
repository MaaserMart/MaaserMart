"""Cross-cutting HTTP behaviour that no single domain app owns.

`Content-Security-Policy` has no Django setting, so production adds a middleware
with the policy it needs (audit SEC1). The templates are CSP-friendly (no inline
handlers; every script and style is a same-origin file), so a `default-src
'self'` policy costs nothing and would have been the second line of defence
behind write-side image validation (D-056).

`DatabaseWakeMiddleware` handles a different cross-cutting fact: the database
lives on RDS and is stopped when idle (D-070), so a request can arrive with
nothing to connect to. Asking the AWS API is the only way to answer that while
the database is down, which is why the gate sits in front of the app rather than
inside it.
"""

from __future__ import annotations

from django.conf import settings
from django.db import OperationalError, connections
from django.http import HttpResponse
from django.template.loader import render_to_string

from apps.support.rds import DatabaseState, RdsInstance

# The policy the site's own pages can keep. Images may come from the allowlisted
# image hosts (https), which write-side validation already restricted to
# settings.CHARITY_IMAGE_HOSTS; the header allows any https image as a backstop
# only because hosts change with the setting and the pixel is harmless next to a
# validation that already ran.
SITE_POLICY = (
    "default-src 'self'; img-src 'self' https:; base-uri 'none'; "
    "form-action 'self'; frame-ancestors 'none'"
)

# Django admin relies on inline styles and scripts, so it keeps no CSP rather
# than a policy it cannot uphold. It is staff-only and already behind the frame
# protections.
NO_POLICY_PREFIXES = ("/django-admin/", "/admin/")


class ContentSecurityPolicyMiddleware:
    """Add the CSP header to ordinary pages, unless a path opts out."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        policy = getattr(settings, "CONTENT_SECURITY_POLICY", None)
        if not policy:
            return response
        if any(request.path.startswith(prefix) for prefix in NO_POLICY_PREFIXES):
            return response
        response.headers["Content-Security-Policy"] = policy
        return response


def waking_response(request) -> HttpResponse:
    """The page a visitor gets while the database is starting.

    It carries `Retry-After` and reloads itself, because the instance comes up
    on its own schedule — minutes later — and the request that started it has to
    end now. `no-store` keeps a proxy from handing the same 503 to everyone
    after the database is back.
    """
    body = render_to_string(
        "503.html",
        {"retry_after": settings.DATABASE_WAKE_RETRY_AFTER},
        request=request,
    )
    response = HttpResponse(body, status=503, content_type="text/html; charset=utf-8")
    response.headers["Retry-After"] = str(settings.DATABASE_WAKE_RETRY_AFTER)
    response.headers["Cache-Control"] = "no-store"
    return response


class DatabaseWakeMiddleware:
    """Start the RDS instance before a request waits on a stopped database.

    Settings insert this before `SessionMiddleware`: sessions and auth both read
    the database, so anything earlier in the chain would fail before this gate
    could answer (D-070). Requests for static files skip it, so the page above
    is not rendered unstyled.

    The cached state makes the common case free: while the instance is up, this
    costs one `DescribeDBInstances` call per process per minute, not per request.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.instance = RdsInstance(
            settings.RDS_INSTANCE_ID,
            region=getattr(settings, "AWS_REGION", None),
            available_ttl=settings.DATABASE_WAKE_AVAILABLE_TTL,
            waking_ttl=settings.DATABASE_WAKE_WAKING_TTL,
        )

    def __call__(self, request):
        if self._is_static(request):
            return self.get_response(request)

        state = self.instance.state()
        if state is DatabaseState.STOPPED:
            self.instance.wake()
            return waking_response(request)
        if state is DatabaseState.WAKING:
            return waking_response(request)

        try:
            return self.get_response(request)
        except OperationalError:
            # The cached check said the instance was up and the query disagreed.
            # Ask again without the cache: that answer is the one this branch
            # was waiting for. A healthy instance means this is a real database
            # fault (bad credentials, no disk, too many connections) and it
            # stays a real error instead of becoming a friendly retry loop.
            state = self.instance.refresh()
            if state is DatabaseState.STOPPED:
                self.instance.wake()
            if state is DatabaseState.AVAILABLE:
                raise
            connections["default"].close()
            return waking_response(request)

    @staticmethod
    def _is_static(request) -> bool:
        prefix = "/" + (settings.STATIC_URL or "").lstrip("/")
        return prefix != "/" and request.path.startswith(prefix)
