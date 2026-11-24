# PR #30 — The maaser tools: income, donations, and the calculator

- Branch: `tools/maaser` → `main`
- Merge commit: `7551cdb` (2026-11-24)
- Author: Platform Lead (Shaul)
- Decision recorded: D-074
- Size: 14 files, +732 / −5

---

## 1. Read this part even if you read nothing else

Some Jewish households give a tenth of their income to charity. The tenth is called
**maaser**. It is the feature this website is named after, and these four pages are
where a member keeps the books for it.

The idea is exactly a pocket ledger. When money comes in, you write it down:
"salary, 800". When you give to a charity, you write the donation down too:
"Tomchei Shabbos, 18". At any moment the site can answer the one question that
matters: **how much maaser do I still owe?** — because the answer is one tenth of
everything written down as income, minus everything written down as given.

There are four pages. **Tools** is the front door: it answers the question and
links onward. **Calculator** shows the working, line by line. **Income** is the
book of money that came in, with a box to add a line and a Remove button per line.
**Donations** is the same book for money given.

Only signed-in members can open any of them. There are no guests in this feature:
you cannot keep a ledger you cannot be identified on.

Five rules run through the whole thing, and they are the actual content of this
change. The tenth is rounded to the cent. If you have given more than is due, the
page says so but **the excess never counts against future income** — you cannot
give maaser before the money it comes from exists. An amount must be more than
zero, be a real number, and only go to the cent. A date may not be tomorrow: the
ledger records what already happened. And a Remove button may only touch your own
lines — asking it to remove someone else's acts as if that line does not exist.

Two words on what is *not* here, because both are deliberate. A donation cannot yet
be linked to a particular charity — that would make the tools area depend on the
charities area, which the house rules forbid, and nobody has asked for it. And
nothing on these pages can be edited in place; if you mistype, you remove the line
and add it again. Both are cheap to add later.

Everything below is the same idea in more detail.

---

## 2. How to read this file

For two people at once.

- If you do not write software, read the **glossary**, then the **story**, then the
  bold one-line summary at the top of each file section.
- If you are reviewing the code, the same sections carry it, quoted, in reading
  order, with a `file.py:line` address on each box.

Three rules:

1. **Read the glossary first.** Every term is defined there.
2. **Every code box is optional.** The sentence above it says the same thing in
   plain English.
3. **Skim the bold lines.** They are the summary.

---

## 3. The glossary

Nine words, one table.

- **Maaser** — the tenth of one's income given to charity. The books and the
  calculation here exist to work it out.
- **Ledger** — a list of what happened, oldest money in the past, newest at the
  top. There are two: income and donations.
- **Entry** — one line of the ledger: an amount, a date, a short note.
- **Transaction** — the code's name for an entry. One row in the `TRANSACTION`
  table.
- **Member** — a signed-in account. Every account on this site is a member; there
  is no separate "just looking" tier.
- **Summary** — the calculator's answer, as a set of four figures: money in, given,
  the tenth due, and what remains owed.
- **Round to the cent** — two decimal places, the half-way case going up. A tenth
  of 18.05 is 1.805, which becomes 1.81.
- **Clamp at zero** — the rule "never go below nothing". If 500 is due and 600 was
  given, the answer is 0 owed, not minus 100.
- **Service** — the one door one part of the site may knock on to use another.
  Here the members area can ask "how much does this member owe?" without touching
  the tools' tables.

Names that exist only in this code, and the plain word used here:

| in the code | in this file |
|---|---|
| `Entry` | entry (one ledger line) |
| `MaaserSummary` / `summary` | the four figures |
| `debug`: `0.00` `Decimal` | the code's way of writing money figures to the penny |
| `INCOME` / `DONATION` | the two kinds of entry |
| `type` (the code word) | which ledger a line belongs to |
| `localdate()` | "today", in the site's timezone |
| `floatformat:"2g"` | "show two decimals, thousands separated" |
| `login_required` | "only for signed-in members" |

---

## 4. The story

### What the site does all day

1. A member earns something, or gives something.
2. They open the tools pages and write the line down, date and amount.
3. The site adds the income, subtracts what was given, and shows what is still
   owed.
