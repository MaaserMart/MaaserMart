"""A member's history and recommendation inputs stay private and scoped."""

import pytest

from apps.events.models import Event
from apps.events.services import (
    get_history,
    hide_all_history,
    hide_history,
    recommendation_signals,
)
from tests.factories import CharityFactory, EventFactory, UserFactory

pytestmark = pytest.mark.django_db


def test_history_only_returns_visible_visits_and_clicks_for_that_member():
    member = UserFactory()
    first = EventFactory(user=member, action=Event.Action.VIEW)
    second = EventFactory(user=member, action=Event.Action.LINK_CLICK)
    EventFactory(user=member, hidden_by_user=True)
    EventFactory(user=member, action=Event.Action.CHARITY_UPDATED)
    EventFactory(user=member, action=Event.Action.REJECT)
    EventFactory()
    EventFactory(user=None)

    history = get_history(member.pk)
    assert [item.id for item in history] == [second.pk, first.pk]
    assert history[0].charity_id == second.charity_id
    assert history[0].action == Event.Action.LINK_CLICK
    assert history[0].created == second.created


def test_hide_one_and_all_do_not_touch_others_or_non_history_events():
    member = UserFactory()
    first = EventFactory(user=member)
    second = EventFactory(user=member, action=Event.Action.LINK_CLICK)
    other = EventFactory()
    update = EventFactory(user=member, action=Event.Action.CHARITY_UPDATED)
    rejected = EventFactory(user=member, action=Event.Action.REJECT)

    assert not hide_history(member.pk, other.pk)
    assert not hide_history(member.pk, update.pk)
    assert hide_history(member.pk, first.pk)
    assert not hide_history(member.pk, first.pk)
    assert hide_all_history(member.pk) == 1
    assert hide_all_history(member.pk) == 0
    assert get_history(member.pk) == ()
    for row in (other, update, rejected):
        row.refresh_from_db()
        assert not row.hidden_by_user
    second.refresh_from_db()
    assert second.hidden_by_user


def test_recommendation_signals_exclude_hidden_scores_but_not_activity_or_rejections():
    member = UserFactory()
    first = CharityFactory()
    second = CharityFactory()
    EventFactory(user=member, charity=first)
    EventFactory(user=member, charity=first, action=Event.Action.LINK_CLICK)
    EventFactory(user=member, charity=second, hidden_by_user=True)
    EventFactory(user=member, charity=second, action=Event.Action.REJECT, hidden_by_user=True)
    EventFactory(user=member, charity=second, action=Event.Action.CHARITY_UPDATED)
    EventFactory(charity=second)

    assert recommendation_signals(member.pk) == (3, {first.pk: 2}, {second.pk})


@pytest.mark.parametrize("operation", [get_history, hide_all_history, recommendation_signals])
def test_anonymous_history_is_never_exposed_or_modified(operation):
    EventFactory(user=None)
    with pytest.raises(ValueError, match="user id"):
        operation(None)
    assert Event.objects.get().hidden_by_user is False


def test_anonymous_cannot_hide_an_event():
    event = EventFactory(user=None)
    with pytest.raises(ValueError, match="user id"):
        hide_history(None, event.pk)
    event.refresh_from_db()
    assert not event.hidden_by_user
