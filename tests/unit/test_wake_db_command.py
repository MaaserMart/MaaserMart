"""`manage.py wake_db`: the CLI half of the wake gate (D-070).

The middleware cannot help `migrate` or `seed`, because neither is a request. So
this command is what a person runs on a stopped instance, and the only place the
gate is allowed to block.
"""

from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.support.management.commands import wake_db
from apps.support.rds import DatabaseState, RdsInstance
from tests.support.rds import FakeRds


@pytest.fixture
def fake(settings, monkeypatch):
    """The command's client replaced with a fake, and the setting it needs set."""
    settings.RDS_INSTANCE_ID = "maasermart-db"
    settings.AWS_REGION = "us-east-1"
    fake = FakeRds("stopped")
    monkeypatch.setattr(
        wake_db,
        "RdsInstance",
        lambda *args, **kwargs: RdsInstance("maasermart-db", region="us-east-1", client=fake),
    )
    return fake


def test_without_an_instance_identifier_it_says_so(settings):
    settings.RDS_INSTANCE_ID = ""

    with pytest.raises(CommandError, match="RDS_INSTANCE_ID is not set"):
        call_command("wake_db", stdout=StringIO())


def test_an_available_instance_needs_no_start(settings, monkeypatch):
    settings.RDS_INSTANCE_ID = "maasermart-db"
    fake = FakeRds("available")
    monkeypatch.setattr(
        wake_db, "RdsInstance", lambda *a, **k: RdsInstance("maasermart-db", client=fake)
    )
    out = StringIO()

    call_command("wake_db", stdout=out)

    assert fake.starts == 0
    assert "available" in out.getvalue()


def test_a_stopped_instance_is_started_and_says_how_to_wait(fake):
    out = StringIO()

    call_command("wake_db", stdout=out)

    assert fake.starts == 1
    assert "stopped" in out.getvalue()
    assert "--wait" in out.getvalue()


def test_wait_passes_the_timeout_and_reports_the_waking_states(fake, monkeypatch):
    seen = {}

    def wait(self, *, timeout, interval, on_state=None):
        seen["timeout"] = timeout
        on_state(DatabaseState.WAKING)
        on_state(DatabaseState.AVAILABLE)
        return True

    monkeypatch.setattr(RdsInstance, "wait", wait)
    out = StringIO()

    call_command("wake_db", "--wait", "--timeout", "60", stdout=out)

    assert seen["timeout"] == 60
    assert "starting" in out.getvalue()
    assert "available" in out.getvalue()


def test_a_wait_that_times_out_fails_the_command(fake, monkeypatch):
    monkeypatch.setattr(RdsInstance, "wait", lambda self, **kwargs: False)

    with pytest.raises(CommandError, match="was not available"):
        call_command("wake_db", "--wait", stdout=StringIO())
