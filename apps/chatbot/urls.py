"""The chatbot panel's endpoints. §7: a panel on every page, not a page of its own."""

from django.urls import path

from . import views

app_name = "chatbot"

urlpatterns = [
    path("", views.panel, name="panel"),
    path("ask/", views.ask, name="ask"),
    path("clear/", views.clear, name="clear"),
    path("status/<str:task_id>/", views.status, name="status"),
]
