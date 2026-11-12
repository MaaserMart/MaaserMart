# Project scaffold — a runnable skeleton for MaaserMart

*Explains the change not yet saved into the project's shared history: the new `src/` project plus the relocation of the two design documents.*

---

## 1. Read this part even if you read nothing else

Imagine a workshop where the tools are still in their boxes. The blueprints are pinned to the wall. Everything you need is in the room, but nothing is plugged in, and every time someone says "let's build the first shelf" the answer is "first we have to wire the workshop." That was this project before the change. It held two Word documents — a requirements document and a design document — and no code at all. There was no program to start, no database, no web page, and no agreed place to put any of it.

This change wires the workshop. It adds a folder called `src/` that holds a working website project, written in Python with a widely used website-building toolkit. The project can start, serve pages, build its database tables, and run its automated checks. It has a place for each feature's code, a shared outer frame for pages, a style sheet, a list of what to install, a sample configuration file, and rules for what must never be saved into the project's shared history.

It deliberately builds **no feature**. There are no charities in it yet, no listing page, no models of real-world things. The only thing that exists is the machine that future code will be bolted onto. The single new web address, `/listing/`, points at an empty list of pages, so visiting it today returns the project's standard "not found" page. That is expected, and it is the one thing a reader might otherwise mistake for breakage.

The work is verified the only way an empty skeleton can be verified: the project was checked, its tables were built, and the tool that runs the automated tests was run. All three succeeded. The test runner found zero tests, which is correct, because no behaviour has been written yet.

Everything below is the same idea in more detail.

---

## 2. How to read this file

This document has two complete layers and neither is a summary of the other.

- **If you do not read code**, read the glossary, the story, and the bold one-line summary at the top of each file section, plus the plain sentence that sits directly above every code box. You will lose nothing.
- **If you are reviewing the change**, the code boxes are the change itself, quoted in full enough that you should not need to open the side-by-side comparison of changed lines.

Three rules:

1. **Read the glossary first.** Every term used here is defined there before it is used anywhere else.
2. **Every code box is optional.** The sentence directly above each box says the same thing in English. Skip every box and the document still stands.
3. **Each file section opens with a bold one-line summary.** Skim only those summaries and you have the shape of the whole change.

This document explains; it does not grade. There is no verdict and no recommendation at the end.

---

## 3. The glossary

Thirteen words, each defined by what it does and why anyone cares.

| term | plain words | what it is and why it matters |
|---|---|---|
| **Django** | the website-building program | A toolkit for the Python language that turns a folder of code into a website: it receives a request from a browser, picks the code that should answer, and sends back a page. The whole project is Django plus our own code. |
| **virtual environment** | a private copy of Python | A folder (here `.venv/`) holding this project's own Python and the software packages it installed. It keeps this project's packages from colliding with anything else on the machine. |
| **requirements file** | the shopping list | A text file listing the packages the project needs, so a fresh machine can install exactly the same ones with one command. |
| **app** | one feature's folder | Django's unit of organisation. An app is a folder grouping the code for one area. The design document lists nine for this project; this change creates the first, `charities`. |
| **settings** | the rulebook | The single Python file Django reads at startup to learn where files live, how to reach the database, which apps exist, and what is secret. |
| **environment variable** | a note passed in at startup | A named value the operating system gives the program when it starts, such as a password or a database location. Values kept here never enter the code or the shared history. |
| **database** | the filing cabinet | The store that keeps data between visits. Django uses it for user accounts, sessions, and (later) charities. |
| **database address** | where the cabinet is | A single line of text describing the database's type, location, user, and password. Set through `DATABASE_URL`. |
| **SQLite** | a database in a single file | The simplest kind of database: one file on disk holding every table and row. Used here for local work so the project runs with no server. |
| **PostgreSQL** | the full database server | A separate always-running database program built for many users at once. The design requires it for the finished site; the code switches to it when `DATABASE_URL` is set. |
| **repository** | the project's shared history | The saved record of every change to the project, which everyone with a copy receives. "Committed" means saved into this record; "working tree" means the changes not yet saved. |
| **migration** | a written instruction that builds shelves | A recorded change to the database's structure. Django keeps these as files and replays them in order, so every copy of the project gets the same tables. |
| **template and static file** | the page's frame, and the things that never change | A template is a web page (written in HTML, the page language) with blanks that Django fills in per request. A static file is a style sheet (the file that controls how pages look) or an image, served as-is and the same for every visitor. |

