"""Recommendation ranking, privacy and activity semantics (§6.2.11)."""

import pytest
from django.test import override_settings

from apps.recommendations.services import recommend_for
from tests.factories import (
    CharityDomainFactory,
    CharityFactory,
    CharityLocationFactory,
    DomainFactory,
    EventFactory,
    LocationFactory,
    UserFactory,
)

pytestmark = pytest.mark.django_db


def names(user):
    return [charity.name for charity in recommend_for(user.id)]


@override_settings(
    RECOMMENDATIONS_MIN_HISTORY=3,
    RECOMMENDATIONS_THRESHOLD=0.4,
    RECOMMENDATIONS_SINGLE_OFFSET=0.1,
    RECOMMENDATIONS_PAIR_OFFSET=0.2,
)
def test_ranking_tiers_published_rejections_and_user_isolation():
    user = UserFactory()
    domain, location = DomainFactory(), LocationFactory()
    source = CharityFactory(name="Z visited", is_visible=True)
    pair_a = CharityFactory(name="A pair", is_visible=True)
    pair_b = CharityFactory(name="B pair", is_visible=True)
    single = CharityFactory(name="A domain only", is_visible=True)
    invisible = CharityFactory(name="Hidden charity", is_visible=False)
    rejected = CharityFactory(name="Rejected", is_visible=True)
    for charity in (source, pair_a, pair_b, single, invisible, rejected):
        CharityDomainFactory(charity=charity, domain=domain)
    for charity in (source, pair_a, pair_b, invisible, rejected):
        CharityLocationFactory(charity=charity, location=location)
    other = CharityFactory(name="Other", is_visible=True)
    for _ in range(4):
        EventFactory(user=user, charity=source, action="view")
    for _ in range(2):
        EventFactory(user=user, charity=other, action="link_click")
    EventFactory(user=user, charity=rejected, action="reject", hidden_by_user=True)
    EventFactory(user=UserFactory(), charity=pair_a, action="reject")

    assert names(user) == ["Z visited", "A pair", "B pair", "A domain only"]


@override_settings(
    RECOMMENDATIONS_MIN_HISTORY=1,
    RECOMMENDATIONS_THRESHOLD=0.5,
    RECOMMENDATIONS_SINGLE_OFFSET=0.1,
    RECOMMENDATIONS_PAIR_OFFSET=0.1,
)
def test_hidden_events_stay_in_denominator_and_threshold_is_strict():
    user = UserFactory()
    charity = CharityFactory(name="Visited", is_visible=True)
    for _ in range(2):
        EventFactory(user=user, charity=charity)
        EventFactory(user=user, charity=charity, hidden_by_user=True)
    assert names(user) == []


@override_settings(RECOMMENDATIONS_MIN_HISTORY=3)
def test_minimum_history_ignores_rejections_and_other_users():
    user = UserFactory()
    charity = CharityFactory(is_visible=True)
    EventFactory(user=user, charity=charity)
    EventFactory(user=user, charity=charity, action="reject")
    EventFactory(user=UserFactory(), charity=charity)
    assert recommend_for(user.id) == ()


@override_settings(
    RECOMMENDATIONS_MIN_HISTORY=1,
    RECOMMENDATIONS_THRESHOLD=0.4,
    RECOMMENDATIONS_SINGLE_OFFSET=0.1,
    RECOMMENDATIONS_PAIR_OFFSET=0.2,
)
def test_low_share_visited_charity_can_be_suggested_by_other_history():
    user = UserFactory()
    domain, location = DomainFactory(), LocationFactory()
    high = CharityFactory(name="High", is_visible=True)
    low = CharityFactory(name="Low", is_visible=True)
    for charity in (high, low):
        CharityDomainFactory(charity=charity, domain=domain)
        CharityLocationFactory(charity=charity, location=location)
    for _ in range(4):
        EventFactory(user=user, charity=high)
    EventFactory(user=user, charity=low)

    assert names(user) == ["High", "Low"]


@override_settings(RECOMMENDATIONS_MIN_HISTORY=1)
def test_unpublished_history_informs_but_is_never_recommended():
    user = UserFactory()
    domain = DomainFactory()
    source = CharityFactory(name="Unpublished", is_visible=False)
    candidate = CharityFactory(name="Published", is_visible=True)
    CharityDomainFactory(charity=source, domain=domain)
    CharityDomainFactory(charity=candidate, domain=domain)
    EventFactory(user=user, charity=source)

    assert names(user) == ["Published"]
