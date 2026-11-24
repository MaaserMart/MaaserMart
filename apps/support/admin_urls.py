"""The admin ticket queue at /admin/tickets/ (§7.3.10, D-027).

Separate from `urls.py` because it lives under /admin/, not /support/.
"""

from django.urls import path

from . import views

app_name = "support_admin"

urlpatterns = [
    path("", views.ticket_queue, name="tickets"),
    path("<int:ticket_id>/", views.resolve, name="resolve"),
]
