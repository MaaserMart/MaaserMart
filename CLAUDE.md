# MaaserMart project rules

MaaserMart is a Django modular monolith: DTL templates, HTMX + Alpine, PostgreSQL, Celery + SQS, SES, Caddy, Gunicorn. The design doc fixes this stack. Do not change it.

## Sources of truth
- Decisions that override or fill gaps in the design doc are in docs/DECISIONS.md. Check it before following the doc.
- If `docs/design/INDEX.md` exists (local only, git-ignored), read it and open only the sections it lists for your piece. Never read the full design doc.

## Building
- Bare minimum, as long as changing it later is easy (D-025). Leave out whatever is cheap to add later. Never cut corners on schema shape, app boundaries, URL structure, settings and secrets, auth, or migration history.
- Every report includes "Shortcuts taken that would be costly to reverse: none / <list>".
- If you see something, say something (D-031). Never drop a finding because it is out of scope or you can't verify it. Report unverified items as questions.

## Layout
- `config/`: settings (`config/settings/{base,local,test,prod}.py`, with secrets from env vars only), root URLs, WSGI, Celery.
- `apps/`: the nine apps from design doc §6.1 (accounts, charities, events, approvals, support, tools, recommendations, chatbot, dashboards).
- `templates/base.html`: the nav bar. Every page extends it. HTMX and Alpine are served from `static/vendor/`, never a CDN (D-029).
- `tests/unit/`, `tests/integration/`, `tests/factories/` (shared factory_boy factories).

## App boundaries
- Apps talk to each other only through their `services.py`. Never import another app's models or query its tables. Foreign keys to another app's models use string labels (`"charities.Charity"`) and `related_name="+"`; they are schema-only and may point either way (D-034). Only call the apps that §6.1 lists as dependencies. (D-006)
- Exception: test factories and the dev seed command (`apps/dashboards/management/commands/seed.py`) may create any app's rows directly. They are dev tooling, never runtime code. (D-022)
- Files grow into packages when they get big: `services.py` becomes `services/`, `views.py` becomes `views/`, and so on.

## URLs
- Hyphens, and each app's pages live under the app's own prefix (D-009, D-026, D-027):
  - accounts: `/accounts/login/`, `/accounts/signup/`, `/accounts/logout/`
  - charities: `/charity/` (listing), `/charity/<id>/`, `/charity/add/`
  - dashboards: `/dashboard/`
  - tools: `/tools/`, `/tools/income/`, `/tools/donations/`, `/tools/maaser/`
  - support: `/support/help/`, `/support/report/`
  - approvals: `/admin/approvals/`
  - support (admin): `/admin/tickets/`
- Django's own admin is at `/django-admin/` (D-008). `/` will redirect to `/charity/` once the listing exists (D-028).
- Times are UTC (D-010).

## Database and migrations
- Only the Platform Lead creates migrations. If you need a schema change, ask for it; don't run `makemigrations` yourself. (D-007)
- A migration is never edited after it is merged to `main`.

## Git
- Small feature branches cut from `main`, merged by PR with passing CI. Never commit to `main`. (D-011)
- Anything out of scope goes into your report, not into the branch.
- Commit policy (D-012):
  - During Phase 0 only, commits need not be single-purpose.
  - That exception ends when Phase 1 starts. From then on, every commit is meaningful and single-purpose.
- A commit that applies a decision names its ID, e.g. "Make CHARITY.created required (D-017)".
- When a decision changes code, add its D-entry to docs/DECISIONS.md in the same commit.

## Before you push
```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
```
