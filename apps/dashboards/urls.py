"""Member dashboard URLs."""

from django.urls import path

from . import views

app_name = "dashboards"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("history/<int:event_id>/hide/", views.hide, name="hide"),
    path("history/clear/", views.clear_history, name="clear-history"),
    path("recommendations/<int:charity_id>/reject/", views.reject, name="reject"),
]
