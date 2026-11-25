"""Charity owner signup: claiming a charity and the admin deciding it (D-YOSEF-owner-signup)."""

import pytest
from django.core import mail

from apps.accounts.models import CharityOwner, RoleAssignment
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
