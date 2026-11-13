# Notes: observations that are not decisions

Where things go, so this file does not turn into a junk drawer:

- **A decision** goes in `docs/DECISIONS.md` as a `D-NNN` entry, with its date and who decided.
- **A question that needs a decision** goes in the Open questions list at the end of `docs/DECISIONS.md`.
- **Work to do** goes in `comtai` (`comtai add`), not here.
- **An observation** — something checked, noticed or measured, with no decision in it — goes here,
  newest first, with the date and how it was checked.

---

## 2026-11-13 — Database schema checked against §5.2 of the design doc

Checked the models in `apps/*/models.py` and the live dev database (`.pgdata`, port 5433) against
§5.2.1–5.2.21 of `docs/design.docx`.

**Verdict: the schema matches the doc. No contradiction is undocumented.** All 19 tables exist.
Every column the doc lists exists with the same nullability and delete rule. All 8 indexes from
§5.2.20 exist in Postgres (`pg_indexes`). Every difference from the doc is a recording decision
already in `docs/DECISIONS.md`:

| Table | Difference from §5.2 | Decision |
| --- | --- | --- |
| CHARITY | `description`, `image` not unique (doc marks them unique) | D-013 |
| CHARITY | `created` required (doc says nullable) | D-017 |
| CHARITY | `is_visible` is an extra column, not in §5.2.9 | D-038 |
| USER | `AbstractUser` adds `first_name`, `last_name`, `is_staff`, `is_active`, `date_joined`, `last_login`; the doc lists only id, username, email, password | D-003 |
| USER, LOCATION | username/email unique ignoring case; LOCATION unique on (name, region, country) | D-032 |
| ROLE_ASSIGNMENT, CHARITY_OWNER, CHARITY_DOMAIN, CHARITY_LOCATION, HASKAMA, DOMAIN | uniqueness the doc does not state | D-019 |
| EDIT_REQUEST | `charity_id` nullable plus a target check; `user_id` cascades | D-014, D-015 |
| REVIEW, TICKET | `Review.body` empty string rather than null; `Ticket.body` required | D-020 |
| LINK | one link per kind | D-036 |

Apps that own no table: `chatbot`, `recommendations`, `dashboards` have no models, which matches
§6.1 — they own no table. Derived values (§5.2.21: average rating, last updated, visit and click
counts, trending, maaser owed) are stored nowhere, which is what §5.2.21 asks for.

## 2026-11-13 — Findings from that check, none of them decided yet

**N1. "One review per member per charity" is not enforced by the database.** §8.6 and UC-05 say a
member has one review per charity. REVIEW has no unique constraint on (charity, author); the rule
would be left to `save_review`, which does not exist yet. Adding the constraint after reviews are
written needs a cleanup migration, so it is cheaper to decide before the review form lands. Raised
as an open question in `docs/DECISIONS.md` and filed in `comtai`.

**N2. Two status columns have defaults the doc does not give.** `ApprovalRequest.status` defaults to
`pending`, `Ticket.status` to `not_responded`. Additive rather than contradictory, but they are
choices nobody wrote down.

**N3. An old seed run tried to store a rating of 6.** `.pgdata/server.log` holds a failed INSERT of
`charities_review.rating = 6`, rejected by the `review_rating_1_to_5` constraint. The current factory
clamps to 1–5 (`tests/factories/charities.py`), and the live table is min 1 / max 5 over 595 rows, so
this is history and the constraint did its job. Worth remembering only because it proves the range
check is load-bearing against dev data, not just against requests.

**N4. The listing now reads REVIEW on every page view.** Since D-044, `DjangoCharityRepository.page`
annotates `Count`/`Avg` over REVIEW. It costs no extra query and benefits from the existing
`charities_review_charity_id` index, but it does mean the charity listing — the site's front door —
cannot render if REVIEW is unavailable.
