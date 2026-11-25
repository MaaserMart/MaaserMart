from django.urls import path

from . import views

app_name = "dashboards"

urlpatterns = [
    # The nav's "Dashboard": sends each user to their own page (D-YOSEF-dashboard-router).
    path("", views.dashboard_view, name="dashboard"),
    path("owner/", views.owner_dashboard_view, name="charity_owner"),
    path("admin/", views.admin_dashboard_view, name="admin"),
    # §6.2.9.2: haskama writing lives on the rabbi's dashboard.
    path("rabbi/", views.rabbi_dashboard_view, name="rabbi"),
    path("rabbi/haskama/<int:charity_id>/", views.rabbi_haskama_view, name="rabbi_haskama"),
]
