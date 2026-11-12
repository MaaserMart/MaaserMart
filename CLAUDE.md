# MaaserMart project rules

MaaserMart is a Django modular monolith: DTL templates, HTMX + Alpine, PostgreSQL, Celery + SQS, SES, Caddy, Gunicorn. The stack is fixed by the design doc. Do not change it.

## Sources of truth
- Decisions that override or fill gaps in the design doc are in docs/DECISIONS.md. Check it before following the doc.
- If docs/design/INDEX.md exists (locally at /Users/yosefwolf/Desktop/MaaserMart/docs/design/INDEX.md), read it and open only the sections it lists for your piece. Never read the full design doc.

## Architecture
- The nine apps live in `apps/`: accounts, charities, events, approvals, support, tools, recommendations, chatbot, dashboards (design doc §6.1).
- Apps talk to each other only through their `services.py`. Never import another app's models or query its tables. Foreign keys to another app's models use string labels (`"charities.Charity"`). Only call apps that §6.1 lists as dependencies. (D-006)
- Exception: test factories (`tests/factories/`) and the dev seed command may create any app's rows directly. They are dev tooling, never runtime code.
- Each app owns its URLs under its own prefix, with hyphens: `/accounts/...`, `/charity/<id>/`, `/charity/add/`, `/dashboard/`, `/admin/approvals/`, `/admin/tickets/`. Django's own admin is at `/django-admin/`. (D-008, D-009)
- Files grow into packages when they get big: `services.py` becomes `services/`, `views.py` becomes `views/`, and so on.
- Times are UTC (D-010).

## Database and migrations
- Only the Platform Lead creates migrations. If you need a schema change, ask for it; don't run `makemigrations` yourself. (D-007)
- Migrations are never edited after they are merged to `main`.

## Git
- Small feature branches cut from `main`, merged by PR with passing CI. Never commit to `main`. (D-011)
- Anything out of scope goes into your report, not into the branch.
- From Phase 1 onward, every commit is meaningful and single-purpose (D-012). A commit that applies a decision names its ID, e.g. "Make CHARITY.created required (D-017)".
- When a CEO decision changes code, add its D-entry to docs/DECISIONS.md in the same commit.