4. When the day comes to give the maaser, the member knows the exact figure.

Until this change, none of steps 1–3 existed in any usable form. The tools app was
an empty shell: a URL prefix with no pages behind it. A member could not write
anything down, and nothing could be calculated.

### What was wrong

Four separate gaps, each fixed in its own place.

**No books.** There was no way to record income or a donation at all.

**No calculator.** Even with the books, nothing said how to combine them. The design
document gives the formula in two places — §6.4 (the maaser calculator) and §6.3
(a failure path called "negative maaser balance") — and, as usual for a design doc,
it leaves the hard part out: what happens when donations *exceed* what is due.

**No identity rule.** The design says "members only", but it does not say how to
tell a member from anybody else, and the tools area is forbidden (§6.1) from
depending on the accounts area to find out.

**No boundary.** The design says tools services must exist for adding transactions
and computing the amount owed, so the member dashboards can show the figure. It
does not say what shape those services take, or how a caller is stopped from
reading another member's ledger by guessing row numbers.

### The cost of leaving it

A concrete case, carried through. A member named in this file as *the giver* earns
3,000 and gives 180 to a charity. The naive site shows "you owe 300 minus what
you've given" and leaves it there. The giver types a donation of 18 by mistake one
day — 3,000 minus 180 is missing a zero, and now the page says 102 owed, and later
a tenth of somebody's income is quietly wrong. The same site, told "the date is
tomorrow", happily counts a donation that has not happened yet against money that
has not been earned yet, and today's true figure vanishes.

### The fix, in one sentence

Four member-only pages over one small set of rules: a tenth rounded to the cent,
subtract what was given, never go below zero, put the excess in a box that says
"shown, not carried forward", refuse entries that are not real money or real past
dates, and let a member remove only their own lines.

The consequences, listed plainly:

- The answer "maaser owed" is always non-negative, and always the same on every
  page that shows it.
- An overpayment is visible — "you have given 15 more than the tenth due" — and
  cannot be argued away by a future page doing subtraction differently.
- A typo is fixed by removing and re-adding, which is safe because Remove will not
  touch anyone else's lines.
- Amounts and dates are refused at the moment of typing, with sentences, rather
  than stored and discovered broken later.
- Another part of the site (the member dashboard) can ask for the owed figure
  through a service call, without any knowledge of the tools' tables.

---

## 5. Contradictions

None between the pull request, the D-074 entry and the code. One sentence in the
push message is worth a straight reading, though:

> a guest who opens a tools page is redirected to a 404 until it merges

That is not a defect in this change. The member-only rule sends guests to the login
page, and the login page's address (`/accounts/login/`) belongs to Yosef's still
open PR #15. Until it merges, the redirect lands on a page that does not exist. The
note is there so nobody files "tools page 404s for guests" as a bug against this
work — it is a known cross-dependency, and it is folded into issue #36 later.

One test-file detail: the PR body says nothing about a test count for this file, so
there is no number to check; it collects 35 tests (24 functions, two of them run
many times).

---

## 6. Reading order

| # | File | What it is | Why here |
|---|---|---|---|
| 1 | `apps/tools/services.py` | the rules: cleaning, books, calculation | everything hangs off it |
| 2 | `apps/tools/views.py` | the four pages | how pages call the services |
| 3 | `apps/tools/urls.py`, `config/urls.py` | the addresses | wiring |
| 4 | `apps/tools/templates/tools/*` (4 files) | what the member sees | rendering |
| 5 | `static/css/site.css` | the styling | looks |
| 6 | `tests/factories/tools.py`, `tests/factories/__init__.py` | the test data-maker | small |
| 7 | `docs/DECISIONS.md` | the D-074 record: the decision in prose | the argument, not the code |
| 8 | `tests/unit/test_maaser_tools.py`, `tests/integration/test_base_template.py` | the proof | last |

The shape in one sentence: **`services.py` decides what money the pages may record
and what the calculator may answer, and `views.py` is a thin door that lets only
members through.**

---

## 7. The files

### 7.1 `apps/tools/services.py` — the rules of the ledger, in one file

