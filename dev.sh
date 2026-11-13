#!/usr/bin/env bash
# Run MaaserMart locally. Works from any directory: `./dev.sh` or `/path/to/dev.sh`.
#
# It figures out everything it can on its own, in this order:
#   1. finds the project root from its own location (so cwd never matters)
#   2. starts the bundled Postgres in .pgdata/ if it is not already running
#   3. picks the settings module, secret key, allowed hosts and a free port
#   4. waits for the database, applies migrations, and starts the server
#
# Usage:
#   ./dev.sh                  serve on the first free port from 8000
#   ./dev.sh --port 9000      serve on a specific port
#   ./dev.sh --seed           seed first (only works on an empty database)
#   ./dev.sh --no-migrate     skip migrations (faster restart)
#   ./dev.sh --fresh          drop and recreate the dev database, migrate, seed
#
# Override anything by exporting it first; the script never overwrites an env var
# you have already set: DATABASE_URL, DJANGO_SECRET_KEY, DJANGO_SETTINGS_MODULE, PORT.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# --- pretty output ---------------------------------------------------------
if [ -t 1 ]; then
  BOLD=$'\033[1m'; DIM=$'\033[2m'; RED=$'\033[31m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; OFF=$'\033[0m'
else
  BOLD=''; DIM=''; RED=''; GREEN=''; YELLOW=''; OFF=''
fi
say()  { printf '%s==>%s %s\n' "$GREEN" "$OFF" "$*"; }
warn() { printf '%slocal dev:%s %s\n' "$YELLOW" "$OFF" "$*"; }
die()  { printf '%serror:%s %s\n' "$RED" "$OFF" "$*" >&2; exit 1; }

# --- args ------------------------------------------------------------------
PORT="${PORT:-}"
DO_SEED=0
DO_MIGRATE=1
FRESH=0
while [ $# -gt 0 ]; do
  case "$1" in
    --port)      PORT="${2:?--port needs a number}"; shift 2 ;;
    --port=*)    PORT="${1#*=}"; shift ;;
    --seed)      DO_SEED=1; shift ;;
    --no-migrate) DO_MIGRATE=0; shift ;;
    --fresh)     FRESH=1; DO_SEED=1; shift ;;
    -h|--help)   sed -n '2,19p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *)           die "unknown option: $1 (try --help)" ;;
  esac
done

command -v uv >/dev/null 2>&1 || die "uv is not installed (see https://docs.astral.sh/uv/)"

# --- Postgres --------------------------------------------------------------
PGDATA="$ROOT/.pgdata"
PGPORT="$(sed -n 's/^port *= *\([0-9]*\).*/\1/p' "$PGDATA/postgresql.conf" 2>/dev/null || true)"
PGPORT="${PGPORT:-5433}"

# Postgres may not be on PATH (nix, a bare install, a Docker-less box). Look in the
# usual places plus the cluster's own catalog before giving up.
find_pg_bin() {
  local candidate
  for candidate in \
    "$(dirname "$(command -v pg_ctl 2>/dev/null || echo /nonexistent)")" \
    /usr/bin /usr/local/bin /opt/homebrew/bin /usr/lib/postgresql/16/bin \
    "$PGDATA/../.pg-bin"
  do
    if [ -x "$candidate/pg_ctl" ] && [ -x "$candidate/psql" ]; then echo "$candidate"; return 0; fi
  done
  # Fall back to the newest matching nix store path (this machine's setup).
  if compgen -G '/nix/store/*postgresql-and-plugins-*/bin/pg_ctl' >/dev/null; then
    candidate="$(ls -d /nix/store/*postgresql-and-plugins-*/bin 2>/dev/null | sort | tail -1)"
    [ -x "$candidate/pg_ctl" ] && { echo "$candidate"; return 0; }
  fi
  return 1
}

PG_BIN="$(find_pg_bin || true)"

# The cluster's superuser is whoever initdb created; read it from the cluster rather
# than parsing pg_hba.conf (which commonly trusts "all").
pg_superuser() {
  local u
  for u in maasermart postgres "${USER:-}" "${LOGNAME:-}"; do
    [ -n "$u" ] || continue
    if "$PG_BIN/psql" -h 127.0.0.1 -p "$PGPORT" -U "$u" -d postgres -tAc 'SELECT 1' >/dev/null 2>&1; then
      echo "$u"; return 0
    fi
  done
  return 1
}
PGUSER_LOCAL="maasermart"   # replaced below once the cluster answers

if [ ! -d "$PGDATA" ]; then
  [ -n "$PG_BIN" ] || die "no .pgdata/ directory and no Postgres tools found; install Postgres 16 first"
  warn "no .pgdata/ found; creating a local cluster in $PGDATA"
  "$PG_BIN/initdb" -D "$PGDATA" -U "$PGUSER_LOCAL" --encoding=UTF8 --locale=C >/dev/null
  printf 'port = %s\nlisten_addresses = %s\nunix_socket_directories = %s\n' \
    "$PGPORT" "'127.0.0.1'" "'$PGDATA'" >> "$PGDATA/postgresql.conf"
fi

pg_up() { [ -n "$PG_BIN" ] && "$PG_BIN/pg_isready" -h 127.0.0.1 -p "$PGPORT" -q 2>/dev/null; }

