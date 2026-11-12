"""Root URL configuration.

Module URLs are included here as their apps are built; each app keeps its own
urls.py (see the Page Inventory in docs/design.docx).
"""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("listing/", include("charities.urls")),
]
