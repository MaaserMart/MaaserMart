"""URL table for the charities app."""

from django.urls import path

from . import views

app_name = "charities"

urlpatterns = [
    path("", views.listing, name="listing"),
]
