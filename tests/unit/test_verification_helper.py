"""The verification plumbing shared by accounts and support (D-078)."""

import re

import pytest
from django.core import mail
from django.core.cache import caches

from apps.accounts.tasks import send_signup_code
from apps.support.tasks import send_ticket_email_code
from common import verification

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _fresh_tries():
    caches["login"].clear()
    yield
    caches["login"].clear()


def test_new_code_is_six_digits():
    assert re.fullmatch(r"\d{6}", verification.new_code())


def test_spend_try_counts_every_guess():
    assert [verification.spend_try("test:shared-tries") for _ in range(3)] == [1, 2, 3]


def test_both_app_tasks_use_the_shared_email():
    send_signup_code("signup@example.com", "111111")
    send_ticket_email_code("guest@example.com", "222222")

    assert [message.to for message in mail.outbox] == [
        ["signup@example.com"],
        ["guest@example.com"],
    ]
    assert "111111" in mail.outbox[0].body
    assert "finish signing up" in mail.outbox[0].body
    assert "222222" in mail.outbox[1].body
    assert "help or report" in mail.outbox[1].body
