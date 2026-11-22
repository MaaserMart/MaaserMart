# PR 20 — "Defects": settling the audit's ledger

- **PR:** [#20](https://github.com/MaaserMart/MaaserMart/pull/20) — `audit/04-defects` into `audit/03-charity-page-and-errors`
- **Size:** 31 files, 1560 added lines, 825 removed
- **Position in the stack:** fourth of five.
- **Commits:** `d7b3efc` — close the audit's defects: cache, CSP, seed password, loggers, tests; `2dc8911` — gate coverage at 85% and correct the README (T1, DOC1, DOC2); `917bca3` — record what happened to each audit finding; `f3fab90` — show `ADMIN_SEED_PASSWORD` in the example env (D-062).
- **Written for:** the reviewer working without the diff, and anyone who wants to know what these four commits are for.

---

## 1. Read this part even if you read nothing else

Earlier in this stack there was a **security-and-quality audit** of the project. Its report is
`docs/AUDIT-2026-11-17.md`, and it is a long list of claims: some defects, some performance
complaints, some smells, some gaps in the tests, some wrong statements in the README. Each claim has an
id — `B1`, `SEC2`, `P1`, `T3` — so anyone can point at one.

**This PR settles that ledger.** Every finding in that document gets one of three answers, and the
answer is written down in the audit document itself:

- **fixed** — the code changed, with a decision entry naming what was decided;
- **filed** — it is real, it is not being done now, and there is a filed task with the *trigger* that
  reopens it;
- **accepted** — a known risk with a date and the thing that will close it.

Nothing is left silently dropped. That is the single most important thing about this PR, and it is why
it looks so scattered: it touches thirty-one files because it is finishing thirty-ish separate
findings, not because it is one feature.

The four largest things in it:

**Performance.** The listing's sidebar reads two entire tables — every domain, every location — on
every single request, and did so six queries deep. That list now comes from a one-minute cache. The
page also stops blocking on a 50 KB script it does not use yet, production serves versioned asset names
so a deploy busts caches, and pagination gained first/last jumps and a count of how many charities
matched.

**Security.** Production now serves a Content-Security-Policy header and a one-year HSTS policy with
preload; `manage.py seed` no longer creates an `admin` account whose password is the word "admin"; and
a half-finished logging package is removed from the app instead of being paid for and never used.

**Cleanliness, of a specific kind.** Module loggers so a production error is not swallowed; a protocol
for the sidebar's option lists instead of an untyped parameter; one brand colour instead of two
almost-identical blues; factory defaults that are fixed rather than random (a random default in a
factory is a flaky test waiting for a bad day); and one focus ring site-wide.

**The test suite measuring itself.** Coverage is measured on every run and fails below 85% (it is ~93
today). Three tests that used a regex to find a CSS rule now parse the stylesheet the way a browser
resolves it. A 749-line test file became five files. Production settings are imported in a subprocess
and checked, because they are the one thing whose failure only appears at deploy time.

**Three things to look at before you approve**, all in section 5: the CSP allows images from *any*
`https` host while PR #18 restricted images to an allowlist (deliberate, and stated in the code — but it
is a gap between two defences); two decision entries cite a design-doc section that does not exist
(`§4.12 (security)` is the document's *Request Concurrency* chapter, and there is no security chapter at
all); and UC-03's "checks only for published charities" constraint is wired but switched off in every
view, which is D-042's deliberate choice and now visible because this PR is where the enforcement lands.

---

## 2. How to read this file

Three rules.

1. **Read the glossary first** (section 3). Every term is defined there before it is used.
2. **Every grey code box is optional.** The sentence above each box says the same thing in English.
3. **Each file section opens with a bold one-line summary.** Those lines are the change in twenty
   sentences.

This document explains; it does not grade. Section 6 lists where the code departs from the customer's
written design so you can decide what to do about each.

---

## 3. The glossary

| word | what it means here |
|---|---|
| **audit** | A separate pass over the finished code by someone looking for security holes, performance problems, smells, test gaps and documentation errors. Its report is a numbered list of findings. |
| **finding** | One item in that list, with an id (`B1`, `SEC2`, `P1`, `T3`…). |
| **disposition** | The answer recorded for one finding: fixed, filed, or accepted. |
| **CSP** (Content-Security-Policy) | A header the server sends with a page, telling the browser which sources of script, image, style and form submission are allowed. It is a second line of defence: if a page ever renders something it should not, the browser refuses to run it. |
| **HSTS** | A header telling browsers "only ever reach this site over an encrypted connection, and remember that". |
| **preload** | A list maintained outside this project: browsers are shipped with the list, so a site on it is *forced* to HTTPS even on the very first visit. Getting on it is a request; getting off it takes months. |
| **cache** | A copy of something expensive, kept somewhere cheap for a short while. |
| **TTL** (time to live) | How long a cached copy is allowed to be used before it is thrown away and rebuilt. Here: 60 seconds. |
| **LocMemCache** | Django's simplest cache: a dictionary inside the process. Each running copy of the app has its own, and it dies when the process does. |
| **defer** | An instruction on a `<script>` tag: "download this, but do not hold up the page for it". |
| **manifest storage** | A way of naming static files by a hash of their contents (`site.9f3a1c.css`), so a new deploy produces new names and no browser can serve a stale file. |
| **coverage** | The percentage of the application's lines that at least one test executes. |
| **subprocess** | A separate program run alongside the tests, so importing production settings there cannot contaminate the settings the tests themselves use. |
| **protocol** (in Python) | A description of the methods something must have, without saying what implements it. It is how a function says "give me anything that can answer these questions". |
| **logger** | The named channel a message is written to. A module logger means a message says which module produced it. |
| **factory** | Test code that builds a realistic row (`UserFactory`, `CharityFactory`). Its defaults are what most tests get for free. |
| **preload / OCSP / etc.** | (not used here) |

The plain words map onto the code like this:

| the code says | this document says |
|---|---|
| `CACHES`, `OPTIONS_TTL`, `_cached_options` | the one-minute copy of the sidebar's lists |
| `ContentSecurityPolicyMiddleware`, `SITE_POLICY` | the header production sends with each page |
| `SECURE_HSTS_PRELOAD`, `SECURE_HSTS_SECONDS` | the "always HTTPS" commitment |
| `ManifestStaticFilesStorage` | asset names that change with their contents |
| `ADMIN_SEED_PASSWORD`, `secrets.token_urlsafe` | the seed no longer makes a known admin password |
| `FilterOptionsRepository` (a Protocol) | the sidebar's "give me the option lists" contract |
| `logger.warning(...)` in `record_event` | the error is written down as well as raised |
| `--cov`, `fail_under` | the suite now reports and gates its own coverage |
| `tests/support/css.py` | a small CSS reader the tests use instead of a regex |
| `_import_prod()` | running the production settings in a separate process to check them |

---

## 4. The story

### 4.1 What an audit is, and what its ledger looks like

An audit is not a bug report. It is somebody reading the finished code the way a stranger would and
writing down everything suspicious, with an id and a severity. Some of it is a real hole; some is a
performance complaint; some is a smell; some is a wrong sentence in the README. Any of them could be
wrong, and the auditor says so where they are unsure.

The tempting response to a list like that is to fix the easy half and let the rest fade. The response
taken here is the harder one: **every id gets an answer, and the answer goes in the document.** The
table added at the end of `docs/AUDIT-2026-11-17.md` is that ledger. Its three verbs are the whole
design:

