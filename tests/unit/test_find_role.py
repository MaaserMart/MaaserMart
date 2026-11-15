"""accounts.services.find_role and User.is_admin (§6.2.1.5, D-YOSEF-admin-superuser)."""

import pytest
from django.contrib.auth.models import AnonymousUser
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.accounts.models import RoleAssignment
from apps.accounts.services import find_role
from apps.approvals.models import ApprovalRequest
from tests.factories import ApprovalRequestFactory, RoleAssignmentFactory, UserFactory

pytestmark = pytest.mark.django_db

Role = RoleAssignment.Role


def give(user, *roles):
    for role in roles:
        RoleAssignmentFactory(user=user, role=role)
    return user


# --- is_admin --------------------------------------------------------------


def test_superuser_is_admin():
    assert UserFactory(is_superuser=True, is_staff=True).is_admin is True


def test_superuser_is_admin_even_without_staff():
    assert UserFactory(is_superuser=True, is_staff=False).is_admin is True


def test_regular_user_is_not_admin():
    assert UserFactory().is_admin is False


def test_staff_alone_is_not_admin():
    """A helper given is_staff to reach /django-admin/ is not a MaaserMart admin."""
    assert UserFactory(is_staff=True).is_admin is False


def test_staff_alone_gets_no_admin_role():
    assert find_role(UserFactory(is_staff=True)) == []


# --- find_role: what a user should get --------------------------------------


def test_one_role():
    assert find_role(give(UserFactory(), Role.MEMBER)) == ["member"]


def test_several_roles_in_a_fixed_order():
    user = give(UserFactory(), Role.CHARITY_OWNER, Role.MEMBER, Role.RABBI)
    assert find_role(user) == ["member", "rabbi", "charity_owner"]


def test_admin_is_listed_after_other_roles():
    user = give(UserFactory(is_superuser=True), Role.MEMBER)
    assert find_role(user) == ["member", "admin"]


def test_admin_with_no_role_rows():
    assert find_role(UserFactory(is_superuser=True)) == ["admin"]


def test_every_role_at_once():
    user = give(UserFactory(is_superuser=True), *Role.values)
    assert find_role(user) == [
        "member",
        "rabbi",
        "charity_owner",
        "technical_supporter",
        "admin",
    ]


def test_roles_are_plain_strings():
    (role,) = find_role(give(UserFactory(), Role.MEMBER))
    assert type(role) is str


# --- find_role: what a user should NOT get ----------------------------------


def test_no_roles():
    assert find_role(UserFactory()) == []


def test_pending_rabbi_request_is_not_a_role():
    user = give(UserFactory(), Role.MEMBER)
    ApprovalRequestFactory(submitted_by=user, kind=ApprovalRequest.Kind.RABBI)
    assert find_role(user) == ["member"]


def test_rejected_rabbi_request_is_not_a_role():
    user = give(UserFactory(), Role.MEMBER)
    ApprovalRequestFactory(
        submitted_by=user,
        kind=ApprovalRequest.Kind.RABBI,
        status=ApprovalRequest.Status.REJECTED,
    )
    assert find_role(user) == ["member"]


def test_another_users_roles_are_not_included():
    me = give(UserFactory(), Role.MEMBER)
    give(UserFactory(is_superuser=True), Role.RABBI, Role.CHARITY_OWNER)
    assert find_role(me) == ["member"]


def test_visitor_who_is_not_logged_in_has_no_roles_and_costs_no_query():
    with CaptureQueriesContext(connection) as queries:
        assert find_role(AnonymousUser()) == []
    assert len(queries) == 0


# --- find_role: cost ---------------------------------------------------------


def test_one_query_however_many_roles():
    user = give(UserFactory(is_superuser=True), *Role.values)
    with CaptureQueriesContext(connection) as queries:
        find_role(user)
    assert len(queries) == 1
