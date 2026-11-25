"""The nav's Dashboard link and the charity owner dashboard (D-YOSEF-dashboard-router)."""

import pytest

from apps.accounts.models import RoleAssignment
from tests.factories import UserFactory
from tests.factories.accounts import CharityOwnerFactory, RabbiProfileFactory, RoleAssignmentFactory
from tests.factories.charities import CharityFactory

pytestmark = pytest.mark.django_db

Role = RoleAssignment.Role
DASHBOARD = "/dashboard/"
OWNER = "/dashboard/owner/"
RABBI = "/dashboard/rabbi/"
ADMIN = "/dashboard/admin/"


def member():
    return RoleAssignmentFactory(role=Role.MEMBER).user


def rabbi():
    return RabbiProfileFactory().user


def owner():
    user = CharityOwnerFactory().user
    RoleAssignmentFactory(user=user, role=Role.CHARITY_OWNER)
    return user


def admin():
    return UserFactory(is_superuser=True, is_staff=True)


def applicant():
    return UserFactory()


# --- /dashboard/ sends each user to their own page ------------------------


@pytest.mark.parametrize(
    ("who", "where"),
    [
        (rabbi, RABBI),
        (owner, OWNER),
        (admin, ADMIN),
        (applicant, "/accounts/pending/"),
        (member, "/"),  # No member dashboard yet: home, as after login.
    ],
    ids=["rabbi", "owner", "admin", "applicant", "member"],
)
def test_dashboard_sends_each_user_to_their_own_page(client, who, where):
    client.force_login(who())
    response = client.get(DASHBOARD)
    assert response.status_code == 302
    assert response.url == where


def test_someone_with_two_roles_gets_the_chooser(client):
    user = rabbi()
    RoleAssignmentFactory(user=user, role=Role.CHARITY_OWNER)
    client.force_login(user)
    assert client.get(DASHBOARD).url == "/accounts/choose-dashboard/"
    page = client.get("/accounts/choose-dashboard/").content.decode()
    assert RABBI in page
    assert OWNER in page


def test_a_visitor_is_sent_to_log_in_and_back(client):
    response = client.get(DASHBOARD)
    assert response.url == f"/accounts/login/?next={DASHBOARD}"


def test_the_nav_shows_dashboard(client):
    client.force_login(rabbi())
    page = client.get("/charity/").content.decode()
    assert f'href="{DASHBOARD}"' in page


def test_a_role_removed_counts_on_the_next_click(client):
    """Checked on the server on every request, not remembered in the browser."""
    user = rabbi()
    client.force_login(user)
    assert client.get(DASHBOARD).url == RABBI
    RoleAssignment.objects.filter(user=user, role=Role.RABBI).delete()
    RoleAssignmentFactory(user=user, role=Role.MEMBER)
    assert client.get(DASHBOARD).url == "/"
    assert client.get(RABBI).status_code == 404


# --- each dashboard keeps other roles out ---------------------------------


@pytest.mark.parametrize(
    ("who", "path"),
    [
        (member, OWNER),
        (rabbi, OWNER),
        (admin, OWNER),
        (applicant, OWNER),
        (member, RABBI),
        (owner, RABBI),
        (member, ADMIN),
        (owner, ADMIN),
        (rabbi, ADMIN),
    ],
    ids=lambda v: v if isinstance(v, str) else v.__name__,
)
def test_typing_another_roles_dashboard_is_not_found(client, who, path):
    client.force_login(who())
    assert client.get(path).status_code == 404


def test_a_visitor_typing_the_owner_dashboard_is_not_found(client):
    assert client.get(OWNER).status_code == 404


# --- the owner dashboard --------------------------------------------------


def test_the_owner_dashboard_lists_only_their_charities(client):
    user = owner()
    mine = CharityOwnerFactory(user=user, charity=CharityFactory(name="Hatzalah")).charity
    theirs = CharityOwnerFactory(charity=CharityFactory(name="Bikur Cholim")).charity
    client.force_login(user)
    page = client.get(OWNER).content.decode()
    assert "Hatzalah" in page
    assert f'href="/charity/{mine.pk}/"' in page
    assert "Bikur Cholim" not in page
    assert f"/charity/{theirs.pk}/" not in page


def test_an_owner_whose_charities_are_gone_sees_an_empty_list(client):
    user = UserFactory()
    RoleAssignmentFactory(user=user, role=Role.CHARITY_OWNER)
    client.force_login(user)
    assert "own a charity on MaaserMart yet" in client.get(OWNER).content.decode()
