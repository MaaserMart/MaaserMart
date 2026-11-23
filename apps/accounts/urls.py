from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("signup/", views.signup_view, name="signup"),
    path("signup/verify/", views.signup_verify_view, name="signup_verify"),
    path("rabbi-signup/", views.rabbi_signup_view, name="rabbi_signup"),
    path("rabbi-application/", views.rabbi_application_view, name="rabbi_application"),
    path("pending/", views.pending_view, name="pending"),
    path("choose-dashboard/", views.choose_dashboard_view, name="choose_dashboard"),
]