**This file goes from a three-line stub to the whole of the feature's logic: cleaning amounts and dates, the two books, deletion scoped to the owner, and the calculator with its clamp.**

Before this change the file was only a docstring:

```python
"""Public interface of the tools app.

Other apps call only the functions defined here, never this app's models.
"""
```

The new docstring states the two rules every function obeys
(`apps/tools/services.py:1`):

```python
"""Public interface of the tools app (§6.1: income and donation CRUD, maaser calculation).

Other apps call only the functions defined here, never this app's models. Every
function takes the member's user id and touches only that member's rows, so a
caller cannot read or delete someone else's ledger by passing a row id.
"""
```

The constants, which are the rules in table form (`apps/tools/services.py:19`):

```python
INCOME = Transaction.Type.INCOME
DONATION = Transaction.Type.DONATION

# The column is Decimal(12, 2): anything at or above this cannot be stored.
MAX_AMOUNT = Decimal("9999999999.99")
MAX_NOTE_LENGTH = 500
MAASER_RATE = Decimal("0.10")
CENT = Decimal("0.01")
```

The amounts are decimal numbers, not code's ordinary floating-point numbers, because
floating-point arithmetic famously makes 0.1 + 0.2 equal 0.30000000000000004, and a
ledger that adds up to 0.30000004 is a ledger nobody trusts. The maximum amount is
literally the biggest value the `Decimal(12, 2)` column in the database can hold —
ten billion minus a cent — so the check in code and the check at the database
cannot disagree.

Cleaning an amount (`apps/tools/services.py:58`):

```python
def _clean_amount(raw) -> Decimal:
    try:
        amount = Decimal(str(raw).strip().replace(",", ""))
    except (InvalidOperation, AttributeError):
        raise TransactionError("Enter the amount as a number, like 1250.00.") from None
    if not amount.is_finite():
        raise TransactionError("Enter the amount as a number, like 1250.00.")
    if amount != amount.quantize(CENT):
        raise TransactionError("Amounts go to the cent at most.")
    if amount <= 0:
        # The table refuses it too (D-055); this is the readable version.
        raise TransactionError("The amount must be more than zero.")
    if amount > MAX_AMOUNT:
        raise TransactionError("That amount is too large.")
    return amount
```

The four refusals correspond to four ways a typed figure can be nonsense. Letters or
nothing, and the special values `NaN` and `Infinity` (a real machine will type those
in, believe it or not), get the same sentence: "as a number." A figure with more
than two decimals, like `1.005`, is refused outright — my writing "round to the
cent" in the glossary describes the *calculator*; a typed amount is expected to be a
clean figure for a real transaction. Zero and negative are refused. And the comment
on the zero check says something worth reading twice: the database table refuses it
too (a constraint from another decision, D-055), so this check exists to give the
member a sentence instead of an error page — the two layers of defence are
intentional. `.replace(",", "")` means `1,250.50` is accepted as written, since
people type money with commas.

Cleaning a date (`apps/tools/services.py:75`):

```python
def _clean_date(raw) -> datetime.date:
    if raw in (None, ""):
        return timezone.localdate()
    if isinstance(raw, datetime.date):
        date = raw
    else:
        try:
            date = datetime.date.fromisoformat(str(raw).strip())
        except ValueError:
            raise TransactionError("Enter the date as YYYY-MM-DD.") from None
    if date > timezone.localdate():
        raise TransactionError("The date cannot be in the future.")
    return date
```

"Today, if you leave it blank" is the polite default, and "not tomorrow, ever" is
the rule, and the reason is stated in the docstring of `add_transaction`: a future
donation would lower what is owed *today*, which means the amount owed could stop
being true mid-week and go back up when the imaginary date passes. The ledger must
be a record of fact, so falsity is refused at the door. The date accepts either a
typed string in the exact YYYY-MM-DD shape or a real date object (tests call it both
ways).

The entry point (`apps/tools/services.py:90`):

