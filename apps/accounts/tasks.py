"""Emails accounts sends, through Celery (§4.14)."""

from celery import shared_task

from common.verification import send_verification_code


@shared_task
def send_signup_code(email, code):
    """The shared verification-code email, worded for signup (D-078)."""
    send_verification_code(email, code, "signup")
