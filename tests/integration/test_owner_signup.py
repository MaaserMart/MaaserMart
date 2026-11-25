"""Charity owner signup: claiming a charity and the admin deciding it (D-YOSEF-owner-signup)."""

import re

import pytest
from django.contrib.auth import SESSION_KEY
from django.core import mail

from apps.accounts.models import CharityOwner, RoleAssignment, User
from apps.approvals import services as approvals
from apps.approvals.models import ApprovalRequest, OwnerClaimRequest
from tests.factories import UserFactory
from tests.factories.accounts import CharityOwnerFactory, RoleAssignmentFactory
from tests.factories.charities import CharityFactory

pytestmark = pytest.mark.django_db

OWNER = RoleAssignment.Role.CHARITY_OWNER


def applicant():
    """An account with no role, as a confirmed owner signup leaves it."""
    return UserFactory()


def admin():
    return UserFactory(is_superuser=True, is_staff=True)


def is_owner(user):
    return RoleAssignment.objects.filter(user=user, role=OWNER).exists()


def claimed(user, charity):
    approvals.submit_owner_claim(user, charity.pk)
    return ApprovalRequest.objects.get(submitted_by=user, kind="owner_claim")


# --- submit_owner_claim ---------------------------------------------------


def test_a_claim_waits_for_an_admin_and_owns_nothing_yet():
    user, charity = applicant(), CharityFactory()
    outcome = approvals.submit_owner_claim(user, charity.pk)
    assert outcome is approvals.SubmitOutcome.SUBMITTED
    request = ApprovalRequest.objects.get(submitted_by=user)
    assert (request.kind, request.status) == ("owner_claim", "pending")
    assert OwnerClaimRequest.objects.get(approval_request=request).charity_id == charity.pk
    assert not is_owner(user)
    assert not CharityOwner.objects.filter(user=user).exists()


def test_a_claim_for_a_charity_that_does_not_exist_is_refused():
    user = applicant()
    outcome = approvals.submit_owner_claim(user, 999_999)
    assert outcome is approvals.SubmitOutcome.NO_SUCH_CHARITY
    assert not ApprovalRequest.objects.filter(submitted_by=user).exists()


def test_a_second_claim_is_refused():
    user = applicant()
    claimed(user, CharityFactory())
    outcome = approvals.submit_owner_claim(user, CharityFactory().pk)
    assert outcome is approvals.SubmitOutcome.ALREADY_APPLIED
    assert ApprovalRequest.objects.filter(submitted_by=user).count() == 1


def test_an_account_that_applied_as_a_rabbi_cannot_also_claim():
    """One application per account, of any kind."""
    user = applicant()
    approvals.submit_rabbi_request(user, "Moshe Cohen", "Rav")
    outcome = approvals.submit_owner_claim(user, CharityFactory().pk)
    assert outcome is approvals.SubmitOutcome.ALREADY_APPLIED


def test_an_account_that_claimed_cannot_also_apply_as_a_rabbi():
    user = applicant()
    claimed(user, CharityFactory())
    outcome = approvals.submit_rabbi_request(user, "Moshe Cohen", "Rav")
    assert outcome is approvals.SubmitOutcome.ALREADY_APPLIED


def test_an_owner_cannot_claim_through_signup():
    owner = RoleAssignmentFactory(role=OWNER).user
    outcome = approvals.submit_owner_claim(owner, CharityFactory().pk)
    assert outcome is approvals.SubmitOutcome.ALREADY_GRANTED
    assert not ApprovalRequest.objects.filter(submitted_by=owner).exists()


def test_another_users_claim_on_the_same_charity_does_not_block_this_one():
    """Who really runs a charity is the admin's call, so both claims reach the queue."""
    charity = CharityFactory()
    CharityOwnerFactory(charity=charity)
    claimed(applicant(), charity)
    outcome = approvals.submit_owner_claim(applicant(), charity.pk)
    assert outcome is approvals.SubmitOutcome.SUBMITTED


# --- deciding a claim -----------------------------------------------------


def test_approving_makes_the_user_an_owner_of_that_charity(django_capture_on_commit_callbacks):
    user, charity, other = applicant(), CharityFactory(), CharityFactory()
    request = claimed(user, charity)
    with django_capture_on_commit_callbacks(execute=True):
        outcome = approvals.decide_request(request.pk, True, admin())
    assert outcome is approvals.DecideOutcome.DONE
    assert is_owner(user)
    owned = list(CharityOwner.objects.filter(user=user).values_list("charity_id", flat=True))
    assert owned == [charity.pk]
    assert other.pk not in owned
    assert mail.outbox[-1].to == [user.email]
    assert mail.outbox[-1].subject == "Your MaaserMart charity owner account is approved"


