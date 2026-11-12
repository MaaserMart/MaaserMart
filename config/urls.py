"""Root URLconf. Each app is mounted under its own prefix as features arrive."""

from django.contrib import admin
from django.urls import path

urlpatterns = [
    path("django-admin/", admin.site.urls),
]
