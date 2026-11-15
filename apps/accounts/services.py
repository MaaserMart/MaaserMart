"""Public interface of the accounts app.

Other apps call only the functions defined here, never this app's models.
"""

from .models import RoleAssignment

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