```python
def add_transaction(user_id: int, type: str, amount, date=None, note: str = "") -> int:
    """Record one income or donation for a member. Returns the new row's id.

    `date` defaults to today (D-055). Future dates are refused: the ledger is
    what already happened, and a future donation would lower maaser owed today.
    """
    if type not in (INCOME, DONATION):
        raise TransactionError("Choose income or donation.")
    note = (note or "").strip()
    if len(note) > MAX_NOTE_LENGTH:
        raise TransactionError(f"Keep the note under {MAX_NOTE_LENGTH} characters.")
    row = Transaction.objects.create(
        user_id=user_id,
        type=type,
        amount=_clean_amount(amount),
        date=_clean_date(date),
        note=note or None,
    )
    return row.id
```

`type` — which ledger — is checked against the two known kinds before anything is
saved, because it arrives from a URL or a form and a stranger can type anything
there. The note is trimmed, capped at 500 characters, and stored as *nothing* when
blank, so the ledger's note column never carries empty strings. Only the new row's
id crosses the door, never the row.

The books (`apps/tools/services.py:111`, `:120`):

```python
def list_transactions(user_id: int, type: str) -> list[Entry]:
    """A member's income or donations, newest first."""
    rows = Transaction.objects.filter(user_id=user_id, type=type).order_by("-date", "-id")
    return [
        Entry(id=row.id, type=row.type, amount=row.amount, date=row.date, note=row.note or "")
        for row in rows
    ]


def delete_transaction(user_id: int, transaction_id: int) -> bool:
    """Remove one of the member's own entries. False when there was none to remove."""
    deleted, _ = Transaction.objects.filter(user_id=user_id, pk=transaction_id).delete()
    return bool(deleted)
```

Here is where "scoped to one member" does its work. The listing filters by both the
member *and* the type, newest first with the row number as the tie-break so two
entries from the same day keep a stable order. The deletion filters by the member
*and* the id, so asking to delete a row that is not yours matches nothing and
returns `False` — never a deletion, never an error. That is what makes issue #30's
"someone else's id gets a 404" work: the page sees `False` and shows a 404, and an
attacker cannot tell a mistyped number from somebody else's row.

The calculator (`apps/tools/services.py:126`):

```python
def maaser_summary(user_id: int) -> MaaserSummary:
    """income / 10 − donations for one member, never below zero (§6.4, §6.3).

    All of a member's amounts are taken to be in one currency (§6.3.1).
    """
    totals = {
        row["type"]: row["total"]
        for row in Transaction.objects.filter(user_id=user_id)
        .values("type")
        .annotate(total=Sum("amount"))
        .order_by()
    }
    income = totals.get(INCOME) or Decimal("0.00")
    donations = totals.get(DONATION) or Decimal("0.00")
    due = (income * MAASER_RATE).quantize(CENT, rounding=ROUND_HALF_UP)
    balance = due - donations
    zero = Decimal("0.00")
    return MaaserSummary(
        income=income,
        donations=donations,
        due=due,
        owed=max(balance, zero),
        given_beyond=max(-balance, zero),
    )
```

The sum is done by the database in one question — `Sum` over the member's rows
grouped by kind — rather than fetched and added in code, so the calculator is one
query no matter how long the ledger grows. A member with no entries gets 0.00 for
both sides, via the `or Decimal("0.00")` safety.

The two clamped counts are the decision D-074 is named for. `due` (the tenth) is
rounded to the cent with "half up", so 1.805 becomes 1.81. Then the balance is
`due − donations`, and both directions are reported without ever letting the answer
go below zero: `owed` is the balance when positive, zero otherwise; `given_beyond`
is the opposite — the excess the page will display as "shown but not carried
forward". One subtraction, both readings, no hidden state.

The one-liner the rest of the site uses (`apps/tools/services.py:152`):

```python
def maaser_owed(user_id: int) -> Decimal:
    """Just the amount still owed, for callers such as the member dashboard."""
    return maaser_summary(user_id).owed
```

Why both shapes exist: other areas' dashboards (the chatbot, the member dashboard)
only ever want the one figure, so they get a decimal; the tools pages want the whole
breakdown, so they get the summary.

What it buys: the entire feature's arithmetic lives in one file, with every refusal
reading as a sentence, and no caller — page or other area — can make the numbers
come out differently than the rules say.

### 7.2 `apps/tools/views.py` — the four pages, members only

**This empty file becomes the four handlers: a front page, a calculator page, and one shared ledger page used twice, with the member-only rule on every public entry point.**

