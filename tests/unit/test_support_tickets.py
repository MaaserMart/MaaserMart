"""Help and report tickets (§6.3 Tickets, SRS FR 18 and FR 19, D-072)."""

import re
from unittest import mock

import pytest
from django.core import mail
from django.core.cache import cache
from django.urls import reverse

from apps.charities.services import find_charities_by_name, get_charity_choice
from apps.support import verification
from apps.support.models import Ticket
from apps.support.services import (
    MAX_BODY_LENGTH,
    TicketError,
    submit_help,
    submit_report,
)
from tests.factories import CharityFactory, UserFactory
from tests.factories.accounts import DEFAULT_PASSWORD

pytestmark = pytest.mark.django_db

HELP = reverse("support:help")
REPORT = reverse("support:report")


@pytest.fixture(autouse=True)
def _fresh_cache():
    cache.clear()
    yield
    cache.clear()


def _code_from_mail() -> str:
    return re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)


def _verify(client, email="guest@example.com", url=HELP):
    client.post(url, {"action": "send_code", "email": email})
    client.post(url, {"action": "verify", "code": _code_from_mail()})


# --- services --------------------------------------------------------------


class TestSubmit:
    def test_help_from_a_user(self):
        user = UserFactory()
        ticket = Ticket.objects.get(pk=submit_help("  How do I donate?  ", user_id=user.id))
        assert ticket.kind == Ticket.Kind.HELP
        assert ticket.body == "How do I donate?"
        assert ticket.submitted_by_id == user.id
        assert ticket.email is None
        assert ticket.status == Ticket.Status.NOT_RESPONDED

    def test_help_from_a_guest_lowercases_the_address(self):
        ticket = Ticket.objects.get(pk=submit_help("Hi", email=" Guest@Example.com "))
        assert ticket.email == "guest@example.com"
        assert ticket.submitted_by_id is None

    def test_report_names_the_charity(self):
        charity = CharityFactory()
        ticket = Ticket.objects.get(pk=submit_report("Wrong phone", charity.id, email="a@b.co"))
        assert ticket.kind == Ticket.Kind.REPORT
        assert ticket.charity_id == charity.id

    @pytest.mark.parametrize("body", ["", "   ", None, "x" * (MAX_BODY_LENGTH + 1)])
    def test_refuses_an_empty_or_huge_body(self, body):
        with pytest.raises(TicketError):
            submit_help(body, email="a@b.co")
        assert not Ticket.objects.exists()

    @pytest.mark.parametrize("who", [{}, {"user_id": 1, "email": "a@b.co"}])
    def test_needs_exactly_one_submitter(self, who):
        with pytest.raises(TicketError):
            submit_help("Hi", **who)

    def test_report_needs_a_charity(self):
        with pytest.raises(TicketError):
            submit_report("Hi", None, email="a@b.co")


class TestCharityLookups:
    def test_find_by_name_is_case_insensitive_and_sorted(self):
        CharityFactory(name="Zion Fund")
        CharityFactory(name="Bikur Cholim")
        CharityFactory(name="Hatzolah")
        names = [c.name for c in find_charities_by_name("o")]
        assert names == ["Bikur Cholim", "Hatzolah", "Zion Fund"]

    def test_blank_term_matches_nothing(self):
        CharityFactory()
        assert find_charities_by_name("  ") == ()

    def test_limit_is_capped(self):
        for i in range(12):
            CharityFactory(name=f"Fund {i:02d}")
        assert len(find_charities_by_name("fund", limit=500)) == 10

    @pytest.mark.parametrize("value", [None, "", "abc", "999999"])
    def test_unknown_id_is_none(self, value):
        assert get_charity_choice(value) is None

    def test_known_id(self):
        charity = CharityFactory(name="Tomchei Shabbos")
        choice = get_charity_choice(str(charity.id))
        assert (choice.id, choice.name) == (charity.id, "Tomchei Shabbos")


# --- verification ----------------------------------------------------------


class TestVerification:
    def test_code_is_emailed_and_confirms(self):
        session = {}
        assert verification.start(session, "Guest@Example.com").ok
        assert mail.outbox[-1].to == ["guest@example.com"]
        assert verification.pending_email(session) == "guest@example.com"
        assert verification.confirm(session, _code_from_mail()).ok
        assert verification.verified_email(session) == "guest@example.com"
        assert verification.pending_email(session) is None

    def test_the_session_never_holds_the_code(self):
        session = {}
        verification.start(session, "a@b.co")
        assert _code_from_mail() not in str(session)

    def test_wrong_code(self):
        session = {}
        verification.start(session, "a@b.co")
        assert not verification.confirm(session, "not-it").ok
        assert verification.verified_email(session) is None

    def test_no_pending_code(self):
        assert not verification.confirm({}, "123456").ok

    def test_too_many_tries_drops_the_code(self):
        session = {}
        verification.start(session, "a@b.co")
        code = _code_from_mail()
        for _ in range(verification.MAX_TRIES):
            verification.confirm(session, "000000" if code != "000000" else "111111")
        assert not verification.confirm(session, code).ok
        assert verification.pending_email(session) is None

    def test_expired_code(self):
        session = {}
        verification.start(session, "a@b.co")
        later = verification.time.time() + verification.CODE_LIFETIME_SECONDS + 1
        with mock.patch.object(verification.time, "time", return_value=later):
            assert not verification.confirm(session, _code_from_mail()).ok

    def test_sends_per_address_are_capped(self):
        for _ in range(verification.MAX_SENDS_PER_EMAIL_PER_HOUR):
            assert verification.start({}, "a@b.co").ok
        assert not verification.start({}, "A@B.co").ok
        assert len(mail.outbox) == verification.MAX_SENDS_PER_EMAIL_PER_HOUR

    def test_a_new_code_unverifies(self):
        session = {}
        verification.start(session, "a@b.co")
        verification.confirm(session, _code_from_mail())
        verification.start(session, "c@d.co")
        assert verification.verified_email(session) is None


