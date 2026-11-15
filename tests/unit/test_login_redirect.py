"""Where a user goes after login (§6.2.1.6, D-YOSEF-accounts-login)."""

import pytest
from django.test import RequestFactory
from django.urls import reverse

from apps.accounts.login import redirect_after_login
from apps.accounts.models import RoleAssignment
from tests.factories import RoleAssignmentFactory, UserFactory

pytestmark = pytest.mark.django_db

Role = RoleAssignment.Role
STUB = "tests.unit.urlconfs.dashboards_stub"


def user_with(*roles, **fields):
    user = UserFactory(**fields)
    for role in roles:
        RoleAssignmentFactory(user=user, role=role)
    return user


def request(next_url=None, method="post", secure=False):
    data = {"next": next_url} if next_url is not None else {}
    factory = RequestFactory()
    make = factory.post if method == "post" else factory.get
    return make("/accounts/login/", data, secure=secure)


def go(user, next_url=None, **kw):
    return redirect_after_login(request(next_url, **kw), user)


# --- ?next= that should be followed ------------------------------------------


@pytest.mark.parametrize(
    "next_url",
    ["/charity/12/", "/charity/?q=bread&sort=name", "/accounts/rabbi-signup/"],
)
def test_a_path_on_this_site_is_followed(next_url):
    assert go(user_with(Role.MEMBER), next_url) == next_url


def test_next_in_the_query_string_is_followed():
    assert go(user_with(Role.MEMBER), "/charity/12/", method="get") == "/charity/12/"


def test_next_wins_over_several_roles():
    user = user_with(Role.MEMBER, Role.RABBI)
    assert go(user, "/charity/12/") == "/charity/12/"


def test_a_full_address_on_this_site_is_followed():
    assert go(user_with(Role.MEMBER), "http://testserver/charity/12/") == (
        "http://testserver/charity/12/"
    )


# --- ?next= that should NOT be followed --------------------------------------


@pytest.mark.parametrize(
    "next_url",
    [
        "https://evil.com/",  # another site
        "//evil.com/",  # another site, no scheme
        "http://testserver.evil.com/",  # looks like ours, isn't
        "javascript:alert(1)",  # runs script
        "https:///evil.com",  # malformed, browsers read it as evil.com
        "/\\evil.com",  # backslash trick some browsers read as //evil.com
        "",  # empty
    ],
)
def test_a_next_that_leaves_the_site_is_ignored(next_url):
    assert go(user_with(Role.MEMBER), next_url) == reverse("home")


def test_an_http_next_is_ignored_on_an_https_request():
    """Following it would drop the user from HTTPS to plain HTTP."""
    user = user_with(Role.MEMBER)
    assert go(user, "http://testserver/charity/12/", secure=True) == reverse("home")


# --- by role, with the dashboards in place -----------------------------------


@pytest.mark.urls(STUB)
@pytest.mark.parametrize(
    ("role", "path"),
    [
        (Role.MEMBER, "/dashboard/member/"),
        (Role.RABBI, "/dashboard/rabbi/"),
        (Role.CHARITY_OWNER, "/dashboard/owner/"),
        (Role.TECHNICAL_SUPPORTER, "/dashboard/support/"),
    ],
)
def test_one_role_goes_to_its_dashboard(role, path):
    assert go(user_with(role)) == path


@pytest.mark.urls(STUB)
def test_admin_only_goes_to_the_admin_dashboard():
    assert go(user_with(is_superuser=True)) == "/dashboard/admin/"


@pytest.mark.urls(STUB)
def test_several_roles_go_to_the_chooser():
    assert go(user_with(Role.MEMBER, Role.RABBI)) == "/accounts/choose-dashboard/"


@pytest.mark.urls(STUB)
def test_a_member_who_is_also_admin_goes_to_the_chooser():
    assert go(user_with(Role.MEMBER, is_superuser=True)) == "/accounts/choose-dashboard/"


@pytest.mark.urls(STUB)
def test_one_role_never_goes_to_the_chooser():
    assert go(user_with(Role.RABBI)) != "/accounts/choose-dashboard/"


@pytest.mark.urls(STUB)
def test_a_user_with_no_roles_goes_home():
    assert go(user_with()) == "/"


# --- by role, before the dashboards exist (the real URLconf today) -----------


def test_without_dashboard_pages_one_role_goes_home():
    assert go(user_with(Role.MEMBER)) == reverse("home")


def test_without_a_chooser_page_several_roles_go_home():
    assert go(user_with(Role.MEMBER, Role.RABBI)) == reverse("home")
