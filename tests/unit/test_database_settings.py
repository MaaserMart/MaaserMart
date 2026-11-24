"""The connection settings a database that gets stopped needs (D-070).

Two of them are load-bearing rather than taste: without a connect timeout a
request to a stopped instance hangs instead of failing, and without health
checks a worker keeps trusting a socket that died when the instance stopped.
"""

from django.conf import settings


def test_the_connection_gives_up_after_five_seconds():
    assert settings.DATABASES["default"]["OPTIONS"]["connect_timeout"] == 5


def test_a_reused_connection_is_checked_before_it_is_trusted():
    assert settings.DATABASES["default"]["CONN_HEALTH_CHECKS"] is True


def test_the_wake_gate_follows_the_environment():
    """Installed exactly when there is an instance to name, in any environment."""
    installed = "apps.support.middleware.DatabaseWakeMiddleware" in settings.MIDDLEWARE
    assert installed == bool(settings.RDS_INSTANCE_ID)
