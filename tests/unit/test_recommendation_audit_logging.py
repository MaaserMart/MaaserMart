"""Personal recommendation signals stay out of ordinary application logs."""

import os
import stat
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]


def _run(script, log_dir):
    env = {
        **os.environ,
        "DJANGO_SECRET_KEY": "s" * 40,
        "DJANGO_ALLOWED_HOSTS": "maasermart.example",
        "DJANGO_LOG_DIR": str(log_dir),
        "EMAIL_HOST": "smtp.example",
        "EMAIL_HOST_USER": "user",
        "EMAIL_HOST_PASSWORD": "password",
        "RDS_INSTANCE_ID": "",
    }
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=BASE_DIR, env=env, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


def test_production_audit_log_is_private_and_does_not_propagate(tmp_path):
    _run(
        "import logging, logging.config\n"
        "from config.settings.prod import LOGGING\n"
        "LOGGING['handlers']['recommendation_audit']['maxBytes'] = 150\n"
        "logging.config.dictConfig(LOGGING)\n"
        "audit = logging.getLogger('maasermart.recommendations.audit')\n"
        "logging.getLogger('ordinary').warning('GENERAL_MARKER')\n"
        "for i in range(5): audit.info('PRIVATE_MARKER %s %s', i, 'x' * 90)\n"
        "logging.shutdown()\n",
        tmp_path,
    )
    general = (tmp_path / "maasermart.log").read_text()
    logs = sorted(tmp_path.glob("recommendations-audit.log*"))
    assert "GENERAL_MARKER" in general
    assert "PRIVATE_MARKER" not in general
    assert len(logs) > 1  # the rotated backups need the same protection
    assert any("PRIVATE_MARKER" in path.read_text() for path in logs)
    for path in logs:
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
    lockfiles = list(tmp_path.glob("*recommendations-audit*.lock"))
    assert lockfiles
    assert all(stat.S_IMODE(path.stat().st_mode) == 0o600 for path in lockfiles)


def test_nonproduction_audit_logger_does_not_send_to_root(tmp_path):
    _run(
        "import io, logging, logging.config\n"
        "from config.settings.base import LOGGING\n"
        "logging.config.dictConfig(LOGGING)\n"
        "output = io.StringIO()\n"
        "logging.getLogger().addHandler(logging.StreamHandler(output))\n"
        "logging.getLogger('maasermart.recommendations.audit').info('PRIVATE_MARKER')\n"
        "assert 'PRIVATE_MARKER' not in output.getvalue()\n",
        tmp_path,
    )
