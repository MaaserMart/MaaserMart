"""Rabbi signup, the application, its status page and the admin queue (D-YOSEF-rabbi-signup)."""

import re
from unittest import mock

import pytest
from django.contrib.auth import SESSION_KEY
from django.core import mail
from django.urls import reverse

from apps.accounts.models import RabbiProfile, RoleAssignment, User
from apps.accounts.services import search_rabbis
from apps.approvals import services as approvals
from apps.approvals.models import ApprovalRequest
from tests.factories import UserFactory
from tests.factories.accounts import RabbiProfileFactory, RoleAssignmentFactory
from tests.factories.approvals import ApprovalRequestFactory

pytestmark = pytest.mark.django_db

RABBI = RoleAssignment.Role.RABBI
SIGNUP = "/accounts/rabbi-signup/"
VERIFY = "/accounts/signup/verify/"
ACCOUNT = {
    "username": "mcohen",
    "email": "mcohen@example.com",
    "password": "a-long-pass-42",
    "agree": "on",
}
APPLICATION = {"display_name": "Moshe Cohen", "title": "Rav", "agree_hashkafa": "on"}
APPLY = "/accounts/rabbi-application/"
STATUS = "/accounts/pending/"


def member():
    return RoleAssignmentFactory(role=RoleAssignment.Role.MEMBER).user


def applicant():
    """An account with no role, as a confirmed rabbi signup leaves it."""
    return UserFactory()


def admin():
    return UserFactory(is_superuser=True, is_staff=True)


def is_rabbi(user):
    return RoleAssignment.objects.filter(user=user, role=RABBI).exists()


def submitted(user):
    approvals.submit_rabbi_request(user, "Moshe Cohen", "Rav")
    return ApprovalRequest.objects.get(submitted_by=user, kind="rabbi")


def sign_up_as_rabbi(client, **changes):
    """Fill in the rabbi signup page and type the emailed code. Returns the code page's reply."""
    client.post(SIGNUP, {k: v for k, v in {**ACCOUNT, **changes}.items() if v is not None})
    code = re.search(r"\d{6}", mail.outbox[-1].body).group()
    return client.post(VERIFY, {"code": code})


def apply(client, **changes):
    return client.post(APPLY, {**APPLICATION, **changes})


def log_in(client, username="mcohen", password=ACCOUNT["password"]):
    client.logout()
    return client.post(reverse("accounts:login"), {"username": username, "password": password})


# --- submit_rabbi_request -------------------------------------------------


def test_a_request_saves_the_profile_and_waits_without_the_role():
    user = applicant()
    outcome = approvals.submit_rabbi_request(user, "Moshe Cohen", "Rav")
    assert outcome is approvals.SubmitOutcome.SUBMITTED
    request = ApprovalRequest.objects.get(submitted_by=user)
    assert (request.kind, request.status) == ("rabbi", "pending")
    profile = RabbiProfile.objects.get(user=user)
    assert (profile.display_name, profile.title) == ("Moshe Cohen", "Rav")
    assert not is_rabbi(user)


def test_a_blank_title_is_saved_as_none():
    user = applicant()
    approvals.submit_rabbi_request(user, "Moshe Cohen", "")
    assert RabbiProfile.objects.get(user=user).title is None


def test_a_second_request_while_one_waits_is_refused():
    user = applicant()
    approvals.submit_rabbi_request(user, "Moshe Cohen", "Rav")
    outcome = approvals.submit_rabbi_request(user, "Moshe Cohen", "Rav")
    assert outcome is approvals.SubmitOutcome.ALREADY_APPLIED
    assert ApprovalRequest.objects.filter(submitted_by=user).count() == 1


def test_a_rabbi_cannot_apply_again():
    rabbi = RabbiProfileFactory().user
    outcome = approvals.submit_rabbi_request(rabbi, "Someone Else", "")
    assert outcome is approvals.SubmitOutcome.ALREADY_GRANTED
    assert not ApprovalRequest.objects.filter(submitted_by=rabbi).exists()
    assert RabbiProfile.objects.get(user=rabbi).display_name != "Someone Else"


