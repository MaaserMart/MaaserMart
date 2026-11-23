"""Rabbi signup, the account waiting for an admin, and the admin queue (D-YOSEF-rabbi-signup)."""

import re

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
FORM = {
    "username": "mcohen",
    "email": "mcohen@example.com",
    "password": "a-long-pass-42",
    "agree": "on",
    "display_name": "Moshe Cohen",
    "title": "Rav",
    "agree_hashkafa": "on",
}


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
    """Fill in the rabbi page and type the emailed code. Returns the code page's response."""
    client.post(SIGNUP, {k: v for k, v in {**FORM, **changes}.items() if v is not None})
    code = re.search(r"\d{6}", mail.outbox[-1].body).group()
    return client.post(VERIFY, {"code": code})


def log_in(client, username="mcohen", password=FORM["password"]):
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
    assert outcome is approvals.SubmitOutcome.ALREADY_PENDING
    assert ApprovalRequest.objects.filter(submitted_by=user).count() == 1


def test_a_rabbi_cannot_apply_again():
    rabbi = RabbiProfileFactory().user
    outcome = approvals.submit_rabbi_request(rabbi, "Someone Else", "")
    assert outcome is approvals.SubmitOutcome.ALREADY_GRANTED
    assert not ApprovalRequest.objects.filter(submitted_by=rabbi).exists()
    assert RabbiProfile.objects.get(user=rabbi).display_name != "Someone Else"


def test_after_a_rejection_the_user_may_apply_again_with_new_details():
    user = applicant()
    request = submitted(user)
    approvals.decide_request(request.pk, False, admin())
    outcome = approvals.submit_rabbi_request(user, "Moshe Cohen", "Rabbi")
    assert outcome is approvals.SubmitOutcome.SUBMITTED
    assert RabbiProfile.objects.get(user=user).title == "Rabbi"


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


def test_rejecting_keeps_the_user_a_member_and_emails_them(django_capture_on_commit_callbacks):
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


def test_the_page_asks_for_the_account_and_the_rabbi_details(client):
    page = client.get(SIGNUP).content.decode()
    for field in ("username", "email", "password", "agree", "display_name", "title"):
        assert f'name="{field}"' in page
    assert 'name="agree_hashkafa"' in page


def test_the_member_signup_page_links_to_it(client):
    assert f'href="{SIGNUP}"' in client.get(reverse("accounts:signup")).content.decode()


def test_the_right_code_creates_a_waiting_account_and_shows_pending(client):
    response = sign_up_as_rabbi(client)
    assert response.status_code == 302
    assert response.url == reverse("accounts:pending")
    user = User.objects.get(username="mcohen")
    assert not RoleAssignment.objects.filter(user=user).exists()
    assert approvals.has_pending(user, "rabbi")
    profile = RabbiProfile.objects.get(user=user)
    assert (profile.display_name, profile.title) == ("Moshe Cohen", "Rav")
    assert SESSION_KEY not in client.session  # Not logged in.
    assert "with an admin" in client.get(response.url).content.decode()


def test_nothing_is_created_before_the_code(client):
    client.post(SIGNUP, FORM)
    assert not User.objects.filter(username="mcohen").exists()
    assert not ApprovalRequest.objects.exists()


def test_an_email_already_in_use_is_refused_before_any_code(client):
    member_account = member()
    response = client.post(SIGNUP, {**FORM, "email": member_account.email.upper()})
    assert "already has an account" in response.content.decode()
    assert mail.outbox == []


def test_without_the_hashkafa_tick_no_code_is_sent(client):
    response = client.post(SIGNUP, {**FORM, "agree_hashkafa": ""})
    assert "agree to the hashkafa statement" in response.content.decode()
    assert mail.outbox == []


def test_without_a_name_no_code_is_sent(client):
    response = client.post(SIGNUP, {**FORM, "display_name": ""})
    assert "Enter your name" in response.content.decode()
    assert mail.outbox == []


def test_a_logged_in_user_is_sent_away(client):
    client.force_login(member())
    assert client.get(SIGNUP).status_code == 302


def test_if_the_email_is_taken_while_the_code_is_out_nothing_is_created(client):
    client.post(SIGNUP, FORM)
    code = re.search(r"\d{6}", mail.outbox[-1].body).group()
    UserFactory(email="MCohen@example.com")
    response = client.post(VERIFY, {"code": code})
    assert "Someone took that username or email" in response.content.decode()
    assert not ApprovalRequest.objects.exists()
    assert not RabbiProfile.objects.exists()


def test_a_member_signup_still_logs_in_with_the_member_role(client):
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
    client.post(VERIFY, {"code": code})
    user = User.objects.get(username="sarah")
    assert RoleAssignment.objects.filter(user=user, role="member").exists()
    assert not ApprovalRequest.objects.filter(submitted_by=user).exists()
    assert int(client.session[SESSION_KEY]) == user.pk


# --- logging in while the account waits ----------------------------------


def test_a_waiting_rabbi_cannot_log_in_and_is_told_why(client):
    sign_up_as_rabbi(client)
    response = log_in(client)
    assert response.status_code == 200
    assert "Your application for the rabbi role is still under review" in response.content.decode()
    assert SESSION_KEY not in client.session


def test_a_wrong_password_does_not_reveal_the_application(client):
    sign_up_as_rabbi(client)
    response = log_in(client, password="not-it")
    page = response.content.decode()
    assert "Wrong username or password" in page
    assert "under review" not in page


def test_a_rejected_rabbi_is_told_where_to_write(client, settings):
    settings.SUPPORT_EMAIL = "help@example.org"
    sign_up_as_rabbi(client)
    request = ApprovalRequest.objects.get()
    approvals.decide_request(request.pk, False, admin())
    response = log_in(client)
    page = response.content.decode()
    assert "Your rabbi application wasn&#x27;t approved" in page
    assert "help@example.org" in page
    assert SESSION_KEY not in client.session


def test_an_approved_rabbi_logs_in(client):
    sign_up_as_rabbi(client)
    approvals.decide_request(ApprovalRequest.objects.get().pk, True, admin())
    response = log_in(client)
    assert response.status_code == 302
    assert int(client.session[SESSION_KEY]) == User.objects.get(username="mcohen").pk


def test_a_user_with_no_role_and_no_application_still_logs_in(client):
    """Near miss: only an account with an application waiting or refused is held back."""
    user = UserFactory()
    response = log_in(client, user.username, "password")
    assert response.status_code == 302


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
    assert "Approval queue (2 waiting)" in page
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
