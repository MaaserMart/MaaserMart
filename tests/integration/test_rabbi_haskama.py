"""The rabbi dashboard and writing a haskama (§6.2.9, UC-06)."""

import pytest

from apps.accounts.models import RoleAssignment
from apps.accounts.services import is_rabbi
from apps.charities import services as charities
from apps.charities.models import Haskama
from tests.factories import UserFactory
from tests.factories.accounts import RabbiProfileFactory, RoleAssignmentFactory
from tests.factories.charities import CharityFactory

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


# --- Search ------------------------------------------------------------------


def test_a_blank_search_lists_nothing():
    CharityFactory()
    assert charities.search_charities("   ") == ()
    assert charities.search_charities("x" * 101) == ()


# --- The service on its own --------------------------------------------------


def test_is_rabbi_both_ways():
    assert is_rabbi(rabbi().id)
    assert not is_rabbi(pending_rabbi().id)
    assert not is_rabbi(member().id)
    assert not is_rabbi(None)


def test_save_haskama_refuses_a_non_rabbi_before_writing():
    outcome = charities.save_haskama(member().id, CharityFactory().id, "approve")
    assert outcome is charities.HaskamaOutcome.NOT_A_RABBI
    assert not Haskama.objects.exists()


def test_save_haskama_refuses_a_missing_charity():
    outcome = charities.save_haskama(rabbi().id, 999999, "approve")
    assert outcome is charities.HaskamaOutcome.NO_SUCH_CHARITY
    assert not Haskama.objects.exists()


@pytest.mark.parametrize("verdict, importance", [("maybe", None), ("approve", 0), ("approve", 11)])
def test_save_haskama_raises_on_values_a_form_should_have_refused(verdict, importance):
    with pytest.raises(ValueError):
        charities.save_haskama(rabbi().id, CharityFactory().id, verdict, importance)
    assert not Haskama.objects.exists()


def test_save_haskama_creates_then_updates():
    user, charity = rabbi(), CharityFactory()
    assert charities.save_haskama(user.id, charity.id, "approve", 3, "  ") is (
        charities.HaskamaOutcome.CREATED
    )
    assert Haskama.objects.get().body is None  # blank is stored as NULL
    assert charities.save_haskama(user.id, charity.id, "disapprove") is (
        charities.HaskamaOutcome.UPDATED
    )
    assert Haskama.objects.count() == 1