def test_rejecting_makes_no_owner_and_says_so(django_capture_on_commit_callbacks):
    user, charity = applicant(), CharityFactory()
    request = claimed(user, charity)
    with django_capture_on_commit_callbacks(execute=True):
        approvals.decide_request(request.pk, False, admin())
    assert not is_owner(user)
    assert not CharityOwner.objects.filter(user=user).exists()
    assert "charity owner application wasn't approved" in mail.outbox[-1].body


def test_the_status_names_the_charity_owner_role():
    user = applicant()
    claimed(user, CharityFactory())
    assert approvals.latest_application(user) == ("charity owner", "pending")


def test_the_queue_shows_which_charity_is_claimed():
    user, charity = applicant(), CharityFactory(name="Tomchei Shabbos")
    claimed(user, charity)
    [item] = approvals.get_requests()
    assert item.kind == "owner_claim"
    assert item.detail == f"Claims Tomchei Shabbos (#{charity.pk})"
    assert item.decidable


# --- the pages ------------------------------------------------------------

SIGNUP = "/accounts/owner-signup/"
VERIFY = "/accounts/signup/verify/"
CLAIM = "/accounts/owner-application/"
STATUS = "/accounts/pending/"
ACCOUNT = {
    "username": "dlevi",
    "email": "dlevi@example.com",
    "password": "a-long-pass-42",
    "agree": "on",
}


def sign_up_as_owner(client):
    """Fill in the owner signup page and type the emailed code. Returns the code page's reply."""
    client.post(SIGNUP, ACCOUNT)
    code = re.search(r"\d{6}", mail.outbox[-1].body).group()
    return client.post(VERIFY, {"code": code})


def member():
    return RoleAssignmentFactory(role=RoleAssignment.Role.MEMBER).user


def test_the_member_signup_page_links_the_owner_signup(client):
    assert SIGNUP in client.get("/accounts/signup/").content.decode()


def test_the_code_creates_a_roleless_account_and_opens_the_claim_page(client):
    response = sign_up_as_owner(client)
    assert response.status_code == 302
    assert response.url == CLAIM
    user = User.objects.get(username="dlevi")
    assert not RoleAssignment.objects.filter(user=user).exists()
    assert int(client.session[SESSION_KEY]) == user.pk


def test_a_rabbi_signup_still_opens_the_rabbi_application(client):
    client.post("/accounts/rabbi-signup/", ACCOUNT)
    code = re.search(r"\d{6}", mail.outbox[-1].body).group()
    assert client.post(VERIFY, {"code": code}).url == "/accounts/rabbi-application/"


def test_the_claim_page_finds_charities_by_name(client):
    CharityFactory(name="Tomchei Shabbos")
    CharityFactory(name="Hatzalah")
    client.force_login(applicant())
    page = client.get(CLAIM, {"q": "tomchei"}).content.decode()
    assert "Tomchei Shabbos" in page
    assert "Hatzalah" not in page


def test_the_search_answers_htmx_with_only_the_results(client):
    CharityFactory(name="Tomchei Shabbos")
    client.force_login(applicant())
    page = client.get(CLAIM, {"q": "tomchei"}, HTTP_HX_REQUEST="true").content.decode()
    assert "Tomchei Shabbos" in page
    assert "<html" not in page


def test_choosing_a_charity_claims_it_for_the_logged_in_user(client):
    user, charity = applicant(), CharityFactory()
    client.force_login(user)
    response = client.post(CLAIM, {"charity_id": charity.pk})
    assert response.url == STATUS
    claim = OwnerClaimRequest.objects.get()
    assert (claim.approval_request.submitted_by, claim.charity_id) == (user, charity.pk)
    assert "under review" in client.get(STATUS).content.decode()
    assert "charity owner" in client.get(STATUS).content.decode()


def test_a_user_id_in_the_form_is_ignored(client):
    """The claimant is the session's user; a posted user id can't claim for someone else."""
    user, victim, charity = applicant(), applicant(), CharityFactory()
    client.force_login(user)
    client.post(CLAIM, {"charity_id": charity.pk, "user_id": victim.pk, "submitted_by": victim.pk})
    assert not ApprovalRequest.objects.filter(submitted_by=victim).exists()
    assert ApprovalRequest.objects.get().submitted_by == user


