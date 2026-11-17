"""`tests/support/css.py` answers the question the contract tests ask it (audit T2)."""

from tests.support.css import declarations, value

CSS = """
/* a comment with a fake rule: .nav { position: static; } */
.nav {
  position: sticky;
  top: 4.5rem;
}

.nav,
.footer {
  color: #fff;
}

.nav {
  /* a later override wins, as in a browser */
  padding: 1rem;
}

@media (max-width: 48rem) {
  .nav {
    position: static;
  }
}
"""


def test_a_later_block_overrides_an_earlier_one():
    assert value(CSS, ".nav", "position") == "sticky"
    assert value(CSS, ".nav", "padding") == "1rem"


def test_a_selector_inside_a_list_still_applies():
    assert value(CSS, ".nav", "color") == "#fff"


def test_a_media_query_does_not_answer_for_the_unconditional_rule():
    # The mobile override says `static`; the page's own rule is what is asked for.
    assert value(CSS, ".nav", "position") != "static"


def test_a_missing_selector_or_property_is_none():
    assert declarations(CSS, ".nothing-here") == {}
    assert value(CSS, ".nav", "border") is None


def test_comments_are_not_mistaken_for_rules():
    assert declarations(CSS, ".nav") == {
        "position": "sticky",
        "top": "4.5rem",
        "color": "#fff",
        "padding": "1rem",
    }