def test_after_a_rejection_the_user_cannot_apply_again():
    """One application per account, whatever its outcome (D-YOSEF-rabbi-signup)."""
    user = applicant()
    request = submitted(user)
    approvals.decide_request(request.pk, False, admin())
    outcome = approvals.submit_rabbi_request(user, "Moshe Cohen", "Rabbi")
    assert outcome is approvals.SubmitOutcome.ALREADY_APPLIED
    assert ApprovalRequest.objects.filter(submitted_by=user).count() == 1


def test_another_users_pending_request_does_not_block_this_one():
    submitted(applicant())
    outcome = approvals.submit_rabbi_request(applicant(), "Other Rav", "")
    assert outcome is approvals.SubmitOutcome.SUBMITTED


# --- approval makes the rabbi public -------------------------------------


def test_a_pending_applicant_is_not_listed_until_approved():
    user = applicant()
    request = submitted(user)
    assert user.pk not in [r.user_id for r in search_rabbis()]
    approvals.decide_request(request.pk, True, admin())
    assert user.pk in [r.user_id for r in search_rabbis()]


# --- decide_request -------------------------------------------------------


def test_approving_grants_the_role_and_emails_the_user(django_capture_on_commit_callbacks):
    user = applicant()
    request = submitted(user)
    boss = admin()
    with django_capture_on_commit_callbacks(execute=True):
        outcome = approvals.decide_request(request.pk, True, boss)
    assert outcome is approvals.DecideOutcome.DONE
    request.refresh_from_db()
    assert (request.status, request.decided_by, request.decided_at is not None) == (
        "approved",
        boss,
        True,
    )
    assert is_rabbi(user)
    assert mail.outbox[-1].to == [user.email]
    assert "approved" in mail.outbox[-1].subject


def test_rejecting_grants_no_role_and_emails_them(django_capture_on_commit_callbacks):
    user = applicant()
    request = submitted(user)
    with django_capture_on_commit_callbacks(execute=True):
        approvals.decide_request(request.pk, False, admin())
    request.refresh_from_db()
    assert request.status == "rejected"
    assert not is_rabbi(user)
    assert mail.outbox[-1].to == [user.email]
    assert "wasn't approved" in mail.outbox[-1].body


def test_a_decided_request_cannot_be_decided_again(django_capture_on_commit_callbacks):
    user = applicant()
    request = submitted(user)
    with django_capture_on_commit_callbacks(execute=True):
        approvals.decide_request(request.pk, False, admin())
        outcome = approvals.decide_request(request.pk, True, admin())
    assert outcome is approvals.DecideOutcome.ALREADY_DECIDED
    assert not is_rabbi(user)
    assert len(mail.outbox) == 1


def test_a_missing_request_is_not_found():
    assert approvals.decide_request(999_999, True, admin()) is approvals.DecideOutcome.NOT_FOUND


def test_a_kind_the_queue_cannot_decide_yet_stays_pending():
    request = ApprovalRequestFactory(kind="new_charity")
    outcome = approvals.decide_request(request.pk, True, admin())
    assert outcome is approvals.DecideOutcome.NOT_DECIDABLE
    request.refresh_from_db()
    assert request.status == "pending"


def test_a_request_from_a_deleted_account_is_decided_without_email(
    django_capture_on_commit_callbacks,
):
    user = applicant()
    request = submitted(user)
    user.delete()
    with django_capture_on_commit_callbacks(execute=True):
        outcome = approvals.decide_request(request.pk, True, admin())
    assert outcome is approvals.DecideOutcome.DONE
    assert mail.outbox == []


def test_the_queue_lists_pending_requests_oldest_first_with_the_name():
    first, second = applicant(), applicant()
    submitted(first)
    approvals.submit_rabbi_request(second, "Second Rav", "")
    decided = submitted(applicant())
    approvals.decide_request(decided.pk, False, admin())
    items = approvals.get_requests()
    assert [item.username for item in items] == [first.username, second.username]
    assert items[0].detail == "Rav Moshe Cohen"
    assert items[0].email == first.email
    assert items[0].decidable