# --- help page -------------------------------------------------------------


class TestHelpPage:
    def test_guest_sees_the_email_step_and_a_disabled_send(self, client):
        html = client.get(HELP).content.decode()
        assert 'name="email"' in html
        assert "disabled>Send</button>" in html

    def test_guest_flow_files_a_ticket(self, client):
        _verify(client)
        response = client.post(HELP, {"action": "submit", "body": "Where is the calculator?"})
        assert "Message sent" in response.content.decode()
        ticket = Ticket.objects.get()
        assert (ticket.email, ticket.kind) == ("guest@example.com", Ticket.Kind.HELP)

    def test_guest_cannot_submit_unverified(self, client):
        response = client.post(HELP, {"action": "submit", "body": "Hi"})
        assert "Verify your email address first." in response.content.decode()
        assert not Ticket.objects.exists()

    def test_bad_email_is_refused(self, client):
        response = client.post(HELP, {"action": "send_code", "email": "nope"})
        assert "Enter a valid email address." in response.content.decode()
        assert not mail.outbox

    def test_typed_message_survives_a_step(self, client):
        response = client.post(HELP, {"action": "send_code", "email": "a@b.co", "body": "Keep me"})
        html = response.content.decode()
        assert "Keep me</textarea>" in html
        assert 'name="code"' in html

    def test_wrong_code_shows_an_error(self, client):
        client.post(HELP, {"action": "send_code", "email": "a@b.co"})
        response = client.post(HELP, {"action": "verify", "code": "x"})
        assert "That code is not right" in response.content.decode()

    def test_signed_in_user_skips_the_email_step(self, client):
        user = UserFactory()
        client.login(username=user.username, password=DEFAULT_PASSWORD)
        assert 'name="email"' not in client.get(HELP).content.decode()
        client.post(HELP, {"action": "submit", "body": "Hello"})
        assert Ticket.objects.get().submitted_by_id == user.id

    def test_signed_in_user_cannot_post_a_code_step(self, client):
        user = UserFactory()
        client.login(username=user.username, password=DEFAULT_PASSWORD)
        response = client.post(HELP, {"action": "send_code", "email": "x@y.co"})
        assert "Write your message first." in response.content.decode()
        assert not mail.outbox

    def test_empty_body_shows_an_error(self, client):
        _verify(client)
        response = client.post(HELP, {"action": "submit", "body": " "})
        assert "Write your message first." in response.content.decode()


# --- report page -----------------------------------------------------------


class TestReportPage:
    def test_charity_page_links_to_the_report(self, client):
        charity = CharityFactory()
        html = client.get(reverse("charities:detail", args=[charity.id])).content.decode()
        assert f"{REPORT}?charity={charity.id}" in html

    def test_link_arrives_with_the_charity_chosen(self, client):
        charity = CharityFactory(name="Yad Eliezer")
        html = client.get(REPORT, {"charity": charity.id}).content.decode()
        assert "Reporting" in html and "Yad Eliezer" in html
        assert f'name="charity" value="{charity.id}"' in html

    def test_search_lists_matches(self, client):
        CharityFactory(name="Ezras Torah")
        CharityFactory(name="Other")
        html = client.get(REPORT, {"q": "ezras"}).content.decode()
        assert "Ezras Torah" in html
        assert "Other" not in html

    def test_search_with_no_match(self, client):
        html = client.get(REPORT, {"q": "nothing"}).content.decode()
        assert "No charity matches" in html

    def test_choose_another_clears_the_choice(self, client):
        charity = CharityFactory()
        response = client.post(REPORT, {"action": "search", "charity": charity.id})
        assert 'name="q"' in response.content.decode()

    def test_guest_report_is_filed(self, client):
        charity = CharityFactory(name="Chai Lifeline")
        _verify(client, url=REPORT)
        response = client.post(
            REPORT, {"action": "submit", "charity": charity.id, "body": "Bad link"}
        )
        assert "Report sent" in response.content.decode()
        ticket = Ticket.objects.get()
        assert (ticket.kind, ticket.charity_id) == (Ticket.Kind.REPORT, charity.id)

    def test_report_without_a_charity_is_refused(self, client):
        user = UserFactory()
        client.login(username=user.username, password=DEFAULT_PASSWORD)
        response = client.post(REPORT, {"action": "submit", "body": "Bad", "charity": "999"})
        assert "Choose the charity you are reporting." in response.content.decode()
        assert not Ticket.objects.exists()

    def test_nav_shows_help_and_report(self, client):
        html = client.get(HELP).content.decode()
        assert f'href="{HELP}"' in html
        assert f'href="{REPORT}"' in html
