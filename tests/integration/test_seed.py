"""The dev seed command every developer runs after setup (D-022, D-030, D-038)."""

import pytest
from django.core.management import CommandError, call_command

from apps.approvals.models import ApprovalRequest
from apps.charities.models import Charity
from apps.events.models import Event
from tests.factories import CharityFactory

pytestmark = pytest.mark.django_db


def test_seed_fills_an_empty_database(settings):
    settings.DEBUG = True
    call_command("seed")

    assert Charity.objects.count() == 200
    assert Event.objects.exists()
    visible = ApprovalRequest.objects.filter(
        kind=ApprovalRequest.Kind.NEW_CHARITY, status=ApprovalRequest.Status.APPROVED
    )
    assert visible.count() == 185
    assert Charity.objects.filter(is_visible=True).count() == 185


def test_second_run_is_refused_and_leaves_data_untouched(settings):
    settings.DEBUG = True
    call_command("seed")
    charity_ids = set(Charity.objects.values_list("id", flat=True))
    events = Event.objects.count()

    with pytest.raises(CommandError, match="empty database"):
        call_command("seed")

    assert set(Charity.objects.values_list("id", flat=True)) == charity_ids
    assert Event.objects.count() == events


def test_seed_refuses_when_any_app_table_has_rows(settings):
    settings.DEBUG = True
    CharityFactory()
    with pytest.raises(CommandError, match="charities.Charity"):
        call_command("seed")
    assert Charity.objects.count() == 1


def test_seed_refuses_without_debug(settings):
    settings.DEBUG = False
    with pytest.raises(CommandError, match="DEBUG"):
        call_command("seed")
