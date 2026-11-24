"""Support's pages under /support/ (D-026)."""

from django.urls import path

from . import views

app_name = "support"

urlpatterns = [
    path("help/", views.help_page, name="help"),
    path("report/", views.report_page, name="report"),
]