Plain-word substitutions used throughout the code sections:

| code type | plain word |
|---|---|
| `bool` | switch (on or off) |
| `str` | text |
| `int` | whole number |
| `list` | list of items |
| `dict` | labelled bag |
| `Path` | folder address |

---

## 4. The story

### What the system will do all day

MaaserMart is a website about charities. When it is finished, a visitor will:

1. Open the site and see a list of charities, each with a picture and a description.
2. Narrow that list by type, place, rabbinical approval, or rating; sort it; search it.
3. Open one charity's page to read its description, links, reviews, and approvals.
4. Sign in — as a member to write a review, as a rabbi to give an approval, as an owner to update a charity and see its visitor statistics.
5. Rely on an administrator to approve new charities and edits before they appear.

All of it is built the same way: a browser asks for a page, the server-side program decides what to show, and it sends back a finished page. There is no separate phone app and no separate front-end program.

### What was missing

The project's shared history contained exactly two files, both Word documents: `requirements.docx` (what the site must do) and `design.docx` (how it will be built). Nothing could run. There was no list of software to install, no way to start it, no rulebook, no folder for a feature, no database, and no shared page frame.

That matters because the design document describes **fifteen small end-to-end slices** — it calls them tracer bullets — and the first of them is the charity listing. A listing needs a web address, a page frame, a database connection, and a place to put its code. None existed. Building the listing without the skeleton would mean inventing all of those inside the first feature, and then untangling them later.

### The fix in one sentence

Create the smallest Django project that genuinely runs, give it one app for charities, and make every environment-specific value (secret key, debug switch, database address) come from outside the code.

Its consequences, plainly:

- The project starts with `manage.py runserver` and can serve pages.
- The database's own tables can be built with `manage.py migrate`, using a local single-file database (SQLite) by default.
- Tests can run, even though there are none yet.
- Moving to the full database server the design requires (PostgreSQL) is a single environment variable, not a code change.
- No secret is stored in the project's shared history.
- A shared page frame, a stylesheet, and a URL prefix now exist, so the charity listing can be added as a small, obvious change.

### Why this is a whole change and not several

It is one idea: make the workshop runnable. The individual files are all serving that idea. The only exception is the relocation of the two Word documents into `docs/`, which happens to be in the same set of unsaved changes but is not part of the scaffold; it is called out in the next section.

---

## 5. Contradictions

Where the written material disagrees with what is actually in the project folder. Trust the code; it is the only thing that runs.

### 5.1 The two Word documents moved

The saved history has `design.docx` and `requirements.docx` at the top folder of the project. The unsaved changes delete both and add `docs/design.docx` and `docs/requirements.docx`. This is a move, not a deletion of content, and it was not part of the scaffold. The change therefore shows the two documents as deleted at their old place and added under `docs/`. They should be accounted for as a move.

### 5.2 `.env.example` says to copy the file, but nothing reads it

`src/.env.example:1` says:

```
# Copy to .env and fill in. Never commit .env.
```

Copying that file to `.env` has **no effect by itself**. The settings file reads only real environment variables through `os.environ`. There is no code that loads a `.env` file. Trust the code: for now, values must be set in the terminal before starting the project, or a loader must be added later. This is worth fixing, but it is a documentation-versus-code gap, not a broken program.

### 5.3 The ignore rule for `.venv/` does not actually cover the venv in use

`src/.gitignore:4` contains `.venv/`, but the virtual environment was created at the top folder of the project, one level above `src/`, so that pattern does not match it. The venv is nonetheless ignored, because Python writes its own `.venv/.gitignore` containing `*` when it creates one. `git check-ignore -v .venv` names that inner file as the reason. Convenient, but accidental: if a future virtual environment is created without that inner file, it would start showing up as a file waiting to be added.

### 5.4 The design lists nine apps; the project folder contains one

The design document's module list names accounts, charities, events, tools, approvals, support, chatbot, recommendations, and dashboards. Only `charities` exists. The others will be added with the slices that need them. This is deferral, not an omission.

