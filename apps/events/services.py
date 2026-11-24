"""Public interface of the events app.

Other apps call only the functions defined here, never this app's models.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.db import IntegrityError, transaction
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

logger = logging.getLogger(__name__)

# Only the member's own browsing activity is shown in their history. Other
# events, such as charity updates, are administrative records.
HISTORY_ACTIONS = (Event.Action.VIEW, Event.Action.LINK_CLICK)


@dataclass(frozen=True)
class HistoryEvent:
    """A member's activity without exposing an EVENT model across apps."""

    id: int
    charity_id: int
    link_id: int | None
    action: str
    created: datetime


def _member_history(user_id):
    """Scope history operations to a real member, never anonymous events."""
    if user_id is None:
        raise ValueError("A user id is required")
    return Event.objects.filter(user_id=user_id, action__in=HISTORY_ACTIONS, hidden_by_user=False)


def get_history(user_id) -> tuple[HistoryEvent, ...]:
    """Return the member's visible visits and clicks, most recent first."""
    rows = _member_history(user_id).order_by("-created", "-pk")
    return tuple(
        HistoryEvent(
            id=row.pk,
            charity_id=row.charity_id,
            link_id=row.link_id,
            action=row.action,
            created=row.created,
        )
        for row in rows
    )


def hide_history(user_id, event_id) -> bool:
    """Hide one of this member's history entries, returning whether it existed."""
    return bool(_member_history(user_id).filter(pk=event_id).update(hidden_by_user=True))


def hide_all_history(user_id) -> int:
    """Hide the member's visible history and return the number of rows changed."""
    return _member_history(user_id).update(hidden_by_user=True)


def recommendation_signals(user_id) -> tuple[int, dict[int, int], set[int]]:
    """Return activity threshold, visible charity counts and rejected charity IDs.

    Hidden browsing events still contribute to the activity threshold, but not
    to the charity scores. Rejections remain effective regardless of history.
    """
    if user_id is None:
        raise ValueError("A user id is required")
    activity = Event.objects.filter(user_id=user_id, action__in=HISTORY_ACTIONS)
    total = activity.count()
    counts = dict(
        activity.filter(hidden_by_user=False)
        .order_by()
        .values_list("charity_id")
        .annotate(total=Count("pk"))
    )
    rejected = set(
        Event.objects.filter(user_id=user_id, action=Event.Action.REJECT).values_list(
            "charity_id", flat=True
        )
    )
    return total, counts, rejected


# §6.4.3 Trending: events in the past week count three, events in the past month
# count two. The two windows do not overlap, or a row from this week would be
# counted twice (D-050): the month bucket holds days 8–30 only.
TRENDING_WEEK_WEIGHT = 3
TRENDING_MONTH_WEIGHT = 2
TRENDING_WEEK = timedelta(days=7)
TRENDING_MONTH = timedelta(days=30)


def record_event(charity_id, action, link_id=None, user_id=None):
    """Record one EVENT (§6.1). `action` must be one of Event.Action's values.

    A reference to a charity or a link that does not exist becomes a
    `ValueError` naming what was passed, not a raw `IntegrityError` from the
    foreign key (audit B6): the caller gets the same kind of error as a bad
    action, with the id that was wrong in it.

    Django creates foreign keys DEFERRABLE INITIALLY DEFERRED on PostgreSQL, so
    when this runs inside a caller's transaction the check happens at that
    outer commit and cannot be caught here. The callers that exist today
    (`publish_charity`, `hide_charity`, `update_charity`) look the charity up
    first, so a bad id never reaches this function from them; the guard covers
    a direct call, which commits on its own.
    """
    if action not in Event.Action.values:
        raise ValueError(f"Unknown event action {action!r}")
    try:
        with transaction.atomic():
            return Event.objects.create(
                charity_id=charity_id, action=action, link_id=link_id, user_id=user_id
            )
    except IntegrityError as error:
        logger.warning(
            "record_event rejected: charity_id=%s action=%s link_id=%s user_id=%s",
            charity_id,
            action,
            link_id,
            user_id,
        )
        raise ValueError(
            f"Event refers to a row that does not exist: charity_id={charity_id}, "
            f"link_id={link_id}, user_id={user_id}"
        ) from error


# --- Activity reads ----------------------------------------------------------
# The charity listing orders by activity, but charities may not query EVENT
# itself (D-006). These functions return subqueries over this app's table, so the
# caller can annotate its own queryset, order and paginate in one query, without
# knowing EVENT's shape (D-048).


def event_count(charity_ref: OuterRef) -> Expression:
    """How many EVENT rows reference one charity (§6.2.5's "most events").

    Every action counts: a view, a link click, a rejection and a charity update
    are all activity. An event the member hid from their own history does not
    count (D-057): hiding it is a statement that it should not be remembered,
    not a separate flag the totals may ignore. A charity with no events has no
    row to aggregate, so the expression coalesces to 0 rather than NULL: "no
    events" is zero activity, and Postgres would otherwise sort NULL first when
    ordering high to low.
    """
    return Coalesce(
        Subquery(
            Event.objects.filter(charity=charity_ref, hidden_by_user=False)
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

    The score is `3 × events in the past week + 2 × events 8–30 days ago`,
    measured from `now` (UTC by default, D-010). The buckets do not overlap, so
    an event is worth 3 or 2, never both: the week sits inside the month window,
    and counting it in both was the literal reading the doc's wording allows
    (D-050).
    """
    now = now or timezone.now()
    week_ago = now - TRENDING_WEEK
    month_ago = now - TRENDING_MONTH
    return Coalesce(
        Subquery(
            Event.objects.filter(charity=charity_ref, created__gte=month_ago, hidden_by_user=False)
            .order_by()
            .values("charity")
            .annotate(
                week=Count("pk", filter=Q(created__gte=week_ago)),
                older=Count("pk", filter=Q(created__lt=week_ago)),
            )
            .annotate(
                score=ExpressionWrapper(
                    F("week") * TRENDING_WEEK_WEIGHT + F("older") * TRENDING_MONTH_WEIGHT,
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
