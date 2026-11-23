"""Root URLconf. Each app is mounted under its own prefix as features arrive (D-009)."""

from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

admin.site.site_header = "MaaserMart administration"
admin.site.site_title = "MaaserMart admin"

urlpatterns = [
    # D-028: the listing is the front page; `/` redirects to it while home.html is unused.
    path("", RedirectView.as_view(url="/charity/", permanent=False), name="home"),
    path("charity/", include("apps.charities.urls")),
    path("accounts/", include("apps.accounts.urls")),
    path("dashboard/", include("apps.dashboards.urls")),
    path("admin/approvals/", include("apps.approvals.urls")),
    path("django-admin/", admin.site.urls),
]