### 5.5 The architecture requires PostgreSQL; the default local database is SQLite

The design (SRS 2.7) requires PostgreSQL. This machine has no PostgreSQL server, no Docker, and no package manager for one. The code therefore defaults to SQLite (a database in a single file) and switches to PostgreSQL automatically when `DATABASE_URL` is set. That keeps the project runnable now without pretending the production choice changed. The trade-off is stated here rather than hidden.

### 5.6 `/listing/` is routed but returns "not found"

`src/config/urls.py:11` sends `/listing/` to `charities.urls`, whose page list is empty (`src/charities/urls.py:5`). Django therefore answers "not found" (the standard 404 reply). The address exists so the listing slice has a fixed place to fill in. Nothing is broken; the page simply has not been written.

### 5.7 Development defaults are unsafe for production, by design

`DEBUG` defaults to on and allowed hosts to `*` when debugging (`src/config/settings.py:80-81`). That is convenient locally and wrong on a public server. The environment variable overrides both. This is a deliberate development default, not a production configuration.

---

## 6. Reading order

Read by dependency: what gets installed, then the door, then the rulebook, then the wiring, then the placeholders, then the page furniture, then the housekeeping.

| order | file | what it is |
|---|---|---|
| 1 | `src/requirements.txt` | the shopping list |
| 2 | `src/.env.example` | the documented knobs |
| 3 | `src/.gitignore` | what must never be saved |
| 4 | `src/manage.py` | the door: every command starts here |
| 5 | `src/config/settings.py` | the rulebook |
| 6 | `src/config/__init__.py` | the marker that makes `config` a nameable unit |
| 7 | `src/config/urls.py` | the signpost from address to code |
| 8 | `src/config/wsgi.py`, `src/config/asgi.py` | the two doorways a web server uses |
| 9 | `src/charities/apps.py` | registering the app |
| 10 | `src/charities/__init__.py` | the app's own note |
| 11 | `src/charities/urls.py` | the app's addresses (empty for now) |
| 12 | `src/charities/models.py` | the app's data (empty for now) |
| 13 | `src/charities/views.py` | the app's page logic (empty for now) |
| 14 | `src/charities/admin.py` | the app's admin registration (empty for now) |
| 15 | `src/charities/migrations/__init__.py` | makes migrations a package |
| 16 | `src/charities/tests/__init__.py` | makes tests a package |
| 17 | `src/templates/base.html` | the shared page frame |
| 18 | `src/static/css/site.css` | the style sheet |

**The whole change in one sentence:** a Django project and one empty app, configured entirely from the environment, with a shared page frame and a fixed `/listing/` address waiting for the first feature.

---

## 7. One section per file

### `src/requirements.txt` — **the shopping list, three lines long**

This file tells a fresh machine what to install. It is read by the install command `pip install -r requirements.txt`, not by the project itself.

There was nothing before; this file is new.

The first two lines are a comment and the install instruction. The third pins Django to the 5.2 line, meaning "5.2 or newer, but not 6".

```text
# MaaserMart dependencies.
# Install with:  pip install -r requirements.txt
Django~=5.2
```

Why not pin an exact version? The 5.2 line is the long-term-support line, so it receives security fixes. A minor upgrade inside the line is expected and safe. The consequence in the world: installing on a clean machine gets a supported Django without editing the file.

---

### `src/.env.example` — **a filled-in sample of every knob, with no secrets**

This file documents the four environment variables the settings file understands. It is a sample, not a file the program reads; see contradiction 5.2.

There was nothing before; this file is new.

The comments explain each value. The database address is left commented out, because when it is absent the project falls back to a local file.

```text
# Copy to .env and fill in. Never commit .env.
#
# Core
DJANGO_SECRET_KEY=change-me
DJANGO_DEBUG=1
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
#
# Database. When unset, the project falls back to a local SQLite file
# (db.sqlite3) so the project runs with no server. Set DATABASE_URL to use
# PostgreSQL, as the architecture (SRS 2.7) requires:
# DATABASE_URL=postgres://USER:PASSWORD@HOST:5432/DBNAME
```

Why this file exists at all: a new developer needs to know the names and shapes of the values without reading Python. The consequence is that the configuration surface is documented in one place, and the real values stay out of the shared history.

