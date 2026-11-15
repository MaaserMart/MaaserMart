"""Public interface of the accounts app.

Other apps call only the functions defined here, never this app's models.
"""

import enum

from django.db import IntegrityError, transaction

from .models import RoleAssignment, User
from .tasks import send_signup_code

ADMIN = "admin"

# The order roles appear in, e.g. on the dashboard chooser.
_ROLE_ORDER = [
    RoleAssignment.Role.MEMBER,
    RoleAssignment.Role.RABBI,
    RoleAssignment.Role.CHARITY_OWNER,
    RoleAssignment.Role.TECHNICAL_SUPPORTER,
    ADMIN,
]


def find_role(user):
    """Return the roles a user holds, e.g. ["member", "rabbi"] (§6.2.1.5).

    Only granted roles are returned. A pending rabbi or owner request is not
    a role yet: its ROLE_ASSIGNMENT row is created when an admin approves it.
    "admin" is included when user.is_admin. One query; none for a visitor who
    isn't logged in.
    """
    if not user.is_authenticated:
        return []
    roles = set(RoleAssignment.objects.filter(user=user).values_list("role", flat=True))
    if user.is_admin:
        roles.add(ADMIN)
    return [str(role) for role in _ROLE_ORDER if role in roles]


class SignupOutcome(enum.Enum):
    CREATED = "created"
    USERNAME_TAKEN = "username_taken"
    EMAIL_TAKEN = "email_taken"


def submit_member_signup(username, email, password_hash):
    """Create a USER with the member role (§6.2.2.5). Both rows or neither.

    Takes the password already hashed, so the plain password never has to be
    kept between signup steps. The unique indexes decide if two people race for
    the same username or email. Returns (SignupOutcome, user or None).
    """
    try:
        with transaction.atomic():
            user = User.objects.create(username=username, email=email, password=password_hash)
            RoleAssignment.objects.create(user=user, role=RoleAssignment.Role.MEMBER)
    except IntegrityError as error:
        constraint = getattr(getattr(error.__cause__, "diag", None), "constraint_name", None)
        if constraint == "user_username_ci_uniq":
            return SignupOutcome.USERNAME_TAKEN, None
        if constraint == "user_email_ci_uniq":
            return SignupOutcome.EMAIL_TAKEN, None
        raise
    return SignupOutcome.CREATED, user


def enqueue_signup_code(email, code):
    """Queue the email with a signup code (§6.2.2.5 enqueue_email). Sent by Celery."""
    send_signup_code.delay(email, code)
