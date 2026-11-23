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
from .tasks import send_notice, send_signup_code


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
    # Only approved rabbis: a pending or rejected applicant also has a profile
    # (§6.2.2.5 saves it with the request), but must not appear as a rabbi.
    profiles = (
        RabbiProfile.objects.filter(user__role_assignments__role=RoleAssignment.Role.RABBI)
        .select_related("user")
        .order_by("display_name", "user_id")
    )
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


def emails(user_ids) -> dict[int, str]:
    """The email addresses of the given users, keyed by id. For admins' eyes only."""
    ids = list(dict.fromkeys(user_ids))
    if not ids:
        return {}
    return dict(User.objects.filter(pk__in=ids).values_list("pk", "email"))


def usernames(user_ids) -> dict[int, str]:
    """The account names of the given users, keyed by id, for showing authorship."""
    ids = list(dict.fromkeys(user_ids))
    if not ids:
        return {}
    return dict(User.objects.filter(pk__in=ids).values_list("pk", "username"))


ADMIN = "admin"
RABBI = RoleAssignment.Role.RABBI.value

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
    return _create_account(username, email, password_hash, RoleAssignment.Role.MEMBER)


def submit_applicant_signup(username, email, password_hash):
    """Create a USER with no role yet: a rabbi or owner applicant (D-YOSEF-rabbi-signup).

    The account can't log in until an admin approves its application and grants
    the role. Returns (SignupOutcome, user or None), as submit_member_signup does.
    """
    return _create_account(username, email, password_hash, None)


def _create_account(username, email, password_hash, role):
    try:
        with transaction.atomic():
            user = User.objects.create(username=username, email=email, password=password_hash)
            if role is not None:
                RoleAssignment.objects.create(user=user, role=role)
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


def grant_role(user_id, role):
    """Give a user a role (§6.2.13.5). Granting a role they already hold changes nothing."""
    RoleAssignment.objects.get_or_create(user_id=user_id, role=role)


def save_rabbi_profile(user_id, display_name, title):
    """Save the name and title a rabbi applied with (§5.2.3), replacing any earlier ones.

    The profile is public only once the user holds the rabbi role (see search_rabbis).
    """
    RabbiProfile.objects.update_or_create(
        user_id=user_id, defaults={"display_name": display_name, "title": title or None}
    )


def notify_user(user_id, subject, message):
    """Email a user by id. The address is read when the email is sent."""
    send_notice.delay(user_id, subject, message)