---

### `src/.gitignore` — **the list of things that must never be saved**

The project's shared history ignores some files on purpose: compiled leftovers, the virtual environment, the local database file, logs, the real environment file, and the folder of collected static files.

There was nothing before; this file is new.

Each line is a pattern. A trailing slash means "a folder".

```text
# Python
__pycache__/
*.py[cod]
.venv/
venv/
# Django
db.sqlite3
*.log
# Local environment
.env
# Static files collected for deployment
staticfiles/
media/
```

Why it matters: `db.sqlite3` holds real data, `.env` holds secrets, and `.venv/` holds hundreds of megabytes of someone else's code. Saving any of them would either leak secrets or bloat the shared history. Note that this file sits inside `src/` and therefore governs only that folder — see contradiction 5.3.

---

### `src/manage.py` — **the door every command goes through**

This is the file every command goes through. Starting the server, building the database, and running tests all happen by passing a command name to it.

There was nothing before; this file is new.

It adds `src/` to Python's list of places to look for code, names the rulebook, loads Django, and hands the typed command to Django to carry out. If Django is missing, the failure is a readable message instead of a wall of errors.

```python
#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
from pathlib import Path


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    sys.path.insert(0, str(base_dir))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:  # pragma: no cover - environment problem
        raise ImportError(
            "Couldn't import Django. Are you sure it is installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
```

Why add the folder to Python's search list instead of placing the project at the very top? Because the top also holds `docs/` and, later, other documents. Keeping runnable code under `src/` keeps the top level clean and means the command is always `python src/manage.py …`. The consequence: one predictable command from the top folder, whatever folder the terminal happens to be in.

---

### `src/config/settings.py` — **the rulebook Django reads before doing anything**

This file decides where files live, which apps exist, how to reach the database, how secrets are supplied, and how pages and logs behave. It is 168 lines, so it is covered in parts.

There was nothing before; the file is new. Three lines were drafted and then corrected during this work, and those corrections are shown as before and after, because the saved change will only show the corrected result.

#### 7.0 The opening note and the tools it borrows

**The file starts with a short description of itself and brings in the four tools the rest of it uses.**

It says what the file is, turns on a Python feature that keeps type hints simple, and brings in the operating-system access, folder handling, and web-address parsing it needs.

```python
"""Django settings for the MaaserMart project.

Configuration comes from the environment (a .env file holds the values, see
.env.example); nothing secret is committed.
"""
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import unquote, urlparse
```

Why quote the imports? Because a reviewer checking the database-address function needs to see where `urlparse` and `unquote` come from. The consequence: every line of the rulebook is accounted for.

#### 7.1 The folder anchor

**It finds the source folder by walking up from its own location, and that was initially wrong.**

The first draft walked up three folders from the file:

```
BASE_DIR = Path(__file__).resolve().parent.parent.parent

DOCTRINE_DIR = BASE_DIR
```

`settings.py` lives in `src/config/`, so walking up three folders lands on the top folder of the project, not `src/`. Django therefore looked for `templates/` and `static/` at the repository root, which is exactly what the observed warning said: `staticfiles.W004 … /home/shaul/projects/maasermart/static does not exist`. The second line was a stray assignment that nothing referenced.

The corrected version walks up two folders and names what it means: (`src/config/settings.py:12-13`)

```python
# src/ - the directory holding manage.py, the apps, templates, and static.
BASE_DIR = Path(__file__).resolve().parent.parent
```

Why it matters: one wrong folder makes Django look in the wrong place for every relative path at once — templates, stylesheets, the database file. Fixing the anchor fixed all of them together. The consequence is that `templates/base.html` is found, `static/css/site.css` is served, and the SQLite file is created inside `src/`.

#### 7.2 Reading values from the environment

**Three small helpers read text, on/off switches, and comma-separated lists out of the environment, treating an empty value as absent.**

Nothing existed before.

The text helper returns the default when the variable is missing or blank, so `DJANGO_DEBUG=` behaves like "not set" rather than like an empty string. The switch helper accepts the usual spellings of yes. The list helper splits on commas and drops empty entries. (`src/config/settings.py:16-37`)