# --- the rabbi signup page ------------------------------------------------


def test_the_signup_page_asks_only_for_the_account(client):
    page = client.get(SIGNUP).content.decode()
    for field in ("username", "email", "password", "agree"):
        assert f'name="{field}"' in page
    assert 'name="display_name"' not in page


def test_the_member_signup_page_links_to_it(client):
    assert f'href="{SIGNUP}"' in client.get(reverse("accounts:signup")).content.decode()


def test_the_right_code_logs_in_an_account_with_no_role_and_opens_the_application(client):
    response = sign_up_as_rabbi(client)
    assert response.url == APPLY
    user = User.objects.get(username="mcohen")
    assert not RoleAssignment.objects.filter(user=user).exists()
    assert int(client.session[SESSION_KEY]) == user.pk
    assert not ApprovalRequest.objects.exists()  # Nothing is sent until the application.


def test_nothing_is_created_before_the_code(client):
    client.post(SIGNUP, ACCOUNT)
    assert not User.objects.filter(username="mcohen").exists()


def test_an_email_already_in_use_is_refused_before_any_code(client):
    member_account = member()
    response = client.post(SIGNUP, {**ACCOUNT, "email": member_account.email.upper()})
    assert "already has an account" in response.content.decode()
    assert mail.outbox == []


def test_a_logged_in_member_is_sent_away(client):
    client.force_login(member())
    assert client.get(SIGNUP).status_code == 302


def test_a_member_signup_still_gets_the_member_role(client):
    """Near miss: the member page is unchanged by the rabbi path."""
    client.post(
        reverse("accounts:signup"),
        {
            "username": "sarah",
            "email": "s@example.com",
            "password": "a-long-pass-42",
            "agree": "on",
        },
    )
    code = re.search(r"\d{6}", mail.outbox[-1].body).group()
    response = client.post(VERIFY, {"code": code})
    user = User.objects.get(username="sarah")
    assert RoleAssignment.objects.filter(user=user, role="member").exists()
    assert response.url != APPLY


# --- the application page -------------------------------------------------


def test_the_application_asks_for_name_title_and_the_hashkafa_tick(client):
    sign_up_as_rabbi(client)
    page = client.get(APPLY).content.decode()
    for field in ("display_name", "title", "agree_hashkafa"):
        assert f'name="{field}"' in page


def test_submitting_files_the_application_and_shows_pending(client):
    sign_up_as_rabbi(client)
    response = apply(client)
    assert response.url == STATUS
    user = User.objects.get(username="mcohen")
    assert approvals.latest_application(user) == ("rabbi", "pending")
    profile = RabbiProfile.objects.get(user=user)
    assert (profile.display_name, profile.title) == ("Moshe Cohen", "Rav")
    page = client.get(STATUS).content.decode()
    assert "Your application for the rabbi role is still under review" in page


def test_without_the_hashkafa_tick_nothing_is_filed(client):
    sign_up_as_rabbi(client)
    response = apply(client, agree_hashkafa="")
    assert "agree to the hashkafa statement" in response.content.decode()
    assert not ApprovalRequest.objects.exists()


def test_without_a_name_nothing_is_filed(client):
    sign_up_as_rabbi(client)
    response = apply(client, display_name="")
    assert "Enter your name" in response.content.decode()
    assert not ApprovalRequest.objects.exists()


def test_a_sent_application_cannot_be_sent_again(client):
    sign_up_as_rabbi(client)
    apply(client)
    assert client.get(APPLY).url == STATUS
    apply(client, display_name="Someone Else")
    assert ApprovalRequest.objects.count() == 1
    assert RabbiProfile.objects.get().display_name == "Moshe Cohen"


def test_a_member_has_no_application_page(client):
    client.force_login(member())
    assert client.get(APPLY).status_code == 302
    client.post(APPLY, APPLICATION)
    assert not ApprovalRequest.objects.exists()


