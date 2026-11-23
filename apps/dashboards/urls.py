from django.urls import path

from . import views

app_name = "dashboards"

urlpatterns = [
    path("admin/", views.admin_dashboard_view, name="admin"),
    # §6.2.9.2: haskama writing lives on the rabbi's dashboard.
    path("rabbi/", views.rabbi_dashboard_view, name="rabbi"),
    path("rabbi/haskama/<int:charity_id>/", views.rabbi_haskama_view, name="rabbi_haskama"),
]