```python
def env(name: str, default: str | None = None) -> str | None:
    """Read a setting from the environment."""
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value


def env_bool(name: str, default: bool = False) -> bool:
    """Read a boolean setting from the environment."""
    value = env(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: list[str] | None = None) -> list[str]:
    """Read a comma-separated list setting from the environment."""
    value = env(name)
    if value is None:
        return list(default or [])
    return [item.strip() for item in value.split(",") if item.strip()]
```

Why not read `os.environ` directly everywhere? Because the "blank means default" rule and the yes-spellings would then be repeated at each call site, and drift. The consequence: every knob behaves consistently, including when a deployment sets a variable to an empty string.

#### 7.3 Turning one database address into Django's database settings

**It accepts a `postgres://user:password@host:port/database` address, or a single-file database path, and converts it into the labelled bag Django expects, passing through any extra options it does not recognise.**

Nothing existed before.

It reads the address's type to choose the matching database connector, treats the single-file database specially, and otherwise splits out user, password, host, port, and any extra options. Extra options are passed through, so a hosted database's security setting `?sslmode=require` works with no code change. (`src/config/settings.py:40-76`)

```python
def database_from_url(url: str) -> dict:
    """Build a Django DATABASES entry from a DATABASE_URL-style string.

    Unknown query parameters are passed through to the backend, so a URL such
    as postgres://user:pass@host/db?sslmode=require works as-is.
    """
    parsed = urlparse(url)
    scheme = parsed.scheme.split("+", 1)[0]
    engines = {
        "postgres": "django.db.backends.postgresql",
        "postgresql": "django.db.backends.postgresql",
        "pgsql": "django.db.backends.postgresql",
        "sqlite": "django.db.backends.sqlite3",
    }
    if scheme not in engines:
        raise ValueError(f"Unsupported database scheme: {parsed.scheme!r}")

    name = (parsed.path or "").lstrip("/")
    if scheme == "sqlite":
        return {
            "ENGINE": engines[scheme],
            "NAME": name if name.startswith("/") else str(BASE_DIR / name),
        }

    options = {}
    for key, value in (pair.split("=", 1) for pair in parsed.query.split("&") if pair):
        options[key] = unquote(value)

    return {
        "ENGINE": engines[scheme],
        "NAME": unquote(name),
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": parsed.hostname or "",
        "PORT": str(parsed.port or ""),
        "OPTIONS": options,
    }
```

An unrecognised address type is refused immediately instead of quietly connecting to the wrong thing, so a mistyped address fails at startup with a clear message. The consequence: one environment variable moves the project between a local file and the full database server the design requires, with no code edit and no secret in the shared history.

#### 7.4 The values themselves

**Secrets and hosts come from the environment; development defaults are loud and obvious.**

Nothing existed before.

The secret key falls back to a string that says, in effect, "this is not a real key." Debugging defaults to on. Allowed hosts default to "anything" only while debugging. The last line lists trusted web addresses for a deployment that sits behind a forwarding server (a proxy). (`src/config/settings.py:79-82`)

```python
SECRET_KEY = env("DJANGO_SECRET_KEY", "insecure-development-key-change-me")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", ["*"] if DEBUG else [])
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")
```

The second draft repeated the debug check inside the host default, so the same switch was read twice:

```python
# first draft (not saved)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", ["*"] if env_bool("DJANGO_DEBUG", True) else [])
```

It was harmless — the environment cannot change mid-process — but two readings of one switch invite drift. The corrected line uses the already-computed `DEBUG`. This is the only change to this block.

Why the insecure fallback? So a fresh copy of the project starts without ceremony. It is safe only because it is obviously fake and overridden in any real deployment. The consequence: `runserver` works on a new machine with no configuration, and a real deployment must set the secret.

#### 7.5 The installed apps

**Django's built-in apps plus one project app, `charities`.**

Nothing existed before.

Six built-in pieces give the admin site, user accounts, permissions, sessions, one-time messages, and style-sheet handling. The last entry is this project's first feature folder. (`src/config/settings.py:84-93`)

```python
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Project apps (see the module list in docs/design.docx).
    "charities.apps.CharitiesConfig",
]
```

