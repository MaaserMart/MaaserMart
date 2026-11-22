# MaaserMart

Charity discovery for maaser giving. See MaaserMart.com.

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
git clone https://github.com/MaaserMart/MaaserMart.git
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
`seed` adds about 200 fake charities, with users, reviews, haskamas and events. It only runs on an empty database and refuses otherwise. To start over with Homebrew Postgres:
```bash
dropdb maasermart && createdb maasermart
uv run python manage.py migrate
uv run python manage.py seed
```
With Docker, use `docker exec maasermart-db dropdb -U postgres maasermart` and `docker exec maasermart-db createdb -U postgres maasermart` for the first line.

**4. Run it:**
```bash
uv run python manage.py runserver
```
Open http://localhost:8000. `/` redirects to the charity listing at `/charity/` (D-028), and a card opens the charity's own page at `/charity/<id>/` (D-057). The admin is at http://localhost:8000/django-admin/: log in as `admin` with the random password `seed` printed when it ran (D-062), or set `ADMIN_SEED_PASSWORD` before seeding. Every other seeded user (`member1`, `owner1`, `rabbi1`, ...) has the password `password`.

## The charity listing

The listing lives in `apps/charities/` and is split into layers, each with its own tests:

- `contracts.py` — plain read models (`CharityCard`, `CharityPage`, `DomainTag`, `LocationTag`). No ORM behaviour, so the template cannot depend on how rows were fetched.
- `repositories.py` — the `CharityRepository` and `FilterOptionsRepository` protocols and their Django implementations, the only code that queries Postgres. Also where the sidebar's domain and location lists are cached for a minute (D-061).
- `filters.py` — §6.2.4's groups: reading them from the query string, clamping numbers into range, producing the sidebar's form, and rebuilding the query string a page link carries.
- `sorting.py` — §6.2.5's mechanisms and directions, and the same three query-string helpers.
- `search.py` — §6.2.6's term and advanced options, and the same three helpers again.
- `state.py` — the whole address as one `PageState`: search, filters, order and the page window, with the order they are read and written in stated once (D-068).
- `services.py` — the listing rules (page clamping, page size, page+count as one snapshot) plus `publish_charity` / `hide_charity` (D-038).
- `views.py` / `urls.py` — `GET /charity/` takes `page` and `page_size`, clamping both, plus `q`, the filter parameters and `sort`. `GET /charity/<id>/` is the charity page and `GET /charity/<id>/link/<id>/` records a link click and redirects.

The listing currently shows every charity, including unpublished ones. Nothing publishes a charity yet, so reading `is_visible` would render an empty page; see D-042 for why, D-059 for where the flag is enforced, and what flips it back.

## Tests and lint

CI runs these on every pull request; run them before you push:
```bash
uv run ruff check .
uv run ruff format --check .
uv run python manage.py makemigrations --check --dry-run
uv run pytest
```
`uv run ruff format .` fixes formatting. `pytest` also measures coverage of `apps/` and `config/` and fails under 85% (see `[tool.coverage.report]` in `pyproject.toml`).

## Working on the code

Read [CLAUDE.md](CLAUDE.md) for the project rules, and [docs/DECISIONS.md](docs/DECISIONS.md) for the decisions that override or fill gaps in the design doc.
