"""The wake gate's conversation with the AWS API, against a fake client (D-070).

No test here touches AWS: the client is injected, so these pin the decisions the
gate makes about a status rather than the shape of the RDS API.
"""

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError

from apps.support import rds
from apps.support.rds import DatabaseState, RdsConfigurationError, RdsInstance
from tests.support.rds import FakeCache, FakeRds, client_error


def instance(fake: FakeRds, **kwargs) -> RdsInstance:
    return RdsInstance("maasermart-db", region="us-east-2", client=fake, **kwargs)


def test_an_available_instance_is_available():
    fake = FakeRds("available")

    assert instance(fake).state() is DatabaseState.AVAILABLE
    assert fake.starts == 0


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("stopped", DatabaseState.STOPPED),
        ("starting", DatabaseState.WAKING),
        ("stopping", DatabaseState.WAKING),
    ],
)
def test_the_down_statuses_map_to_what_the_gate_needs(status, expected):
    assert instance(FakeRds(status)).state() is expected


@pytest.mark.parametrize(
    "status", ["backing-up", "modifying", "rebooting", "storage-optimization", "upgrading"]
)
def test_every_other_status_is_left_to_the_query(status):
    """An unfamiliar status must not become an outage the gate invented.

    `rebooting` is briefly unreachable, but the query is a better judge of that
    than a status list that has to guess RDS's vocabulary (`available` today,
    something new next year).
    """
    assert instance(FakeRds(status)).state() is DatabaseState.AVAILABLE


def test_the_answer_is_cached_for_a_minute(monkeypatch):
    fake_cache = FakeCache()
    monkeypatch.setattr(rds, "cache", fake_cache)
    fake = FakeRds("available")

    assert instance(fake).state() is DatabaseState.AVAILABLE
    assert instance(fake).state() is DatabaseState.AVAILABLE

    assert fake.describes == 1
    assert set(fake_cache.ttls.values()) == {60}


def test_a_down_answer_is_cached_only_briefly(monkeypatch):
    """A page polling during a start must see it become available, not in a minute."""
    fake_cache = FakeCache()
    monkeypatch.setattr(rds, "cache", fake_cache)

    assert instance(FakeRds("starting")).state() is DatabaseState.WAKING

    assert set(fake_cache.ttls.values()) == {10}


def test_refresh_ignores_the_cache(monkeypatch):
    monkeypatch.setattr(rds, "cache", FakeCache())
    fake = FakeRds("available")
    rds_instance = instance(fake)

    rds_instance.state()
    rds_instance.refresh()

    assert fake.describes == 2


def test_waking_an_instance_clears_the_cached_answer(monkeypatch):
    monkeypatch.setattr(rds, "cache", FakeCache())
    fake = FakeRds("stopped")
    rds_instance = instance(fake)
    assert rds_instance.state() is DatabaseState.STOPPED

    rds_instance.wake()

    assert rds_instance.state() is DatabaseState.WAKING
    assert fake.describes == 2


def test_wake_starts_the_instance():
    fake = FakeRds("stopped")

    instance(fake).wake()

    assert fake.starts == 1


def test_wake_tolerates_losing_the_race_to_another_worker():
    """Both callers wanted a start; one of them getting it is success for both."""
    fake = FakeRds("stopped")
    fake.start_error = client_error("InvalidDBInstanceState", "StartDBInstance")

    instance(fake).wake()  # does not raise

    assert fake.starts == 1


def test_wake_reports_every_other_error():
    fake = FakeRds("stopped")
    fake.start_error = client_error("AccessDenied", "StartDBInstance")

    with pytest.raises(ClientError):
        instance(fake).wake()


def test_an_aws_failure_fails_open(monkeypatch):
    """A credential or throttling problem says nothing about the database."""
    fake_cache = FakeCache()
    monkeypatch.setattr(rds, "cache", fake_cache)
    fake = FakeRds()
    fake.describe_error = client_error("AccessDenied")
    rds_instance = instance(fake)

    assert rds_instance.state() is DatabaseState.AVAILABLE
    assert rds_instance.state() is DatabaseState.AVAILABLE
    # Not cached: the next request has to ask again.
    assert fake.describes == 2
    assert fake_cache.data == {}


def test_a_network_failure_fails_open():
    fake = FakeRds()
    fake.describe_error = EndpointConnectionError(endpoint_url="https://rds.example.com")

    assert instance(fake).state() is DatabaseState.AVAILABLE


def test_a_missing_instance_is_a_configuration_error():
    fake = FakeRds()
    fake.describe_error = client_error("DBInstanceNotFound")

    with pytest.raises(RdsConfigurationError):
        instance(fake).state()


def test_a_strict_refresh_reports_an_unreachable_api():
    """`wake_db` asks strictly: telling an operator "available" would be a lie.

    A request fails open because the query behind it is the real judge. A command
    has nothing behind it, so a status it could not read has to be an error.
    """
    fake = FakeRds()
    fake.describe_error = EndpointConnectionError(endpoint_url="https://rds.example.com")

    with pytest.raises(EndpointConnectionError):
        instance(fake).refresh(strict=True)


def test_a_strict_refresh_reports_a_denied_api_too():
    fake = FakeRds()
    fake.describe_error = client_error("AccessDenied")

    with pytest.raises(ClientError):
        instance(fake).refresh(strict=True)


def test_a_strict_refresh_reports_a_description_with_no_instance():
    class Empty:
        def describe_db_instances(self, **kwargs):
            return {"DBInstances": []}

    with pytest.raises(RdsConfigurationError):
        RdsInstance("maasermart-db", client=Empty()).refresh(strict=True)


def test_an_instance_needs_an_identifier():
    with pytest.raises(ValueError):
        RdsInstance("")


def test_wait_returns_when_the_instance_is_available(monkeypatch):
    monkeypatch.setattr(rds, "cache", FakeCache())
    fake = FakeRds()
    fake.statuses = ["stopped", "starting", "available"]
    seen = []

    assert instance(fake).wait(timeout=5, interval=0, on_state=seen.append) is True
    assert seen == [DatabaseState.STOPPED, DatabaseState.WAKING, DatabaseState.AVAILABLE]


def test_wait_gives_up_after_the_timeout(monkeypatch):
    monkeypatch.setattr(rds, "cache", FakeCache())
    fake = FakeRds("stopped")
    seen = []

    assert instance(fake).wait(timeout=0, interval=0, on_state=seen.append) is False
    assert seen == [DatabaseState.STOPPED]
