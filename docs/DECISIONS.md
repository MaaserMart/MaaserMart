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

---

## Open questions

- **2026-11-11: Which models get audit logging?** django-auditlog is installed (§4.15.1.2), but no models are registered with it. Deferred to Phase 1.
- **2026-11-11: Default charity listing order.** §6.2.3 says alphabetical; UC-03 (§8.5) says "no particular order".
- **2026-11-11: Email verification method.** §6.2.2 has the user type a code from an email; UC-02 (§8.4) uses a link.
