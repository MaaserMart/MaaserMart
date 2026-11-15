# MaaserMart decisions log

This file records every decision that overrides the design doc, fills a gap in it, or otherwise affects how the developers work. Check it before following the design doc.

Rules for this file:
- There is one entry per decision, with IDs D-001, D-002, and so on. Entries are never edited or deleted. When a decision changes, a new entry is added and the old entry's Status becomes "Superseded by D-0XX on <date>". That status line is the only edit allowed to an old entry.
- Dates are absolute ("As of 2026-11-11, …").
- Code is referred to by file path and setting, model or field name, never by commit SHA. Commits that apply a decision carry its ID in the message, so `git log --grep D-0NN` finds them.
- The design doc is referred to by section number (§x.y).
- Open questions go at the bottom, dated. When one is resolved it becomes a D-entry, and the open item gets the line "Resolved as D-0XX on <date>".

---

## D-001: Python 3.13, pinned with uv
- Date: 2026-11-11
- Decided by: CEO (Yosef)
- Status: Active
- Design doc ref: not in design doc
- Decision: The project runs on Python 3.13. uv pins the version and manages dependencies, and the lockfile is committed. The system Python on dev machines (3.15 as of 2026-11-11) is not used, because Django 5.2 does not support it.
- Why: Every developer and CI then get exactly the same interpreter and packages.
- Where in code: `.python-version`, `pyproject.toml` (`requires-python`), `uv.lock`

## D-002: Django 5.2 LTS
- Date: 2026-11-11
- Decided by: CEO (Yosef)
- Status: Active
- Design doc ref: §4.5
- Decision: The framework is Django 5.2, the long-term-support release, not Django 6.0.
- Why: §4.5 picks Django partly for its long security support. As of 2026-11-11, 5.2 LTS is supported until April 2028.
- Where in code: `pyproject.toml` (`django>=5.2,<5.3`), `uv.lock`

## D-003: Custom user model from day one
- Date: 2026-11-11
- Decided by: CEO (Yosef)
- Status: Active
- Design doc ref: §5.2.1
- Decision: The user model is `accounts.User`, a subclass of Django's `AbstractUser`. Code refers to it through `settings.AUTH_USER_MODEL` or `get_user_model()`, never `django.contrib.auth.models.User`.
- Why: Swapping the user model after the first migration is very hard in Django.
- Where in code: `apps/accounts/models.py` (`User`), `config/settings/base.py` (`AUTH_USER_MODEL`)

## D-004: Settings split by environment, secrets from environment variables only
- Date: 2026-11-11
- Decided by: CEO (Yosef)
- Status: Active
- Design doc ref: not in design doc
- Decision: Settings are split into `base`, `local`, `test` and `prod`. Every secret and host-specific value is read from environment variables, or from a git-ignored `.env` file locally. No secret is ever committed. `.env.example` lists the variables.
- Why: One codebase runs on laptops, CI and AWS without code changes and without leaking secrets.
- Where in code: `config/settings/base.py`, `local.py`, `test.py`, `prod.py`; `.env.example`; `.gitignore` (`.env`)

## D-005: Local Postgres for development, AWS RDS only for the deployed site
- Date: 2026-11-11
- Decided by: CEO (Yosef)
- Status: Active
- Design doc ref: §4.8, §4.9
- Decision: Each developer runs PostgreSQL locally, through Homebrew or Docker as they prefer. AWS RDS is used only by the deployed site. SQLite is not used anywhere.
- Why: Dev must use the same database engine as production, and RDS costs money (§4.9).
- Where in code: `.env.example` (`DATABASE_URL`), `config/settings/base.py` (`DATABASES`), `README.md`

## D-006: Apps call each other only through services.py
- Date: 2026-11-11
- Decided by: CEO (Yosef)
- Status: Active
- Design doc ref: §6.1
- Decision: An app never imports another app's models or queries another app's tables. It calls the other app's public functions in `services.py`, and only for dependencies §6.1 lists. Foreign keys that cross apps use string labels (e.g. `"charities.Charity"`).
- Why: This keeps the modular monolith modular (§4.4), so each app can change its internals safely.
- Where in code: `apps/*/services.py`, `CLAUDE.md`

## D-007: Only the Platform Lead creates migrations; merged migrations are never edited
- Date: 2026-11-11
- Decided by: CEO (Yosef)
- Status: Active
- Design doc ref: not in design doc
- Decision: Only the Platform Lead runs `makemigrations` and commits migration files. Other developers ask the Platform Lead for schema changes. A migration merged to `main` is never edited; changes go in a new migration.
- Why: Three people generating migrations in parallel produces conflicting migration graphs.
- Where in code: `apps/*/migrations/`, `CLAUDE.md`

## D-008: Django admin at /django-admin/
- Date: 2026-11-11
- Decided by: CEO (Yosef)
- Status: Active
- Design doc ref: §6.2.13, §7.1.6
- Decision: Django's built-in admin is mounted at `/django-admin/`, which leaves `/admin/` free for MaaserMart's own admin pages (`/admin/approvals/`, `/admin/tickets/`).
- Why: The doc's `/admin/approval/` would otherwise collide with Django admin at `/admin/`.
- Where in code: `config/urls.py`

## D-009: URL convention: hyphens, grouped by app
- Date: 2026-11-11
- Decided by: CEO (Yosef)
- Status: Active
- Design doc ref: §6.2.x, §7.1
- Decision: URLs use hyphens, never underscores, and each app's pages live under its own prefix: `/accounts/...` (login, signup, pending), `/charity/<id>/`, `/charity/add/`, `/dashboard/`, `/admin/approvals/`, `/admin/tickets/`. The plural "approvals" is used throughout. This replaces the doc's mixed URLs (e.g. `/member_signup/`, `/charity-id/`, `/admin/approval/`).
- Why: The doc mixes styles and puts most pages at the root, which conflicts with each app owning its URLs.
- Where in code: `config/urls.py`, `apps/*/urls.py`, `CLAUDE.md`

## D-010: Server time zone is UTC
- Date: 2026-11-11
- Decided by: CEO (Yosef)
- Status: Active
- Design doc ref: not in design doc
- Decision: `TIME_ZONE = "UTC"` and `USE_TZ = True`. Times are stored and handled in UTC and converted to local time only in templates, if needed.
- Why: UTC avoids daylight-saving bugs and keeps stored times unambiguous.
- Where in code: `config/settings/base.py` (`TIME_ZONE`, `USE_TZ`)

## D-011: Feature branches off main, merged by PR
- Date: 2026-11-11
- Decided by: CEO (Yosef)
- Status: Active
- Design doc ref: not in design doc
- Decision: Work happens on small feature branches cut from `main` and lands only through a pull request with passing CI. Nobody commits to `main` directly. Anything out of a branch's scope is reported, not added to the branch.
- Why: Small, reviewed changes keep three developers from stepping on each other.
- Where in code: `CLAUDE.md`, `.github/workflows/`

## D-012: Commit policy by phase
- Date: 2026-11-11
- Decided by: CEO (Yosef)
- Status: Active
- Design doc ref: not in design doc
- Decision: During Phase 0, commits need not be single-purpose; one commit per step is fine. From Phase 1 onward, every commit must be meaningful and single-purpose.
- Why: Phase 0 builds the foundation in one connected pass, while feature work needs reviewable history.
- Where in code: `CLAUDE.md`

## D-013: CHARITY.description and CHARITY.image are not unique
- Date: 2026-11-11
- Decided by: CEO (Yosef)
- Status: Active
- Design doc ref: §5.2.9
- Decision: `description` and `image` on CHARITY have no unique constraint. Both are nullable.
- Why: §5.2.9 marks them unique, which is almost certainly a mistake: two charities could share a placeholder image or have no description.
- Where in code: `apps/charities/models.py` (`Charity.description`, `Charity.image`)

