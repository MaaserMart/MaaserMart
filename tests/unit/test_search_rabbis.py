"""search_rabbis lists only approved rabbis (D-YOSEF-rabbi-request)."""

import pytest

from apps.accounts.services import search_rabbis
from tests.factories.accounts import RabbiProfileFactory

pytestmark = pytest.mark.django_db


def ids():
    return [rabbi.user_id for rabbi in search_rabbis()]


def test_a_profile_with_the_rabbi_role_is_listed():
    assert RabbiProfileFactory().user_id in ids()


def test_a_profile_without_the_rabbi_role_is_not_listed():
    """An applicant's profile is saved before an admin decides; it must stay hidden."""
    assert RabbiProfileFactory(approved=False).user_id not in ids()


def test_a_search_term_still_narrows_approved_rabbis_only():
    shown = RabbiProfileFactory(display_name="Moshe Cohen")
    hidden = RabbiProfileFactory(display_name="Moshe Levi", approved=False)
    found = [rabbi.user_id for rabbi in search_rabbis("moshe")]
    assert shown.user_id in found and hidden.user_id not in found


def test_a_seeded_rabbi_label_never_repeats_the_title():
    """The factory feeds the seed; "Rabbi Rabbi Robinson" came from it (2026-11-23)."""
    RabbiProfileFactory()
    (rabbi,) = search_rabbis()
    assert rabbi.title == "Rabbi"
    assert not rabbi.display_name.lower().startswith("rabbi ")
    assert "Rabbi Rabbi" not in rabbi.label