@pytest.mark.parametrize("charity_id", ["", "abc", "999999"])
def test_a_bad_charity_id_claims_nothing(client, charity_id):
    client.force_login(applicant())
    response = client.post(CLAIM, {"charity_id": charity_id})
    assert response.status_code == 400
    assert "That charity isn&#x27;t in MaaserMart" in response.content.decode()
    assert not ApprovalRequest.objects.exists()


def test_after_claiming_the_claim_page_shows_the_status(client):
    user = applicant()
    claimed(user, CharityFactory())
    client.force_login(user)
    assert client.get(CLAIM).url == STATUS
    client.post(CLAIM, {"charity_id": CharityFactory().pk})
    assert ApprovalRequest.objects.filter(submitted_by=user).count() == 1


@pytest.mark.parametrize(
    "who",
    [member, lambda: RoleAssignmentFactory(role=OWNER).user, admin],
    ids=["member", "owner", "admin"],
)
def test_only_applicants_can_claim(client, who):
    """A member, an owner or an admin has no claim page; the check is the role, not login."""
    client.force_login(who())
    response = client.post(CLAIM, {"charity_id": CharityFactory().pk})
    assert response.status_code == 302
    assert not ApprovalRequest.objects.exists()


def test_a_guest_is_sent_to_log_in(client):
    response = client.get(CLAIM)
    assert response.status_code == 302
    assert response.url.startswith("/accounts/login/")


def test_add_a_charity_is_shown_but_disabled_until_that_page_exists(client):
    client.force_login(applicant())
    page = client.get(CLAIM).content.decode()
    assert "Add a charity" in page
    assert "disabled" in page


def test_logging_in_after_claiming_shows_the_status(client):
    sign_up_as_owner(client)
    client.post(CLAIM, {"charity_id": CharityFactory().pk})
    client.logout()
    response = client.post(
        "/accounts/login/", {"username": "dlevi", "password": ACCOUNT["password"]}
    )
    assert response.url == STATUS
    assert "under review" in client.get(STATUS).content.decode()


def test_logging_in_before_claiming_offers_the_claim_page(client):
    sign_up_as_owner(client)
    client.logout()
    client.post("/accounts/login/", {"username": "dlevi", "password": ACCOUNT["password"]})
    assert CLAIM in client.get(STATUS).content.decode()


def test_an_approved_owner_leaves_the_status_page(client):
    user = applicant()
    request = claimed(user, CharityFactory())
    approvals.decide_request(request.pk, True, admin())
    client.force_login(user)
    assert client.get(STATUS).status_code == 302
    assert client.get(CLAIM).status_code == 302


def test_the_admin_queue_can_approve_a_claim(client):
    user, charity = applicant(), CharityFactory(name="Tomchei Shabbos")
    request = claimed(user, charity)
    client.force_login(admin())
    assert "Claims Tomchei Shabbos" in client.get("/admin/approvals/").content.decode()
    client.post(f"/admin/approvals/{request.pk}/decide/", {"decision": "approve"})
    assert is_owner(user)
    assert CharityOwner.objects.filter(user=user, charity=charity).exists()


# --- production's CSP -----------------------------------------------------

INLINE_SCRIPT = re.compile(r"<script(?![^>]*\bsrc=)[^>]*>", re.IGNORECASE)
INLINE_HANDLER = re.compile(r"\son[a-z]+\s*=", re.IGNORECASE)
ALPINE = re.compile(r"\s(x-[a-z]+|@[a-z]+|:[a-z]+)=", re.IGNORECASE)


@pytest.mark.parametrize("path", [SIGNUP, CLAIM, STATUS])
def test_the_owner_pages_need_nothing_production_csp_blocks(client, settings, path):
    """Production sends `default-src 'self'`, so no inline script, handler or Alpine."""
    from apps.support.middleware import SITE_POLICY

    settings.MIDDLEWARE = [
        *settings.MIDDLEWARE,
        "apps.support.middleware.ContentSecurityPolicyMiddleware",
    ]
    settings.CONTENT_SECURITY_POLICY = SITE_POLICY
    CharityFactory(name="Tomchei Shabbos")
    if path != SIGNUP:
        client.force_login(applicant())
    response = client.get(path, {"q": "tomchei"})
    assert response.headers["Content-Security-Policy"] == SITE_POLICY
    page = response.content.decode()
    assert not INLINE_SCRIPT.search(page)
    assert not INLINE_HANDLER.search(page)
    assert not ALPINE.search(page)