## D-014: EDIT_REQUEST.charity_id is nullable, with a target check
- Date: 2026-11-11
- Decided by: CEO (Yosef)
- Status: Active
- Design doc ref: §5.2.8
- Decision: `EditRequest.charity` is nullable. A check constraint requires `charity` when `target_type = "charity"` and `user` when `target_type = "profile"`.
- Why: §5.2.8 is inconsistent: non-nullable in relationships, nullable in columns. Profile edits (a rabbi's title) have no charity, so the column must allow null, and the constraint keeps charity edits from losing their charity.
- Where in code: `apps/approvals/models.py` (`EditRequest.charity`, constraint `edit_request_target_present`)

## D-015: EDIT_REQUEST.user_id cascades on delete
- Date: 2026-11-11
- Decided by: CEO (Yosef)
- Status: Active
- Design doc ref: §5.2.8
- Decision: `EditRequest.user` is a nullable foreign key to the user with `on_delete=CASCADE`.
- Why: §5.2.8 lists the column but gives no relationship or delete rule, and a profile edit means nothing once its user is gone.
- Where in code: `apps/approvals/models.py` (`EditRequest.user`)

## D-016: RABBI_PROFILE belongs to accounts
- Date: 2026-11-11
- Decided by: CEO (Yosef)
- Status: Active
- Design doc ref: §5.2.3, §6.1
- Decision: The `accounts` app owns RABBI_PROFILE.
- Why: §6.1 assigns RABBI_PROFILE to no app, and it is per-user profile data like the other accounts tables.
- Where in code: `apps/accounts/models.py` (`RabbiProfile`)

## D-017: CHARITY.created is required
- Date: 2026-11-11
- Decided by: CEO (Yosef)
- Status: Active
- Design doc ref: §5.2.9
- Decision: `Charity.created` is NOT NULL and set automatically on insert (`auto_now_add`).
- Why: §5.2.9 marks it nullable, but every charity has a creation time.
- Where in code: `apps/charities/models.py` (`Charity.created`)

## D-018: Pending roles live only in approvals
- Date: 2026-11-11
- Decided by: CEO (Yosef)
- Status: Active
- Design doc ref: §6.2.1, §5.2.2, §5.3
- Decision: A ROLE_ASSIGNMENT row is created only when a role is granted, either right away (member) or on approval (rabbi, charity owner). A role is "pending" when the user has an open APPROVAL_REQUEST of kind `rabbi` or `owner_claim`/`new_charity`. `find_role` returns role assignments only, so it never returns pending roles.
- Why: §6.2.1 says pending roles are not returned, but ROLE_ASSIGNMENT has no status. §5.3 rule 5 keeps pending status only in the approval table.
- Where in code: `apps/accounts/models.py` (`RoleAssignment`), `apps/approvals/models.py` (`ApprovalRequest.kind`, `ApprovalRequest.status`)

## D-019: Uniqueness constraints the doc implies
- Date: 2026-11-11
- Decided by: CEO (Yosef)
- Status: Active
- Design doc ref: §5.2.2, §5.2.4, §5.2.11, §5.2.12, §5.2.13, §5.2.16
- Decision: These pairs and fields are unique: RoleAssignment (user, role); CharityOwner (user, charity); CharityDomain (charity, domain); CharityLocation (charity, location); Haskama (rabbi_user, charity), one editable haskama per rabbi per charity; Domain.name.
- Why: The doc does not state these, but duplicates would be meaningless or would double-count.
- Where in code: `apps/accounts/models.py` and `apps/charities/models.py` (`Meta.constraints`, `Domain.name`)

## D-020: REVIEW.body is optional, TICKET.body is required
- Date: 2026-11-11
- Decided by: CEO (Yosef)
- Status: Active
- Design doc ref: §5.2.15, §5.2.19
- Decision: `Review.body` may be empty (an empty string, not null). `Ticket.body` is required.
- Why: The doc gives neither column a nullability. A rating alone is a valid review, but a ticket with no text is not actionable.
- Where in code: `apps/charities/models.py` (`Review.body`), `apps/support/models.py` (`Ticket.body`)

## D-021: CHARITY.image is a URL/path string
- Date: 2026-11-11
- Decided by: CEO (Yosef)
- Status: Active
- Design doc ref: §5.2.9
- Decision: `Charity.image` is a nullable string holding an image URL or path, not an uploaded-file field.
- Why: §5.2.9 types it as a string and the doc does not specify image upload or storage.
- Where in code: `apps/charities/models.py` (`Charity.image`)

## D-022: Dev tooling may write any app's rows
- Date: 2026-11-12
- Decided by: CEO (Yosef)
- Status: Active
- Design doc ref: §6.1
- Decision: The shared test factories (`tests/factories/`) and the dev seed command (`manage.py seed`, in the dashboards app) may create any app's rows directly. This is the only exception to D-006, and it applies to dev tooling only, never to runtime code.
- Why: Building fake data through every app's services would mean writing services that no feature needs yet. Dashboards is the app §6.1 already lets depend on every other app.
- Where in code: `tests/factories/`, `apps/dashboards/management/commands/seed.py`, `CLAUDE.md`

## D-023: A charity is visible only with an approved NEW_CHARITY request
- Date: 2026-11-12
- Decided by: CEO (Yosef)
- Status: Superseded by D-038 on 2026-11-12
- Design doc ref: §5.3, §6.2.14
- Decision: A charity is visible to the public if and only if it has an APPROVAL_REQUEST of kind `new_charity` with status `approved`. When an admin adds a charity directly (§6.2.14), a `new_charity` request is still created, already approved and decided by that admin. There are no exceptions.
- Why: §5.3 hides unapproved charities and keeps pending status only in the approval tables, but the doc does not say what makes a charity with no request visible. A single rule covers every case.
- Where in code: `apps/approvals/models.py` (`ApprovalRequest`, `NewCharityRequest`), `apps/dashboards/management/commands/seed.py`

## D-024: Seeded charity images use an external placeholder host
- Date: 2026-11-12
- Decided by: CEO (Yosef)
- Status: Active
- Design doc ref: not in design doc
- Decision: Fake charity images in dev seed data point at an external placeholder image host. This applies to dev data only.
- Why: It needs no image files in the repo.
- Where in code: `apps/dashboards/management/commands/seed.py` (`PLACEHOLDER_IMAGE`)

## D-025: Bare minimum, as long as changing it later is easy
- Date: 2026-11-12
- Decided by: CEO (Yosef)
- Status: Active
- Design doc ref: not in design doc
- Decision: Build the smallest thing that meets the goal, and leave out anything that is cheap to add later (extra seed data, options, tooling). Do not cut corners on anything expensive to change later: schema shape, app boundaries, URL structure, settings and secrets, auth, and migration history. Every step or PR report includes the line "Shortcuts taken that would be costly to reverse: none / <list>".
- Why: Cheap omissions save time now. Expensive shortcuts cost far more to undo once data and other developers' code depend on them.
- Where in code: `CLAUDE.md`

## D-026: Nav URLs for pages D-009 doesn't name
- Date: 2026-11-12
- Decided by: COO, under the CEO's delegation
- Status: Active
- Design doc ref: §7.1, §7.2
- Decision: As of 2026-11-12, these paths are fixed: charity listing `/charity/`, help `/support/help/`, report a charity `/support/report/`, maaser tools `/tools/`, login `/accounts/login/`, signup `/accounts/signup/`, logout `/accounts/logout/` (a POST).
- Why: Each page sits under the prefix of the app that owns it (§6.1), following D-009.
- Where in code: `templates/base.html` (nav)

## D-027: Maaser pages live under /tools/
- Date: 2026-11-12
- Decided by: COO, under the CEO's delegation
- Status: Active
- Design doc ref: §7.1.3, §6.1
- Decision: Income history, donation history and the maaser calculator are at `/tools/income/`, `/tools/donations/` and `/tools/maaser/`, not under `member_dashboard/` as §7.1.3 lists them. The member dashboard links to them.
- Why: The tools app owns TRANSACTION and the maaser calculation (§6.1), and D-009 puts each app's pages under its own prefix.
- Where in code: `apps/tools/urls.py` (when the tools pages are built)

## D-028: / redirects to the charity listing
- Date: 2026-11-12
- Decided by: COO, under the CEO's delegation
- Status: Active
- Design doc ref: §6.2.3
- Decision: Once the charity listing exists, `/` redirects to `/charity/`. As of 2026-11-12, `/` shows a placeholder page.
- Why: §6.2.3 makes the listing the landing page.
- Where in code: `config/urls.py`, `templates/home.html`

## D-029: HTMX and Alpine are served from static/
- Date: 2026-11-12
- Decided by: COO, under the CEO's delegation
- Status: Active
- Design doc ref: §4.7, §4.13, §2.4.3
- Decision: HTMX 2.0.4 and Alpine.js 3.14.8 are committed under `static/vendor/` and served with the site's own static files, never from a third-party CDN. Upgrading means replacing the file and its versioned name.
- Why: §4.13 says no CDN; a third-party CDN would see every visitor's IP, against the privacy requirement (§2.4.3); and the site must not break when the CDN is down.
- Where in code: `static/vendor/`, `templates/base.html`

## D-030: The seed command only runs on an empty database
- Date: 2026-11-12
- Decided by: CEO (Yosef)
- Status: Active
- Design doc ref: not in design doc
- Decision: `manage.py seed` deletes nothing. It refuses to run, with an error naming the tables that have rows, unless every app table is empty and DEBUG is on. To reseed, a developer drops and recreates the database, then runs `migrate` and `seed`.
- Why: DEBUG is on by default in local settings, so a seed that wiped tables could erase a real database (such as RDS) if a `.env` pointed at it.
- Where in code: `apps/dashboards/management/commands/seed.py` (`Command.handle`), `tests/integration/test_seed.py`, `README.md`

## D-031: If you see something, say something
- Date: 2026-11-12
- Decided by: CEO (Yosef)
- Status: Active
- Design doc ref: not in design doc
- Decision: Every problem, risk or doubt anyone notices goes into their report, even if it is out of scope or cannot be verified. Unverified items are reported as questions. Nothing is dropped silently; worst case, it reaches the CEO.
- Why: A finding that is reported and turns out not to matter costs little; one that is dropped can cost a lot later.
- Where in code: `CLAUDE.md`

## D-032: Constraints stricter than the data dictionary
- Date: 2026-11-12
- Decided by: Platform Lead (schema and platform owner); open to CEO override by a later entry
- Status: Active
- Design doc ref: §5.2.1, §5.2.8, §5.2.10
- Decision: USER.username and USER.email are unique ignoring case (unique on `Lower(...)`). LOCATION is unique on (name, region, country). EDIT_REQUEST.target_type is non-null. The doc states the first two as plain "unique" and gives no uniqueness for LOCATION or nullability for target_type. Login and signup must normalise username case to match (a Phase 1 task).
- Why: Case-variant duplicate accounts and duplicate filter locations are costly to clean up once data exists. target_type must be set for D-014's check constraint to work.
- Where in code: `apps/accounts/models.py` (`User.Meta.constraints`), `apps/charities/models.py` (`Location.Meta.constraints`), `apps/approvals/models.py` (`EditRequest.target_type`)

## D-033: Nav hides Sign up when logged in
- Date: 2026-11-12
- Decided by: Platform Lead (schema and platform owner); open to CEO override by a later entry
- Status: Active
- Design doc ref: §7.2
- Decision: When a user is logged in, the nav shows "Log out" in place of both "Log in" and "Sign up". §7.2 says only that login becomes logout.
- Why: Signing up again while logged in is not a normal path; the signup pages (§6.2.2) handle extra roles for logged-in users on their own.
- Where in code: `templates/base.html`

## D-034: Cross-app foreign keys are schema-only and allowed in any direction
- Date: 2026-11-12
- Decided by: Platform Lead (schema and platform owner); open to CEO override by a later entry
- Status: Active
- Design doc ref: §6.1
- Decision: A model may hold a foreign key to another app's model in any direction, declared with a string label and always with `related_name="+"`, so no app gets reverse accessors into another app's tables. Foreign keys are not dependencies in the §6.1 sense: queries and calls still go only through `services.py` and only along §6.1's dependencies (D-006).
- Why: §6.1 marks only events as "string FKs only", yet accounts, tools and support "depend on nothing" while needing foreign keys to CHARITY and USER. The schema needs these keys; keeping them schema-only preserves the module boundaries.
- Where in code: `apps/*/models.py` (every cross-app `ForeignKey`), `CLAUDE.md`

## D-035: Friendly error pages and the network retry indicator arrive in Phase 1
- Date: 2026-11-12
- Decided by: Platform Lead (schema and platform owner); open to CEO override by a later entry
- Status: Active
- Design doc ref: §4.1, §4.16
- Decision: As of 2026-11-12, there are no custom 403/404/500 pages and no 5-second retry with a "connecting" indicator. Both are built in Phase 1: the error pages extend `base.html` (500.html without context that can fail), and the retry comes with the first HTMX interaction.
- Why: Both are cheap to add when there are real pages to show them on (D-025). The site is not deployed in Phase 0.
- Where in code: `templates/` (403.html, 404.html, 500.html in Phase 1)

## D-036: One LINK per kind per charity, built to relax later
- Date: 2026-11-12
- Decided by: CEO (Yosef)
- Status: Superseded by D-040 on 2026-11-12
- Design doc ref: §5.2.14, §5.2.8
- Decision: As of 2026-11-12, a charity has at most one link of each kind (donate, about, contact), enforced by a unique constraint on LINK (charity, kind). The CEO: "right now 1 per and if we need more later we can add but build it ajustable". To keep it adjustable, links stay in their own table (no single-valued `website_*` columns on CHARITY), and nothing outside `apps/charities/services.py` assumes one link per kind: anything that reads links gets a list or queryset. To allow several links per kind later, drop the `link_charity_kind_uniq` constraint in one migration, with no other code change.
- Why: §5.2.14 does not say, but EDIT_REQUEST (§5.2.8) edits a link kind with a single new_value, which implies one per kind. Adding the constraint after data exists would need a cleanup migration, while dropping it later is free.
- Where in code: `apps/charities/models.py` (`Link.Meta.constraints`, `link_charity_kind_uniq`), `tests/unit/test_models.py`

## D-037: The nav stays pinned to the top while scrolling
- Date: 2026-11-12
- Decided by: CEO (Yosef)
- Status: Active
- Design doc ref: §7.2
- Decision: §7.2's "always visible" means the nav bar is on every page and stays pinned to the top of the screen while scrolling, on every screen size. It uses CSS `position: sticky`, which keeps it in the page flow so it never covers content. The CEO: "so well go for b now". Hiding the bar on phones while scrolling down was considered and deferred. Could add later: hide-on-scroll-down for small screens, which is a small Alpine addition to `base.html`.
- Why: Settles the open question on what "always visible" means.
- Where in code: `templates/base.html` (`nav` style), `tests/integration/test_base_template.py`

## D-038: Charity visibility is an on/off switch owned by charities
- Date: 2026-11-12
- Decided by: CEO (Yosef)
- Status: Active
- Design doc ref: §5.3, §6.1, §6.2.14
- Decision: CHARITY has `is_visible` (default false, indexed). A new charity starts hidden. When its approval goes through, approvals calls `charities.services.publish_charity(charity_id)`, which is the allowed direction under §6.1. An admin can hide a visible charity again with `hide_charity(charity_id)`, for example to review it after many reports. Nothing outside the charities app sets the field directly. The listing reads `is_visible` and does not depend on approvals. Every charity still gets a NEW_CHARITY approval request as its approval record, and an admin who adds a charity directly (§6.2.14) creates it already approved, then publishes it. The CEO: "option b please makes sense charitys start as hidden then when approved its fipped to visible but theres still an option to hide it for lets say its been reported a lot and we want to review it again". Could add later: a reason for hiding, an "under review" state, and a link from hiding to the reports/tickets that caused it. It stays a plain on/off switch for now so it is easy to grow.
- Why: It replaces D-023, which would have made the listing depend on approvals' tables against §6.1. It also lets a charity be hidden again without touching its approval history.
- Where in code: `apps/charities/models.py` (`Charity.is_visible`), `apps/charities/services.py` (`publish_charity`, `hide_charity`), `apps/dashboards/management/commands/seed.py`, `tests/unit/test_charity_services.py`

## D-039: Visibility changes are recorded as charity_updated events, without details
- Date: 2026-11-12
- Decided by: Platform Lead (schema and platform owner); open to CEO override by a later entry
- Status: Active
- Design doc ref: §5.2.17, §6.1
- Decision: `publish_charity` and `hide_charity` each record one EVENT with action `charity_updated` and the acting user (`by_user_id`), in the same transaction as the change, through `events.services.record_event`. EVENT (§5.2.17) has no details column, so the event says who changed the charity and when, but not that it was a publish or a hide. No column is added for it. If that detail is needed later, register CHARITY with django-auditlog (an open question) or add a details column in a new migration.
- Why: §6.1 has charities record a `charity_updated` event on every change, which gives hiding an audit trail of who and when. Adding a details column is a schema change the doc does not ask for.
- Where in code: `apps/charities/services.py` (`_set_visible`), `apps/events/services.py` (`record_event`), `tests/unit/test_charity_services.py`

## D-040: One LINK per kind per charity; relaxing it also needs EDIT_REQUEST to name the link
- Date: 2026-11-12
- Decided by: CEO (Yosef); correction by Platform Lead
- Status: Active
- Design doc ref: §5.2.14, §5.2.8
- Decision: Same rule as D-036: a charity has at most one link of each kind, enforced by `link_charity_kind_uniq` on LINK (charity, kind). The CEO: "right now 1 per and if we need more later we can add but build it ajustable". Links stay in their own table and are read as lists. D-036 said relaxing the rule needs no other code change, which is wrong: EDIT_REQUEST names a link only by `field` (`website_donate`/`website_about`/`website_contact`) with one `new_value`, so with several links of a kind an edit request could not say which one it changes. To allow several per kind later: (1) drop `link_charity_kind_uniq` in a new migration, (2) add a nullable `link` foreign key to EDIT_REQUEST in a new migration, (3) make `apply_charity_edit` use it.
- Why: The review of D-036 found the overclaim. Entries are never edited, so the correction is this new entry.
- Where in code: `apps/charities/models.py` (`Link.Meta.constraints`), `apps/approvals/models.py` (`EditRequest.field`), `tests/unit/test_models.py`

## D-041: Publishing or hiding a charity already in that state does nothing
- Date: 2026-11-12
- Decided by: Platform Lead (schema and platform owner); open to CEO override by a later entry
- Status: Active
- Design doc ref: §5.2.21, §6.1
- Decision: `publish_charity` on a visible charity and `hide_charity` on a hidden one change nothing and record no event. Django admin shows `is_visible` read-only and offers "Publish selected charities" / "Hide selected charities" actions that call the services with the admin as the acting user. The seed publishes approved charities through `publish_charity` too, so seeded data has the same events as real data (all dated at seed time).
- Why: A charity_updated event moves the derived "last updated" date (§5.2.21), so it must mean a real change. The admin form must not bypass the services, or changes would skip the event that D-039 relies on.
- Where in code: `apps/charities/services.py` (`_set_visible`), `apps/charities/admin.py` (`CharityAdmin`), `apps/dashboards/management/commands/seed.py`, `tests/unit/test_charity_services.py`, `tests/integration/test_charity_admin.py`

## D-042: The listing shows every charity until something can publish one

- Date: 2026-11-12
- Decided by: builder, pending CEO/COO confirmation
- Status: Active
- Design doc ref: §6.2.3
- Decision: `charities.repositories.DjangoCharityRepository` takes `published_only`, default `False`, so the listing reads all charities. It flips to `True` when the admin approval queue lands, since that queue is what calls `publish_charity` (D-038). The option is a constructor argument, not a setting or a class attribute, so the behaviour is explicit at the call site and testable in both directions.
- Why: D-038 makes `is_visible` the visibility switch and gives every charity `False` by default. Nothing calls `publish_charity` yet, because the admin approval queue is not built. Reading `is_visible` literally would render an empty listing and make the tracer bullet unverifiable. This is a deliberate, temporary departure from D-038 and it is undone by one argument when the queue exists.
- Where in code: `apps/charities/repositories.py` (`published_only`), `apps/charities/views.py` (`listing`)
## D-YOSEF-accounts-login: Accounts: one signup, roles requested after, and how login is protected
- Date: 2026-11-14
- Decided by: CEO (Yosef)
- Status: Active, except the admin point: superseded by D-YOSEF-admin-superuser on 2026-11-15
- Design doc ref: §6.2.1, §6.2.2, §7.1.1, §8.3, §8.4
- Decision:
  - Sign-in is username and password through Django's built-in auth. Google sign-in may be added later alongside it.
  - There is one signup for everyone, at `/accounts/signup/`. It creates the user and the `member` role, so every account is a member. There is no "pick a role" page and no guest version of the rabbi or owner forms.
  - A logged-in user asks for an extra role at `/accounts/rabbi-signup/` or `/accounts/owner-signup/`. Both require login, take no user id in the URL (the user comes from the session), and end pending until an admin approves.
  - The other accounts URLs are `/accounts/login/`, `/accounts/logout/`, `/accounts/pending/` and `/accounts/choose-dashboard/`. These are flat, hyphenated names under the D-009 prefix.
  - "Admin" means `User.is_staff`, read through a `User.is_admin` property. It is not a role row and not a new column.
  - Login looks usernames up with `LOWER(username)`, which uses the `user_username_ci_uniq` index (D-032). Django's `iexact` compiles to `UPPER(...)` on PostgreSQL and scans the whole table.
  - Five failed logins for a username lock that username for one hour. Until then the message is only "wrong username or password". During the lock even the right password is refused.
  - Login is rate limited per client IP with a token bucket: 20 tokens, one added every 3 seconds. Over the limit the request gets 429 before any password check. The client IP comes from `X-Forwarded-For` only when the request arrives through Caddy.
  - Every page or service that takes an object id checks that the current user may access that object, with a test showing another user is refused. Access is checked in code, not with PostgreSQL row-level security.
- Why: One signup keeps the email check in a single place and drops the guest/logged-in duplicates of each form. Roles added later go through the same pending approval as the doc describes. Password hashing is deliberately slow (about 0.07 s per try in local testing), so refusing over-limit requests before the check protects the server. The lockout protects each account from guessing.
- Where in code: `docs/DECISIONS.md` (this entry); later `apps/accounts/` (backend, services, views, urls), `config/settings/base.py`, `config/urls.py`

## D-YOSEF-sql-params: Queries take user input only as parameters
- Date: 2026-11-14
- Decided by: CEO (Yosef)
- Status: Active
- Design doc ref: not in design doc
- Decision: Database queries go through the Django ORM, which sends user input to PostgreSQL as separate parameters, never pasted into the SQL text. If raw SQL is ever needed, it uses `cursor.execute(sql, params)` or `QuerySet.raw(sql, params)` with placeholders (`%s`), never f-strings, `+` or `%` formatting. `QuerySet.extra()` and `RawSQL` are not used. Ruff enforces this with rules S608, S610 and S611; as of 2026-11-14 no app code uses raw SQL.
- Why: A query built from text the user typed can be turned into a different query (SQL injection), e.g. a username of `' OR 1=1 --`. Parameters make the input data, never code.
- Where in code: `pyproject.toml` (`[tool.ruff.lint] select`), `tests/unit/test_auth_backend.py` (injection-shaped usernames are refused)

## D-YOSEF-shared-cache: Django's cache lives in PostgreSQL
- Date: 2026-11-15
- Decided by: CEO (Yosef)
- Status: Active
- Design doc ref: §6.2.1.8 (lockout); not otherwise in design doc
- Decision: The caches are `DatabaseCache`: `default` in the table `django_cache` (rate-limit buckets), and `login` in `login_cache` (login failures and locks). A DatabaseCache over its MAX_ENTRIES deletes its alphabetically lowest keys whether or not they have expired, so locks get their own table, where a flood of other keys can't delete them. Both tables are made by one `manage.py createcachetable`, not by a migration, so every database (local, CI, production) needs that command run once after `migrate`. Django's test runner runs it on the test database automatically.
- Why: The login lockout and rate limit (D-YOSEF-accounts-login) keep counters in the cache. Django's default per-process memory cache would give each Gunicorn worker its own counters and lose them on restart, multiplying the allowed tries. PostgreSQL is already in the stack; Redis would add a service. Switching later is one settings change.
- Where in code: `config/settings/base.py` (`CACHES`), `README.md` (setup steps), `tests/unit/test_cache.py`

## D-YOSEF-admin-superuser: A MaaserMart admin is a superuser
- Date: 2026-11-15
- Decided by: CEO (Yosef)
- Status: Active. Replaces the "Admin means `User.is_staff`" point of D-YOSEF-accounts-login.
- Design doc ref: §5.2.2, §6.2.1
- Decision: `User.is_admin` is `is_superuser`, Django's highest level: every permission, everywhere. The founders (Yosef, Shaul, Benjamin) are superusers. `is_staff` alone only lets someone into `/django-admin/`, limited to the permissions they are given, and does not make them a MaaserMart admin. So a helper, such as a technical supporter, can be given `is_staff` to fix data without seeing the approval queue or the admin dashboard.
- Why: Asked during review of PR #12. With `is_staff`, giving anyone access to `/django-admin/` would also have made them a full admin in the app.
- Where in code: `apps/accounts/models.py` (`User.is_admin`), `tests/unit/test_find_role.py`
## D-YOSEF-member-signup: Member signup checks everything first, then confirms the email with a typed 6-digit code
- Date: 2026-11-15
- Decided by: CEO (Yosef)
- Status: Active
- Design doc ref: §6.2.2, §8.4 (resolves the open question "Email verification method": typed code, not a link)
- Decision:
  - `/accounts/signup/` takes username, email, password and a terms tick. `/accounts/signup/verify/` takes the code. The account does not exist until the right code is typed; then it is created with the `member` role (both rows or neither) and the user is logged in and sent where login would send them.
  - Step 1 checks, cheapest first, with nothing written or sent until all pass: the fields and Django's password rules; 5 signups an hour per client network (a form with mistakes doesn't count); username and email not taken ignoring capitals (D-032); 3 code emails an hour per inbox, where aliases of one inbox (`+tags`, and dots or googlemail.com for Gmail) count as one. The page says when a username or email is taken, as §6.2.2.8 asks.
  - The code is 6 digits from `secrets`, lasts 15 minutes and allows 5 tries; the fifth wrong try throws it away. Tries are counted in the `login` cache under a random id per code, with a PostgreSQL advisory lock so parallel guesses can't each count as the first; a used code can't be tried again. Each client network also gets 10 code tries, then one a minute. A new code gets a new id (fresh tries and clock) and counts toward the 3 emails an hour.
  - The pending signup (username, email, password hash, code) waits in the session, which is stored in the database (§8.4: "Verification code lives in Django session"). The plain password is never kept.
  - The email goes through a Celery task (§4.14). The terms paragraph is a placeholder until real terms are written.