Why list the config class rather than just `"charities"`? It is explicit and gives the app a place to hang startup behaviour later. The consequence: the charity models, pages, and admin screens added next will be discovered without touching this file again.

#### 7.6 Middleware, URLs, templates, and server doorways

**The fixed request-handling steps, the root address table, the page-template setup with a project-wide template folder, and the two ways a web server can start the project.**

Nothing existed before.

The request pipeline (called middleware) is the fixed sequence every incoming request passes through — security headers, sessions, common handling, cross-site-request protection, the signed-in user, one-time messages, and clickjacking protection. (`src/config/settings.py:95-105`)

```python
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
```

The template block adds one project-wide folder, `src/templates/`, ahead of each app's own templates. That is where the shared page frame lives. Four small helpers are switched on so that every page can see debugging details, the request itself, the signed-in user, and one-time messages. (`src/config/settings.py:107-124`)

```python
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"
```

Both the traditional way a web server starts a project and the newer asynchronous way are named, so either kind of server works without editing the rulebook. The consequence: pages in `src/templates/` are found from anywhere, and the shared frame is available to every app.

#### 7.7 Choosing the database

**If a database address is provided, use it; otherwise use a local SQLite file inside `src/`.**

Nothing existed before.

This is the one branch that makes the project runnable on a machine with no database server. (`src/config/settings.py:126-134`)

```python
database_url = env("DATABASE_URL")
DATABASES = {
    "default": database_from_url(database_url)
    if database_url
    else {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}
```

Why a fallback at all, when the design mandates PostgreSQL? Because a developer with no server should still be able to build and test. The consequence is honest but temporary: local work uses a file, production must set `DATABASE_URL`. Contradiction 5.5 records the trade-off.

#### 7.8 Passwords, language, time, and static files

**Standard password-strength rules, US English, one shared clock (UTC), and one folder for the style sheets and images the project owns.**

Nothing existed before.

Four password rules reject passwords too similar to the user's details, too short, too common, or all numbers. Times are stored in one shared clock (UTC) and displayed in the visitor's time zone. The last block names the web-address prefix for style sheets and images, the folder where collected files are written for deployment, and the source folder developers edit. (`src/config/settings.py:136-152`)

```python
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
```

Why split `STATIC_ROOT` from `STATICFILES_DIRS`? The first is the output folder for deployment; the second is the source folder developers edit. Mixing the two up is a classic way to have files overwritten. The consequence: `site.css` is served during development from `src/static/`, and collected into `src/staticfiles/` for deployment.

#### 7.9 Logging

**Logs go to the console at an everyday level of detail, and request errors are printed once, not twice.**

There was nothing before; this block is new.

It sends log records to the console and prints each request error once, without passing it on to be printed again. (`src/config/settings.py:154-168`)

```python
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
    },
}
```

Why so minimal? The design asks for two kinds of logging — a technical log, and a permanent record of who changed what — but both belong with the features that produce the events. This block only guarantees that something is printed. The consequence: a startup mistake is visible instead of silent.

---

### `src/config/__init__.py` — **makes the config folder a unit of code**

An empty file whose presence lets Python treat `src/config/` as one unit of code rather than a plain folder.

There was nothing before; this file is new.

The file is empty by design; there is no code to quote.

Why an empty file? Django imports the rulebook and the address table by names that start with `config`, and Python needs the marker to find them. The consequence: `config.settings` and `config.urls` can be imported by name.

---

### `src/config/urls.py` — **the root signpost: which prefix goes to which code**

This file maps web addresses to the code that answers them. It is the only place the project-wide address layout is visible.

There was nothing before; this file is new.

The admin site is wired at `/admin/`. The prefix `/listing/` is handed to the charities app's own address table, which is currently empty. (`src/config/urls.py`)

```python
"""Root URL configuration.

Module URLs are included here as their apps are built; each app keeps its own
urls.py (see the Page Inventory in docs/design.docx).
"""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("listing/", include("charities.urls")),
]
```

Why hand `/listing/` over now if the app has no pages? Because it fixes the address from the design document in one line, and the app can grow without editing this file again. The consequence today: `/listing/` answers "not found" (contradiction 5.6); tomorrow, the listing slice only edits the app's own table.

---

