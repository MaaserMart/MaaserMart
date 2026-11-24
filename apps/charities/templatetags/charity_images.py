"""The one place that turns a stored `Charity.image` into a safe `src` (audit B8).

Write-side validation (`charities.services.validate_image`) is the real gate, but
a database written before that rule existed still has to render safely, so the
same rule runs again here: a relative path becomes a static URL, an allowed
absolute URL is used as it is, and anything else renders as no image at all.
"""

from django import template
from django.templatetags.static import static

from apps.charities.services import validate_image

register = template.Library()


@register.filter
def image_src(value: str | None) -> str:
    """The URL to load a charity image from, or an empty string when it is not usable."""
    try:
        clean = validate_image(value)
    except ValueError:
        return ""
    if not clean:
        return ""
    return clean if "://" in clean else static(clean)
