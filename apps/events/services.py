"""Public interface of the events app.

Other apps call only the functions defined here, never this app's models.
"""

from datetime import datetime, timedelta

from django.db.models import (
    Count,
    DateTimeField,
    Expression,
    ExpressionWrapper,
    F,
    IntegerField,
    Max,
    OuterRef,
    Q,
    Subquery,
    Value,
)
from django.db.models.functions import Coalesce
from django.utils import timezone

from .models import Event

# §6.4.3 Trending: events in the past week count three, events in the past month
# count two. The week is inside the month, so a row from this week counts in both.
TRENDING_WEEK_WEIGHT = 3
TRENDING_MONTH_WEIGHT = 2
TRENDING_WEEK = timedelta(days=7)
TRENDING_MONTH = timedelta(days=30)


def record_event(charity_id, action, link_id=None, user_id=None):
    """Record one EVENT (§6.1). `action` must be one of Event.Action's values."""
    if action not in Event.Action.values:
        raise ValueError(f"Unknown event action {action!r}")
    Event.objects.create(charity_id=charity_id, action=action, link_id=link_id, user_id=user_id)


# --- Activity reads ----------------------------------------------------------
# The charity listing orders by activity, but charities may not query EVENT
# itself (D-006). These functions return subqueries over this app's table, so the
# caller can annotate its own queryset, order and paginate in one query, without
# knowing EVENT's shape (D-048).


def event_count(charity_ref: OuterRef) -> Expression:
    """How many EVENT rows reference one charity (§6.2.5's "most events").

    Every action counts: a view, a link click, a rejection and a charity update
    are all activity. A charity with no events has no row to aggregate, so the
    expression coalesces to 0 rather than NULL: "no events" is zero activity,
    and Postgres would otherwise sort NULL first when ordering high to low.
    """
    return Coalesce(
        Subquery(
            Event.objects.filter(charity=charity_ref)
            .order_by()
            .values("charity")
            .annotate(total=Count("pk"))
            .values("total"),
            output_field=IntegerField(),
        ),
        Value(0),
        output_field=IntegerField(),
    )


def trending_score(charity_ref: OuterRef, *, now: datetime | None = None) -> Expression:
    """§6.4.3's trending score for one charity, as an integer expression.

    The score is `3 × events in the past week + 2 × events in the past month`,
    measured from `now` (UTC by default, D-010). The week is part of the month,
    so a charity with one event today scores 5 and one event 20 days ago scores 2.
    """
    now = now or timezone.now()
    week_ago = now - TRENDING_WEEK
    month_ago = now - TRENDING_MONTH
    return Coalesce(
        Subquery(
            Event.objects.filter(charity=charity_ref, created__gte=month_ago)
            .order_by()
            .values("charity")
            .annotate(
                week=Count("pk", filter=Q(created__gte=week_ago)),
                month=Count("pk"),
            )
            .annotate(
                score=ExpressionWrapper(
                    F("week") * TRENDING_WEEK_WEIGHT + F("month") * TRENDING_MONTH_WEIGHT,
                    output_field=IntegerField(),
                )
            )
            .values("score"),
            output_field=IntegerField(),
        ),
        Value(0),
        output_field=IntegerField(),
    )


def last_changed(charity_ref: OuterRef) -> Expression:
    """When a change to this charity was last recorded, as a datetime expression.

    Only `charity_updated` events count: a view is not a change to the charity.
    The result is NULL when the charity has none, which lets the caller fall back
    to its own creation time (D-048).
    """
    return Subquery(
        Event.objects.filter(charity=charity_ref, action=Event.Action.CHARITY_UPDATED)
        .order_by()
        .values("charity")
        .annotate(last=Max("created"))
        .values("last"),
        output_field=DateTimeField(),
    )