### `src/config/wsgi.py` and `src/config/asgi.py` — **the two doorways a web server knocks on**

These do the same job in two ways that two kinds of web server each expect. A traditional server (Gunicorn, named in the design) uses the first; a newer asynchronous server uses the second.

Nothing existed before; both files are new.

Each names the rulebook and then asks Django to build the object the server calls for every request. (`src/config/wsgi.py`)

```python
"""WSGI config for the MaaserMart project."""
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_wsgi_application()
```

The asynchronous doorway is the same shape with a different builder: (`src/config/asgi.py`)

```python
"""ASGI config for the MaaserMart project."""
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_asgi_application()
```

Why both? The toolkit's own guidance expects both; providing them costs two small files and removes a later decision. The consequence: deploying with Gunicorn needs no new code, and an asynchronous server remains an option.

---

### `src/charities/apps.py` — **registering the charities app**

This tiny setup class tells Django the feature folder exists, its name in code, and the default kind of database key its data definitions (models) will use.

There was nothing before; this file is new.

It defines the app's setup class and points at the app's name. (`src/charities/apps.py`)

```python
from django.apps import AppConfig


class CharitiesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "charities"
```

Why a setup class at all? It gives the app a place for startup work later, and it is the exact name the rulebook refers to. The consequence: the app is discovered automatically, and its tables will use large integer keys by default — enough for years of rows without changing the key type.

---

### `src/charities/__init__.py` — **the app's own note about what belongs here**

An otherwise empty file that makes the folder a unit Python recognises as code. Its comment records the app's ownership, so the next person does not have to infer it.

There was nothing before; this file is new.

It records the app's ownership in a comment and defines nothing else. (`src/charities/__init__.py`)

```python
# The charities app owns the public read queries for the charity list,
# filter, sort, and search (SRS FR 1-4) plus the charity page (FR 8).
#
# Models follow the data dictionary in docs/design.docx.
```

Why put prose in a file that executes nothing? Because the app's boundary is a design decision, and this is the cheapest place to state it. The consequence: the first feature's code has a stated home, and the comment names the design sections it must satisfy.

---

### `src/charities/urls.py` — **the app's address table, intentionally empty**

This file will hold the charity-specific addresses. Today it holds only a namespace and an empty list.

There was nothing before; this file is new.

It names the app's address group and leaves the page list empty. (`src/charities/urls.py`)

```python
from django.urls import path

app_name = "charities"

urlpatterns: list = []
```

The `app_name` gives these addresses a short group name (a namespace), so pages can refer to them by name (`charities:...`) rather than by a hard-coded address. The empty list is why `/listing/` currently answers "not found". The consequence: the listing slice adds one entry here and the root signpost never changes.

---

### `src/charities/models.py` — **the app's data definitions, intentionally empty**

This file will describe the real-world things the app stores — charities, locations, domains, links — following the design document's data dictionary. Today it only imports the tool it will use.

There was nothing before; this file is new.

It imports the data-definition tools for the first time, with a trailing note telling code checkers the unused import is deliberate. (`src/charities/models.py`)

```python
from django.db import models  # noqa: F401 - models land here next
```

The `noqa: F401` note tells code checkers the unused import is deliberate. Why keep an unused import at all? So the first real edit starts from a working import rather than a broken one, and the trailing comment says plainly that models are next. The consequence: no tables exist yet, so `migrate` creates only Django's own.

---

### `src/charities/views.py` — **the app's page logic, intentionally empty**

This file will contain the code that answers a request for the listing (and later the charity page). Today it imports the page-rendering helper and nothing else.

There was nothing before; this file is new.

It imports the page-rendering helper and defines nothing else. (`src/charities/views.py`)

```python
from django.shortcuts import render  # noqa: F401 - views land here next
```

Why an unused import? Same reason as the models file: the first function can be written without rediscovering the import, and the note prevents a code checker's complaint from being mistaken for a problem. The consequence: no page exists yet; this is a labelled empty slot.

---

### `src/charities/admin.py` — **the app's admin registration, intentionally empty**

Django's admin site can manage this app's data once it is registered here. Nothing is registered yet.

There was nothing before; this file is new.

It imports the admin tools and registers nothing yet. (`src/charities/admin.py`)

