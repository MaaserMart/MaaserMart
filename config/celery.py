import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

app = Celery("maasermart")
app.config_from_object("django.conf:settings", namespace="CELERY")
# The shared verification task lives outside the apps (D-078), so autodiscovery
# cannot find it; importing it registers it with this Celery app.
import common.verification  # noqa: E402, F401

app.autodiscover_tasks()
