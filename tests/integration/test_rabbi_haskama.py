"""The rabbi dashboard and writing a haskama (§6.2.9, UC-06)."""

import pytest

from apps.accounts.models import RoleAssignment
from apps.accounts.services import is_rabbi
from tests.factories import UserFactory
from tests.factories.accounts import RabbiProfileFactory, RoleAssignmentFactory

pytestmark = pytest.mark.django_db

DASHBOARD = "/dashboard/rabbi/"
APPROVE = {"verdict": "approve", "importance": "7", "body": "Trustworthy."}


def rabbi():
    return RabbiProfileFactory().user


def pending_rabbi():
    """Applied for the role but not approved: has a profile, no rabbi role."""
    return RabbiProfileFactory(approved=False).user


def member():
    return RoleAssignmentFactory(role=RoleAssignment.Role.MEMBER).user


def admin():
    return UserFactory(is_superuser=True, is_staff=True)


def box(charity_id):
    return f"/dashboard/rabbi/haskama/{charity_id}/"


def logged_in(client, user):
    client.force_login(user)
    return client


# --- The service on its own --------------------------------------------------


def test_is_rabbi_both_ways():
    assert is_rabbi(rabbi().id)
    assert not is_rabbi(pending_rabbi().id)
    assert not is_rabbi(member().id)
    assert not is_rabbi(None)