- Why: A typed code keeps the user on one tab and matches §6.2.2. Checking first means a refused signup costs no email and no password hash. The limits stop guessing codes and stop anyone using signup to flood an inbox. These emails are account (transactional) emails, so no separate email consent is asked; marketing email would need its own opt-in.
- Where in code: `apps/accounts/signup.py`, `apps/accounts/services.py` (`submit_member_signup`, `enqueue_signup_code`), `apps/accounts/tasks.py`, `apps/accounts/views.py`, `templates/accounts/signup*.html`, `tests/integration/test_signup.py`

## D-042: The listing shows every charity until something can publish one

- Date: 2026-11-12
- Decided by: builder, pending CEO/COO confirmation
- Status: Active
- Design doc ref: §6.2.3
- Decision: `charities.repositories.DjangoCharityRepository` takes `published_only`, default `False`, so the listing reads all charities. It flips to `True` when the admin approval queue lands, since that queue is what calls `publish_charity` (D-038). The option is a constructor argument, not a setting or a class attribute, so the behaviour is explicit at the call site and testable in both directions.
- Why: D-038 makes `is_visible` the visibility switch and gives every charity `False` by default. Nothing calls `publish_charity` yet, because the admin approval queue is not built. Reading `is_visible` literally would render an empty listing and make the tracer bullet unverifiable. This is a deliberate, temporary departure from D-038 and it is undone by one argument when the queue exists.
- Where in code: `apps/charities/repositories.py` (`published_only`), `apps/charities/views.py` (`listing`)

