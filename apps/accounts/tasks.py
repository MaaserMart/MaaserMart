"""Emails accounts sends, through Celery (§4.14)."""

from celery import shared_task
from django.core.mail import send_mail

from .models import User


@shared_task
def send_signup_code(email, code):
    send_mail(
        subject=f"Your MaaserMart code: {code}",
        message=(
            f"Your MaaserMart signup code is {code}.\n\n"
            "It works for 15 minutes. If you didn't sign up, ignore this email."
        ),
        from_email=None,  # DEFAULT_FROM_EMAIL
        recipient_list=[email],
    )


@shared_task
def send_notice(user_id, subject, message):
    """Email one user, e.g. an admin's decision. Nothing is sent if the account is gone."""
    email = User.objects.filter(pk=user_id).values_list("email", flat=True).first()
    if email:
        send_mail(subject=subject, message=message, from_email=None, recipient_list=[email])
