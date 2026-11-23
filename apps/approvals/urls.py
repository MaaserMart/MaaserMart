from django.urls import path

from . import views

app_name = "approvals"

urlpatterns = [
    path("", views.queue_view, name="queue"),
    path("<int:request_id>/decide/", views.decide_view, name="decide"),
]
