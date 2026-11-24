"""Settings shared by every environment. Secrets come from environment variables only."""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY")

# Password for the admin user that `manage.py seed` creates. Unset on purpose:
# locally the seed picks one at random and prints it (SEC4).
ADMIN_SEED_PASSWORD = env("ADMIN_SEED_PASSWORD", default="")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.accounts",
    "apps.charities",
    "apps.events",
    "apps.approvals",
    "apps.support",
    "apps.tools",
    "apps.recommendations",
    "apps.chatbot",
    "apps.dashboards",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                # The nav's links: only what a URL pattern actually resolves (B1).
                "apps.support.context_processors.nav",
            ],
        },
    },
]

DATABASES = {"default": env.db("DATABASE_URL")}
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DATABASE_CONN_MAX_AGE", default=60)
# A stopped RDS instance does not refuse connections, it ignores them, so an
# untimed connect holds a worker until the OS gives up. Five seconds turns that
# into an error the wake gate can act on (D-070).
DATABASES["default"].setdefault("OPTIONS", {})["connect_timeout"] = env.int(
    "DATABASE_CONNECT_TIMEOUT", default=5
)
# A worker keeps a socket for `CONN_MAX_AGE` seconds. If the instance was stopped
# inside that window the socket is dead, and without this check the first
# request after a wake-up fails instead of reconnecting (D-070).
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True

# Caches shared by every Gunicorn worker, so login lockout and rate-limit counters
# hold across workers and restarts. Needs `manage.py createcachetable` once per
# database, which makes both tables (D-YOSEF-shared-cache).
# A DatabaseCache over MAX_ENTRIES deletes its alphabetically lowest keys, live or
# not. Login failures and locks get their own table, so a flood of other keys
# (e.g. one rate-limit bucket per IP) can never delete a lock.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "django_cache",
        "OPTIONS": {"MAX_ENTRIES": 100_000},
    },
    "login": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "login_cache",
        "OPTIONS": {"MAX_ENTRIES": 1_000_000},
    },
}

# Addresses whose X-Forwarded-For header is believed: Caddy on the same machine.
# Gunicorn must listen on TCP (e.g. 127.0.0.1:8000), not a unix socket: over a
# socket REMOTE_ADDR is empty, every visitor would share one rate-limit bucket,
# and 20 logins a minute would be the limit for the whole site.
TRUSTED_PROXY_IPS = env.list("DJANGO_TRUSTED_PROXY_IPS", default=["127.0.0.1", "::1"])

AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = ["apps.accounts.backends.CaseInsensitiveModelBackend"]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# Filter option lists are cached briefly so the sidebar does not read the whole
# domain and location tables on every listing request (audit P1, D-061). LocMem is
# per process, which is exactly the point: a multi-megabyte directory is read once
# a minute per worker instead of once per page. The cache never stores users. It is
# its own alias so the shared caches above stay shared (D-YOSEF-shared-cache).
CACHES["options"] = {
    "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    "LOCATION": "maasermart-options",
}

# --- RDS wake-up (D-070) -----------------------------------------------------
# The deployed database lives on RDS and is stopped when nobody is using it, so
# a request can arrive with nothing to connect to. When the instance identifier
# is set, every request first asks the AWS API whether it is up and starts it if
# it is not. Unset means the app never calls AWS, which is what local Postgres
# and the test suite want.
RDS_INSTANCE_ID = env("RDS_INSTANCE_ID", default="")
AWS_REGION = env("AWS_REGION", default="us-east-1")
# Cached status: a minute while the database is up (it stays up), seconds while
# it is not, so a page polling during a start sees the change.
DATABASE_WAKE_AVAILABLE_TTL = env.int("DATABASE_WAKE_AVAILABLE_TTL", default=60)
DATABASE_WAKE_WAKING_TTL = env.int("DATABASE_WAKE_WAKING_TTL", default=10)
# How long the waiting page asks a browser to wait before reloading.
DATABASE_WAKE_RETRY_AFTER = env.int("DATABASE_WAKE_RETRY_AFTER", default=15)
if RDS_INSTANCE_ID:
    # Immediately after SecurityMiddleware, deliberately before SessionMiddleware:
    # the session store reads the database, so it has to run after this gate.
    MIDDLEWARE.insert(1, "apps.support.middleware.DatabaseWakeMiddleware")

# Hosts a charity image may be loaded from, besides the repo's own static files
# (D-021, audit B8). An entry starting with "." allows subdomains. Empty means
# only repo-relative paths are allowed, which is the safe default.
CHARITY_IMAGE_HOSTS = env.list("CHARITY_IMAGE_HOSTS", default=[])

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Celery (broker is SQS in production; see prod.py).
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="memory://")
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=False)

DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="no-reply@maasermart.com")
