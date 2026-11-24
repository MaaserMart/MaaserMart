"""The maaser tools pages under /tools/ (D-026, D-027)."""

from django.urls import path

from . import views

app_name = "tools"

urlpatterns = [
    path("", views.index, name="index"),
    path("maaser/", views.maaser, name="maaser"),
    path("income/", views.income, name="income"),
    path("donations/", views.donations, name="donations"),
    path("<str:type>/<int:transaction_id>/delete/", views.delete, name="delete"),
]
