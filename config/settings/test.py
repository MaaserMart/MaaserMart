"""Test runs: fast hashing, in-memory email, Celery inline. Uses DATABASE_URL (Postgres)."""

from .base import *  # noqa: F403
from .base import MIDDLEWARE

DEBUG = False
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
CELERY_TASK_ALWAYS_EAGER = True
CELERY_BROKER_URL = "memory://"
# The suite never talks to AWS, whatever the developer's .env says, so no test
# can describe a status or start the instance that .env names (D-070). `base`
# already inserted the gate while importing, from the .env value, so it is set
# to empty *and* removed. The "installed when set" case is covered in
# test_prod_settings.py, which imports production in a subprocess.
RDS_INSTANCE_ID = ""
MIDDLEWARE = [mw for mw in MIDDLEWARE if not mw.endswith("DatabaseWakeMiddleware")]
