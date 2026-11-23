"""The rabbi dashboard and writing a haskama (§6.2.9, UC-06)."""

import pytest
from django.urls import reverse

from apps.accounts.models import RoleAssignment
from apps.accounts.services import is_rabbi
from apps.charities import services as charities
from apps.charities.models import Haskama
from tests.factories import UserFactory
from tests.factories.accounts import RabbiProfileFactory, RoleAssignmentFactory
from tests.factories.charities import CharityFactory, HaskamaFactory

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


# --- URLs and login ---------------------------------------------------------


def test_url_names_match_the_paths():
    assert reverse("dashboards:rabbi") == DASHBOARD
    assert reverse("dashboards:rabbi_haskama", args=[5]) == box(5)


def test_a_rabbi_lands_on_his_dashboard_after_login(client):
    user = rabbi()
    response = client.post(
        reverse("accounts:login"), {"username": user.username, "password": "password"}
    )
    assert response.status_code == 302
    assert response.url == DASHBOARD


# --- Who may see the pages ---------------------------------------------------


def test_a_rabbi_sees_his_dashboard(client):
    response = logged_in(client, rabbi()).get(DASHBOARD)
    assert response.status_code == 200
    assert b"Add a haskama" in response.content


@pytest.mark.parametrize("who", [None, member, pending_rabbi, admin, UserFactory])
def test_anyone_but_a_rabbi_gets_404(client, who):
    charity = CharityFactory()
    if who:
        client.force_login(who())
    assert client.get(DASHBOARD).status_code == 404
    assert client.get(box(charity.id)).status_code == 404
    assert client.post(box(charity.id), APPROVE).status_code == 404
    assert not Haskama.objects.exists()


def test_the_dashboard_lists_only_his_own_haskamos(client):
    user = rabbi()
    mine = HaskamaFactory(rabbi_user=user, charity=CharityFactory(name="Mine Fund"))
    HaskamaFactory(rabbi_user=rabbi(), charity=CharityFactory(name="Other Fund"))
    response = logged_in(client, user).get(DASHBOARD)
    assert mine.charity.name.encode() in response.content
    assert b"Other Fund" not in response.content


# --- Search ------------------------------------------------------------------


def test_search_finds_a_charity_by_name(client):
    CharityFactory(name="Hatzolah Volunteers")
    CharityFactory(name="Bikur Cholim")
    response = logged_in(client, rabbi()).get(DASHBOARD, {"q": "hatz"}, HTTP_HX_REQUEST="true")
    assert b"Hatzolah Volunteers" in response.content
    assert b"Bikur Cholim" not in response.content
    assert b"<html" not in response.content  # only the results list comes back


def test_a_blank_search_lists_nothing():
    CharityFactory()
    assert charities.search_charities("   ") == ()
    assert charities.search_charities("x" * 101) == ()


def test_search_without_javascript_shows_results_on_the_page(client):
    CharityFactory(name="Hatzolah Volunteers")
    response = logged_in(client, rabbi()).get(DASHBOARD, {"q": "hatz"})
    assert b"Hatzolah Volunteers" in response.content
    assert b"<html" in response.content


# --- Writing and editing -----------------------------------------------------


def test_a_rabbi_adds_a_haskama_and_sees_it_on_the_charity_page(client):
    user = rabbi()
    charity = CharityFactory()
    logged_in(client, user)
    response = client.post(box(charity.id) + "?from=charity", APPROVE)
    assert response.status_code == 302
    assert response.url == f"/charity/{charity.id}/"
    haskama = Haskama.objects.get()
    assert (haskama.rabbi_user, haskama.charity, haskama.verdict, haskama.importance) == (
        user,
        charity,
        "approve",
        7,
    )
    page = client.get(response.url)
    assert b"Trustworthy." in page.content


def test_from_the_dashboard_saving_returns_to_the_dashboard(client):
    response = logged_in(client, rabbi()).post(box(CharityFactory().id), APPROVE)
    assert response.url == DASHBOARD


