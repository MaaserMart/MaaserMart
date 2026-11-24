"""The admin ticket queue at /admin/tickets/ (§7.3.10, D-073)."""

import logging
from datetime import timedelta
from unittest import mock

import pytest
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from apps.support.models import Ticket
from apps.support.services import CLOSE, RESPOND, TicketError, get_tickets, resolve_ticket
from tests.factories import CharityFactory, UserFactory
from tests.factories.accounts import DEFAULT_PASSWORD

pytestmark = pytest.mark.django_db

QUEUE = reverse("support_admin:tickets")


def _ticket(**fields):
    fields.setdefault("kind", Ticket.Kind.HELP)
    fields.setdefault("body", "Help me")
    fields.setdefault("email", "asker@example.com")
    return Ticket.objects.create(**fields)


@pytest.fixture
def admin_user():
    return UserFactory(is_staff=True)


@pytest.fixture
def admin_client(client, admin_user):
    client.login(username=admin_user.username, password=DEFAULT_PASSWORD)
    return client


# --- services --------------------------------------------------------------


class TestGetTickets:
    def test_unanswered_first_then_oldest_and_closed_left_out(self):
        old_answered = _ticket(status=Ticket.Status.RESPONDED)
        new_open = _ticket()
        old_open = _ticket()
        _ticket(status=Ticket.Status.CLOSED)
        Ticket.objects.filter(pk=old_open.pk).update(created=timezone.now() - timedelta(days=2))
        Ticket.objects.filter(pk=old_answered.pk).update(created=timezone.now() - timedelta(days=3))
        assert [t.id for t in get_tickets()] == [old_open.id, new_open.id, old_answered.id]

    def test_card_names_the_charity_and_the_guest(self):
        charity = CharityFactory(name="Kupat Ha'ir")
        _ticket(kind=Ticket.Kind.REPORT, charity=charity)
        (card,) = get_tickets()
        assert (card.charity_name, card.from_member) == ("Kupat Ha'ir", False)

    def test_member_ticket(self):
        user = UserFactory()
        _ticket(submitted_by=user)
        assert get_tickets()[0].from_member is True


class TestResolveTicket:
    def test_respond_saves_and_emails(self, admin_user, django_capture_on_commit_callbacks):
        ticket = _ticket(body="Where is the calculator?")
        with django_capture_on_commit_callbacks(execute=True):
            resolve_ticket(ticket.id, admin_user.id, "  Under Maaser tools.  ", RESPOND)
        ticket.refresh_from_db()
        assert ticket.status == Ticket.Status.RESPONDED
        assert ticket.response == "Under Maaser tools."
        assert ticket.responded_by_id == admin_user.id
        assert ticket.responded is not None
        (sent,) = mail.outbox
        assert sent.to == ["asker@example.com"]
        assert "Under Maaser tools." in sent.body
        assert "Where is the calculator?" in sent.body

    def test_respond_needs_text(self, admin_user):
        ticket = _ticket()
        with pytest.raises(TicketError):
            resolve_ticket(ticket.id, admin_user.id, " ", RESPOND)
        assert not mail.outbox

    def test_close_without_text_sends_nothing(self, admin_user):
        ticket = _ticket()
        resolve_ticket(ticket.id, admin_user.id, "", CLOSE)
        ticket.refresh_from_db()
        assert ticket.status == Ticket.Status.CLOSED
        assert ticket.closed is not None
        assert ticket.response is None
        assert not mail.outbox

    def test_close_with_text_replies_first(self, admin_user, django_capture_on_commit_callbacks):
        ticket = _ticket()
        with django_capture_on_commit_callbacks(execute=True):
            resolve_ticket(ticket.id, admin_user.id, "Fixed.", CLOSE)
        ticket.refresh_from_db()
        assert (ticket.status, ticket.response) == (Ticket.Status.CLOSED, "Fixed.")
        assert len(mail.outbox) == 1

    def test_a_closed_ticket_cannot_be_resolved(self, admin_user):
        ticket = _ticket(status=Ticket.Status.CLOSED)
        with pytest.raises(TicketError):
            resolve_ticket(ticket.id, admin_user.id, "Late", RESPOND)

    @pytest.mark.parametrize(("ticket_id", "action"), [(999999, RESPOND), (None, "delete")])
    def test_unknown_ticket_or_action(self, admin_user, ticket_id, action):
        ticket_id = ticket_id or _ticket().id
        with pytest.raises(TicketError):
            resolve_ticket(ticket_id, admin_user.id, "Hi", action)

    def test_huge_text_is_refused(self, admin_user):
        ticket = _ticket()
        with pytest.raises(TicketError):
            resolve_ticket(ticket.id, admin_user.id, "x" * 6000, CLOSE)

    def test_email_failure_keeps_the_answer_and_logs(
        self, admin_user, caplog, django_capture_on_commit_callbacks
    ):
        ticket = _ticket()
        with (
            mock.patch("apps.support.tasks.send_mail", side_effect=OSError("SES down")),
            caplog.at_level(logging.ERROR, logger="apps.support.tasks"),
            django_capture_on_commit_callbacks(execute=True),
        ):
            resolve_ticket(ticket.id, admin_user.id, "Answer", RESPOND)
        ticket.refresh_from_db()
        assert ticket.status == Ticket.Status.RESPONDED
        assert f"ticket {ticket.id}" in caplog.text


