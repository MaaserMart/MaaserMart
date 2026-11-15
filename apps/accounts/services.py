"""Public interface of the accounts app.

Other apps call only the functions defined here, never this app's models, so a
caller asks for "who is this rabbi" or "what is this member called" and not for
a view of USER or RABBI_PROFILE (D-006).
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

from django.db import IntegrityError, transaction
from django.db.models import Q

from .models import RabbiProfile, RoleAssignment, User
from .tasks import send_signup_code


@dataclass(frozen=True)
class RabbiIdentity:
    """A rabbi's public identity, as §5.2.3 stores it.

    `user_id` is USER's id, not RABBI_PROFILE's: HASKAMA stores the user, and
    the listing's filter compares user ids (D-045, audit Q3).
    """

    user_id: int
    display_name: str
    title: str | None

    @property
    def label(self) -> str:
        """The name as it is shown: title and name when there is a title."""
        return f"{self.title} {self.display_name}" if self.title else self.display_name


def search_rabbis(term: str = "") -> tuple[RabbiIdentity, ...]:
    """Every rabbi's public identity, optionally narrowed by a typed term (§6.2.4).

    The listing's Haskamos filter needs this list (D-045), and the charity page
    needs the identity of the rabbis who endorsed one charity. `term` matches
    the display name and the account name, case-insensitively, so a search box
    can be put on the group later without a second function. An empty term
    returns every rabbi, which is what the filter's checkbox list shows.
    """
    profiles = RabbiProfile.objects.select_related("user").order_by("display_name", "user_id")
    if term.strip():
        needle = term.strip()
        profiles = profiles.filter(
            Q(display_name__icontains=needle) | Q(user__username__icontains=needle)
        )
    return tuple(
        RabbiIdentity(
            user_id=profile.user_id, display_name=profile.display_name, title=profile.title
        )
        for profile in profiles
    )


def rabbi_identities(user_ids) -> dict[int, RabbiIdentity]:
    """The identities of the given rabbis, keyed by user id.

    A user with no RABBI_PROFILE (a haskama whose author never completed the
    profile) is left out of the result; the caller decides what to show then
    rather than getting a made-up name.
    """
    ids = list(dict.fromkeys(user_ids))
    if not ids:
        return {}
    profiles = RabbiProfile.objects.filter(user_id__in=ids).select_related("user")
    return {
        profile.user_id: RabbiIdentity(
            user_id=profile.user_id, display_name=profile.display_name, title=profile.title
        )
        for profile in profiles
    }


def usernames(user_ids) -> dict[int, str]:
    """The account names of the given users, keyed by id, for showing authorship."""
    ids = list(dict.fromkeys(user_ids))
    if not ids:
        return {}
    return dict(User.objects.filter(pk__in=ids).values_list("pk", "username"))


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
        if "user_username_ci_uniq" in str(error):
            return SignupOutcome.USERNAME_TAKEN, None
        if "user_email_ci_uniq" in str(error):
            return SignupOutcome.EMAIL_TAKEN, None
        raise
    return SignupOutcome.CREATED, user


def enqueue_signup_code(email, code):
    """Queue the email with a signup code (§6.2.2.5 enqueue_email). Sent by Celery."""
    send_signup_code.delay(email, code)
