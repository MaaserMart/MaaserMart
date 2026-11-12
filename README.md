# MaaserMart

Charity discovery for maaser giving. See MaaserMart.com.
Hosting info: https://ap.www.namecheap.com/domains/domaincontrolpanel/maasermart.com/advancedns

A Django app with PostgreSQL, HTMX and Alpine.

## Setup

You need [uv](https://docs.astral.sh/uv/) and PostgreSQL 16. uv installs the right Python (3.13) for you.

**1. Start Postgres 16**, either with Homebrew or with Docker.

Homebrew:
```bash
brew install postgresql@16
brew services start postgresql@16
createdb maasermart
```
On macOS, Postgres may refuse to start, with "postmaster became multithreaded" in `$(brew --prefix)/var/log/postgresql@16.log`. In that case, start it with a locale set (this lasts until you reboot):
```bash
LC_ALL=en_US.UTF-8 "$(brew --prefix postgresql@16)/bin/pg_ctl" -D "$(brew --prefix)/var/postgresql@16" -l "$(brew --prefix)/var/log/postgresql@16.log" start
```

Docker:
```bash
docker run -d --name maasermart-db -p 5432:5432 -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=maasermart postgres:16
```

**2. Get the code and configure it:**
```bash
git clone https://github.com/BenjaminYazdi/MaaserMart.git
cd MaaserMart
cp .env.example .env
```
If you use Docker, change `DATABASE_URL` in `.env` to `postgres://postgres:postgres@localhost:5432/maasermart`.

**3. Install, create the tables, and add fake data:**
```bash
uv sync
uv run python manage.py migrate
uv run python manage.py seed
```
`seed` wipes the app's data and adds about 200 fake charities, with users, reviews, haskamas and events.

**4. Run it:**
```bash
uv run python manage.py runserver
```
Open http://localhost:8000. The admin is at http://localhost:8000/django-admin/: log in as `admin` / `admin`. Every other seeded user (`member1`, `owner1`, `rabbi1`, ...) has the password `password`.

## Tests and lint

```bash
uv run pytest
uv run ruff check .
uv run ruff format .
```
CI runs the same checks on every pull request.

## Working on the code

Read [CLAUDE.md](CLAUDE.md) for the project rules, and [docs/DECISIONS.md](docs/DECISIONS.md) for the decisions that override or fill gaps in the design doc.