- *Fixed* — with the decision entry (`D-059`…`D-067`) and the place in the code.
- *Filed* — with a task number (#39, #40, #41, #42) and, in the decision entry, the **trigger** that
  reopens it. S1/S7 (three near-identical state modules) are filed with a trigger: "a fourth URL state,
  or the first 'form forgot an include' bug".
- *Accepted* — a risk with the reason it is tolerable now and the specific change that will close it.
  The only accepted one is SEC3: `/django-admin/`'s login has no lockout, and the accounts-login branch
  must add it there too (D-065).

That is why the diff looks like a hundred unrelated small edits. It is a ledger being settled.

### 4.2 Performance: reading less, on every request

The listing page's sidebar offers every domain and every location as checkboxes. Those two lists come
from two tables, in full, on **every request** — six queries per page view, two of them unbounded. On
the sample data that is a shrug; on a real Jewish-charity directory it is thousands of rows read for a
sidebar that changes about once a week.

The fix is a one-minute cache per list:

```python
    # How long an option list stays fresh. Short: options change rarely and the
    # cost of staleness is a checkbox appearing a minute late.
    OPTIONS_TTL = 60
```

The number is the entire decision. A minute is short enough that an admin adding a domain sees it
while working, and long enough that a busy page stops paying per request. D-061 records it, along with
three smaller performance decisions made in the same pass: the HTMX script is `defer`red (the page does
not wait for a 50 KB library nothing uses yet), production serves hash-named assets, and the pagination
gained first/last jumps and a total count.

One consequence to know about: **the cache lives inside each running copy of the app** (`LocMemCache`).
Five workers means five copies, each one up to a minute stale. That is fine for a sidebar; it would not
be fine for anything a visitor expects to change on the same screen, which is why D-061 says "no page
size, TTL or query strategy beyond this until a load test says otherwise".

### 4.3 Security: three separate things, of three different weights

**The header** (SEC1). Django has no setting for a Content-Security-Policy, so this PR adds a small
middleware that sets one on production pages:

```
default-src 'self'; img-src 'self' https:; base-uri 'none'; form-action 'self'; frame-ancestors 'none'
```

Read out loud, that says: scripts, styles and fonts come from this site only; images may be from this
site or any `https` address; no page may be put in a frame by another site; and forms may only post
back to this site. `/django-admin/` is exempted, because Django's own admin uses inline styles that the
policy would block — an admin that half-renders is worse than an admin without the header, and it is
staff-only behind a deliberate URL.

**The commitment** (SEC1's second half). HSTS tells browsers to refuse plain HTTP for a year, including
subdomains, and `preload` asks to be put on the shipped list. That is the one item in this PR that is
hard to walk back: preload removal takes months, and with subdomains included it applies to every
subdomain the project will ever have. D-062 makes the call and explains why one year is the minimum
that preload accepts.

**The password** (SEC4). `manage.py seed` created an admin account with the password `admin`. The
command already refuses to run on a non-empty database (D-030), so this was never going to land on a
real deployment — but a known admin password on a dev database that might be reachable from a café
laptop is the exact shape of an accident:

```python
        admin_password = settings.ADMIN_SEED_PASSWORD or secrets.token_urlsafe(18)
```

Either an explicit password from the environment, or 18 random bytes printed once. The other seeded
users keep `password`, because they are test fixtures (D-022) and the seed's job is to make them easy
to log in as.

**And a subtraction** (S9). `django-auditlog` was in the dependency list, in `INSTALLED_APPS` and in the
middleware stack — and not one model was registered with it, so it could never write a row. It created
migration surface and wrapped every request to produce nothing. D-063 removes it and says what brings
it back: the first `register(...)` call, in Phase 1.

### 4.4 Cleanliness: the small things that cost an hour later

Each of these is a finding the audit ranked low, fixed because it is cheap now:

- **Loggers (S2, S3).** Module-level loggers in the charity and event services, and a `logger.warning`
  in `record_event` next to the `ValueError` it raises. A raised error is invisible in production once
  the request is over; the log line is the trace.
- **A protocol for the sidebar (S5).** `FilterOptionsRepository` describes what the sidebar's service
  functions need: something that can produce domains, locations and rabbis. Before, the parameter was
  untyped, so a wrong object failed at the first attribute access instead of being a contract.
- **One brand colour (S6).** Two blues a few hex digits apart (`#1a4d8f`, `#1a4f8a`) became one
  `--brand-blue` custom property. The duplicate `.jump__input` rule went with it.
- **Fixed factory defaults (S8).** `ReviewFactory` gave every review a random rating and
  `HaskamaFactory` a random importance. A random default means a test that happens to pass today can
  fail on an unrelated commit tomorrow. They are now 5 and 5, with the reasoning in a comment.
- **The seed's test import (S2).** `from tests import factories` moved inside the command, so a
  production install that ships only `apps/` still imports.
- **Accessibility (A2, A4).** A disabled pagination step is a dimmed `<span>` again, not a `<span>` with
  `aria-disabled` — nothing can focus it, so announcing "dimmed" to a screen reader describes a control
  that does not exist. And every focusable control now has one visible focus ring, with a white variant
  on the blue current-page buttons where a blue ring would vanish.

### 4.5 The test suite, measuring itself

**Coverage (T1).** The suite now measures how much of `apps/` and `config/` it actually executes, prints
the uncovered lines, and **fails under 85%**. It sits at ~93 today, so the gate is a floor rather than a
target: it catches a change that adds a branch nobody exercises. Generated migrations are excluded,
because generated code is not behaviour.

**CSS tests that meant what they said (T2).** Three tests asserted that a rule *appears* in `site.css`
— by regex. A regex is satisfied by a rule that a later block overrides, or one whose selector was
swallowed into a list, or one whose class never appears on the page. They now go through a small
stylesheet reader (`tests/support/css.py`) that merges blocks in source order, so "the last value wins"
is answered the way a browser answers it:

```python
def value(css: str, selector: str, prop: str) -> str | None:
    """The final value of one property for one selector, or None if unset."""
    return declarations(css, selector).get(prop)
```

and one test now also asserts the sidebar's class is actually on the rendered page — because a rule for
a class nobody uses proves nothing. Media queries are deliberately not evaluated; the reader ignores
them rather than guessing, and D-066 says a real browser is the only full check and there is none in
the suite.

**One file becomes five (T3).** `tests/unit/test_views.py` was 749 lines covering five features. It is
now `test_views_listing.py` (21 tests), `test_views_sort.py` (11), `test_views_filter.py` (22),
`test_views_clamp.py` (3) and `test_views_search.py` (19), and the old path keeps a docstring saying
where each went — so a reader who lands there is not lost and a reviewer's muscle memory still works.

**Production settings, actually run (T4).** Every other test runs against `config/settings/test.py`.
The production settings are the ones whose failure appears only at deploy time, so they are imported in
a **subprocess** with a controlled environment, and five facts are asserted: a real secret imports, a
short secret refuses, a development secret refuses, no allowed hosts refuses, and the header/HSTS/asset
settings are what the deploy actually gets. The Celery app is checked in the same file, because
`config/__init__.py` imports it and a bad name there breaks every management command.

### 4.6 The documentation catching up

The README told you to clone a personal fork (`BenjaminYazdi/MaaserMart`), documented a `per_page`
parameter that has never existed in the code, described the listing in four modules when it is now
seven, and told you the admin password was `admin`. All four are fixed, and the module map now names
`filters.py`, `sorting.py` and `search.py` as what they are.

### 4.7 What settled, in one sentence

Every finding in the audit now has a recorded answer; the sidebar stops reading whole tables per
request; production sends a CSP and a year of HSTS; the seed stops shipping a known admin password; a
package that could never write a row is gone; a dozen small smells are fixed at the root; and the test
suite measures itself, reads CSS properly and runs the production settings for real.

---

## 5. Contradictions — places where code and documents disagree

### 5.1 Two decision entries cite a design-doc section that is not about security

D-062 ("Production ships a CSP and HSTS preload; the seed admin password is never public") and D-065
("`django-admin/`'s login is accepted without a lockout") both say:

> Design doc ref: §4.12 (security)

The design document's chapter 4 is its technical-decision chapter, and §4.12 is **Request Concurrency**
— Gunicorn workers versus async, with no security content. §4.15 is Logging; nothing in chapter 4 is a
security chapter, and the document has none anywhere: no CSP, no HSTS, no lockout, no password policy.
(D-063 also cites `§4.15.1.2`, a sub-heading that does not exist; §4.15 has only a decision and its
alternatives.)

So these decisions are not applying the customer's document; they are **adding security commitments the
document never asked for**. That is defensible — a payments-adjacent site needs them — but the citation
makes it look like the document required them, and a later reader will go looking and find a section
about worker counts. Worth correcting the two reference lines, and worth knowing that CSP and preload
are new promises rather than compliance.

### 5.2 The CSP is looser than the image rule it is supposed to back up

PR #18 restricted a charity's image to a repo path or a host on `CHARITY_IMAGE_HOSTS`, and the template
refuses anything else at read time. The new header, though, says `img-src 'self' https:` — any `https`
address at all. The middleware's own comment is honest about the gap:

> the header allows any https image as a backstop only because hosts change with the setting and the
> pixel is harmless next to a validation that already ran.

That reasoning is sound for *images*: a tracking pixel is a privacy nuisance, not an execution risk, and
a per-host policy in the header would have to be rebuilt from settings on every request. But it means
the two defences do not reinforce each other; if the validation is ever bypassed, the header will allow
the image. If you want them aligned, `img-src` can be built from `CHARITY_IMAGE_HOSTS` in the
middleware — the cost is that changing the setting requires a deploy or a settings reload, which it
already does.

### 5.3 The preload commitment is asymmetric and the site is not live

HSTS with `preload` and `includeSubDomains` on, at a one-year max-age, is a promise the *browser*
enforces for a year, and the preload list makes it much longer. Two facts worth weighing before this
lands on a real domain:

- the domain does not exist yet, so this is being decided at the cheapest possible moment — which is
  exactly when it should be decided, and also means nobody has tested that the deploy really serves
  HTTPS on every hostname it will use;
- it applies to *all* subdomains forever-ish. A future `staging.maasermart.com` served over plain HTTP
  on an internal network will not load in a preloaded browser.

Both are D-062's call, made consciously ("Preload is a commitment (hard to leave)"). Flagged because a
reviewer should see the one-way door before it is walked through, not after.

### 5.4 A decision entry points at a decision id that does not exist

D-065 says the accounts-login branch's rate-limit middleware — identified as `D-YOSEF-accounts-login` —
must also cover `/django-admin/login/`. That identifier is not in `docs/DECISIONS.md` and does not
follow the file's `D-NNN` convention. It reads as a placeholder for a decision someone else will write.
Harmless today; a dangling pointer the moment somebody greps for it.

### 5.5 The disposition table's "fixed" for B1/S4 relies on a test in another PR

The ledger row reads "Fixed: the nav is built from URL patterns (D-060); a test requests every nav
href". Both halves are already true in this stack — D-060's nav processor landed in PR #19 — so the
ledger is accurate about the branch as a whole. If you are reviewing PR #20 *on its own*, note that the
commit it describes is one PR down the stack, not in this diff. The ledger is written for the branch,
not for the PR boundary, and says so in its heading ("branch `audit-fixes`").

### 5.6 UC-03 says the listing "checks only for published charities"; it does not, on purpose

UC-03's Implementation Constraints, quoted from the customer's document:

> Full page loads (so back works), **everything is stored in URL parameters, checks only for published
> charities**, uses Django's annotate, parameters are clamped, case-insensitive search.

Two of those six are honoured completely (URL parameters, clamping) and one is honoured in shape only.
The listing and the charity page pass `published_only=False`, so an unpublished charity is shown to any
visitor who reaches it. The reason is D-042 and it is a good one: nothing in the application publishes a
charity yet, so enforcing the flag today would make the site look empty. That decision also flipped the
default — the repository filters `is_visible` when it is *asked* to, rather than filtering by default and
letting a caller opt out.

So a reader comparing the docx to the site will see the opposite of what the document says, and this PR
is where that became visible (D-059 wired the enforcement and left every caller switched off). Worth a
sentence in the PR body or the decision entry: *"UC-03's published-only check is wired and off until the
approval queue publishes; D-042 is the reason."* It is already recorded as D-042 and D-059 — it just is
not obvious from either entry that the document's own constraint is currently unmet.

---

## 6. Departures from the design document

### 6.D1 django-auditlog leaves the stack the document names

- **Document says:** §4.15, "We will use django-auditlog, which saves logs automatically whenever a
  change is made [17]", and the deployment summary table that lists the whole stack names it too
  ("Audit Logging — django-auditlog").
- **Code does:** the package is removed from `pyproject.toml`, `INSTALLED_APPS` and `MIDDLEWARE`.
- **Why:** no model was ever registered with it, so it could not write a row; it was paying migration
  surface and a per-request middleware for a plan.
- **Judged:** D-063 (Active). The document's intent — an audit trail of who changed what — is currently
  served by the events table (D-052) for charity changes; auditlog returns when a model registers.
- **Reversible in:** one dependency line, two settings lines, one `register()` call. Cheap — which is
  why removing it now is not throwing work away.

### 6.D2 Security headers and HTTPS enforcement are new commitments

- **Document says:** nothing. There is no security chapter; CSP, HSTS and lockout appear nowhere in it.
- **Code does:** production serves a CSP (`default-src 'self'; img-src 'self' https:; base-uri 'none';
  form-action 'self'; frame-ancestors 'none'`), a one-year HSTS with `includeSubDomains` and `preload`.
- **Why:** the audit named the absence (SEC1), and the site handles donation-adjacent data.
- **Judged:** D-062 (Active). These are additions, not compliance — see 5.1.
- **Reversible in:** the CSP is two lines in `prod.py` plus a middleware file; HSTS is one setting and,
  once submitted to the preload list, months of patience.

### 6.D3 The listing gains a total and first/last jump links

- **Document says:** §6.2.3 describes the listing with a page of charities and pagination; it names
  `page` and `per_page` and nothing about jump links or a result count.
- **Code does:** a line above the list — "200 charities" — and "« 1" / "last »" jump links that appear
  only when the current page is far from that edge (more than three pages in, more than two from the
  end).
- **Why:** with hundreds of charities, "next" forty times is not navigation (audit P5), and a visitor
  cannot tell a filtered page from an empty dataset without a count.
- **Judged:** D-061 (Active). A UI addition the document does not describe; easily removed.
- **Reversible in:** two `{% if %}` blocks in the template and four properties on `Page`.

### 6.D4 A new domain or location may take up to a minute to appear

- **Document says:** the sidebar offers the domain and location lists (§5.2.10–11, §6.2.4) — no
  statement about freshness.
- **Code does:** those two lists are cached for 60 seconds per process. A newly added domain can be
  missing from the sidebar for up to a minute (and, with several workers, up to a minute per worker).
- **Why:** they were being read in full on every request (audit P1).
- **Judged:** D-061. A freshness window nobody has complained about, on data that changes rarely.
- **Reversible in:** `OPTIONS_TTL` — set to 0 or remove the two `_cached_options` calls.

### 6.D5 `is_visible` is enforced at read time, while every view still asks for everything

- **Document says:** `CHARITY.is_visible` exists (§5.2.1) and unpublished charities should not be shown
  to visitors.
- **Code does:** the repository now filters `is_visible=True` whenever it is told to publish only — for
  both the listing and the charity page — **and every view passes `published_only=False`**, so nothing
  is filtered today.
- **Why:** wiring the enforcement while the flag still reads False is the cheap version; when the
  approval queue starts publishing, the flip is one view argument (D-042). Passing `True` today would
  make the site empty, because nothing publishes yet.
- **Judged:** D-059 (Active), and it answers audit Q2: when the flag flips, filters, search and sort read
  published charities only.
- **Reversible in:** one argument per view. That is the whole point of putting it in the repository.

### 6.D6 The seed's admin password is generated, not documented

- **Document says:** the design document does not describe the seed command at all (it is dev tooling).
  The README did say `admin` / `admin`.
- **Code does:** a random password printed once, or `ADMIN_SEED_PASSWORD` from the environment.
- **Why:** a known admin credential on a local box that may be reachable (SEC4).
- **Judged:** D-062. Not a design-document departure — a README correction, which this PR makes.
- **Reversible in:** set `ADMIN_SEED_PASSWORD` in `.env` if you want a memorable local login.

### 6.D7 The document's `per_page` parameter is `page_size` in the code

- **Document says:** "The page number is a `page=` attribute and the amount per page is `per_page=`"
  (§6.2.3).
- **Code does:** `page_size`, everywhere.
- **Why:** pre-existing (the parameter was named in the listing work); the README documented the
  document's name rather than the code's, which is audit finding DOC2.
- **Judged:** not recorded as its own decision — the code has been `page_size` since the listing
  landed. This PR fixes the README to describe the code. Either the rename is undone or the document is
  simply out of date; today the site and the README agree, and only the docx disagrees.
- **Reversible in:** a query-string alias if old links matter (they do not — the site is not live).

### Not departures, though they may look like it

- **The result count comes from a window over the page's own query, and only falls back to a separate
  count for a page past the end.** D-061 and B3: the total and the rows are one read, so a row written
  between them cannot make a charity repeat or vanish; the fallback exists because a page past the end
  returns no rows, and the view needs the total to clamp it.
- **The `@media` rules are ignored by the CSS test helper.** That is a testing limitation stated in the
  helper's docstring, not a behaviour of the site.
- **Django admin keeps its own login.** D-008's deliberate URL, unchanged here.
- **`page_size` still has a cap.** Unchanged from the listing PR.

---

## 7. Reading order

Read in this order; each row is a file and why it is in this PR.

| # | file | why it changed | size |
|---|---|---|---|
| 1 | `docs/AUDIT-2026-11-17.md` | the ledger: every finding, answered | +31 |
| 2 | `docs/DECISIONS.md` | D-059 … D-067, nine decisions | +89, −2 |
| 3 | `config/settings/base.py` | cache, seed password setting, auditlog out | +17, −6 |
| 4 | `config/settings/prod.py` | CSP, HSTS, hashed assets | +20, −2 |
| 5 | `apps/support/middleware.py` | the CSP header | +42 |
| 6 | `apps/charities/repositories.py` | option cache, options protocol, read-time `is_visible` | +59, −5 |
| 7 | `apps/charities/services.py` | page-jump properties, logger, typed option lists | +32, −2 |
| 8 | `apps/events/services.py` | a logger next to the raised error | +10 |
| 9 | `apps/charities/templates/charities/listing.html` | total, jumps, honest disabled steps | +15, −4 |
| 10 | `templates/base.html` | defer the unused script | +1, −2 |
| 11 | `apps/dashboards/management/commands/seed.py` | no more `admin`/`admin`; lazy test import | +25, −6 |
| 12 | `static/css/site.css` | one brand colour, one focus ring | +58, −14 |
| 13 | `pyproject.toml` | auditlog out, coverage gate in | +15, −2 |
| 14 | `.env.example` | the seed password option | +4 |
| 15 | `tests/conftest.py` | a cold cache for every test | +19 |
| 16 | `tests/factories/charities.py` | fixed, not random, defaults | +6, −2 |
| 17 | `tests/support/css.py` | the stylesheet reader | +85 |
| 18 | `tests/unit/test_css_helper.py` | the reader's own tests | +55 |
| 19 | `tests/unit/test_prod_settings.py` | production settings run in a subprocess | +111 |
| 20 | `tests/unit/test_views*.py` | one 749-line file becomes five | split |
| 21 | `README.md` | clone URL, `page_size`, module map, seed password | +21, −8 |

---

## 8. The files, one at a time

### 8.1 `docs/AUDIT-2026-11-17.md` — the ledger, settled (+31)

The whole PR's purpose in one table. New section heading: "Disposition (2026-11-17, branch
`audit-fixes`)". Every finding id gets one row:

| ID | Disposition |
| --- | --- |
| B1, S4 | Fixed: the nav is built from URL patterns (D-060); a test requests every nav href |
| B2, B7 | Fixed: the admin publishes what it adds and refuses an unapplied field |
| B3, P5 | Fixed: page and count come from one query; first/last jumps and a result count |
| B4, B5, B9 | Fixed: each group's clamp is its own, the term is capped, repeated `q` keeps the last |
| B6, B8 | Fixed: a bad FK is a named `ValueError`; an image must be static or an allowlisted host |
| D1-D6 | Fixed: D-055's migration (review uniqueness, indexes, ledger rules, real batch ids) |
| M1, M2, M7 | Out of scope: whole features (the other apps, the remaining 24 services). Not this audit |
| M3, M4, M5, M9 | Fixed: the charity page, its view/click events, read-time `is_visible`, hidden events |
| M6, Q3 | Fixed: `search_rabbis` exists; the Haskamos filter uses user ids (D-058) |
| M8 | Fixed: 403/404/500 templates extend `base.html` |
| P1-P3, P4 | Fixed: option cache, deferred HTMX, manifest storage; P4's remaining cost is its indexes (D-055) plus the deferred summary-row decision |
| S1, S7 | Filed (#39): deliberate deferral with a trigger, recorded as D-067 |
| S2, S3, S5, S6, S8, S9 | Fixed: D-063, D-064 |
| SEC1, SEC2, SEC4 | Fixed: D-062 |
| SEC3 | Accepted risk, recorded as D-065 and filed (#41) so the login middleware absorbs it |
| A1-A4 | Fixed: D-060, D-064 |
| T1-T3 | Fixed: D-066 |
| T4 | Fixed: `tests/unit/test_prod_settings.py` imports the production settings in a subprocess |
| DOC1, DOC2 | Fixed: README clone URL, `page_size`, module map, seed password |
| DOC3 | Fixed before the fix pass as D-057 (`/charity/<id>/`) |
| DOC4, Q1 | Filed (#40): needs a human answer about the apex host |
| Q2 | Answered in D-059 |
| Q4 | Filed (#42): needs a Postgres extension decision |

The `filed` rows carry a task number and the trigger that reopens them; the `accepted` row carries the
reason and the future change that closes it. This is the document a reviewer should read *after* the
code, to check each answer matches what they just read.

### 8.2 `docs/DECISIONS.md` — nine decisions, one per cluster (+89, −2)

D-059 to D-067, each in the file's standard shape. The ones worth a reviewer's time, beyond what
section 4 covered:

- **D-059** answers audit Q2 out loud: when `is_visible` flips, filters/search/sort read *published*
  charities only, "because D-042's wording is about what a visitor may see, not a separate analytics
  channel". That is a policy sentence someone had to say before writing the filter code.
- **D-067** is the honest *no*: the three state modules stay separate, with the trigger to revisit. It is
  the difference between a decision and a lost note.
- **D-065** records the accepted risk and names the future middleware that closes it — see 5.4 for its
  one flaw.

### 8.3 `config/settings/base.py` — cache, seed password, auditlog out (+17, −6)

Three unrelated edits. The cache is the biggest:

```python
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "maasermart",
    }
}
```

The comment above it says the point plainly: "a multi-megabyte directory is read once a minute per
worker instead of once per page. The cache never stores users." The seed password and the auditlog
removal are each one line with a comment explaining the *why*:

```python
ADMIN_SEED_PASSWORD = env("ADMIN_SEED_PASSWORD", default="")
```

(an empty default means "generate one", and the seed decides).

### 8.4 `config/settings/prod.py` — the production hardening (+20, −2)

The middleware is appended only here, so a local run is untouched by it, and the HSTS default becomes a
year with preload on:

```python
MIDDLEWARE.append("apps.support.middleware.ContentSecurityPolicyMiddleware")
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; img-src 'self' https:; base-uri 'none'; "
    "form-action 'self'; frame-ancestors 'none'"
)
```

```python
SECURE_HSTS_SECONDS = env.int("DJANGO_SECURE_HSTS_SECONDS", default=60 * 60 * 24 * 365)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
```

The static-files backend is new, and needs `collectstatic` at deploy time (the comment says Caddy serves
`STATIC_ROOT`, which is already the production story):

```python
STORAGES = {
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage",
    }
}
```

### 8.5 `apps/support/middleware.py` — the CSP header (+42)

A small middleware that adds the header after the page is rendered, unless the path is one of the
exempted ones:

```python
class ContentSecurityPolicyMiddleware:
    """Add the CSP header to ordinary pages, unless a path opts out."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        policy = getattr(settings, "CONTENT_SECURITY_POLICY", None)
        if not policy:
            return response
        if any(request.path.startswith(prefix) for prefix in NO_POLICY_PREFIXES):
            return response
        response.headers["Content-Security-Policy"] = policy
        return response
```

The docstring makes the site's own claim about why this is safe: the templates are CSP-friendly (no
inline handlers; every script and style is a same-origin file), so `default-src 'self'` "costs nothing
and would have been the second line of defence behind write-side image validation (D-056)". The
`NO_POLICY_PREFIXES` tuple is why the admin still works.

### 8.6 `apps/charities/repositories.py` — cache, protocol, read-time flag (+59, −5)

**The cache**, one helper used twice:

```python
    def _cached_options(self, key: str, load) -> tuple:
        options = cache.get(key)
        if options is None:
            options = tuple(load())
            cache.set(key, options, self.OPTIONS_TTL)
        return options
```

`domains()` and `locations()` both go through it; `rabbis()` does not — "Rabbis, being people, are
never cached", the class docstring says. The rabbit-hole test (P1) asserts the second call makes zero
queries.

**The protocol**, so the sidebar's service functions take a contract rather than an untyped object:

```python
class FilterOptionsRepository(Protocol):
    """The sidebar's option lists, as the page-building code sees them.
    ...
    """

    def domains(self) -> tuple[DomainOption, ...]: ...
```

**Read-time `is_visible`**, the D-059 enforcement — two lines, in `detail`:

```python
        rows = self._annotated(reviews=True, approving=True, disapproving=True)
        if self.published_only:
            rows = rows.filter(is_visible=True)
```

The listing's row source gets the same guard. It does nothing today because every view passes
`published_only=False` — which is the point: D-059 says the enforcement exists now so the flag can flip
later with one argument.

### 8.7 `apps/charities/services.py` — jump links, a logger, typed options (+32, −2)

The pagination jumps are four properties, each one reading as English:

```python
    @property
    def can_jump_to_first(self) -> bool:
        """Whether the first page is far enough to warrant a jump link (P5)."""
        return self.number > 3
```

```python
    @property
    def last_query(self) -> str:
        """The last page of this same result set, for a jump link (audit P5)."""
        return self.query(self.page_count)
```

`can_jump_to_first` uses a threshold of 3, D-061's named "jump threshold of 3"; a page is not worth
jumping from unless it is far enough away that the jump is actually shorter. The logger is one line at
the top of `update_charity`'s rejection path, and `list_domains`/`list_locations` are retyped to the new
protocol.

### 8.8 `apps/events/services.py` — the error is written down (+10)

A `logger.warning` next to the `ValueError` that `record_event` raises:

```python
    except IntegrityError as error:
        logger.warning(
            "record_event rejected: charity_id=%s action=%s link_id=%s user_id=%s",
            charity_id,
            action,
            link_id,
            user_id,
        )
        raise ValueError(...) from error
```

The raise is the contract; the log line is the trace. One without the other would be a 500 with no
record.

### 8.9 `apps/charities/templates/charities/listing.html` — the total and the jumps (+15, −4)

The count above the list:

```html
        {% if page.total %}
          <p class="listing__total">{{ page.total }} charit{{ page.total|pluralize:"y,ies" }}</p>
        {% endif %}
```

(`pluralize:"y,ies"` is Django's way of handling "charity"/"charities", and `{{ page.total }}` is the
one-snapshot total from 8.6's window count.) The jump links, guarded by the two `can_jump_to_*`
properties:

```html
            {% if page.can_jump_to_first %}
              <a class="pagination__step" href="?{{ page.first_query }}" aria-label="First page">&laquo; 1</a>
            {% endif %}
```

and the disabled steps stop claiming to be controls (A2):

```html
-              <span class="pagination__step" aria-disabled="true">&larr; Prev</span>
+              {# A disabled step is not a control: the dimmed span says enough (A2). #}
+              <span class="pagination__step pagination__step--disabled">&larr; Prev</span>
```

### 8.10 `templates/base.html` — one attribute changed, and why (+1, −2)

```html
-  <script src="{% static 'vendor/htmx-2.0.4.min.js' %}"></script>
+  {# Htmx is unused today; `defer` keeps it from blocking first paint (P2). #}
+  <script defer src="{% static 'vendor/htmx-2.0.4.min.js' %}"></script>
```

A 50 KB library with no `hx-` attribute anywhere no longer blocks the page. The Alpine script was
already deferred.

### 8.11 `apps/dashboards/management/commands/seed.py` — no known admin password, lazy import (+25, −6)

```python
        admin_password = settings.ADMIN_SEED_PASSWORD or secrets.token_urlsafe(18)
        self.rng = random.Random(613)
        factory.random.reseed_random(613)
```

and the print line now names the actual password once. The `tests` import moves inside the command, so a
production artifact that ships only `apps/` still imports the command cleanly:

```python
    def seed(self, admin_password):
        from tests import factories as f
```

The seed's `self.stdout` block still prints `DEFAULT_PASSWORD` for the other users — but that import now
happens after `seed()` runs, keeping the lazy boundary.

### 8.12 `static/css/site.css` — one colour, one ring (+58, −14)

The brand colour is defined once and everything draws from it:

```css
:root {
  --brand-blue: #1a4d8f;
}
```

The old two blues (`#1a4d8f`, `#1a4f8a`) both became `var(--brand-blue)`. The focus ring is one rule
site-wide, with a white variant for the blue current states:

```css
:focus-visible {
  outline: 2px solid var(--brand-blue);
  outline-offset: 2px;
}

.sort__direction--current:focus-visible,
.pagination__page--current:focus-visible {
  outline-color: #fff;
  outline-offset: -2px;
}
```

### 8.13 `pyproject.toml` + `.env.example` — the gate, and the option it documents (+15, −2 / +4)

Coverage is measured on every run and gated in the same file, so CI and a laptop agree:

```toml
[tool.pytest.ini_options]
addopts = "--ds=config.settings.test --cov=apps --cov=config --cov-report=term-missing:skip-covered"
testpaths = ["tests"]

[tool.coverage.report]
fail_under = 85
skip_covered = true
```

`auditlog` leaves `dependencies`, `pytest-cov` joins `dev`. `.env.example` documents the new seed option
with its two behaviours.

### 8.14 `tests/conftest.py` — every test starts cold (+19)

```python
@pytest.fixture(autouse=True)
def _empty_cache():
    """Every test starts with a cold cache.
    ...
    """
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()
```

Without this, the one-minute cache would outlive a test's transaction: a domain created in one test
would be invisible to the next, and tests that never touch the cache would run on another test's
leftovers. An `autouse` fixture is exactly the right shape for "the suite's assumptions", and its
docstring says the trap it exists for.

### 8.15 `tests/factories/charities.py` — fixed, not random, defaults (+6, −2)

```python
-    rating = factory.Faker("random_int", min=1, max=5)
+    # S8: factories keep obvious, fixed defaults; a review is a positive review.
+    rating = 5
```

A random default in a factory means a test's *setup* can be nondeterministic — the failure it causes is
a week later and unrelated. A fixed default, with the reasoning in a comment, is boring on purpose.

### 8.16 `tests/support/css.py` + `tests/unit/test_css_helper.py` — reading CSS for real (+85 / +55)

The helper's job, from its docstring: *"This helper answers the two questions a regex cannot: what is
the final value of a property for one selector, and is that selector actually used by the page being
tested."* It strips comments, drops `@media` blocks it cannot evaluate, splits selectors out of lists,
and merges declarations in source order so a later block wins — which is how a browser resolves
same-specificity rules. Its own tests exercise exactly the failure modes it exists for:

```python
def test_a_later_block_overrides_an_earlier_one():
    assert value(CSS, ".nav", "position") == "sticky"
    assert value(CSS, ".nav", "padding") == "1rem"


def test_a_media_query_does_not_answer_for_the_unconditional_rule():
    # The mobile override says `static`; the page's own rule is what is asked for.
    assert value(CSS, ".nav", "position") != "static"
```

D-066 states the honest boundary: media queries and specificity are still not evaluated, and a DOM
measurement is the only full check — there is no browser in the test suite.

### 8.17 `tests/unit/test_prod_settings.py` — the deploy-time guard (+111)

The one place a broken production setting shows up before a deploy, run in a subprocess so importing it
cannot leak into the suite's own settings:

```python
def _import_prod(**overrides) -> subprocess.CompletedProcess:
    """Import `config.settings.prod` in a clean interpreter and report the result."""
    env = {key: value for key, value in os.environ.items() if not key.startswith("DJANGO_")}
    env["DJANGO_LOG_DIR"] = str(BASE_DIR / "logs")
    env.update(GOOD_ENV)
    env.update(overrides)
    return subprocess.run(
        [sys.executable, "-c", "import config.settings.prod"],
        cwd=BASE_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
```

Five imports are checked (good secret, short secret, development secret, missing hosts — and the
lucky path), plus one test that prints the CSP/HSTS/middleware/asset facts and asserts them. The Celery
app is asserted in the same file (`app.main == "maasermart"`, eager tasks from the test settings, and
no tasks defined yet — "the audit's M7 list is where the first one lands").

### 8.18 `tests/unit/test_views.py` — one file becomes five (split)

The old file now exists to say where it went:

```python
"""Black-box page contracts for the listing (design doc §6.2.x).

Five page features used to live in this one 752-line file (audit T3); they now
live next door:

- `test_views_listing.py` — the page, the page size and the pagination
- `test_views_sort.py` — ordering by name, rating, activity and recency
- `test_views_filter.py` — domains, locations, rabbis and the clear link
- `test_views_clamp.py` — out-of-range numbers are clamped visibly (D-046)
- `test_views_search.py` — the tracer-bullet search (D-050)
"""
```

The docstring (and D-066) says 752 lines; the file it replaced is 749. Trivial, and noted only so a
reader who counts does not think they are looking at a different commit.

### 8.19 `README.md` — the setup story corrected (+21, −8)

Four corrections, each the answer to a finding: the clone URL is the organisation's, not a personal
fork (DOC1); the parameter is `page_size` and the module map names seven modules, not four (DOC2); and
the admin password sentence now describes the seed as it behaves:

> The admin is at http://localhost:8000/django-admin/: log in as `admin` with the random password
> `seed` printed when it ran (D-062), or set `ADMIN_SEED_PASSWORD` before seeding.

---

## 9. The tests

Read the names as sentences. This PR is partly *about* tests, so the list matters more than usual.

**The new guards this PR adds**

- `test_the_option_lists_are_read_once_a_minute` (P1) — counts queries, so a future edit that drops the
  cache fails loudly:

  ```python
          with self.assertNumQueries(1):
              options.domains()
          with self.assertNumQueries(0):
              options.domains()
  ```

- `test_prod_settings_import_with_a_real_secret`, `test_prod_settings_refuse_a_development_secret`,
  `test_prod_settings_refuse_a_short_secret`, `test_prod_settings_refuse_no_allowed_hosts` — the four
  ways a deploy either boots with a development secret or refuses to boot for no reason.
- `test_prod_serves_a_csp_and_preload_hsts` — asserts the header's first directive, a max-age of at
  least a year, preload on, the middleware in the list, and the manifest storage backend. This is the
  test that would have caught "the CSP was configured but never appended in prod".
- `test_the_celery_app_is_configured_and_discovers_no_tasks_yet` — because `config/__init__.py` imports
  it, a bad name breaks every management command.
- `test_a_later_block_overrides_an_earlier_one`, `test_a_selector_inside_a_list_still_applies`,
  `test_a_media_query_does_not_answer_for_the_unconditional_rule`,
  `test_a_missing_selector_or_property_is_none`, `test_comments_are_not_mistaken_for_rules` — the CSS
  reader's own tests, one per way a regex lies.
- `test_the_sidebar_class_is_on_the_page` — the rule above only matters if an element carries the class.

**The tests that changed shape rather than substance**

- `test_nav_is_pinned_to_the_top` now asks the stylesheet `value(css, ".nav", "position") == "sticky"`
  instead of matching a regex, with the reason in the docstring: *"a later block overriding `position`
  would fail this test, where a regex for the declaration would pass."*
- The sidebar's contract test now asserts `max-height`, `overflow-y: auto` **and** `position: sticky`
  through `declarations(...)`, plus the class being on the page.
- The 76 tests of `test_views.py` are unchanged in behaviour and redistributed across five files
  (21 + 11 + 22 + 3 + 19). Nothing was dropped: the counts add up and the names are the same ones.

**What the suite proves that it did not before**

Coverage now fails the build under 85%, which is not a test but a gate. Its first effect is visible in
this PR's own diff: the split, the CSS helper and the production-settings tests exist partly because the
gate made the uncovered surfaces visible.

---

## 10. The audit

The Dilbert test run against the finished document, and the two-layer check.

**Where he would have fallen off, and what was fixed:**

- **"audit"** is the word the whole document rests on and it is not a term a lay reader owns. It is the
  first glossary row, and section 1 states it in one sentence before any finding id appears. — fixed.
- **"finding id" (`B1`, `SEC2`, `P1`, `T3`)** would have been noise. Section 1 says what an id is ("so
  anyone can point at one"), and the ledger table in 8.1 is introduced as *the document a reviewer reads
  after the code*. — fixed.
- **"CSP"** is defined before it is used, in the glossary and again in plain words in 4.3: *"scripts,
  styles and fonts come from this site only; images may be from this site or any https address…"* —
  fixed. This is the single most important definition in the document, because two of the review points
  in section 5 depend on understanding what the header does and does not cover.
- **"HSTS preload"** would have been opaque. 4.3 explains the browser-side consequence (*refuse plain
  HTTP for a year*) and the one-way door (getting off the list takes months) before 5.3 asks him to weigh
  it. — fixed.
- **"cache" and "TTL"** are defined together, and 4.2 gives the concrete numbers (two tables, six
  queries, sixty seconds) rather than the word alone. — fixed.
- **"coverage"** — 4.5 says what it counts ("the percentage of the application's lines that at least one
  test executes") and what the gate does, before the config box appears. — fixed.
- **"subprocess"** — defined in the glossary and then explained by its *purpose* in 4.5 ("so importing
  production settings there cannot contaminate the settings the tests themselves use"). — fixed.
- **One paragraph in 4.4 listed six fixes as a wall.** It is now six bullets, one line each. — fixed.
- **Arithmetic checked:** 60 seconds, 85% versus ~93 today, one year (`60 * 60 * 24 * 365`), 749 lines
  into 21+11+22+3+19, 18 random bytes, threshold 3 for the first jump, 2 for the last. Every number in
  the document appears in the code.

**Every code box has an English sentence directly above it.** Walked: the TTL constant, the ledger
table, the two prod settings blocks, the middleware class, `_cached_options`, the protocol, the
`is_visible` guard, the two `Page` properties, the `record_event` logger, the count and jump template
lines, the disabled-step change, the `defer` line, the seed password line and the lazy import, the CSS
custom property and focus ring, the pyproject block, the conftest fixture, the factory default, the CSS
helper's `value` function and its two tests, `_import_prod`, the test-file docstring, the README quote,
and the two query-count assertions. All covered.

**The two-layer check.**

- *Delete every code box.* The document still contains: what an audit is and what a disposition is; the
  three verbs of the ledger; the performance story (two whole tables per request); the three security
  moves and their weights; six cleanliness items; the test suite measuring and correcting itself; four
  contradictions with the document quoted; seven departures with judgement and reversal cost; a reading
  order; twenty file sections in plain English; and the tests read as sentences. It stands.
- *Read only the code boxes.* The whole change is visible: the cache and its TTL, the CSP string and the
  middleware, the HSTS values, the asset storage, the option protocol, the read-time flag, the two jump
  properties, the log line, the template additions, the `defer`, the random seed password, the one brand
  colour, the coverage config, the cold-cache fixture, the CSS reader, the subprocess import, the split
  map, and the README's admin sentence. A reviewer could approve from the boxes. It stands.

**Where he still cannot follow, and why that is acceptable:** `img-src 'self' https:` inside the policy
string. The directive names are a mini-language; 4.3 reads the whole header out loud in English directly
above the box, and 5.2 explains the one gap in that sentence. He never needs to parse the string — he
needs to know that "any https image" is looser than "our allowlist", which 5.2 says in words.

**Bottom line:** the document can be reviewed from, and it explains itself. It does not grade. The
judgement calls it hands back to you are: the CSP's image gap (5.2), the one-way HSTS commitment (5.3),
the two decision entries citing a design-doc section that is about concurrency (5.1), the dangling
`D-YOSEF-accounts-login` id (5.4), and UC-03's published-only constraint being unmet (5.6).
