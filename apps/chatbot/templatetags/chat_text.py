"""Render a chatbot answer safely (D-076).

The model's text is escaped like any user input. Only two kinds of link are
then made clickable: a MaaserMart charity page (`/charity/<id>/`, as the lookup
tools return it) and a Sefaria source. Any other URL the model writes stays
plain text, so an answer cannot send a member somewhere unexpected.
"""

import re

from django import template
from django.utils.html import escape, linebreaks
from django.utils.safestring import mark_safe

register = template.Library()

# Matched against the *escaped* text, so `&` arrives as `&amp;` and a quote as
# `&#x27;`; neither can end the attribute the match is written into.
_LINK = re.compile(
    r"(?P<sefaria>https://www\.sefaria\.org/[^\s<>\"]+?)(?=[.,;:!?)]*(?:\s|$))"
    r"|(?<![\w/.])(?P<charity>/charity/\d+/)"
)


def _link(match: re.Match) -> str:
    url = match.group(0)
    if match.group("sefaria"):
        return f'<a href="{url}" rel="noopener noreferrer" target="_blank">{url}</a>'
    return f'<a href="{url}">{url}</a>'


@register.filter
def chat_text(value: str | None) -> str:
    """Escaped paragraphs, with charity and Sefaria links made clickable."""
    if not (value or "").strip():
        return ""
    escaped = escape(value)
    linked = _LINK.sub(_link, escaped)
    return mark_safe(linebreaks(linked, autoescape=False))
