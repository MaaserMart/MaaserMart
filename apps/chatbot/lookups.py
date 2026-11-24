"""What the model may look up, and how (D-076).

Each tool is read-only and calls another app's `services.py`. The model never
sends SQL and never sees a model row. The member's own figures come from a tool
bound to their user id here, so the model cannot ask for anyone else's.
"""

from __future__ import annotations

from django.urls import reverse

from apps.charities import services as charities
from apps.tools import services as tools

from .loop import ToolError, ToolFunction
from .providers import Tool

# Long text is cut so a lookup stays small; the page link has the rest.
DESCRIPTION_CHARS = 1200
REVIEW_CHARS = 300
REVIEWS_SHOWN = 3


def _cut(text: str | None, limit: int) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


def _page_url(charity_id: int) -> str:
    return reverse("charities:detail", args=[charity_id])


def search_charities(query: str = "", domain: str = "", location: str = "", sort: str = "rating"):
    cards = charities.search_charities(query, domain=domain, location=location, sort=sort)
    return [
        {
            "id": card.id,
            "name": card.name,
            "tagline": card.tagline or "",
            "page": _page_url(card.id),
            "domains": [d.name for d in card.domains],
            "locations": [loc.label for loc in card.locations],
            "average_rating": card.reviews.average,
            "reviews": card.reviews.count,
            "approving_haskamos": card.activity.approving_haskamas,
        }
        for card in cards
    ]


def get_charity(charity_id: int):
    page = charities.get_charity(charity_id)
    if page is None:
        raise ToolError(f"No charity has id {charity_id}.")
    return {
        "id": page.id,
        "name": page.name,
        "tagline": page.tagline or "",
        "description": _cut(page.description, DESCRIPTION_CHARS),
        "page": _page_url(page.id),
        "domains": [d.name for d in page.domains],
        "locations": [loc.label for loc in page.locations],
        "links": [{"label": link.label, "url": link.url} for link in page.links],
        "average_rating": page.review_summary.average,
        "review_count": page.review_summary.count,
        "recent_reviews": [
            {"rating": r.rating, "text": _cut(r.body, REVIEW_CHARS), "date": r.created.date()}
            for r in page.reviews[:REVIEWS_SHOWN]
        ],
        "haskamos": [
            {"rabbi": h.rabbi, "approves": h.approving, "text": _cut(h.body, REVIEW_CHARS)}
            for h in page.haskamas
        ],
    }


def list_domains():
    return list(charities.domain_names())


def _maaser_for(user_id: int):
    def my_maaser():
        summary = tools.maaser_summary(user_id)
        return {
            "income_recorded": summary.income,
            "donations_recorded": summary.donations,
            "maaser_due": summary.due,
            "still_owed": summary.owed,
            "given_beyond_due": summary.given_beyond,
            "page": reverse("tools:maaser"),
        }

    return my_maaser


SORTS = ["rating", "haskamos", "popular", "trending", "newest", "updated", "alphabetical"]

_SEARCH = Tool(
    "search_charities",
    "Find charities on MaaserMart. Every argument is optional and they combine; "
    f"at most {charities.CHAT_RESULT_LIMIT} results come back, best first.",
    {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Part of the charity's name."},
            "domain": {
                "type": "string",
                "description": "A cause, such as 'Hachnasas Kallah'. See list_domains.",
            },
            "location": {"type": "string", "description": "A city, region or country."},
            "sort": {"type": "string", "enum": SORTS, "description": "Default: rating."},
        },
        "additionalProperties": False,
    },
)

_GET = Tool(
    "get_charity",
    "One charity in full: description, links, recent reviews and rabbis' haskamos.",
    {
        "type": "object",
        "properties": {"charity_id": {"type": "integer"}},
        "required": ["charity_id"],
        "additionalProperties": False,
    },
)

_DOMAINS = Tool("list_domains", "The causes charities on MaaserMart are grouped under.")

_MAASER = Tool(
    "my_maaser",
    "The signed-in member's own maaser figures from their Maaser Tools entries: "
    "income, donations, what is due (a tenth of income) and what is still owed.",
)


def functions_for(user_id: int) -> list[ToolFunction]:
    """The tools offered when this member asks."""
    return [
        ToolFunction(_SEARCH, search_charities),
        ToolFunction(_GET, get_charity),
        ToolFunction(_DOMAINS, list_domains),
        ToolFunction(_MAASER, _maaser_for(user_id)),
    ]
