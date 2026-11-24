"""Production settings and the Celery wiring (audit T4).

Nearly everything else in the suite runs on `config.settings.test`. These two
guards are the ones whose failure would only appear at deploy time — a typo in a
condition means either a production boot with a development secret, or a deploy
that refuses to start for no reason. The settings are imported in a subprocess
so the reload cannot leak into (or be leaked by) the settings the rest of the
suite is using.
"""

import os
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]

GOOD_ENV = {
    "DJANGO_SECRET_KEY": "s" * 40,
    "DJANGO_ALLOWED_HOSTS": "maasermart.com",
    "EMAIL_HOST": "email-smtp.us-east-2.amazonaws.com",
    "EMAIL_HOST_USER": "smtp-user",
    "EMAIL_HOST_PASSWORD": "smtp-pass",
}


def _run_script(snippet: str, **overrides) -> subprocess.CompletedProcess:
    """Run Python in a clean interpreter with production's environment."""
    env = {
        key: value for key, value in os.environ.items() if not key.startswith(("DJANGO_", "RDS_"))
    }
    env["DJANGO_LOG_DIR"] = str(BASE_DIR / "logs")
    env.update(GOOD_ENV)
    # Base settings also read the developer's `.env` when there is one, and this
    # file asserts what an *unset* RDS_INSTANCE_ID does. Pinning it empty keeps
    # that assertion about the settings rather than about whose machine ran it.
    env["RDS_INSTANCE_ID"] = ""
    env.update(overrides)
    return subprocess.run(
        [sys.executable, "-c", snippet],
        cwd=BASE_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _import_prod(**overrides) -> subprocess.CompletedProcess:
    """Import `config.settings.prod` in a clean interpreter and report the result."""
    return _run_script("import config.settings.prod", **overrides)


def test_prod_settings_import_with_a_real_secret():
    result = _import_prod()

    assert result.returncode == 0, result.stderr


def test_prod_settings_refuse_a_development_secret():
    result = _import_prod(DJANGO_SECRET_KEY="insecure-development-key-change-me")

    assert result.returncode != 0
    assert "DJANGO_SECRET_KEY must be a real secret" in result.stderr


def test_prod_settings_refuse_a_short_secret():
    result = _import_prod(DJANGO_SECRET_KEY="too-short")

    assert result.returncode != 0
    assert "DJANGO_SECRET_KEY must be a real secret" in result.stderr


def test_prod_settings_refuse_no_allowed_hosts():
    result = _import_prod(DJANGO_ALLOWED_HOSTS="")

    assert result.returncode != 0
    assert "DJANGO_ALLOWED_HOSTS must be set" in result.stderr


def test_prod_serves_a_csp_and_preload_hsts(tmp_path):
    """SEC1: the header and the preload value are what the deploy actually gets."""
    snippet = (
        "import config.settings.prod as s\n"
        "print(s.CONTENT_SECURITY_POLICY)\n"
        "print(s.SECURE_HSTS_SECONDS)\n"
        "print(s.SECURE_HSTS_PRELOAD)\n"
        "print('apps.support.middleware.ContentSecurityPolicyMiddleware' in s.MIDDLEWARE)\n"
        "print(s.STORAGES['staticfiles']['BACKEND'])\n"
    )
    env = {key: value for key, value in os.environ.items() if not key.startswith("DJANGO_")}
    env.update(GOOD_ENV)
    env["DJANGO_LOG_DIR"] = str(tmp_path)
    result = subprocess.run(
        [sys.executable, "-c", snippet],
        cwd=BASE_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    policy, hsts, preload, middleware, storage = result.stdout.strip().splitlines()

    assert policy.startswith("default-src 'self'")
    assert int(hsts) >= 365 * 24 * 60 * 60  # the preload list's minimum
    assert preload == "True"
    assert middleware == "True"
    assert storage == "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"


def test_prod_checks_the_rds_instance_before_the_session_reads_it():
    """D-070: the gate must run before anything whose first act is a query."""
    snippet = (
        "import config.settings.prod as s\n"
        "gate = 'apps.support.middleware.DatabaseWakeMiddleware'\n"
        "print(gate in s.MIDDLEWARE)\n"
        "print(s.MIDDLEWARE.index(gate)"
        " < s.MIDDLEWARE.index('django.contrib.sessions.middleware.SessionMiddleware'))\n"
    )
    result = _run_script(snippet, RDS_INSTANCE_ID="maasermart-db")

    assert result.returncode == 0, result.stderr
    installed, before_session = result.stdout.strip().splitlines()
    assert installed == "True"
    assert before_session == "True"


def test_prod_calls_no_aws_api_without_an_instance_identifier():
    """Unset means local Postgres, and the app never talks to AWS about it."""
    result = _run_script(
        "import config.settings.prod as s; "
        "print('apps.support.middleware.DatabaseWakeMiddleware' in s.MIDDLEWARE)"
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "False"


def test_the_celery_app_is_configured_and_discovers_no_tasks_yet():
    """`config/__init__.py` imports this app, so a bad name breaks every command."""
    from config.celery import app

    assert app.main == "maasermart"
    # Settings arrive through the CELERY_ namespace; the test settings ask for
    # an inline broker and eager tasks, and those are what the app must see.
    assert app.conf.broker_url == "memory://"
    assert app.conf.task_always_eager is True
    # No app defines a task yet; the audit's M7 list is where the first one lands.
    assert not [name for name in app.tasks if not name.startswith("celery.")]