def test_a_guest_is_sent_to_log_in(client):
    response = client.get(APPLY)
    assert response.url.startswith(reverse("accounts:login"))


def test_the_application_takes_no_user_id_from_the_post(client):
    """Swap test: a posted user id is ignored; the application is the logged-in user's."""
    victim = applicant()
    sign_up_as_rabbi(client)
    apply(client, user=victim.pk, user_id=victim.pk, submitted_by=victim.pk)
    assert not ApprovalRequest.objects.filter(submitted_by=victim).exists()
    assert approvals.latest_application(User.objects.get(username="mcohen")) == (
        "rabbi",
        "pending",
    )


# --- logging in while the application waits -------------------------------


def test_logging_in_before_applying_opens_the_application(client):
    sign_up_as_rabbi(client)
    response = log_in(client)
    assert client.get(response.url).url == APPLY


def test_logging_in_while_pending_shows_the_pending_page(client):
    sign_up_as_rabbi(client)
    apply(client)
    response = log_in(
        client,
    )
    assert response.url == STATUS
    assert "still under review" in client.get(STATUS).content.decode()


def test_a_waiting_applicant_is_sent_to_the_status_page_even_with_next(client):
    sign_up_as_rabbi(client)
    apply(client)
    client.logout()
    response = client.post(
        reverse("accounts:login") + "?next=/charity/",
        {"username": "mcohen", "password": ACCOUNT["password"], "next": "/charity/"},
    )
    assert response.url == STATUS


def test_a_rejected_applicant_is_told_where_to_write(client, settings):
    settings.SUPPORT_EMAIL = "help@example.org"
    sign_up_as_rabbi(client)
    apply(client)
    approvals.decide_request(ApprovalRequest.objects.get().pk, False, admin())
    log_in(client)
    page = client.get(STATUS).content.decode()
    assert "Your rabbi application wasn&#x27;t approved" in page
    assert "help@example.org" in page
    assert client.get(APPLY).url == STATUS  # Can't apply again.


def test_an_approved_rabbi_logs_in_to_his_pages_not_the_status(client):
    sign_up_as_rabbi(client)
    apply(client)
    approvals.decide_request(ApprovalRequest.objects.get().pk, True, admin())
    response = log_in(client)
    assert response.url != STATUS
    assert client.get(STATUS).status_code == 302


def test_a_member_has_no_status_page(client):
    client.force_login(member())
    assert client.get(STATUS).status_code == 302


# --- the queue page and admin dashboard -----------------------------------


@pytest.mark.parametrize(
    "who",
    [
        None,
        member,
        lambda: UserFactory(is_staff=True),  # Staff alone is not a MaaserMart admin.
        lambda: RabbiProfileFactory().user,
    ],
)
@pytest.mark.parametrize("url_name", ["approvals:queue", "dashboards:admin"])
def test_only_admins_see_the_queue_and_dashboard(client, who, url_name):
    if who is not None:
        client.force_login(who())
    assert client.get(reverse(url_name)).status_code == 404


def test_an_admin_sees_the_queue_with_buttons(client):
    submitted(applicant())
    client.force_login(admin())
    page = client.get(reverse("approvals:queue")).content.decode()
    assert "Rav Moshe Cohen" in page
    assert "mailto:" in page
    assert 'value="approve"' in page and 'value="reject"' in page


def test_the_dashboard_counts_what_waits(client):
    submitted(applicant())
    submitted(applicant())
    client.force_login(admin())
    page = client.get(reverse("dashboards:admin")).content.decode()
    assert "2 waiting" in page
    assert "MaaserMart administration" in page  # Django admin's look.
    assert reverse("admin:index") in page


def test_an_admin_logging_in_lands_on_the_admin_dashboard(client):
    boss = admin()
    response = client.post(
        reverse("accounts:login"), {"username": boss.username, "password": "password"}
    )
    assert response.url == reverse("dashboards:admin")


