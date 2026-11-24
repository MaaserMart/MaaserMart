"""Production: behind Caddy + Gunicorn, Postgres on RDS, SQS for Celery, SES for email."""

from pathlib import Path

from .base import *  # noqa: F403
from .base import BASE_DIR, env

DEBUG = False

# Refuse to boot with a development secret or no allowed hosts. Checked here,
# in production settings only, so local and test runs are unaffected.
_INSECURE_KEY = "insecure-development-key-change-me"
if SECRET_KEY == _INSECURE_KEY or len(SECRET_KEY) < 32:  # noqa: F405
    raise RuntimeError("DJANGO_SECRET_KEY must be a real secret (32+ chars) in production.")
if not ALLOWED_HOSTS:  # noqa: F405
    raise RuntimeError("DJANGO_ALLOWED_HOSTS must be set in production.")

# The CSP is served by an explicit middleware only in production (SEC1).
MIDDLEWARE.append("apps.support.middleware.ContentSecurityPolicyMiddleware")  # noqa: F405
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; img-src 'self' https:; base-uri 'none'; "
    "form-action 'self'; frame-ancestors 'none'"
)

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
# One year is the preload list's minimum, which is also what SECURE_HSTS_PRELOAD
# promises (SEC1, D-059). A shorter value with preload on would be refused.
SECURE_HSTS_SECONDS = env.int("DJANGO_SECURE_HSTS_SECONDS", default=60 * 60 * 24 * 365)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])

# Versioned static filenames, so a deploy busts cached CSS and JS (P3).
# Requires `collectstatic` at deploy time, which Caddy serves from STATIC_ROOT.
STORAGES = {
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage",
    }
}

# Email through SES SMTP.
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = env("EMAIL_HOST")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD")
EMAIL_USE_TLS = True

# Celery over SQS; credentials come from the instance role or AWS_* env vars.
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="sqs://")
CELERY_BROKER_TRANSPORT_OPTIONS = {"region": env("AWS_REGION", default="us-east-2")}
CELERY_TASK_ALWAYS_EAGER = False

# A real model in production; without its key the chatbot answers "couldn't get
# an answer" rather than echoing like the fake (D-075).
CHATBOT_PROVIDER = env("CHATBOT_PROVIDER", default="openai")

LOG_DIR = Path(env("DJANGO_LOG_DIR", default=str(BASE_DIR / "logs")))
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "{asctime} {levelname} {name} {process:d} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "file": {
            "class": "concurrent_log_handler.ConcurrentRotatingFileHandler",
            "filename": str(LOG_DIR / "maasermart.log"),
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 10,
            "formatter": "standard",
        },
    },
    "root": {"handlers": ["file"], "level": env("DJANGO_LOG_LEVEL", default="INFO")},
}
