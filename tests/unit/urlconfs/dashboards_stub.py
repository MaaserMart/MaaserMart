"""A URLconf where the dashboards and the chooser exist, for redirect tests."""

from django.http import HttpResponse
from django.urls import include, path


def page(request):
    return HttpResponse()


dashboards = (
    [
        path("dashboard/member/", page, name="dashboard"),
        path("dashboard/rabbi/", page, name="rabbi"),
        path("dashboard/owner/", page, name="charity_owner"),
        path("dashboard/support/", page, name="technical_supporter"),
        path("dashboard/admin/", page, name="admin"),
    ],
    "dashboards",
)
accounts = ([path("accounts/choose-dashboard/", page, name="choose_dashboard")], "accounts")

urlpatterns = [
    path("", page, name="home"),
    path("", include(dashboards)),
    path("", include(accounts)),
]
