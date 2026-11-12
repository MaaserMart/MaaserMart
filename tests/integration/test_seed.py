"""The dev seed command every developer runs after setup (D-022, D-023)."""

import pytest
from django.core.management import CommandError, call_command

from apps.approvals.models import ApprovalRequest
from apps.charities.models import Charity
from apps.events.models import Event

pytestmark = pytest.mark.django_db


def test_seed_builds_data_and_can_run_twice(settings):
    settings.DEBUG = True
    call_command("seed")
    call_command("seed")

    assert Charity.objects.count() == 200
    assert Event.objects.exists()
    visible = ApprovalRequest.objects.filter(
        kind=ApprovalRequest.Kind.NEW_CHARITY, status=ApprovalRequest.Status.APPROVED
    )
    assert visible.count() == 185


def test_seed_refuses_without_debug(settings):
    settings.DEBUG = False
    with pytest.raises(CommandError, match="DEBUG"):
        call_command("seed")
