"""Root URLconf. Each app is mounted under its own prefix as features arrive (D-009)."""

from django.contrib import admin
from django.urls import path
from django.views.generic import TemplateView

urlpatterns = [
    path("", TemplateView.as_view(template_name="home.html"), name="home"),
    path("django-admin/", admin.site.urls),
]