```python
from django.contrib import admin  # noqa: F401 - models land here next
```

Why include it if it does nothing? A Django app conventionally has these three files, and the admin is how an administrator will eventually inspect and correct data. The consequence: the admin site exists at `/admin/` but shows nothing from this app until models and registrations are added.

---

### `src/charities/migrations/__init__.py` — **makes the migrations folder a Python package**

An empty file whose presence lets Django treat the folder as a unit of code it can load.

There was nothing before; this file is new.

The file is empty by design; there is no code to quote.

Why an empty file? Python can treat a folder without such a marker as code, but Django's migration tool and older tools expect the marker. The consequence: when the first model is added, `makemigrations` has a folder to write into without creating it first.

---

### `src/charities/tests/__init__.py` — **makes the tests folder a Python package**

An empty file so the test runner can discover test files in this folder.

There was nothing before; this file is new.

The file is empty by design; there is no code to quote.

Why a folder instead of Django's usual single `tests.py`? The design calls for many small slices, so tests will be split by concern rather than grown into one file. The consequence: `manage.py test` discovers this app and reports zero tests today, which is exactly what was observed.

---

### `src/templates/base.html` — **the shared page frame every page will extend**

This is the outer page every page reuses: the page type, language, character set, screen scaling, a title block, the style-sheet link, and a content block.

There was nothing before; this file is new.

It loads the helper that builds links to style sheets and images, then defines two named holes — `title` and `content` — that child pages fill. The title falls back to "MaaserMart" when a page does not set one. (`src/templates/base.html`)

```html
{% load static %}<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{% block title %}MaaserMart{% endblock %}</title>
    <link rel="stylesheet" href="{% static 'css/site.css' %}">
  </head>
  <body>
    {% block content %}{% endblock %}
  </body>
</html>
```

Why a base frame at all when no page exists? Because the design requires server-rendered pages with a consistent outer frame, and every later page can inherit it. The consequence: the listing template will be a few lines of content rather than a full HTML document.

---

### `src/static/css/site.css` — **the stylesheet, deliberately almost empty**

The one style sheet the shared frame links to.

There was nothing before; this file is new.

It sets the page's font and removes the browser's default margin. (`src/static/css/site.css`)

```css
/* Minimal site styling; the templates are thin and server-rendered. */
body {
  font-family: system-ui, sans-serif;
  margin: 0;
}
```

Why not leave it out until a designer is involved? Because the frame links to it, and a link to a missing file produces a "not found" error on every page load — noise that hides real problems. The consequence: pages load with no missing-file noise, and the file is the obvious place for the listing's layout later.

---

## 8. The tests

There are no test files with tests in them yet. The `src/charities/tests/` folder exists but contains only its empty package marker. This is the correct state for a scaffold: there is no behaviour to lock down.

What was actually run, and what each result proves:

The first command asks Django to inspect its own configuration and report problems without starting a server.

```text
$ .venv/bin/python src/manage.py check
System check identified no issues (0 silenced).
```

This proves every setting, app reference, web-address entry, and template folder resolves. A typo in an app name or a missing folder fails here.

The second asks whether any model change is missing a migration file.

```text
$ .venv/bin/python src/manage.py makemigrations --check --dry-run
No changes detected
```

This proves the model files, though empty, are consistent with the database's recorded structure.

The third builds the database's tables from Django's own migrations.

```text
$ .venv/bin/python src/manage.py migrate
  Applying contenttypes.0001_initial... OK
  Applying auth.0001_initial... OK
  Applying admin.0001_initial... OK
  ...
  Applying sessions.0001_initial... OK
```

This proves the database address resolves, the database file can be created, and Django's own tables — users, permissions, sessions, admin history — can be built. It also proves the folder anchor is correct, because the file lands inside `src/`.

The fourth runs the test runner.

```text
$ .venv/bin/python src/manage.py test
Ran 0 tests in 0.000s

NO TESTS RAN
Found 0 test(s).
```

This proves the test runner is wired up and can discover the app. It proves nothing about behaviour, because no behaviour exists.

What no test covers yet, and why that is acceptable: the listing query, the published-only rule, alphabetical ordering, and the page-size limits all belong to the next change. Writing a test for them now would test nothing that exists.

---

*End of document.*
