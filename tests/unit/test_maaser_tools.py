"""Maaser tools: income, donations and the calculator (§6.3.1, §6.4, SRS FR 20–22, D-074)."""

import datetime
from decimal import Decimal

import pytest
from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from apps.tools.models import Transaction
from apps.tools.services import (
    DONATION,
    INCOME,
    MAX_NOTE_LENGTH,
    TransactionError,
    add_transaction,
    delete_transaction,
    list_transactions,
    maaser_owed,
    maaser_summary,
)
from tests.factories import TransactionFactory, UserFactory
from tests.factories.accounts import DEFAULT_PASSWORD

pytestmark = pytest.mark.django_db

INDEX = reverse("tools:index")
MAASER = reverse("tools:maaser")
INCOME_URL = reverse("tools:income")
DONATIONS_URL = reverse("tools:donations")


@pytest.fixture
def member(client):
    user = UserFactory()
    client.login(username=user.username, password=DEFAULT_PASSWORD)
    return user


# --- services --------------------------------------------------------------


class TestAddTransaction:
    def test_records_an_income_dated_today_by_default(self):
        user = UserFactory()
        row = Transaction.objects.get(pk=add_transaction(user.id, INCOME, "1,250.50"))
        assert (row.user_id, row.type, row.amount) == (user.id, INCOME, Decimal("1250.50"))
        assert row.date == timezone.localdate()
        assert row.note is None

    def test_keeps_a_date_and_a_trimmed_note(self):
        user = UserFactory()
        row = Transaction.objects.get(
            pk=add_transaction(user.id, DONATION, "18", "2026-01-05", "  Tomchei Shabbos ")
        )
        assert row.date == datetime.date(2026, 1, 5)
        assert row.note == "Tomchei Shabbos"

    def test_accepts_a_date_object(self):
        user = UserFactory()
        day = datetime.date(2026, 3, 1)
        row = Transaction.objects.get(pk=add_transaction(user.id, INCOME, Decimal("5"), day))
        assert row.date == day

    @pytest.mark.parametrize(
        ("amount", "message"),
        [
            ("", "as a number"),
            ("abc", "as a number"),
            (None, "as a number"),
            ("NaN", "as a number"),
            ("Infinity", "as a number"),
            ("0", "more than zero"),
            ("-5", "more than zero"),
            ("1.005", "to the cent"),
            ("10000000000", "too large"),
        ],
    )
    def test_refuses_a_bad_amount(self, amount, message):
        with pytest.raises(TransactionError, match=message):
            add_transaction(UserFactory().id, INCOME, amount)
        assert not Transaction.objects.exists()

    def test_refuses_a_bad_or_future_date(self):
        user = UserFactory()
        with pytest.raises(TransactionError, match="YYYY-MM-DD"):
            add_transaction(user.id, INCOME, "5", "5/1/2026")
        tomorrow = timezone.localdate() + datetime.timedelta(days=1)
        with pytest.raises(TransactionError, match="future"):
            add_transaction(user.id, INCOME, "5", tomorrow.isoformat())

    def test_refuses_an_unknown_type_and_a_long_note(self):
        user = UserFactory()
        with pytest.raises(TransactionError, match="income or donation"):
            add_transaction(user.id, "gift", "5")
        with pytest.raises(TransactionError, match="note"):
            add_transaction(user.id, INCOME, "5", note="x" * (MAX_NOTE_LENGTH + 1))


class TestListAndDelete:
    def test_lists_one_members_one_type_newest_first(self):
        user = UserFactory()
        old = TransactionFactory(user=user, date=datetime.date(2026, 1, 1))
        new = TransactionFactory(user=user, date=datetime.date(2026, 2, 1))
        TransactionFactory(user=user, type=DONATION)
        TransactionFactory()  # someone else's
        assert [e.id for e in list_transactions(user.id, INCOME)] == [new.id, old.id]

    def test_deletes_only_the_members_own_row(self):
        user = UserFactory()
        mine = TransactionFactory(user=user)
        theirs = TransactionFactory()
        assert delete_transaction(user.id, theirs.id) is False
        assert Transaction.objects.filter(pk=theirs.id).exists()
        assert delete_transaction(user.id, mine.id) is True
        assert not Transaction.objects.filter(pk=mine.id).exists()


