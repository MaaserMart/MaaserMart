from django.urls import path

from . import views

app_name = "dashboards"

urlpatterns = [
    path("admin/", views.admin_dashboard_view, name="admin"),
]