---

## D-043: Seeded charity images use the artwork already in the repo

- Date: 2026-11-13
- Decided by: CEO (Yosef), asked for directly
- Status: Active (supersedes D-024)
- Design doc ref: not in design doc
- Decision: The dev seed gives every charity one of the twelve SVGs in `static/charities/img/`, cycling through them by index, instead of pointing at an external placeholder host. `image` holds a repo-relative path such as `charities/img/charity-04.svg`, so the template serves it through `{% static %}` the way a real uploaded path would be served.
- Why: D-024's placeholders rendered as grey rectangles with the text "600x400", which read as broken. Only every third charity got one at all, so 133 of 200 rows had no image. The repo already ships twelve distinct images that nothing referenced. This also exercises the relative-path branch of the listing template, which the external URLs never touched, and removes a network dependency from dev.
- Where in code: `apps/dashboards/management/commands/seed.py` (`IMAGE_PATHS`), `apps/charities/templates/charities/listing.html`

---

## D-044: The listing shows each charity's average rating and review count

- Date: 2026-11-13
- Decided by: CEO (Yosef), asked for directly
- Status: Active
- Design doc ref: §5.2.15, §5.3, §6.2.3
- Decision: Every card in the charity listing shows the charity's average rating and how many reviews it has. §5.3 has the listing page show "average rating", so that number is on the card, and the count goes with it because an average alone hides whether it is based on one review or fifty. Both are derived from REVIEW on read — nothing is stored, per §5.3's "derive data" rule — and a charity with no reviews shows "No reviews yet" instead of "0 out of 5", which would read as a rating of zero rather than no rating. The average is shown to one decimal. The repository annotates the page query with `Count`/`Avg` so the listing still costs no extra round trip, and the card carries the pair as `ReviewSummary(count, average)` where `average` is `None` when there are no reviews.
- Why: §5.3 names an average rating on the list page but says nothing about a count, the empty state or rounding. Deriving both values keeps them from going stale when a review is written or edited.
- Where in code: `apps/charities/contracts.py` (`ReviewSummary`), `apps/charities/repositories.py` (`DjangoCharityRepository.page`, `_to_card`), `apps/charities/templates/charities/listing.html`, `static/css/site.css`, `tests/unit/test_repositories.py`, `tests/unit/test_template_contract.py`

## D-045: The charity listing filters by six groups, with the shape the doc gives them

- Date: 2026-11-13
- Decided by: CEO (Yosef), asked for directly; built by the filter branch
- Status: Superseded by D-046 on 2026-11-13, for the parameter-name correction and the min_rating range rule
- Design doc ref: §6.2.4 (Filter — FR 2), §8.5 (UC-03)
- Decision: `charities.services.list_charities` takes an optional `filters` mapping and narrows the listing by **six** of §6.2.4's seven groups: `domain`, `location`, `haskama_rabbis`, `min_rating`, `min_reviews`, `min_approving_haskamas`, `max_disapproving_haskamas` — that is all seven, with `haskama_rabbis` present in shape but unpopulated (see the sub-decision below). Values repeat inside a group (OR) and groups combine (AND), exactly as §6.2.4 says; setting any filter returns page 1. The groups mean, precisely:
  - `domain`, `location`, `haskama_rabbi`: repeatable **ids** (`?domain=2&domain=5`), not names. A raw value that names no row is ignored rather than rejected, the same way the listing already treats a junk `page`. Ids because names are not keys: D-032 makes LOCATION unique on (name, region, country), so a name alone can point at several locations.
  - `min_rating`: a minimum **average star rating, 1–5 inclusive**, the scale `REVIEW.rating` holds and the one D-044 prints on the card ("4.5 out of 5"). There is no "no minimum" value: clearing the group is what clears it. A value off the scale is clamped into it and the sidebar says so (D-046). A charity with no reviews has no average, so it does not match a `min_rating` filter.
  - `min_reviews`: minimum `ReviewSummary.count`, the number D-044 already shows on the card.
  - `min_approving_haskamas` / `max_disapproving_haskamas`: minimum and maximum counts of `HASKAMA` rows with verdict `approve` / `disapprove`.
  - `0` is a real value for `min_reviews`, `min_approving_haskamas` and `max_disapproving_haskamas` ("no reviews", "no disapprovals"). An absent `max_disapproving_haskamas` is no cap, because absence cannot mean zero without ruling out every charity that has one.
- Sub-decision — `haskama_rabbis` returns nothing today: `HASKAMA` is queried in its real shape (`verdict`, `rabbi_user_id`), but the **option list** it needs is `accounts.services.search_rabbis`, which §6.2.4 names and which does not exist yet. Until it does, the group's options are empty and its parameter matches nothing; the query path is written and covered by a test with direct `HASKAMA` rows, so wiring the search in changes no other code. Asked for this way: "include whatever tables it needs in real form, but there happens to be no data, so you will have to give that result."
- Sub-decision — no `is_visible` filtering while D-042 stands: as of 2026-11-13 the listing shows charities that are not yet admin-approved (D-042), and the CEO's instruction is that every filter applies the same way, so rating, review and haskama counts are read from all charities' rows, published or not. Repositories filter on `is_visible` only through their existing `published_only` argument, so the day the approval queue flips it, the filters narrow with the listing and nothing else changes.
- Sub-decision — a location's label is its full identity: because a name is not unique, both the card chip and the filter checkbox label show name, region and country ("Lakewood, New Jersey, USA"), never the name alone.
- Sub-decision — a rabbi's option carries RABBI_PROFILE's two parts: `RabbiOption` holds `display_name` and nullable `title` (§5.2.3) and joins them into a label ("Rabbi Yosef Cohen", or the name alone when the title is empty), the same shape `LocationOption` uses, so the formatting rule lives in `charities` where the template is and not in whichever app supplies the list. Its `id` is the **user** id, because `HASKAMA` stores `rabbi_user`.
- Why: §6.2.4 fixes the groups, their URL parameter names and the OR/AND rule but leaves the rating scale, the meaning of zero, the identity of a domain/location/rabbi value and the empty-state behaviour unstated, and those choices decide the URL shape, which is expensive to change once links are shared. Picking ids and a 1–5 scale keeps the filter page, the cards and §5.2.15 saying the same thing.
- Where in code: `apps/charities/contracts.py` (`CharityFilters`, `DomainOption`, `LocationOption`, `RabbiOption`), `apps/charities/services.py` (`list_charities`, `list_domains`, `list_locations`, `list_rabbis`), `apps/charities/repositories.py` (`CharityRepository`, `DjangoCharityRepository`), `apps/charities/views.py` (`_read_filters`), `apps/charities/templates/charities/filters.html`, `tests/unit/test_filter_service.py`

---

## D-046: Filter audit corrections: the rabbi parameter is singular, an out-of-range rating filters nothing, and a chosen zero still shows

- Date: 2026-11-13
- Decided by: CEO (Yosef) and Platform Lead, on the filter-branch audit
- Status: Active
- Design doc ref: §6.2.4 (Filter — FR 2)
- Decision: Four corrections to D-045, three of which change what is built:
  - The Haskamos group's URL parameter is `haskama_rabbi` — singular, exactly as §6.2.4 writes it — not `haskama_rabbis` as D-045 recorded. The group's internal name stays `haskama_rabbis` (one rabbi filters by their id, several filter by several); only the URL surface is the doc's spelling. D-045 is superseded for its parameter-name and rating-range text, and stays active for everything else.
  - A `min_rating` outside 1–5 is **clamped into the scale, once, where the URL is read**, and the correction is shown instead of being silent: the sidebar's input displays the value actually applied and a note beside it says "Kept between 1 and 5; using 5." D-045's original clamp was invisible, which is what made `?min_rating=99` surprising; the problem was the silence, not the saturating.
  - The Haskamos group's values are **ids**, not the usernames §6.2.4's parameter line mentions. Ids survive a rabbi renaming their public name, match the other repeatable groups, and are what `accounts.services.search_rabbis` will feed the sidebar; the doc's "username" was a design note, not a contract. Decided here because D-045 asserted ids without saying the doc names usernames.
  - A chosen `0` in `max_disapproving_haskamas` (or any numeric group) renders as `0`, not as a blank box: the sidebar now carries an explicit `is_set` per group rather than inferring "set" from a truthy value.
  - This entry first said an out-of-range rating would be *ignored* rather than clamped, and that was built and reviewed. The CEO then chose clamping: "clamp it, but make it clear." Clamping therefore stands, and the audit finding is answered by making the correction visible. `clamp_rating` in `filters.py` is the one place it happens, so the query, the sidebar's input and the page links cannot disagree, and `sidebar_groups` receives the raw numbers `requested_numbers` read so it can compare and say what changed.
  - The repeatable groups' option lists scroll inside the panel (`.filters__options`, capped at 14rem) instead of growing without bound, so a real, thousands-row location list cannot push the Apply button off the page. The group table also collapsed into one `Group` entry per filter, keyed by URL parameter, so the code no longer keeps three lists that must agree.
- Why: The audit found the parameter spelling diverging from the doc and two behaviours (the clamp, the blank-zero) that worked today but would break the moment rendering or clamping changed. The option lists were the one unbounded read on the page.
- Where in code: `apps/charities/filters.py` (`GROUPS`, `Group`, `clamp_rating`, `requested_numbers`, `sidebar_groups`, `is_set`), `apps/charities/repositories.py` (`_narrowed`), `apps/charities/views.py`, `apps/charities/templates/charities/filters.html`, `static/css/site.css` (`.filters__options`), `tests/unit/test_filter_service.py`, `tests/unit/test_filter_repository.py`, `tests/unit/test_views.py`

---

## D-047: The filter sidebar scrolls as a whole, so its last groups stay reachable

