"""HTTP security headers Django does not send on its own.

`Content-Security-Policy` has no Django setting, so production adds this
middleware with the policy it needs (audit SEC1). The templates are CSP-friend-
ly (no inline handlers; every script and style is a same-origin file), so a
`default-src 'self'` policy costs nothing and would have been the second line of
defence behind write-side image validation (D-056).
"""

from django.conf import settings

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