# --- pages -----------------------------------------------------------------


class TestQueuePage:
    def test_visitor_is_sent_to_log_in(self, client):
        response = client.get(QUEUE)
        assert response.status_code == 302
        assert "next=/admin/tickets/" in response["Location"]

    def test_non_admin_is_refused(self, client):
        user = UserFactory()
        client.login(username=user.username, password=DEFAULT_PASSWORD)
        assert client.get(QUEUE).status_code == 403
        ticket = _ticket()
        url = reverse("support_admin:resolve", args=[ticket.id])
        assert client.post(url, {"action": "close"}).status_code == 403

    def test_admin_sees_open_tickets(self, admin_client):
        _ticket(body="Guest question")
        _ticket(body="Closed one", status=Ticket.Status.CLOSED)
        html = admin_client.get(QUEUE).content.decode()
        assert "Guest question" in html
        assert "guest &middot; asker@example.com" in html
        assert "Closed one" not in html

    def test_empty_queue(self, admin_client):
        assert "No open tickets." in admin_client.get(QUEUE).content.decode()

    def test_reply_redirects_with_a_notice(self, admin_client, django_capture_on_commit_callbacks):
        ticket = _ticket()
        url = reverse("support_admin:resolve", args=[ticket.id])
        with django_capture_on_commit_callbacks(execute=True):
            response = admin_client.post(url, {"action": "respond", "text": "Done"}, follow=True)
        assert f"Ticket {ticket.id} answered." in response.content.decode()
        assert len(mail.outbox) == 1

    def test_close_removes_it(self, admin_client):
        ticket = _ticket(body="Bye")
        url = reverse("support_admin:resolve", args=[ticket.id])
        response = admin_client.post(url, {"action": "close"}, follow=True)
        html = response.content.decode()
        assert f"Ticket {ticket.id} closed." in html
        assert "Bye" not in html

    def test_failed_reply_keeps_the_draft(self, admin_client):
        ticket = _ticket()
        url = reverse("support_admin:resolve", args=[ticket.id])
        response = admin_client.post(url, {"action": "bogus", "text": "My draft"})
        assert response.status_code == 400
        html = response.content.decode()
        assert "Choose to reply or to close." in html
        assert "My draft</textarea>" in html

    def test_resolve_is_post_only(self, admin_client):
        ticket = _ticket()
        url = reverse("support_admin:resolve", args=[ticket.id])
        assert admin_client.get(url).status_code == 405

    def test_django_admin_links_to_the_queue(self, client):
        superuser = UserFactory(is_staff=True, is_superuser=True)
        client.login(username=superuser.username, password=DEFAULT_PASSWORD)
        html = client.get(reverse("admin:index")).content.decode()
        assert f'href="{QUEUE}"' in html