if ! pg_up && [ -n "$PG_BIN" ] && [ -d "$PGDATA" ]; then
  say "starting Postgres on port $PGPORT"
  "$PG_BIN/pg_ctl" -D "$PGDATA" -o "-p $PGPORT" -l "$PGDATA/server.log" -w start >/dev/null 2>&1 || true
fi

if pg_up; then
  PGUSER_LOCAL="$(pg_superuser || echo "$PGUSER_LOCAL")"
else
  die "Postgres is not reachable on 127.0.0.1:$PGPORT.
  - looked for tools in: ${PG_BIN:-<none found>}
  - see $PGDATA/server.log
  - or export DATABASE_URL to a database you already have"
fi

# --- env -------------------------------------------------------------------
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings.local}"
export DJANGO_DEBUG="${DJANGO_DEBUG:-true}"
export DJANGO_ALLOWED_HOSTS="${DJANGO_ALLOWED_HOSTS:-localhost,127.0.0.1}"

if [ -z "${DJANGO_SECRET_KEY:-}" ]; then
  KEYFILE="$ROOT/.env.local-key"
  if [ ! -f "$KEYFILE" ]; then
    uv run python -c "from django.core.management.utils import get_random_secret_key as k; print(k())" > "$KEYFILE"
    chmod 600 "$KEYFILE"
  fi
  DJANGO_SECRET_KEY="$(tr -d '\n' < "$KEYFILE")"
  export DJANGO_SECRET_KEY
fi

# Dev database: maasermart_dev if it exists (it is the one that is kept seeded),
# otherwise whatever DATABASE_URL says.
if [ -z "${DATABASE_URL:-}" ]; then
  export DATABASE_URL="postgres://${PGUSER_LOCAL}@127.0.0.1:${PGPORT}/maasermart_dev"
fi
DBNAME="${DATABASE_URL##*/}"

# --- database prep ---------------------------------------------------------
exists() { "$PG_BIN/psql" -h 127.0.0.1 -p "$PGPORT" -U "$PGUSER_LOCAL" -d postgres -tAc \
  "SELECT 1 FROM pg_database WHERE datname='$1'" 2>/dev/null | grep -q 1; }

if [ "$FRESH" = 1 ]; then
  say "dropping and recreating $DBNAME"
  "$PG_BIN/psql" -h 127.0.0.1 -p "$PGPORT" -U "$PGUSER_LOCAL" -d postgres -q \
    -c "DROP DATABASE IF EXISTS \"$DBNAME\"" >/dev/null
  exists "$DBNAME" || "$PG_BIN/psql" -h 127.0.0.1 -p "$PGPORT" -U "$PGUSER_LOCAL" -d postgres -q \
    -c "CREATE DATABASE \"$DBNAME\"" >/dev/null
elif ! exists "$DBNAME"; then
  say "creating database $DBNAME"
  "$PG_BIN/psql" -h 127.0.0.1 -p "$PGPORT" -U "$PGUSER_LOCAL" -d postgres -q \
    -c "CREATE DATABASE \"$DBNAME\"" >/dev/null
  DO_SEED=1
fi

if [ "$DO_MIGRATE" = 1 ]; then
  if ! uv run python manage.py migrate --noinput >/tmp/maasermart-migrate.log 2>&1; then
    printf '%s--- migrate failed ---%s\n' "$RED" "$OFF" >&2
    tail -20 /tmp/maasermart-migrate.log >&2
    die "migrations failed. If the database is in an odd state, run: ./dev.sh --fresh"
  fi
  say "migrations applied"
fi

if [ "$DO_SEED" = 1 ]; then
  if uv run python manage.py seed >/tmp/maasermart-seed.log 2>&1; then
    say "$(tail -1 /tmp/maasermart-seed.log)"
  else
    warn "seed skipped: $(tail -1 /tmp/maasermart-seed.log)"
  fi
fi

# --- port ------------------------------------------------------------------
port_free() { ! (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null; }

if [ -z "$PORT" ]; then
  PORT=8000
  while ! port_free "$PORT"; do
    PORT=$((PORT + 1))
    [ "$PORT" -gt 8010 ] && die "no free port between 8000 and 8010 (try --port)"
  done
else
  port_free "$PORT" || die "port $PORT is already in use (try --port with another)"
fi

# --- go --------------------------------------------------------------------
CHARS="$(uv run python manage.py shell -v 0 -c 'from apps.charities.models import Charity; print(Charity.objects.count())' 2>/dev/null | tr -dc '0-9')"
CHARS="${CHARS:-0}"

printf '\n%s  MaaserMart is running%s\n' "$BOLD" "$OFF"
printf '  %sopen:%s      http://127.0.0.1:%s/charity/\n' "$DIM" "$OFF" "$PORT"
printf '  %sdatabase:%s  %s (%s charities)\n' "$DIM" "$OFF" "$DBNAME" "$CHARS"
printf '  %sadmin:%s     http://127.0.0.1:%s/django-admin/  (admin / admin)\n' "$DIM" "$OFF" "$PORT"
printf '  %sstop:%s      Ctrl-C\n\n' "$DIM" "$OFF"

exec uv run python manage.py runserver "127.0.0.1:$PORT"