- Date: 2026-11-14
- Decided by: CEO (Yosef)
- Status: Active
- Design doc ref: §6.2.4 (Filter — FR 2)
- Decision: The sidebar is bounded to the viewport and scrolls inside itself: `max-height: calc(100vh - 5.5rem)` with `overflow-y: auto` on `.listing__sidebar`. D-045 and D-046 bounded each option list (`.filters__options`, 14rem), but the seven groups together are taller than a viewport, so reaching the bottom groups meant scrolling the results off the page while the pinned panel stayed where it was. Below 48rem the sidebar sits above the results, so its own scroll and its pinning are both switched off there.
- Why: the panel's last groups were unreachable for a reader who was reading the results, and the only way to them was to scroll away from the page.
- Where in code: `static/css/site.css` (`.listing__sidebar`, and the 48rem reset), `tests/unit/test_template_contract.py` (the rule is read from the stylesheet the page loads, as D-037's nav test does)

---

## D-048: Sort offers §6.2.5's seven orders, with `sort` and `direction` in the URL

- Date: 2026-11-14
- Decided by: builder, pending CEO/COO confirmation
- Status: Active (amended by D-050 for the trending formula and D-053 for how a changed dropdown is applied)
- Design doc ref: §6.2.5 (Sort — SRS FR 3), §5.2.21 (Derived Values), §6.4.3 (Trending), §6.1 (dependencies)
- Decision: The listing's sort is a `CharitySort` value — a mechanism plus a direction — read from the URL and passed to `charities.services.list_charities(repository, filters, sort, page, page_size)`. §6.2.5 fixes the mechanisms and that each has both directions, but not the parameter values, the default direction, or what several of the orders count, so those are settled here:
  - The URL is `?sort=<mechanism>&direction=<asc|desc>`. The mechanisms, in dropdown order, are `alphabetical`, `trending`, `popular`, `rating`, `haskamos`, `newest` and `updated`. `direction` is `asc` or `desc`.
  - `alphabetical` starts A→Z and is the default; every other mechanism starts high→low. When `sort` is absent the mechanism is alphabetical. When `sort` is present but names no mechanism, the whole choice falls back to alphabetical A→Z, which is §6.2.5's "when nothing recognizable is input, or when nothing is input, it defaults to alphabetical a->z". A `direction` that is absent or not `asc`/`desc` falls back to the chosen mechanism's default direction, the same way §6.2.4's filter groups ignore junk values.
  - The dropdown is a GET form that carries `page_size` and the active filters but never `page`, so choosing a sort lands on page 1 (§6.2.5). Changing the dropdown submits it immediately with no `direction` (D-053), so the new mechanism starts in its default direction and the two buttons' labels always describe the order they will apply. The two direction buttons are submits named `direction`, so they pick the mechanism shown in the dropdown and the clicked direction in one action. Pagination links, the page-size form, the jump form and the filter form carry the sort, so neither control silently drops the other; the filter protocol keeps the sort and vice versa (D-045).
  - The default sort adds no parameters to a URL. `alphabetical` ascending is treated as the default even when written out, so a page-size form or pagination link round-trips to the shortest equivalent address.
  - Ties break alphabetically, A→Z, as §6.2.5's failure path says, then by id so a page boundary cannot repeat or skip a row. The tiebreak is not reversed when the primary order is descending: "latest first" with two equal timestamps still reads A→Z.
  - `trending` is §6.4.3's score, with the two windows read as non-overlapping: 3 × the charity's EVENT rows in the last 7 days plus 2 × its EVENT rows 8–30 days ago. "Past" is measured from the request time, in UTC (D-010). D-050 settled the buckets; this entry first recorded the literal double count.
  - `popular` is the total number of EVENT rows for the charity (§5.2.21's "visit count is derived from events"), of every action: views, link clicks, rejections and charity updates.
  - `rating` is the average REVIEW.rating (D-044's number), not the review count. Charities with no reviews have no average and sort last in **both** directions: no rating is not a low rating.
  - `haskamos` counts **approving** HASKAMA rows only. §6.2.4 already separates approving from disapproving haskamos, and a disapproval is not an endorsement, so it does not raise a charity's position.
  - `newest` is CHARITY.created, which D-017 made required. §6.2.5 lists NEW_CHARITY_REQUEST among the tables read, but §6.1 does not make approvals a dependency of charities; the request and the charity are created in the same transaction (§6.2.2), so the charity's own timestamp says the same thing without a cross-app read.
  - `updated` is the latest EVENT for the charity with action `charity_updated` (§5.2.20's `(charity_id, action, created)` index is built for exactly this), falling back to CHARITY.created when the charity has no such event. It is not read from EDIT_REQUEST or APPROVAL_REQUEST: §6.2.5 lists them, but §6.1 makes approvals depend on charities, not the reverse (D-006). Every save of a charity records a `charity_updated` event through charities' own service (D-052), so edits are included without reading another app's tables.
  - EVENT metrics are ordered in the listing's one database query through subquery expressions exported by `events.services` (`event_count`, `trending_score`, `last_changed`). Charities never imports the EVENT model or queries its table, so D-006 holds. This follows UC-03's implementation constraint that sorting uses Django's `annotate` rather than sorting rows in Python after paging.
- Why: §6.2.5 settles the behaviour but leaves the URL, the defaults and four ambiguous counts open, and the URL is expensive to change once links are shared. The choices keep the sort page and the cards saying the same thing: rating means the average already printed on each card, haskamos means the approving count §6.2.4 already distinguishes from a disapproval, and updated means the same "last change" event trail D-039 writes.
- Where in code: `apps/charities/sorting.py` (`MECHANISMS`, `CharitySort`, `from_query`, `query_pairs`, `sort_form`), `apps/charities/services.py` (`list_charities`, `Page.sort`, `Page.query`, `Page.clear_filters_query`), `apps/charities/repositories.py` (`DjangoCharityRepository.page`, `_with_sort_values`, `_ordered`), `apps/charities/views.py` (`listing`), `apps/charities/templates/charities/{listing,sort,sort_state,state}.html`, `apps/charities/templates/charities/filters.html`, `static/css/site.css`, `apps/events/services.py` (`event_count`, `trending_score`, `last_changed`), `tests/unit/test_sorting.py`, `tests/unit/test_sort_repository.py`

---

## D-049: Seeded charities get distinct names

- Date: 2026-11-15
- Decided by: CEO (Yosef), on the sort-branch audit
- Status: Active
- Design doc ref: not in design doc (§5.2.2's name field, D-013)
- Decision: The dev seed samples a prefix/word pair without replacement from the full 8 × 26 grid, so all 200 seeded charities have different names. `CHARITY.name` stays non-unique in the schema (D-013); the pool only guarantees the sample is large enough (208 pairs for 200 rows) and `random.sample` fails loudly if the counts ever outgrow it, rather than quietly repeating a name.
- Why: the old seed drew each part independently, so the local database held six "Lev Chaim" and five "Tomchei Torah". Paging a rating-ordered listing then repeated a name on two pages, which reads as a paging bug until you check the ids, and ties across 185 rows made the alphabetical tiebreak look broken. Names are also the only thing a developer eyeballs while working on the listing.
- Where in code: `apps/dashboards/management/commands/seed.py` (`NAME_WORDS`, `NAMES`), `tests/integration/test_seed.py`

---

## D-050: Trending counts each event once: 3 for this week, 2 for days 8–30

- Date: 2026-11-15
- Decided by: CEO (Yosef), on the sort-branch audit
- Status: Active (amends D-048's `trending` bullet)
- Design doc ref: §6.4.3 (Trending)
- Decision: `events.services.trending_score` scores `3 × EVENT rows in the last 7 days + 2 × rows 8–30 days ago`. The month bucket excludes the week instead of repeating it, so one event is worth 3 or 2, never 5. The 30-day outer window and the weights are unchanged, as is the UTC measurement from the request time (D-010).
- Why: §6.4.3's wording ("multiplying events in the past week by 3 and events in the past month by 2") is ambiguous because the week is inside the month. D-048 first built the literal reading, then left it pending confirmation. The CEO chose non-overlapping buckets: a score that counts one visit twice makes a single busy day outweigh a month of steady activity, and it would have been copied by recommendations and owner stats.
- Where in code: `apps/events/services.py` (`trending_score`), `tests/unit/test_sort_repository.py` (`TrendingSortTest`)

---

## D-051: Every card shows the activity values the activity orders sort by

- Date: 2026-11-15
- Decided by: CEO (Yosef), on the sort-branch audit
- Status: Active
- Design doc ref: §5.3, §6.2.5 (Sort — SRS FR 3), §5.2.21 (Derived Values)
- Decision: Every card in the listing shows three activity values alongside the rating: the charity's total EVENT count, its count of **approving** HASKAMA rows, and the date of its last change. `CharityCard` carries them as `ActivitySummary(events, approving_haskamas, last_changed)`, annotated in the same page query. `last_changed` is the latest `charity_updated` EVENT, falling back to CHARITY.created, so the value is never empty. The rating row stays as D-044 defined it; the three values sit below the domain/location chips, labelled "N events", "N haskamas" and "Last changed <date>". §5.3 names only the average rating, so these are additions to the doc's list, not replacements.
- Why: sorting by trending, most popular, most haskamos or most recently updated reorders the list, but the cards showed none of those numbers, so a reader could not check the order and two charities with equal counts were indistinguishable from a bug. Showing all three, rather than only the one being ordered by, keeps the card stable while the reader changes the sort and lets them compare the values that place a charity. The cost is two extra subqueries per page row (event count and latest update) plus the haskama count the page now always aggregates; the pagination `COUNT` still reads none of them.
- Where in code: `apps/charities/contracts.py` (`ActivitySummary`, `CharityCard.activity`), `apps/charities/repositories.py` (`_with_activity_values`, `_narrowed`, `_to_card`), `apps/charities/templates/charities/listing.html`, `static/css/site.css` (`.charity-card__activity`), `tests/unit/test_repositories.py`, `tests/unit/test_template_contract.py`

---

## D-052: Every save of a charity goes through a service and records `charity_updated`

- Date: 2026-11-15
- Decided by: CEO (Yosef), on the sort-branch audit
- Status: Active (resolves the open question of 2026-11-14; extends D-039)
- Design doc ref: §6.1, §5.2.17, §5.2.21, §6.2.5
- Decision: Any save that changes a charity — an approved edit, an owner edit, an admin form save, a publish or a hide — records one EVENT with action `charity_updated` and the acting user, in the same transaction as the change. Field saves go through `charities.services.update_charity`, which accepts only `EDITABLE_FIELDS` (`name`, `tagline`, `description`, `image`), locks the row, writes only the fields that actually differ, and records one event; it is the one door for a future edit flow. `is_visible` stays outside it and changes only through `publish_charity`/`hide_charity` (D-038, D-039). Creating a charity is not a change, so it records no event, the same as the factories and the seed (D-022). A save with no change writes nothing and records nothing (D-041). The Django admin's change form now routes its scalar edits through `update_charity`, so it no longer bypasses the event trail.
- Why: D-048's "most recently updated" order and §5.2.21's derived date read the latest `charity_updated` EVENT, and nothing else — charities cannot read EDIT_REQUEST (D-006). The audit's issue #10 asked only about approved edits, but confirming that alone would still leave admin and owner saves invisible to the order. Making every save use one service gives the later edit flow a single, audited write path instead of a rule it has to remember.
- Known gap: a change to a charity's domains or locations through the admin form's multi-selects still saves without an event, because those rows are written by the through tables after `save_model`. The edit-request flow (§5.2.8) is field-based, so no product path does this today; it is filed as a task for the edit-flow work, together with whether `update_charity` should accept membership changes.
- Where in code: `apps/charities/services.py` (`EDITABLE_FIELDS`, `update_charity`, `_set_visible`), `apps/charities/admin.py` (`CharityAdmin.save_model`), `tests/unit/test_charity_services.py`, `tests/integration/test_charity_admin.py`

---

## D-053: A changed sort dropdown applies at once, and Enter takes the same path

- Date: 2026-11-15
- Decided by: CEO (Yosef), on the sort-branch audit
- Status: Active (amends D-048's dropdown paragraph)
- Design doc ref: §6.2.5 (Sort — SRS FR 3)
- Decision: The sort form carries `data-sort-form`, and `static/js/sort.js` submits it both on `change` and on Enter in the dropdown. Both paths call `form.submit()` with no submitter, so no `direction` value is sent and the server uses the chosen mechanism's default direction. The inline `onchange` handler is gone. With JavaScript off, the form still works as before: the visitor picks a mechanism and clicks a direction button, while Enter in the dropdown would still take the first button (ascending) — that fallback is inherent to the form's button order and is not worth a hidden control.
- Why: the dropdown alone submitted nothing, so picking a mechanism looked broken until the visitor also clicked the highlighted "current" direction; and Enter in a `<select>` activates the first submit button, giving trending, popularity, rating, haskamos, newest and updated ascending — the opposite of their documented default. §6.2.5 only requires the dropdown and two direction buttons, so a small script on the existing controls fits the doc; `form.submit()` rather than an Apply button keeps the control at two parts.
- Where in code: `apps/charities/templates/charities/sort.html`, `static/js/sort.js`, `tests/unit/test_template_contract.py`

---

## D-054: The listing search: a `q` term with two advanced options, over name and tagline

- Date: 2026-11-17
- Decided by: builder, pending CEO/COO confirmation
- Status: Active
- Design doc ref: §6.2.6 (Search — SRS FR 4), §6.2.2 (signup search), UC-03 (§8.5)
- Decision: The listing's search is a `Search` value — a term plus the advanced options that shape how it is matched — read from the URL and passed to `charities.services.list_charities(repository, filters, sort, page, page_size, search)`. §6.2.6 fixes that there is a bar, a submit, advanced options, and that page 1 is shown with filters and sort still on, but it names neither the URL parameters nor the matching rules, so those are settled here:
  - The URL is `?q=<term>` plus one parameter per option, `whole_words=1` and `tagline=1`. `q` is the conventional short search parameter; the options are named for what they switch on. Exactly two options are built, the two §6.2.6 names as examples: matching whole words only, and searching the tagline as well as the name. Adding one is one entry in the `OPTIONS` table in `apps/charities/search.py`.
  - The term is matched against the name, case-insensitively, as a substring (`icontains`), which is §6.2.2's "searches the name column" and UC-03's "case-insensitive search". §6.2.6's "searching in the tagline" adds the tagline to the fields searched, OR-ed with the name, so a charity is kept when either column matches; it does not replace the name.
  - "Full words only" matches the term as one contiguous piece of text bounded by word boundaries (`iregex` with `\y...\y`, the term escaped so it is text, not a pattern). A multi-word term has to appear as typed, in that order; the doc says nothing about tokenizing, and splitting the term would make an address's meaning harder to predict. A term that is blank or only whitespace is no search at all: the listing shows every charity, and the options are dropped with it, since they cannot narrow anything.
  - The default search stays off the tagline, so an empty advanced panel and a plain term mean the same address today and after more options are added.
  - Search and the six filter groups AND together (a search does not clear the filters), and page 1 of a search is shown because the search bar form sends no `page`; a URL with an explicit `page` still keeps it, the same rule as the filter and sort forms (D-045, D-048, N5). Every other control on the page — the sort form, the filter form, the pagination links, the page-size form, the jump form and the Clear-filters link — carries the search as hidden inputs or query pairs, so none of them can silently drop the term. The search bar itself carries the filters and the sort, so a search does not silently reorder or unfilter.
  - The advanced options sit behind a `<details>` toggle that opens when one is on, the same no-JavaScript pattern the filter sidebar uses, so the visitor can see why the results are narrowed differently than the term alone would explain.
  - Nothing-found is its own message, following §6.2.6: "No charities match that search." when only the search is on, "No charities match that search and those filters." when both narrow, keeping the two older messages (N6) for filters-only and for an empty database.
- Why: §6.2.6 names the behaviour but leaves the URL, the matched columns and the meaning of "full words" unstated, and the URL is expensive to change once links are shared. The choices make the search read the same columns the listing displays, keep the doc's "filters and sort remain on" literally true, and fit the existing controls' protocol — every form on the page replays the whole view state, and only a deliberate control change resets the page.
- Where in code: `apps/charities/search.py`, `apps/charities/services.py` (`list_charities`, `Page.search_pairs`), `apps/charities/repositories.py` (`_search_condition`), `apps/charities/views.py`, `apps/charities/templates/charities/{search,search_state,listing,filters,sort,state}.html`, `static/css/site.css` (`.search`), `tests/unit/test_search.py`, `tests/unit/test_search_repository.py`, `tests/unit/test_services.py`, `tests/unit/test_views.py`

---

## D-055: Schema audit corrections (review uniqueness, listing indexes, ledger rules, batch index)

- Date: 2026-11-17
- Decided by: Platform Lead (schema and platform owner), applying `docs/AUDIT-2026-11-17.md` (D1–D4, D6)
- Status: Active
- Design doc ref: §5.2.15, §8.6, UC-05, §5.2.18, §5.2.5, §7.1.6
- Decision: Four schema changes, all enforced by constraints so no writer can drift:
  - REVIEW gets a unique `(charity, author)` constraint, closing the open question of 2026-11-13: the reviewer form still blocks duplicates in its service, but the database now forbids them too, so a second review of the same charity by the same member is impossible no matter which writer lands first. No cleanup migration was needed: no production data exists, and the seed and factories never create a duplicate.
  - CHARITY gets btree indexes on `(name, id)` and `(created)`, the two columns every listing page orders by (the default alphabetical order, and the `newest` order, D-048). Both orders were sequential scans with a top-N sort even for a limit-20 read.
  - TRANSACTION.amount must be greater than zero (check constraint), and TRANSACTION.date is required and defaults to today. A maaser ledger has no zero or negative amounts, and a ledger line without a date cannot be ordered or totalled per period.
  - APPROVAL_REQUEST gets a `(batch_id, status)` index, the lookup §7.1.6's batch queue uses, replacing the per-request batches the seed used to create. The seed now batches its requests ~10 per shared `batch_id`, so the queue screen has real batches to decide in dev.
- Why: Each is a rule the doc states or implies but the schema did not enforce, and all four get more expensive to apply once rows exist.
- Where in code: `apps/charities/models.py` (`Review.Meta.constraints`, `Charity.Meta.indexes`), `apps/approvals/models.py` (`ApprovalRequest.Meta.indexes`), `apps/tools/models.py` (`Transaction.amount`, `Transaction.date`), `apps/dashboards/management/commands/seed.py` (`BATCH_SIZE`), migrations `charities/0002_*`, `approvals/0002_*`, `tools/0002_*`, `tests/unit/test_models.py`

## D-056: Charity writes: cleared fields are NULL, and an image is only what the card can render

- Date: 2026-11-17
- Decided by: Platform Lead, applying `docs/AUDIT-2026-11-17.md` (B2, B7, B8, D5, B4, B5, B6, B9)
- Status: Active
- Design doc ref: §5.2.9 (CHARITY), §6.2.14 (charity addition), §6.2.4 (filter), §6.2.6 (search)
- Decision: The charity write and read edges now enforce these rules:
  - A cleared optional field is stored as `NULL`, never as `""`. `tagline`, `description` and `image` are normalised at the one door (`update_charity`) and in the admin form, so `description = ""` and `description IS NULL` cannot both mean "absent" (D-013). The seed and factories already write `NULL`.
  - `Charity.image` is validated at write time: a repo-relative path under `static/` (what D-043 seeds) or an absolute http(s) URL whose host is listed in the new `CHARITY_IMAGE_HOSTS` setting. Anything else is refused, and the template re-checks with one filter so a row written before the rule cannot load an arbitrary third-party image or a path that escapes `static/`. The default allowlist is empty (repo paths only); a host entry starting with `.` allows subdomains.
  - The admin's add form publishes the charity it creates (D-038: an admin-added charity is already approved). Its approval record still needs `approvals.services.submit_new_charity`, which charities may not call under D-006, so it is filed as work for the approvals queue rather than reached across the app boundary.
  - The admin's change form refuses to save a changed field that `update_charity` does not apply, instead of reporting success while dropping the value.
  - Every numeric filter group is clamped into the bounds its meaning allows (a count cannot be negative), and the sidebar's correction note is built from that group's own bounds instead of always describing the star scale.
  - A search term longer than 100 characters is dropped, like a junk `page`, so an over-long URL cannot become a huge `ILIKE` pattern. A repeated `q` explicitly keeps the last value.
- Why: Each was a place where the code accepted a value it could not honour, or stored two encodings of "absent". Validating at the write edge keeps the template, the filters and the future edit flow reading one meaning.
- Where in code: `apps/charities/services.py` (`NULLABLE_FIELDS`, `validate_image`, `_clean_value`, `update_charity`), `apps/charities/admin.py` (`save_model`, `CharityAdminUnappliedFieldError`), `apps/charities/templatetags/charity_images.py`, `apps/charities/filters.py` (`CLAMPS`, `clamp_number`, `_adjusted_note`), `apps/charities/search.py` (`MAX_TERM_LENGTH`, `from_query`), `apps/events/services.py` (`record_event`), `config/settings/base.py` (`CHARITY_IMAGE_HOSTS`), `.env.example`

## D-057: The charity page is `/charity/<id>/`; it writes the events popularity reads; hidden history counts for nothing

- Date: 2026-11-17
- Decided by: Platform Lead, applying `docs/AUDIT-2026-11-17.md` (M3, M4, M9, DOC3, A1)
- Status: Active
- Design doc ref: §6.2.7 (charity page), §5.2.21 (visit/clicks), §6.2.10 (member history)
- Decision: Three decisions the audit forced to be made before this page was built:
  - The charity page is `/charity/<id>/`, as CLAUDE.md already stated and D-009's prefix rule supports. §6.2.7's bare `/charity_id/` was ambiguous; the listing coupon now links here, so the `href="#"` cards are gone. It also has a counted outbound-link route `/charity/<id>/link/<link_id>/` that records a `link_click` EVENT and redirects (only http(s) targets), so "popularity" stops reading only seeded rows.
  - The page records a `view` EVENT for every visit, attributed to the signed-in user or `NULL` for a visitor (§5.2.17 allows both). This is the lowest-cost way to give §5.2.21's visit count and D-048's `popular`/`trending` orders real traffic; the listing page does not write views, because showing 20 cards is not 20 visits.
  - An EVENT the member hid from their own history (D-060, previously `hidden_by_user`) counts for nothing: the listing's event count, the `popular` order and the `trending` score all filter it out. Hiding is a statement that an event should not be remembered, so it must not quietly keep moving a charity up the ranking. `last_changed` is unaffected, since `charity_updated` events are never hidden.
- Why: The page was the largest missing feature the audit named (M3), and its details (the URL, what events it writes, whether hidden rows count) were all open. Building the page without deciding them would have shipped dead links and noise-driven orders.
- Where in code: `apps/charities/urls.py` (`detail`, `link`), `apps/charities/views.py` (`detail`, `link_redirect`), `apps/charities/services.py` (`get_charity_page`, `get_link_url`), `apps/charities/repositories.py` (`detail`, `link_url`, `CharityPage`), `apps/charities/templates/charities/detail.html`, `apps/charities/contracts.py` (`CharityPage`), `apps/events/services.py` (`event_count`, `trending_score`), `tests/unit/test_charity_page.py`, `tests/unit/test_repositories.py`

## D-058: The Haskamos group is fed by `accounts.services.search_rabbis`

- Date: 2026-11-17
- Decided by: Platform Lead, applying `docs/AUDIT-2026-11-17.md` (M6)
- Status: Active (resolves the open question of 2026-11-13; completes D-045's sub-decision)
- Design doc ref: §6.2.4 (Filter), §5.2.3 (RABBI_PROFILE)
- Decision: `accounts.services.search_rabbis` now exists, so the Haskamos filter finally has an option list (M6). It returns every rabbi with a profile, optionally narrowed by a term against the display name and the account name, as `RabbiIdentity(user_id, display_name, title)` — the same identities the charity page uses for haskama attribution. The filter's option ids are **user** ids (D-045, audit Q3), and the sidebar's "Rabbi search is not available yet" note is gone.
- Why: The group was the only filter a visitor could see that could not work; the empty-note that said so was a placeholder for this service, and this entry clears it.
- Where in code: `apps/accounts/services.py` (`search_rabbis`, `RabbiIdentity`), `apps/charities/repositories.py` (`DjangoFilterOptionsRepository.rabbis`), `apps/charities/filters.py` (`EMPTY_NOTES`), `tests/unit/test_charity_page.py` (`RabbiOptionsTest`)

## D-059: The listing only publishes once; the detail page hides what the flag hides

- Date: 2026-11-17
- Decided by: Platform Lead, applying `docs/AUDIT-2026-11-17.md` (M5, Q2)
- Status: Active
- Design doc ref: §5.2.1 (CHARITY.is_visible), D-042, D-038
- Decision: `is_visible` is now enforced at read time wherever a repository is told to publish only (listing rows and the charity page both filter it; D-042's flip is a view flag, D-038's switch is the column). Nothing in the app publishes yet because the approval queue that drives publication is Phase 1; until then the views pass `published_only=False` on purpose, so the listing stays the whole dataset as Phase 0 has always shown it. Q2's answer: when the flag flips, filters, search and sort read *published* charities only, because D-042's wording is about what a visitor may see, not a separate analytics channel; if the dashboards ever need hidden-charity numbers they will read them through their own (approvals-side) queries.
- Why: The audit listed M5 because enforcement lived only in comments. Wiring it now, while the flag still reads False, is the cheap version; the alternative — a fourth read path that special-cases hidden charities — is exactly the divergence D-038 exists to prevent.
- Where in code: `apps/charities/repositories.py` (`_rows`, `detail`), `apps/charities/views.py` (`published_only`)

## D-060: The nav advertises only shipped pages; error pages are first-class templates

- Date: 2026-11-17
- Decided by: Platform Lead, applying `docs/AUDIT-2026-11-17.md` (B1, S4, M8, A1, A3, SEC2)
- Status: Active
- Design doc ref: §7.2 (nav), D-026, D-027, D-035 (error pages deferred to Phase 1)
- Decision: The nav is built by a context processor (`apps/support/context_processors.nav`) that resolves URL *patterns* and renders a link only for a page that exists. Posting `/accounts/logout/` is a form while that route exists and nothing otherwise. The `<h2>`-before-`<h1>` heading order was fixed in the listing templates, cards got names (A3), a skip link targets `<main id="main">`, and the nav carries `aria-label="Main"`. 403/404/500 templates extend `base.html`. The `hx-headers` CSRF attribute is gone until an HTMX interaction needs it (SEC2).
- Why: A nav link is a promise; the old bar made eight promises to seven 404s, and no test could see it because the tests asserted the same literals. Building links from patterns makes a renamed route fail loudly at render time instead of surfacing later as a dead link, and the context processor keeps that honest without hand-maintained URL lists in templates.
- Where in code: `templates/base.html`, `apps/support/context_processors.py`, `templates/{403,404,500}.html`, `tests/integration/test_base_template.py`

## D-061: Performance budget for the listing: cached option lists, deferred HTMX, manifest assets, first/last pagination

- Date: 2026-11-17
- Decided by: Platform Lead, applying `docs/AUDIT-2026-11-17.md` (P1, P2, P3, P5, B3)
- Status: Active
- Design doc ref: §6.2.x (listing), D-026
- Decision: (P1) The domain and location option lists are cached for 60 seconds per process (LocMem); a new option appears to an admin within a minute, and a busy directory stops reading two full tables per request. (P2) HTMX is `defer`red. (P3) Production uses `ManifestStaticFilesStorage`, so assets get versioned names and deploys bust caches; deploys must run `collectstatic` (Caddy serves `STATIC_ROOT`, already the prod story). (P5) Pagination gained first/last jump links when far from an edge, a charities count above the list, and the count is skipped for pages beyond the obvious bound (B3's one-snapshot page+count). No page size, TTL or query strategy beyond this until a load test says otherwise (D-025).
- Why: The audit measured six queries on every listing request and a render-blocking 50 KB script. Each fix is a one-line decision point (TTL, defer, storage backend, jump threshold of 3) that is cheap to revisit.
- Where in code: `config/settings/base.py` (CACHES), `config/settings/prod.py` (STORAGES), `apps/charities/repositories.py` (option cache), `apps/charities/services.py` (`Page` jump properties), `apps/charities/templates/charities/listing.html`, `templates/base.html`

## D-062: Production ships a CSP and HSTS preload; the seed admin password is never public

- Date: 2026-11-17
- Decided by: Platform Lead, applying `docs/AUDIT-2026-11-17.md` (SEC1, SEC4)*
- Status: Active
- Design doc ref: §4.12 (security)
- Decision: (SEC1) Production serves `Content-Security-Policy: default-src 'self'; img-src 'self' https:; base-uri 'none'; form-action 'self'; frame-ancestors 'none'` from a middleware, except on `/django-admin/` paths where the admin's inline styles would be blocked; HSTS max-age defaults to one year and preload is on, because a sub-year max-age with preload would be refused by the preload list. Both are env-overridable (`CONTENT_SECURITY_POLICY`, `DJANGO_SECURE_HSTS_SECONDS`). (SEC4) `manage.py seed` no longer creates `admin`/`admin`; it generates a random password (printed once), or honours `ADMIN_SEED_PASSWORD`. The other dev users keep `password` (factories are dev tooling, D-022).
- Why: Preload is a commitment (hard to leave) and CSP is a runtime header — both should be decided, not accidental. The seed already refuses non-empty databases (D-030), but a known default *admin* credential is the one thing D-030 cannot defend if both guards ever fail.
- Where in code: `apps/support/middleware.py`, `config/settings/prod.py`, `apps/dashboards/management/commands/seed.py`, `config/settings/base.py` (`ADMIN_SEED_PASSWORD`)

## D-063: django-auditlog leaves the app until a model actually registers

- Date: 2026-11-17
- Decided by: Platform Lead, applying `docs/AUDIT-2026-11-17.md` (S9), resolving the open question of 2026-11-11
- Status: Active (resolves the 2026-11-11 "Which models get audit logging?" open question)
- Design doc ref: §4.15.1.2, D-052, D-039
- Decision: django-auditlog is removed from the dependency list, `INSTALLED_APPS` and `MIDDLEWARE`. The open question stays open in substance — which models get audit logging, deferred to Phase 1 — but a package that creates tables on every migration and wraps every request must earn its place by actually registering one. When Phase 1 registers CHARITY (D-052's note: the events trail says who/when; auditlog would add which fields changed), the package returns with a one-line `register`, which is the reversal cost.
- Why: No registered model means not one row will ever be written; the cost (migration surface, per-request middleware) was being paid for a plan.
- Where in code: `pyproject.toml`, `config/settings/base.py`

## D-064: Small cleanliness items from the audit: loggers, protocols, one brand colour, honest factory defaults

- Date: 2026-11-17
- Decided by: Platform Lead, applying `docs/AUDIT-2026-11-17.md` (S2, S3, S5, S6, S8, A2, A4, M6)
- Status: Active
- Decision: (S2) `seed.py` imports `tests` lazily inside the command, so a production artifact that ships `apps/` only still imports cleanly; the command stays dev-only (D-022, D-030 documents it). (S3) The service layers now have module loggers and log the error paths that used to swallow. (S5) `FilterOptionsRepository` is a `Protocol`, and the sidebar's service functions are typed with it. (S6) The two near-identical brand blues became one `--brand-blue` custom property and the duplicate `.jump__input` rule is gone. (S8) `ReviewFactory.rating` and `HaskamaFactory.importance` default to fixed values. (A2) Disabled pagination steps are dimmed `<span>`s again — no `aria-disabled` on a thing nothing can focus. (A4) One `:focus-visible` rule site-wide, with a white ring on the blue current states.
- Why: Each is the root fix the audit named — the seed's import is now after its guards, the loggers exist before the first production 500, the protocol matches the listing's, the stylesheet cannot drift into two blues, and a factory default of "random" stopped being a flaky-test landmine.
- Where in code: `apps/charities/{services,repositories}.py`, `apps/events/services.py`, `apps/dashboards/management/commands/seed.py`, `static/css/site.css`, `tests/factories/charities.py`

## D-065: `django-admin/`'s login is accepted without a lockout, for now

- Date: 2026-11-17
- Decided by: Platform Lead, applying `docs/AUDIT-2026-11-17.md` (SEC3)
- Status: Active (accepted risk, revisit with the accounts login branch)
- Design doc ref: §4.12, D-008
- Decision: `/django-admin/` keeps Django's own login and gets no rate limiting or account lockout in Phase 0. What protects it is that it is staff-only (`is_staff`), reachable only behind D-008's deliberate URL, and that no staff account exists in production until one is created by hand. The rate-limit middleware the accounts login branch brings (`D-YOSEF-accounts-login`) must also cover `django-admin/login/`, at which point this entry is superseded rather than kept.
- Why: The audit's alternative was "cover it in the same middleware or document that staff-only access makes it acceptable". There is no middleware here to cover it with, and inventing a second, weaker throttle for one URL ahead of the real one is the kind of divergence D-038 exists to prevent. Recording the risk with the trigger that closes it is the honest option.
- Where in code: `config/urls.py` (the `/django-admin/` route), `config/settings/base.py` (auth backends unchanged)

## D-066: Tests measure coverage on every run; three CSS tests read the stylesheet through a parser

- Date: 2026-11-17
- Decided by: Platform Lead, applying `docs/AUDIT-2026-11-17.md` (T1, T2, T3)
- Status: Active
- Decision: (T1) `pytest` now measures coverage of `apps/` and `config/` on every run and fails below 85%; the current figure is ~93%, so the gate is a floor, not a target, and it is edited in `pyproject.toml`, not in CI. `*/migrations/*` is excluded because generated code is not behaviour. (T2) The three tests that grepped `site.css` with a regex now resolve a property for a selector through `tests/support/css.py`, which merges blocks in source order, ignores at-rules it cannot evaluate, and ignores comments; the sidebar test also asserts the class is on the rendered page. Media queries and specificity are still not evaluated — a DOM measurement is the only full check, and there is no browser in the test suite. (T3) `tests/unit/test_views.py` is split into five files by feature, with the old path left as a docstring that says where each went.
- Why: An unmeasured suite answers "is this path covered?" by reading; a CSS regex answers "is the rule in the file?" rather than "does it apply?"; and one 750-line test file makes a reviewer hunt. Each fix is one commit now, and expensive later.
- Where in code: `pyproject.toml` (`--cov`, `[tool.coverage.*]`), `tests/support/css.py`, `tests/unit/test_css_helper.py`, `tests/unit/test_views_{listing,sort,filter,clamp,search}.py`

## D-067: The listing's three state modules stay separate until a fourth state exists

- Date: 2026-11-17
- Decided by: Platform Lead, applying `docs/AUDIT-2026-11-17.md` (S1, S7, Q4)
- Status: Superseded by D-068 on 2026-11-17 (the trigger fired: it was the last open audit finding and the per-form test now covers the risk this entry was waiting on)
- Decision: `filters.py`, `sorting.py` and `search.py` keep their own frozen value object, `from_query`, `query_pairs`, `query_string` and form dataclass; they are not collapsed into one `PageState`. The repeated shape is real, but the three modules encode three different rules (clamping, mechanism/direction pairing, term length and advanced options), and collapsing them is a rewrite of five modules, six templates and every listing test with no behaviour change — the worst kind of change to make under an audit deadline. The trigger to revisit: a fourth URL state (a date range, or a saved search) or the first "form forgot an include" bug, whichever comes first. Q4 (accent-insensitive search) stays open: it changes `Search`, not the page state, and needs a Postgres extension decision.
- Why: The audit ranked it a Medium smell, not a defect; every other finding in this audit that *was* a defect is fixed. Recording the deferral with the trigger keeps it a decision instead of a lost note.
- Where in code: `apps/charities/{filters,sorting,search,services}.py`

## D-068: The listing's URL state is one value, `PageState` (supersedes D-067)

- Date: 2026-11-17
- Decided by: Platform Lead, on comtai#39, applying `docs/AUDIT-2026-11-17.md` (S1, S7)
- Status: Active (supersedes D-067's deferral; D-067's reasoning is kept below for the record)
- Design doc ref: §6.2.4–6.2.6 (the listing's controls), UC-03 (a shareable address)
- Decision: `apps/charities/state.py` holds the whole address as one immutable `PageState` — the search, the filters, the order, and the page/page_size window. One table (`PARTS`) states the order the parts are read in and written in; one `pairs()` / `query_string()` joins them; `Page` carries a single `state` instead of three pair-bundles stapled together by hand. One template partial (`state.html`) writes the whole result set as hidden inputs and takes a `skip` naming the slice the form owns, so the default is "everything" and forgetting is visible. The three feature modules keep their own rules (`from_query`, `query_pairs`, the clamp tables, the mechanism pairing, the term matching); they lost only their duplicate `query_string`, which was the third copy of the same `urlencode` call (S7). Page-size bounds and `page_count` moved here too, because a page size is part of the address.
- Why: D-067 deferred this as a Medium smell with a trigger. The trigger is that it was the last finding in the audit without a disposition, it is a deletion rather than an addition (218 lines added, 226 removed, excluding this entry and the new tests), and the risk it was deferred for is now covered: `EveryFormCarriesTheWholeStateTest` requests the listing and asserts, per form, which slices it carries, so a form that drops one fails loudly. Every existing page test passed unchanged, and the addresses the tests pin stayed byte-identical — the two things that would have made this refactor unsafe.
- Where in code: `apps/charities/state.py` (new), `apps/charities/services.py` (`Page`, `list_charities`), `apps/charities/views.py`, `apps/charities/templates/charities/state.html` (and the three `*_state.html` partials it replaces), `tests/unit/test_page_state.py`, `tests/unit/test_template_contract.py`

## D-069: Search stays case-insensitive and accent-sensitive

- Date: 2026-11-17
- Decided by: CEO (Yosef), answering the audit's Q4 on task #42
- Status: Active (closes the audit's Q4; supersedes nothing)
- Design doc ref: §6.2.6 (search), UC-03 ("case-insensitive search")
- Decision: The search matches case-insensitively and does **not** fold accents. No `unaccent` extension, no normalised column, no fuzzy matching. Verified against the dev database (200 charities) that every term matches the same set in all three cases in **both** search modes — "Chesed", "chesed" and "CHESED" each return the same 29 rows, whole-word included.
- Why: Nobody types accents in real life, so a reader searching "chesed" for a charity registered as "Chésed" is the unusual case, not the common one; the extension would cost a migration, defeat the `name` index (Postgres does not mark `unaccent` immutable), and buy a narrowing that real readers rarely need. If the seeded or imported data ever *does* carry accents, the cheaper fix is at the write side — normalise the name on save — not at the read side, because that keeps one spelling in the database and the search simple. That write-side change is not made here; it needs its own decision if accented names appear.
- Where in code: `apps/charities/search.py` (`lookup`, `pattern` — unchanged), `apps/charities/repositories.py` (`_search_condition` — unchanged), `tests/unit/test_search_repository.py` (`test_the_name_is_matched_case_insensitively`, `test_whole_words_is_case_insensitive_too`)

## D-070: The app checks and starts its RDS instance through the AWS API, and never waits for it inside a request

- Date: 2026-11-22
- Decided by: CEO (Yosef)
- Status: Active
- Design doc ref: §4.9 (Database Hosting, and the ~$200/year budget)
- Decision: The deployed database is the RDS instance named by `RDS_INSTANCE_ID`, and that instance is stopped whenever the site is idle. Since a stopped instance cannot answer a query about whether it is up, both questions — is it running, and start it — go through the AWS API (`DescribeDBInstances`, `StartDBInstance`) via boto3, never a shell-out to `aws rds`. A middleware (`DatabaseWakeMiddleware`) applies the answer, and it is installed only when `RDS_INSTANCE_ID` is set, so local Postgres and the test suite never call AWS. It is inserted immediately after `SecurityMiddleware` and before `SessionMiddleware`, because the session store's first act is a query. Specifics:
  - The status answer is cached: 60s for `available`, 10s for anything else, so the common case costs one API call per process per minute rather than one per request, and a page polling during a start still sees the change.
  - Only `stopped`, `starting` and `stopping` hold a request. Every other status — `available`, `backing-up`, `modifying`, and whatever RDS names next — is treated as reachable and the query is the judge. A whitelist of healthy statuses would turn an unfamiliar one into an outage the gate invented.
  - A stopped instance is started, and the visitor gets `503` with `Retry-After` and a page that reloads itself (`templates/503.html`, extending `base.html` like every other page). **The request does not wait.** Starting an instance is instance recovery and takes minutes to hours; a held Gunicorn worker is capacity lost long after the database is back, and the browser would have given up first anyway.
  - An `OperationalError` from the view re-asks AWS with the cache bypassed. If the instance is `stopped`/`starting` the request becomes the waiting page, after starting it if needed and dropping the dead connection. If the instance is `available` the error is re-raised: bad credentials, a full disk and too many connections all raise `OperationalError`, and starting an instance that is already running fixes none of them. Converting those into "still waking up" would hide a real fault behind a loop that never ends.
  - An AWS failure — denied, throttled, unreachable — fails **open** and is logged, because it says nothing about the instance and failing closed would let a credential problem take the site down by itself. A wrong identifier (`DBInstanceNotFound`) is a configuration error and raises.
  - `manage.py wake_db [--wait]` is the CLI half: `migrate`, `seed` and deploys are not requests, so this is the one place the gate blocks, and a person is watching it. It is the one caller that asks **strictly** (`RdsInstance.refresh(strict=True)`): a request has the query behind it as the real judge, but a command that printed `available` because its `DescribeDBInstances` was denied would hand the operator a connection timeout as the next thing they see, so an unreadable status is a `CommandError` naming the setting to check.
  - `DATABASES["default"]` gains `connect_timeout=5` and `CONN_HEALTH_CHECKS=True`: a stopped instance ignores a connection rather than refusing it, so an untimed connect hangs a worker, and a `CONN_MAX_AGE` socket that died when the instance stopped would otherwise fail the first request after a wake-up.
- Why: The budget is about $200 a year and an RDS instance billed by the hour is most of it, so the database cannot run when nobody is looking; §4.9 already puts the host on a developer's laptop, which leaves the application as the only component present to start it. The design constraint fixes that the check and the start use the AWS API. What this entry settles is the part the constraint leaves open: the waiting belongs in a command and a self-reloading page, not in a request, and "the database is down" has to be decided by the AWS status rather than by any error that happens to be an `OperationalError`. It lives in support because §6.1's nine apps are fixed (a tenth is a stack change), support depends on nothing, and the CSP middleware is already there (D-062).
- Where in code: `apps/support/rds.py` (`RdsInstance`), `apps/support/middleware.py` (`DatabaseWakeMiddleware`), `apps/support/management/commands/wake_db.py`, `templates/503.html`, `templates/base.html` (`extra_head`), `config/settings/base.py` (`RDS_INSTANCE_ID`, `AWS_REGION`, `DATABASE_WAKE_*`, the `DATABASES` options and the `MIDDLEWARE` insert), `tests/unit/test_rds_wake.py`, `tests/unit/test_database_wake.py`, `tests/unit/test_wake_db_command.py`, `tests/unit/test_database_settings.py`

## D-071: The dev seed uses real charities and never fabricates reviews or haskamas

- Date: 2026-11-22
- Decided by: CEO (Yosef)
- Status: Active
- Design doc ref: D-030 (dev seed), D-049 (no repeated names), D-043 (repo-local images)
- Decision: `manage.py seed` draws its charities from a curated `REAL_CHARITIES` list rather than generated name pairs. Names, taglines, causes, locations and about/donate links are taken from each organization's own site or a charity registry; users and view/click events are still generated, but reviews and haskamas are not. A fabricated review or rabbinic endorsement of a named real organization is a false statement about that organization, not harmless demo data. The list is dev seed data, not a vetted guide for donors.
- Why: The original seed produced plausible-looking but invented charities and endorsement links. Once the directory shows real organizations, the same generated endorsements attach a donor's name or a rabbi's approval to a real party who never gave it. Keeping the rest of the generated activity preserves the listing, filter, trending and admin-queue demos without asserting anything untrue about a named charity.
- Where in code: `apps/dashboards/management/commands/seed.py` (`REAL_CHARITIES`, `SeedCharity`, `seed()`), `tests/integration/test_seed.py`

## Open questions

- **2026-11-11: Which models get audit logging?** django-auditlog is installed (§4.15.1.2), but no models are registered with it. Deferred to Phase 1. Resolved on 2026-11-17 as D-063: the package is out of the app until a model registers; the question of *which* models remains Phase 1.
- **2026-11-11: Default charity listing order.** §6.2.3 says alphabetical; UC-03 (§8.5) says "no particular order". Resolved as D-048 on 2026-11-14: alphabetical A→Z is the default sort.
- **2026-11-12: How the charities listing learns visibility without depending on approvals.** D-023 makes visibility depend on approvals' tables, but §6.1 has approvals depending on charities, not the reverse, and D-006 limits calls to listed dependencies. To be decided before the Phase 1 listing. Resolved as D-038 on 2026-11-12.
- **2026-11-11: Email verification method.** §6.2.2 has the user type a code from an email; UC-02 (§8.4) uses a link. Resolved as D-YOSEF-member-signup on 2026-11-15 (typed code).
- **2026-11-12: One LINK per kind per charity?** §5.2.14 does not say, but EDIT_REQUEST.field (§5.2.8) has one `website_donate`/`website_about`/`website_contact` value with a single new_value, which implies one link per kind. `Link` has no (charity, kind) uniqueness. Adding it after data exists needs a cleanup migration, so decide before Phase 1 writes links. Resolved as D-036 on 2026-11-12.
- **2026-11-12: Is the nav sticky?** §7.2 says the nav tab is "always visible": on every page (done, through `base.html`), or also fixed while scrolling (not done). Cheap either way. Resolved as D-037 on 2026-11-12.
- **2026-11-13: Where is "one review per member per charity" enforced?** §8.6 and UC-05 say a member has one review per charity, but REVIEW has no unique (charity, author) constraint and `save_review` does not exist yet. Options: enforce it only in the upsert service, or add a unique constraint too (a schema change, so decide before the review form lands). See `docs/NOTES.md` N1. **Half answered on 2026-11-17 as D-055:** the database now enforces it (`review_charity_author_uniq`), so the "only in the service" option is gone. What is still open is the second half — when a member submits a review for a charity they already reviewed, does `save_review` **overwrite** their review (the reading of UC-05's "edit your review") or **refuse** with a message? To be decided when the review form is built; filed as comtai#12.
- **2026-11-13: Default statuses for APPROVAL_REQUEST and TICKET?** The doc (§5.2.5, §5.2.19) gives no default; the models default `ApprovalRequest.status` to `pending` and `Ticket.status` to `not_responded`. Those defaults are the only choices nobody has confirmed.
- **2026-11-13: Can users pick a rabbi in the listing filter yet?** §6.2.4 makes `haskama_rabbi` repeatable by rabbi and names `accounts.services.search_rabbis`, which does not exist. The filter is wired end to end but its option list is empty, so it matches nothing. Resolved as D-045 (sub-decision) on 2026-11-13; it becomes usable when `search_rabbis` lands. Resolved as D-058 on 2026-11-17: `search_rabbis` exists.
- **2026-11-14: Should an approved edit record a `charity_updated` EVENT?** D-048 orders "most recently updated" by the latest `charity_updated` EVENT, because §6.1 does not let charities read EDIT_REQUEST. Nothing applies edits yet. When the edit/approval flow lands it must record that event through charities' service, or this order will ignore edits. Asked because it is a rule the later flow has to keep. Resolved as D-052 on 2026-11-15: every save records it, not only approved edits.