class TestMaaserCalculator:
    def test_nothing_recorded_owes_nothing(self):
        summary = maaser_summary(UserFactory().id)
        assert summary.owed == summary.income == summary.donations == Decimal("0")

    def test_a_tenth_of_income_less_donations(self):
        user = UserFactory()
        TransactionFactory(user=user, amount=Decimal("3000.00"))
        TransactionFactory(user=user, amount=Decimal("2000.00"))
        TransactionFactory(user=user, type=DONATION, amount=Decimal("180.00"))
        TransactionFactory(amount=Decimal("99999.00"))  # someone else's
        summary = maaser_summary(user.id)
        assert summary.income == Decimal("5000.00")
        assert summary.due == Decimal("500.00")
        assert summary.donations == Decimal("180.00")
        assert summary.owed == Decimal("320.00")
        assert summary.given_beyond == Decimal("0")
        assert maaser_owed(user.id) == Decimal("320.00")

    def test_a_tenth_rounds_to_the_cent(self):
        user = UserFactory()
        TransactionFactory(user=user, amount=Decimal("0.05"))
        assert maaser_summary(user.id).due == Decimal("0.01")

    def test_giving_more_than_due_clamps_to_zero(self):
        """§6.3: you cannot give maaser before the fact."""
        user = UserFactory()
        TransactionFactory(user=user, amount=Decimal("100.00"))
        TransactionFactory(user=user, type=DONATION, amount=Decimal("25.00"))
        summary = maaser_summary(user.id)
        assert summary.owed == Decimal("0")
        assert summary.given_beyond == Decimal("15.00")

    def test_donations_without_income(self):
        user = UserFactory()
        TransactionFactory(user=user, type=DONATION, amount=Decimal("36.00"))
        assert maaser_owed(user.id) == Decimal("0")


# --- pages -----------------------------------------------------------------


class TestAccess:
    @pytest.mark.parametrize("url", [INDEX, MAASER, INCOME_URL, DONATIONS_URL])
    def test_a_guest_is_sent_to_log_in(self, client, url):
        response = client.get(url)
        assert response.status_code == 302
        assert response.url == f"{settings.LOGIN_URL}?next={url}"

    def test_the_nav_links_to_the_tools(self, client, member):
        assert f'href="{INDEX}"' in client.get(MAASER).content.decode()


class TestPages:
    def test_index_shows_what_is_owed(self, client, member):
        TransactionFactory(user=member, amount=Decimal("12345.00"))
        html = client.get(INDEX).content.decode()
        assert "1,234.50" in html or "1234.50" in html

    def test_calculator_shows_the_breakdown(self, client, member):
        TransactionFactory(user=member, amount=Decimal("1000.00"))
        TransactionFactory(user=member, type=DONATION, amount=Decimal("150.00"))
        html = client.get(MAASER).content.decode()
        assert "100.00" in html and "150.00" in html
        assert "more than the maaser due" in html
        assert "50.00" in html

    def test_adding_income_redirects_back_with_a_notice(self, client, member):
        response = client.post(INCOME_URL, {"amount": "800", "date": "", "note": "Salary"})
        assert response.status_code == 302 and response.url == INCOME_URL
        row = Transaction.objects.get()
        assert (row.user_id, row.type, row.note) == (member.id, INCOME, "Salary")
        html = client.get(INCOME_URL).content.decode()
        assert "Added the income." in html
        assert "Salary" in html and "800.00" in html

    def test_adding_a_donation(self, client, member):
        client.post(DONATIONS_URL, {"amount": "18"})
        assert Transaction.objects.get().type == DONATION

    def test_a_bad_amount_keeps_what_was_typed(self, client, member):
        response = client.post(INCOME_URL, {"amount": "lots", "note": "Bonus"})
        assert response.status_code == 400
        html = response.content.decode()
        assert "as a number" in html
        assert 'value="lots"' in html and 'value="Bonus"' in html
        assert not Transaction.objects.exists()

    def test_a_member_sees_only_their_own_entries(self, client, member):
        TransactionFactory(note="Not yours")
        assert "Not yours" not in client.get(INCOME_URL).content.decode()
        assert "No income recorded yet." in client.get(INCOME_URL).content.decode()

    def test_removing_an_entry(self, client, member):
        row = TransactionFactory(user=member, type=DONATION)
        response = client.post(reverse("tools:delete", args=[DONATION, row.id]))
        assert response.status_code == 302 and response.url == DONATIONS_URL
        assert not Transaction.objects.exists()

    def test_cannot_remove_someone_elses_entry(self, client, member):
        row = TransactionFactory()
        response = client.post(reverse("tools:delete", args=[INCOME, row.id]))
        assert response.status_code == 404
        assert Transaction.objects.filter(pk=row.id).exists()

    def test_remove_needs_a_known_type_and_a_post(self, client, member):
        row = TransactionFactory(user=member)
        assert client.post(reverse("tools:delete", args=["gift", row.id])).status_code == 404
        assert client.get(reverse("tools:delete", args=[INCOME, row.id])).status_code == 405
        assert Transaction.objects.filter(pk=row.id).exists()
