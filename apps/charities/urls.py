"""URL table for the charities app."""

from django.urls import path

from . import views

app_name = "charities"

urlpatterns = [
    path("", views.listing, name="listing"),
    # §6.2.7: the charity page is /charity/<id>/, settled as D-057.
    path("<int:charity_id>/", views.detail, name="detail"),
    path("<int:charity_id>/link/<int:link_id>/", views.link_redirect, name="link"),
]