Before this change the file was empty — literally zero bytes — and the tools URLs
pointed at nothing.

The member-only rule, stated honestly in the docstring (`apps/tools/views.py:1`):

```python
"""The maaser tools pages under /tools/ (§6.3.1, SRS FR 20–22, D-027, D-074).

Members only. Every account is a member (D-YOSEF-accounts-login), so signing in
is the check; tools depends on nothing (§6.1) and does not ask accounts.
"""
```

The design said the tools area may depend on no other area, and it said members
only. The way out of the squeeze is that every account is a member by construction
(the accounts area's decision D-YOSEF-accounts-login), so "signed in" *is* "a
member", and the standard `login_required` check answers both without asking
accounts anything.

The two-page table at the top, which is why income and donations share one template
(`apps/tools/views.py:28`):

```python
# Each ledger page's type, URL name and wording.
LEDGERS = {
    INCOME: {
        "url_name": "tools:income",
        "title": "Income",
        "noun": "income",
        "intro": "Record what you earn. A tenth of it is maaser.",
    },
    DONATION: {
        "url_name": "tools:donations",
        "title": "Donations",
        "noun": "donation",
        "intro": "Record what you give. It counts against the maaser you owe.",
    },
}
```

Two pages with one book page each. The table holds every difference between them —
the URL name, the heading, the word used in notices ("Added the income.") and the
intro sentence — so no behaviour branches on "which page am I" anywhere else.

The front pages (`apps/tools/views.py:44`):

```python
@login_required
def index(request: HttpRequest) -> HttpResponse:
    """The tools front page: what is owed now, and the way to each page."""
    return render(request, "tools/index.html", {"summary": maaser_summary(request.user.id)})


@login_required
def maaser(request: HttpRequest) -> HttpResponse:
    """The maaser calculator (FR 20): income / 10 − donations, never below zero."""
    return render(request, "tools/maaser.html", {"summary": maaser_summary(request.user.id)})
```

Both are two lines long because the work is in the service. Note which member: the
request's own user id, read from the signed-in session — never from the URL or the
form, so nobody can ask the calculator to run on somebody else's numbers.

The shared ledger page, which does the add form work (`apps/tools/views.py:56`):

```python
def _ledger(request: HttpRequest, type: str) -> HttpResponse:
    ledger = LEDGERS[type]
    error = None
    if request.method == "POST":
        try:
            add_transaction(
                request.user.id,
                type,
                request.POST.get("amount", ""),
                request.POST.get("date", ""),
                request.POST.get("note", ""),
            )
        except TransactionError as exc:
            error = str(exc)
        else:
            messages.success(request, f"Added the {ledger['noun']}.")
            # Post/redirect/get, so a refresh does not record it twice.
            return redirect(ledger["url_name"])
    entries = list_transactions(request.user.id, type)
    return render(
        request,
        "tools/ledger.html",
        {
            "ledger": ledger,
            "type": type,
            "entries": entries,
            "total": sum((entry.amount for entry in entries), start=0),
            "error": error,
            "form": request.POST if error else {},
            "today": timezone.localdate().isoformat(),
            "max_note_length": MAX_NOTE_LENGTH,
        },
        status=400 if error else 200,
    )
```

The comment names the classic web bug this avoids: a refresh after a successful
submit would re-post the form, so the site saves once and then bounces the browser
to the same page as a plain visit (the "post/redirect/get" pattern). The total is
the sum of the page's entries — a running figure for that ledger, not the whole
summary. And the two details worth a look: `"form": request.POST if error else {}`
is what re-fills the boxes after a refusal, so a refused amount does not eat the
member's typing; and the status code is 400 on a refusal, which is how the browser
and the tests know this was a "bad request" rather than a normal page.

The two public ledger pages and the delete (`apps/tools/views.py:92`, `:104`):

```python
@login_required
def income(request: HttpRequest) -> HttpResponse:
    """Income history and the form to add to it (FR 21)."""
    return _ledger(request, INCOME)


@login_required
def donations(request: HttpRequest) -> HttpResponse:
    """Donation history and the form to add to it (FR 22)."""
    return _ledger(request, DONATION)


@login_required
@require_POST
def delete(request: HttpRequest, type: str, transaction_id: int) -> HttpResponse:
    """Remove one of the member's own entries and return to its page."""
    ledger = LEDGERS.get(type)
    if ledger is None or not delete_transaction(request.user.id, transaction_id):
        # Someone else's id looks the same as a missing one.
        raise Http404
    messages.success(request, f"Removed the {ledger['noun']}.")
    return redirect(ledger["url_name"])
```

`income` and `donations` are the same code called with a different kind, which is
why there is one template. The delete is `@require_POST`, so the remove address
cannot be triggered by a mere link or an image tag — it has to be an actual form
submission — and the unknown-kind and not-yours cases both become a 404, with the
comment saying why: an attacker probing id 3 must not learn whether id 3 is
someone's expense or a number that does not exist.

What it buys: a member gets four pages, two of them the same page wearing
different words, and every one of them refuses anyone who is not signed in.

### 7.3 `apps/tools/urls.py` and `config/urls.py` — the four addresses

**The empty address list becomes the four tools pages plus the delete route, and the root list starts including tools.**

Before the change, the file was:

```python
from django.urls import path  # noqa: F401

app_name = "tools"

urlpatterns = []
```

After (`apps/tools/urls.py:1`):

```python
"""The maaser tools pages under /tools/ (D-026, D-027)."""

from django.urls import path

from . import views

app_name = "tools"

urlpatterns = [
    path("", views.index, name="index"),
    path("maaser/", views.maaser, name="maaser"),
    path("income/", views.income, name="income"),
    path("donations/", views.donations, name="donations"),
    path("<str:type>/<int:transaction_id>/delete/", views.delete, name="delete"),
]
```

The delete route's shape (`<str:type>/<int:transaction_id>/delete/`) is what lets
the URL itself carry which ledger and which row — `/tools/income/5/delete/` — and
the `<int:>` part means a non-number simply does not match the route and gets a 404
before the view runs.

One line added to the root list (`config/urls.py:12`):

```python
    path("tools/", include("apps.tools.urls")),
```

What it buys: the test that used to prove `/tools/` was advertised nowhere can now
be pointed at a different unbuilt route (it now checks `/dashboard/`), which is
exactly the kind of check that keeps the top bar honest as pages come into
existence.

### 7.4 The four templates — what the member sees

**Four new templates: the tool strip shared by all of them, the front page, the calculator, and the ledger used by both books.**

The shared strip, which shows which page you are on and links to the other two
(`apps/tools/templates/tools/_nav.html:1`):

```html
<nav class="tools-nav" aria-label="Maaser tools">
  <a href="{% url 'tools:maaser' %}"{% if request.resolver_match.url_name == "maaser" %} aria-current="page"{% endif %}>Calculator</a>
  <a href="{% url 'tools:income' %}"{% if request.resolver_match.url_name == "income" %} aria-current="page"{% endif %}>Income</a>
  <a href="{% url 'tools:donations' %}"{% if request.resolver_match.url_name == "donations" %} aria-current="page"{% endif %}>Donations</a>
</nav>
```

`aria-current="page"` tells a screen reader that this link points at the page you
are on, and the CSS bolds it — the same information in both channels.

The front page, 20 lines (`apps/tools/templates/tools/index.html:9`):

```html
    <p class="tools-owed">
      You owe <strong>{{ summary.owed|floatformat:"2g" }}</strong> in maaser.
    </p>

    <ul class="tools-links">
      <li><a href="{% url 'tools:maaser' %}">Maaser calculator</a>: how that figure is worked out.</li>
      <li><a href="{% url 'tools:income' %}">Income</a>: what you have earned ({{ summary.income|floatformat:"2g" }} in all).</li>
      <li><a href="{% url 'tools:donations' %}">Donations</a>: what you have given ({{ summary.donations|floatformat:"2g" }} in all).</li>
    </ul>
```

The page answers the question in the first line and then explains where the number
came from without making the reader do arithmetic. `floatformat:"2g"` is the
"thousands separated, two decimals" template word, so 1234.50 renders as 1,234.50 —
numbers with commas, the way money is read.

The calculator, which is the one page where the rule shows its face
(`apps/tools/templates/tools/maaser.html:11`):

```html
    <table class="tools-sum">
      <tbody>
        <tr><th scope="row">Income</th><td>{{ summary.income|floatformat:"2g" }}</td></tr>
        <tr><th scope="row">Maaser due (a tenth)</th><td>{{ summary.due|floatformat:"2g" }}</td></tr>
        <tr><th scope="row">Donations</th><td>&minus; {{ summary.donations|floatformat:"2g" }}</td></tr>
        <tr class="tools-sum__total"><th scope="row">Still owed</th><td>{{ summary.owed|floatformat:"2g" }}</td></tr>
      </tbody>
    </table>

    {% if summary.given_beyond %}
      <p class="tools-note">
        You have given {{ summary.given_beyond|floatformat:"2g" }} more than the maaser due.
        Maaser cannot be given before the income it comes from, so this is not counted
        against future income.
      </p>
    {% endif %}

    <p class="tools-note">All amounts are taken to be in one currency.</p>
```

The three rows show the whole working, and the last row is bold — total owed, not
a figure that has to be combined. The `if` shows the decision's other half: when
there is no excess, the paragraph is not even in the page's source. And the final
line is the design's own caveat (§6.3.1) made visible: no currency is assumed, so
the site says so rather than quietly treating dollars and shekels as the same.

The ledger, both pages in one (`apps/tools/templates/tools/ledger.html:10`):

```html
    <p>{{ ledger.intro }}</p>

    {% for message in messages %}
      <p class="ticket-form__notice" role="status">{{ message }}</p>
    {% endfor %}

    <form class="tools-form" method="post" action="{% url ledger.url_name %}">
      {% csrf_token %}
      {% if error %}<p class="ticket-form__error" role="alert">{{ error }}</p>{% endif %}
      <label>Amount
        <input type="text" name="amount" inputmode="decimal" required value="{{ form.amount }}">
      </label>
      <label>Date
        <input type="date" name="date" max="{{ today }}" value="{{ form.date|default:today }}">
      </label>
      <label class="tools-form__note">Note (optional)
        <input type="text" name="note" maxlength="{{ max_note_length }}" value="{{ form.note }}">
      </label>
      <button class="button" type="submit">Add {{ ledger.noun }}</button>
    </form>
```

Two inputs carry the rules in the browser as well as in the service. The date
picker's `max="{{ today }}"` makes tomorrow unselectable in most browsers before
anything is sent — the service check remains for the browsers that ignore it, and
the two layers are both present on purpose. `inputmode="decimal"` brings up the
number pad on a phone.

The table of entries and its total (`apps/tools/templates/tools/ledger.html:30`):

```html
          {% for entry in entries %}
            <tr>
              <td>{{ entry.date|date:"Y-m-d" }}</td>
              <td>{{ entry.amount|floatformat:"2g" }}</td>
              <td>{{ entry.note }}</td>
              <td>
                <form method="post" action="{% url 'tools:delete' type entry.id %}">
                  {% csrf_token %}
                  <button class="button button--link" type="submit">Remove</button>
                </form>
              </td>
            </tr>
          {% endfor %}
        </tbody>
        <tfoot>
          <tr><th scope="row">Total</th><td>{{ total|floatformat:"2g" }}</td><td colspan="2"></td></tr>
        </tfoot>
```

Each Remove button is its own tiny form wrapping that row's delete address, which
is why removal requires a deliberate click and a POST — no `onclick`, no links. The
footer total is computed in the view, not invented here.

What it buys: the member sees the arithmetic with its source values, an add box
with the rules already visible in the browser, and a Remove button per row that
cannot touch anyone else's row.

### 7.5 `static/css/site.css` — the look of the tools pages

**Eighty lines: the strip of links, the two-column books with right-aligned numbers, and the visually hidden column heading over the Remove buttons.**

Before, nothing existed for these pages. Two rules are worth naming
(`static/css/site.css:932`):

```css
.tools-ledger td:nth-child(2),
.tools-sum td {
  font-variant-numeric: tabular-nums;
  text-align: right;
}
```

`tabular-nums` makes every digit the same width, so the amount column doesn't
shimmer as you scroll — and right-aligning money is how money columns read, in
every ledger that ever existed. And the empty column head over Remove:

```css
.visually-hidden {
  clip: rect(0 0 0 0);
  height: 1px;
  overflow: hidden;
  position: absolute;
  width: 1px;
}
```

The Remove column gets a heading that is invisible visually but still read by
screen readers — the table keeps its four-column shape for everyone who can see it,
and a spoken description for everyone who cannot.

What it buys: the books look like books: numbers to the right, aligned.

### 7.6 The factories — a test helper for one member's rows

**A new factory makes a `Transaction` row for tests, registered in the shared factory list.**

Test factories are the allowed exception to the app-boundary rule: they are dev
tooling and may create any app's rows directly. The new factory
(`tests/factories/tools.py:1`):

```python
class TransactionFactory(DjangoModelFactory):
    class Meta:
        model = Transaction

    user = factory.SubFactory("tests.factories.accounts.UserFactory")
    type = Transaction.Type.INCOME
    amount = Decimal("100.00")
```

Sensible defaults (income, 100.00, a fresh user) that each test overrides as needed.
One line in `tests/factories/__init__.py` exports it, so every test file can
`from tests.factories import TransactionFactory`.

What it buys: tests that read "a member with 3,000 of income and 180 of donations"
instead of five lines of row-building.

---

## 8. The tests

The new file is `tests/unit/test_maaser_tools.py` (35 collected tests), plus one
changed line in an integration test.

**Entering money** — `test_records_an_income_dated_today_by_default` pins the amount,
the owner, the today-default and the no-note-when-blank all at once;
`test_keeps_a_date_and_a_trimmed_note`; `test_accepts_a_date_object`;
`test_refuses_a_bad_amount` runs nine cases — empty, letters, missing, `NaN`,
`Infinity`, zero, negative, three decimals, and too big, each with its sentence —
and asserts *no row exists* after all of them; `test_refuses_a_bad_or_future_date`;
`test_refuses_an_unknown_type_and_a_long_note`.

**The books** — `test_lists_one_members_one_type_newest_first` (two of the member's
incomes, one of the member's donations, and one stranger's income: only the two
member incomes come back, newest first); `test_deletes_only_the_members_own_row`
(the stranger's id returns `False` and the row survives; the member's returns `True`
and the row is gone).

**The calculator** — `test_nothing_recorded_owes_nothing`;
`test_a_tenth_of_income_less_donations` is the doc case: 5,000 of income, 180
given, 320 owed — and a stranger's 99,999 is proven not to leak in;
`test_a_tenth_rounds_to_the_cent` (a tenth of 0.05 is 0.01, the half-up case);
`test_giving_more_than_due_clamps_to_zero` carries the decision's name in its
docstring — 100 of income, 25 given, owed is 0 and given-beyond is exactly 15;
`test_donations_without_income`.

**The door** — `test_a_guest_is_sent_to_log_in` runs all four public pages, each
redirecting to the login page with a `next` back; `test_the_nav_links_to_the_tools`.

**The pages** — `test_index_shows_what_is_owed`; `test_calculator_shows_the_breakdown`
(the numbers are there, and so is the "more than the maaser due" paragraph);
`test_adding_income_redirects_back_with_a_notice` (a 302 to the same page, the row
saved, and the notice and the note and the amount on the page);
`test_adding_a_donation`; `test_a_bad_amount_keeps_what_was_typed` (a 400, the
error, the amount *and* the note still in the boxes, no row);
`test_a_member_sees_only_their_own_entries`; `test_removing_an_entry`;
`test_cannot_remove_someone_elses_entry` (404, and the row survives);
`test_remove_needs_a_known_type_and_a_post` (a junk type gets a 404,
a plain visit gets a 405, and the row survives both).

The changed integration test, `test_base_template.py`, had been asserting that the
top bar advertises no `/tools/` link ("a route with no pattern yet is not advertised
at all") — a check that was true yesterday and false now. It now points the same
check at `/dashboard/`, the next unbuilt route. A test that would have started
failing for the right reason was updated rather than deleted.