def test_an_admin_approves_from_the_queue(client):
    user = applicant()
    request = submitted(user)
    client.force_login(admin())
    response = client.post(
        reverse("approvals:decide", args=[request.pk]), {"decision": "approve"}, follow=True
    )
    assert is_rabbi(user)
    assert "Approved." in response.content.decode()


def test_a_second_decision_shows_already_decided(client):
    request = submitted(applicant())
    client.force_login(admin())
    url = reverse("approvals:decide", args=[request.pk])
    client.post(url, {"decision": "reject"})
    response = client.post(url, {"decision": "approve"}, follow=True)
    assert "already decided" in response.content.decode()


def test_a_member_cannot_decide_even_their_own_request(client):
    user = applicant()
    request = submitted(user)
    client.force_login(user)
    response = client.post(reverse("approvals:decide", args=[request.pk]), {"decision": "approve"})
    assert response.status_code == 404
    assert not is_rabbi(user)
    request.refresh_from_db()
    assert request.status == "pending"


@pytest.mark.parametrize("who", [None, member, applicant])
def test_the_decide_address_is_not_found_for_non_admins_even_by_get(client, who):
    request = submitted(applicant())
    if who is not None:
        client.force_login(who())
    assert client.get(reverse("approvals:decide", args=[request.pk])).status_code == 404


def test_deciding_needs_a_post_and_a_real_choice(client):
    request = submitted(applicant())
    client.force_login(admin())
    url = reverse("approvals:decide", args=[request.pk])
    assert client.get(url).status_code == 405
    assert client.post(url, {"decision": "maybe"}).status_code == 400
    request.refresh_from_db()
    assert request.status == "pending"


def test_the_login_page_passes_next_on_to_signup(client):
    page = client.get(reverse("accounts:login"), {"next": "/charity/"})
    assert "?next=/charity/" in page.content.decode()


# --- review fixes ---------------------------------------------------------


def test_django_admin_cannot_change_a_request(client):
    """A status set in Django admin would skip the role and the email (B1)."""
    request = submitted(applicant())
    client.force_login(admin())
    url = reverse("admin:approvals_approvalrequest_change", args=[request.pk])
    page = client.get(url)
    assert page.status_code == 200  # Viewing is still allowed.
    assert 'name="_save"' not in page.content.decode()  # But there's nothing to save.
    assert client.get(reverse("admin:approvals_approvalrequest_add")).status_code == 403
    delete = reverse("admin:approvals_approvalrequest_delete", args=[request.pk])
    assert client.post(delete, {"post": "yes"}).status_code == 403
    assert ApprovalRequest.objects.filter(pk=request.pk, status="pending").exists()


def test_a_staff_user_with_no_role_is_not_a_rabbi_applicant(client):
    staff = UserFactory(is_staff=True)
    response = log_in(client, staff.username, "password")
    assert response.url != STATUS
    client.force_login(staff)
    client.post(APPLY, APPLICATION)
    assert not ApprovalRequest.objects.exists()


@pytest.mark.django_db(transaction=True)
def test_an_email_that_cannot_be_queued_still_saves_the_decision(client):
    """Real commits, so the email is queued right after the decision is saved (S2)."""
    user = applicant()
    request = submitted(user)
    client.force_login(admin())
    with mock.patch(
        "apps.accounts.services.send_notice.delay", side_effect=ConnectionError("broker down")
    ):
        response = client.post(
            reverse("approvals:decide", args=[request.pk]), {"decision": "approve"}, follow=True
        )
    assert response.status_code == 200
    assert "email to the applicant didn" in response.content.decode()
    request.refresh_from_db()
    assert request.status == "approved"
    assert is_rabbi(user)


def test_an_approved_application_without_the_role_says_so(client):
    user = applicant()
    request = submitted(user)
    approvals.decide_request(request.pk, True, admin())
    RoleAssignment.objects.filter(user=user).delete()
    client.force_login(user)
    page = client.get(STATUS).content.decode()
    assert "approved, but your account isn" in page
    assert "still under review" not in page