def test_a_second_submit_edits_the_first_instead_of_adding(client):
    user = rabbi()
    charity = CharityFactory()
    logged_in(client, user)
    client.post(box(charity.id), APPROVE)
    client.post(box(charity.id), {"verdict": "disapprove", "importance": "", "body": ""})
    haskama = Haskama.objects.get()
    assert (haskama.verdict, haskama.importance, haskama.body) == ("disapprove", None, None)


def test_the_box_opens_filled_in_when_he_already_wrote_one(client):
    user = rabbi()
    haskama = HaskamaFactory(rabbi_user=user, body="Known to me for years.")
    response = logged_in(client, user).get(box(haskama.charity_id))
    assert b"Edit your haskama" in response.content
    assert b"Known to me for years." in response.content


def test_the_box_opens_empty_for_a_new_charity(client):
    response = logged_in(client, rabbi()).get(box(CharityFactory().id))
    assert b"Add a haskama" in response.content


def test_a_missing_charity_is_404(client):
    logged_in(client, rabbi())
    assert client.get(box(999999)).status_code == 404
    assert client.post(box(999999), APPROVE).status_code == 404
    assert not Haskama.objects.exists()


@pytest.mark.parametrize(
    "changes",
    [
        {"verdict": ""},
        {"verdict": "maybe"},
        {"importance": "0"},
        {"importance": "11"},
        {"importance": "seven"},
        {"body": "x" * 5001},
    ],
)
def test_bad_values_are_refused_and_nothing_is_written(client, changes):
    response = logged_in(client, rabbi()).post(box(CharityFactory().id), {**APPROVE, **changes})
    assert response.status_code == 200
    assert b"auth__field-error" in response.content
    assert not Haskama.objects.exists()


@pytest.mark.parametrize("importance", ["1", "10", ""])
def test_the_edges_of_importance_are_accepted(client, importance):
    response = logged_in(client, rabbi()).post(
        box(CharityFactory().id), {**APPROVE, "importance": importance}
    )
    assert response.status_code == 302
    assert Haskama.objects.count() == 1


def test_from_is_a_fixed_word_not_a_url(client):
    response = logged_in(client, rabbi()).post(
        box(CharityFactory().id) + "?from=https://evil.example", APPROVE
    )
    assert response.url == DASHBOARD


# --- No id swapping ----------------------------------------------------------


def test_a_rabbi_cannot_reach_or_change_another_rabbis_haskama(client):
    """Rabbi B uses Rabbi A's charity in the address: he gets his own box, never A's."""
    rabbi_a, rabbi_b = rabbi(), rabbi()
    theirs = HaskamaFactory(rabbi_user=rabbi_a, body="A's words.", verdict="approve")
    logged_in(client, rabbi_b)
    response = client.get(box(theirs.charity_id))
    assert b"A's words." not in response.content
    assert b"Add a haskama" in response.content
    client.post(box(theirs.charity_id), {"verdict": "disapprove"})
    theirs.refresh_from_db()
    assert (theirs.verdict, theirs.body) == ("approve", "A's words.")
    assert Haskama.objects.filter(rabbi_user=rabbi_b, charity=theirs.charity).exists()


def test_a_posted_rabbi_or_haskama_id_is_ignored(client):
    rabbi_a, rabbi_b = rabbi(), rabbi()
    theirs = HaskamaFactory(rabbi_user=rabbi_a)
    logged_in(client, rabbi_b).post(
        box(theirs.charity_id),
        {**APPROVE, "rabbi_user": rabbi_a.id, "rabbi_user_id": rabbi_a.id, "id": theirs.id},
    )
    assert Haskama.objects.filter(rabbi_user=rabbi_a).count() == 1
    assert Haskama.objects.filter(rabbi_user=rabbi_b).count() == 1


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
