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

---

## Open questions

- **2026-11-11: Which models get audit logging?** django-auditlog is installed (§4.15.1.2), but no models are registered with it. Deferred to Phase 1.
- **2026-11-11: Default charity listing order.** §6.2.3 says alphabetical; UC-03 (§8.5) says "no particular order".
- **2026-11-12: How the charities listing learns visibility without depending on approvals.** D-023 makes visibility depend on approvals' tables, but §6.1 has approvals depending on charities, not the reverse, and D-006 limits calls to listed dependencies. To be decided before the Phase 1 listing. Resolved as D-038 on 2026-11-12.
- **2026-11-11: Email verification method.** §6.2.2 has the user type a code from an email; UC-02 (§8.4) uses a link.
- **2026-11-12: One LINK per kind per charity?** §5.2.14 does not say, but EDIT_REQUEST.field (§5.2.8) has one `website_donate`/`website_about`/`website_contact` value with a single new_value, which implies one link per kind. `Link` has no (charity, kind) uniqueness. Adding it after data exists needs a cleanup migration, so decide before Phase 1 writes links. Resolved as D-036 on 2026-11-12.
- **2026-11-12: Is the nav sticky?** §7.2 says the nav tab is "always visible": on every page (done, through `base.html`), or also fixed while scrolling (not done). Cheap either way. Resolved as D-037 on 2026-11-12.
