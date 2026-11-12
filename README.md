# MaaserMart
Repo for MaaserMart.
See MaaserMart.com.
See Hosting info at: https://ap.www.namecheap.com/domains/domaincontrolpanel/maasermart.com/advancedns

## Developer setup (Phase 0, work in progress)

Full instructions arrive with the Phase 0 README step. The short version:

1. Install [uv](https://docs.astral.sh/uv/) and Homebrew `postgresql@16`.
2. Start Postgres. On macOS it may refuse to start ("postmaster became multithreaded") unless a locale is set:
   `LC_ALL=en_US.UTF-8 brew services start postgresql@16`
3. `createdb maasermart`
4. `cp .env.example .env` and set `DJANGO_SECRET_KEY`.
5. `uv sync` (installs Python 3.13 and all dependencies from `uv.lock`)
6. `uv run python manage.py migrate`
7. `uv run python manage.py runserver`

Layout: `config/` holds settings (`config/settings/{base,local,test,prod}.py`), URLs, WSGI and Celery.
`apps/` holds the nine apps from design doc §6.1. Each app exposes its public functions in `services.py`.
