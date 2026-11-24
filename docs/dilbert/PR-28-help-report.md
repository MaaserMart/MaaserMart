# PR #28 — Help and report pages, with a proof-of-email check for guests

- Branch: `support/help-report` → `main`
- Merge commit: `92ab306` (2026-11-24)
- Author: Platform Lead (Shaul)
- Decision recorded: D-072
- Size: 19 files, +896 / −5

---

## 1. Read this part even if you read nothing else

MaaserMart is a website that lists Jewish charities so people can find one to give
money to. Two of the pages on it are for talking back to the people who run the
site. One is **Help**: "I have a question." The other is **Report**: "this entry for
a charity is wrong."

Think of a suggestion box in a shop lobby. Anyone walking past can drop a note in,
no purchase needed. That is what these two pages are — except the shop needs to be
able to write back to whoever left the note, and a note with no name on it is
useless.

This is the change that puts the two boxes in the lobby, and puts a small hold on
them. If you are signed in, you just drop the note; the site already knows who you
are. If you are not signed in, before the note is accepted you must type an email
address and then type back a six-digit number the site sends to that address. That
is called verifying the address: it shows the mailbox is really yours and not
someone else's, so the shop is not talked into sending a reply — or a pile of
mail — to a stranger.

Everything else in this change is the plumbing behind that picture: where a note is
stored, how the six-digit number is kept and for how long, how the Report page
finds the right charity, and a small "Report this charity" link added to each
charity's own page so you can start a report from there.

Nothing here changes how the site looks to a donor browsing charities. It adds two
pages, adds a column or three to a table, and adds one line to the bottom of each
charity page.

Everything below is the same idea in more detail.

---

## 2. How to read this file

This file is for two people at once.

- If you do not write software, read the **glossary** first, then the **story**,
  then the bold one-line summary at the top of each file section. That is the whole
  change.
- If you are reviewing the code, the same sections carry the real code, quoted, in
  reading order, with a `file.py:line` address on each box.

Three rules make this work:

1. **Read the glossary before anything else.** Every word in this file is defined
   there or is ordinary English.
2. **Every code box is optional.** The sentence directly above each box says the
   same thing in plain English. Skip all the boxes and you lose nothing.
3. **Skim the bold lines.** Each file section opens with one bold sentence. Those
   sentences alone are a summary of the change.

---

## 3. The glossary

Ten words, and one table for the names that only exist inside the code.

- **Ticket** — the note a visitor drops in the box. It is one row in a database
  table called `TICKET`. It holds the message, who wrote it, and later the answer.
- **Guest** — someone using the site without signing in. The opposite is a
  **signed-in user**, whose identity the site already knows.
- **Verifying an address** — proving you can read the mail sent to an email
  address. Here: the site mails a six-digit number and you type it back.
- **Session** — the site's short memory of one visitor. It lasts while the browser
  tab is open and is thrown away when it closes. It is where a half-finished
  verification waits.
- **Cache** — a shared scratchpad all the site's processes can read and write. It
  outlives a session, so it is the only place a limit like "five codes per address
  per hour" can be counted.
- **HMAC / digest** — a fingerprint of some data that cannot be turned back into
  the data. The site stores the fingerprint of the six-digit number, not the
  number, so a peek at the stored session does not reveal the code.
- **Celery** — the site's queue for slow work. Anything that waits on the outside
  world (here: sending email) is handed to it, so the visitor's page does not
  freeze while the mail server thinks.
- **Migration** — a recorded, ordered instruction that changes the shape of the
  database. It is how new columns appear on a live site without hand-editing the
  table.
- **Service** — the one door another part of the site is allowed to knock on. Code
  in one area never reaches into another area's database table directly; it calls
  that area's services instead.
- **Charity choice** — a pair of two things only: a charity's number and its name.
  Not the whole charity record. It is what a pick list needs and nothing more.

Names that exist only in this code, and the plain word used in this file:

| in the code | in this file |
|---|---|
| `Ticket` | ticket (the note) |
| `verified_email` / `pending_email` | proved address / address awaiting a code |
| `CharityChoice` | charity choice (number + name) |
| `CheckResult` | the outcome of a step (`ok` + a sentence to show) |
| `action` (form button name) | which button was pressed |
| `HMAC` / `sha256` | fingerprint |
| `cache.incr` | add one to a counter |

---

## 4. The story

### What the site does all day

1. A visitor browses the charity listing and opens a charity's page.
2. Somebody signed in reviews a charity, or uses a maaser calculator.
3. Support questions and complaints arrive from anyone, signed in or not.
4. An admin answers them by email.

Step 3 is the new part. Before this change, the site had a `TICKET` table and a
`TICKET` model — the empty shelf where notes would go — and **nowhere to put a
note in**. There was no help page and no report page: the two links in the top bar
were dead, because their addresses did not exist.

### What was wrong

Three separate holes, and they are worth naming one at a time because they are
fixed in three different places.

**First: no page.** A visitor with a question had nothing to click. That is the
whole of it; there is no subtlety here.

**Second: no way to write back.** A signed-in member is a known person, so an
answer can go to the address on their account. A guest is nobody — a note saying
"your donation link is broken" is unanswerable unless the guest leaves an address,
and an unproven address is worse than none: it lets anyone type a stranger's
address and have the site mail them.

**Third: nothing said how a report names its charity.** "This listing is wrong"
means nothing without saying *which* listing. And the only code allowed to read
charity records is the charities area, so support cannot look them up itself.

### The cost of leaving it

The concrete case, carried through. A visitor named in this file as *the guest*
opens the page of a charity, say Tomchei Shabbos, and sees a phone number that
belongs to a different organisation. They want to tell somebody. Without this
change they close the tab. With the change, they press **Report this charity**,
Tomchei Shabbos arrives already chosen, they type an address, type back the
six-digit number that lands in that mailbox, write one sentence, and press Send.
An admin later emails them: "thanks, fixed."

### The fix, in one sentence

Two pages, one form each, posted back to themselves; a guest proves an address
first with a six-digit code that lives in their session as a fingerprint and is
capped at five codes per address per hour; the note becomes a row in `TICKET` with
room for the answer; and the approved way to look up a charity from outside the
charities area now exists.

The consequences, listed plainly:

- A guest must verify an address once per browser session. Verify once, and both
  the help form and the report form accept the note.
- The address is remembered until the tab closes. That is deliberate: it is one
  visit, not an account.
- Wrong code five times and the code is thrown away, so guessing is pointless.
- A code works for fifteen minutes. After that, ask for a new one.
- The same address cannot be sent more than five codes in an hour, from any
  number of browsers, so the form cannot be used to fill someone's inbox.
- What is typed in the message box survives every one of those steps. A visitor
  never loses their paragraph because they had to go and read their email.

---

## 5. Contradictions

One, and it is small.

The pull request says "43 new tests in `tests/unit/test_support_tickets.py`". The
file contains 37 test functions, three of which run several times with different
inputs (4, 2 and 4 cases), so it collects **44** tests. The claim is off by one;
the file is what it is. Trust the file.

Nothing else disagrees. The commit message, the D-072 entry in `docs/DECISIONS.md`
and the code describe the same design: session-held fingerprint, fifteen minutes,
five tries, five sends per address per hour.

One gap the pull request states openly and does not hide: **guests have no per-IP
send limit.** The cap is per *address*, so one browser can still ask for codes to
a thousand different addresses. Fixing that needs a limit keyed on the visitor's
network address, which the support area is not allowed to reach for (§6.1 keeps
support dependent on nothing). It was filed later as issue #33.

---

## 6. Reading order

| # | File | What it is | Why here |
|---|---|---|---|
| 1 | `apps/support/migrations/0002_ticket_email_response.py` | the shape change | the data comes first |
| 2 | `apps/support/models.py` | the note's three new fields | what the migration creates |
| 3 | `apps/support/services.py` | the only door for writing a note | who may write one, and the rules |
| 4 | `apps/support/verification.py` | the six-digit code check | the guest's proof |
| 5 | `apps/support/tasks.py` | the queued email | how the code reaches the mailbox |
| 6 | `apps/support/views.py` | the two pages | the steps in order |
| 7 | `apps/support/urls.py`, `config/urls.py` | the addresses | wiring |
| 8 | `apps/charities/services.py` | the charity lookup for the report form | the other area's door |
| 9 | `apps/support/templates/support/*` (5 files) | what the visitor sees | rendering |
| 10 | `apps/charities/templates/charities/detail.html` | the "Report this charity" link | a one-line addition |
| 11 | `static/css/site.css` | the styling | looks |
| 12 | `tests/unit/test_support_tickets.py`, `tests/unit/test_prod_settings.py` | the proof | last |

The shape of the whole change in one sentence: **a note is written through
`services.py`, a guest earns the right to write one through `verification.py`, and
both are shown by `views.py` through two templates.**

---

## 7. The files

### 7.1 `apps/support/migrations/0002_ticket_email_response.py` — three new columns appear on the note table

**This new migration adds three empty columns to `TICKET`: the guest's address, the admin's answer, and when that answer was sent.**

A migration is the site's only way to change a live database's shape. Nobody edits
the table by hand, because there are copies of it in development, in tests and in
production, and they have to agree. The file is new, so there is no before; it
follows `0001_initial`, which created the table.

The code, in full:

```python
class Migration(migrations.Migration):

    dependencies = [
        ('support', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='ticket',
            name='email',
            field=models.EmailField(blank=True, max_length=254, null=True),
        ),
        migrations.AddField(
            model_name='ticket',
            name='responded',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='ticket',
            name='response',
            field=models.TextField(blank=True, null=True),
        ),
    ]
```

What it buys: existing notes are untouched and legal — all three columns allow
"empty". `response` and `responded` are not used by this pull request at all; they
are the landing pad for the admin ticket queue, which arrives as PR #29. They are
here now because a migration is never edited after it has merged, so the column has
to exist before the queue is written.

### 7.2 `apps/support/models.py` — the note gains a guest address and room for an answer

**Three fields are added to the ticket: `email`, `response` and `responded`, each with a comment saying who fills it.**

This file defines what a ticket *is* in the database. Before the change a ticket had
a kind (help or report), an optional charity, a body, a status, who answered it, and
two timestamps. There was nowhere to record a guest's address, and nowhere to keep
the answer that was emailed.

Before (`apps/support/models.py:27`), the middle of the class:

```python
    charity = models.ForeignKey(
        "charities.Charity", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    body = models.TextField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.NOT_RESPONDED)
    responded_by = models.ForeignKey(
```

After (`apps/support/models.py:27`):

```python
    charity = models.ForeignKey(
        "charities.Charity", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    # A guest's verified address, where the reply goes (§6.3 Tickets). Empty for a
    # signed-in user, whose reply goes to the account's address (D-072).
    email = models.EmailField(null=True, blank=True)
    body = models.TextField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.NOT_RESPONDED)
    responded_by = models.ForeignKey(
        ...
        related_name="+",
    )
    # The admin's answer, as emailed to the submitter (§6.3 Tickets, D-072).
    response = models.TextField(null=True, blank=True)
    responded = models.DateTimeField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    closed = models.DateTimeField(null=True, blank=True)
```

The charity link is a "string label" (`"charities.Charity"`) rather than an import,
and it is schema-only with `related_name="+"`. That is the house rule: support never
imports another area's classes, and no code may walk from a charity back to its
tickets. (The `...` in the box above stands for the three arguments the *before* box
showed — the account it points at, what happens when that account goes, and whether
empty is allowed — all unchanged.)

What it buys: one row can now answer the question "who do I reply to" for both
kinds of visitor, and "what did I reply" for the queue that follows.

### 7.3 `apps/support/services.py` — the only way to file a note, and who is allowed to

**This file goes from empty to the two functions that create tickets, plus the two guards that refuse a bad one.**

Before this change `apps/support/services.py` was three lines: a docstring saying
that other areas call only these functions, and nothing else. A ticket could only be
created by writing to the model directly, which is exactly what the house rules
forbid outside one's own area.

The rules it now enforces, with the real code (`apps/support/services.py:10`):

```python
MAX_BODY_LENGTH = 5000


class TicketError(ValueError):
    """A ticket that cannot be filed as given; the message is safe to show."""


def _clean_body(body: str) -> str:
    body = (body or "").strip()
    if not body:
        raise TicketError("Write your message first.")
    if len(body) > MAX_BODY_LENGTH:
        raise TicketError(f"Keep the message under {MAX_BODY_LENGTH} characters.")
    return body
```

`TicketError` is a special kind of `ValueError` whose text is written for the
visitor, not the log. That is a deliberate promise: the view shows the message
straight onto the page, so no internal detail may end up in it.

Then the rule the doc asks for but does not spell out — exactly one submitter
(`apps/support/services.py:26`):

```python
def _submitter(user_id: int | None, email: str | None) -> dict:
    """Exactly one of a signed-in user or a verified guest address files a ticket."""
    if (user_id is None) == (not email):
        raise TicketError("A ticket needs either a signed-in user or a verified email.")
    if user_id is not None:
        return {"submitted_by_id": user_id, "email": None}
    return {"submitted_by_id": None, "email": email.strip().lower()}
```

Read the condition slowly, because it is the load-bearing line of the file.
`(user_id is None)` is true when there is no user. `(not email)` is true when there
is no address. The two being equal means **both missing or both present**, and both
are refused. A ticket with nobody to answer is a dead end; a ticket with two
possible answers is ambiguous. Guest addresses are lowercased here so
`Guest@Example.com` and `guest@example.com` cannot become two half-verified
identities.

The two entry points (`apps/support/services.py:35` and `:43`):

```python
def submit_help(body: str, *, user_id: int | None = None, email: str | None = None) -> int:
    """File a help request (§6.3 Tickets, SRS FR 18). Returns the ticket id."""
    ticket = Ticket.objects.create(
        kind=Ticket.Kind.HELP, body=_clean_body(body), **_submitter(user_id, email)
    )
    return ticket.id


def submit_report(
    body: str, charity_id: int, *, user_id: int | None = None, email: str | None = None
) -> int:
    """File a report about one charity (§6.3 Tickets, SRS FR 19). Returns the ticket id.

    The caller has already checked that the charity exists; it is a FK, so a
    stale id fails here rather than filing a report about nothing.
    """
    if charity_id is None:
        raise TicketError("Choose the charity you are reporting.")
    ticket = Ticket.objects.create(
        kind=Ticket.Kind.REPORT,
        charity_id=charity_id,
        body=_clean_body(body),
        **_submitter(user_id, email),
    )
    return ticket.id
```

Both return the new ticket's number and nothing else. No model row crosses the
door, so a caller cannot accidentally edit a ticket afterwards. The report function
trusts its caller to have checked that the charity exists, and says why that is
safe: the charity column is a real reference, so a stale number fails at the
database instead of quietly filing a report about nothing.

What it buys: every ticket in the table has exactly one way to be answered, and no
caller can create one without a message.

### 7.4 `apps/support/verification.py` — the six-digit code, and everything that limits it

**This new file is the guest's proof of address: send a code, check a code, and remember a proved address for the rest of the session.**

This is the heart of the change. Before it, nothing existed anywhere for proving an
address in the support area — accounts has a signup check, but support is not
allowed to depend on accounts (§6.1), and no account is created here anyway.

The file's own docstring, which is the argument for why this is not a duplicate:

```python
"""A guest proves they own an email address before filing a ticket (§6.3 Tickets, D-072).

The design asks that a guest's email "must be verified". The flow is the one the
help and report wireframes draw: type the address, press Verify, type the 6-digit
code from the email. The pending code lives in the visitor's session, hashed;
once it matches, the session remembers the address as verified until it ends.

This is support's own check, not the signup code in accounts: §6.1 lets support
depend on nothing, and the two flows differ (no account is created here).
"""
```

The five limits, all in one place (`apps/support/verification.py:28`):

```python
CODE_LIFETIME_SECONDS = 15 * 60
MAX_TRIES = 5
# Codes a single address may be sent per hour, whoever asks: stops the form being
# used to flood someone's inbox from many sessions.
MAX_SENDS_PER_EMAIL_PER_HOUR = 5
SEND_WINDOW_SECONDS = 60 * 60
```

The fingerprint (`apps/support/verification.py:44`):

```python
def _normalise(email: str) -> str:
    return (email or "").strip().lower()


def _digest(email: str, code: str) -> str:
    """A keyed hash, so a leaked session row does not reveal the code."""
    message = f"{email}:{code}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), message, hashlib.sha256).hexdigest()
```

The signup check and this one both hash; the difference is that this one is keyed
with the site's secret key, so an attacker who reads a stolen session row cannot
brute-force the six-digit number offline without also holding the secret. The email
is part of the fingerprint, so a code sent to one address cannot be confirmed
against another.

Sending a code (`apps/support/verification.py:58`):

```python
def start(session, email: str) -> CheckResult:
    """Email a fresh code to `email` and remember it in the session as pending."""
    email = _normalise(email)
    key = _send_count_key(email)
    cache.add(key, 0, SEND_WINDOW_SECONDS)
    try:
        sends = cache.incr(key)
    except ValueError:  # Expired between add and incr: start a fresh window.
        cache.set(key, 1, SEND_WINDOW_SECONDS)
        sends = 1
    if sends > MAX_SENDS_PER_EMAIL_PER_HOUR:
        return CheckResult(False, "Too many codes were sent to that address. Try again in an hour.")

    code = f"{secrets.randbelow(1_000_000):06d}"
    session[PENDING_KEY] = {
        "email": email,
        "digest": _digest(email, code),
        "expires": time.time() + CODE_LIFETIME_SECONDS,
        "tries": 0,
    }
    session.pop(VERIFIED_KEY, None)
    send_ticket_email_code.delay(email, code)
    return CheckResult(True, f"We sent a 6-digit code to {email}. It works for 15 minutes.")
```

Three details worth naming. The counter lives in the shared cache, not the session,
because the limit has to hold across many browsers — a per-session counter would be
bypassed by pressing the button in a private window. The `add`-then-`incr` dance is
there so two visitors sending at the same instant cannot both create a fresh
window; the `ValueError` case is the counter expiring between the two calls. And
`session.pop(VERIFIED_KEY, None)` means asking for a code for a *new* address takes
the previous proof away — the session proves one address at a time, never two.

The random code is `secrets`, not `random`: six digits, uniform, unpredictable.

Checking a code (`apps/support/verification.py:83`):

```python
def confirm(session, code: str) -> CheckResult:
    """Check `code` against the pending one; on a match the address is verified."""
    pending = session.get(PENDING_KEY)
    if not pending:
        return CheckResult(False, "Ask for a code first.")
    if time.time() > pending["expires"]:
        session.pop(PENDING_KEY, None)
        return CheckResult(False, "That code has expired. Ask for a new one.")
    if pending["tries"] >= MAX_TRIES:
        session.pop(PENDING_KEY, None)
        return CheckResult(False, "Too many wrong codes. Ask for a new one.")

    pending["tries"] += 1
    session[PENDING_KEY] = pending  # Reassign so the session notices the change.
    code = (code or "").strip()
    if not hmac.compare_digest(pending["digest"], _digest(pending["email"], code)):
        return CheckResult(False, "That code is not right. Check the email and try again.")

    session.pop(PENDING_KEY, None)
    session[VERIFIED_KEY] = pending["email"]
    return CheckResult(True, f"{pending['email']} is verified.")
```

The three refusals come before the comparison: no code pending, expired, or tried
too often. Note that the try counter is incremented *before* the comparison, and the
session value is reassigned rather than mutated in place — Django only saves a
session value when it is set again, so a quiet `pending["tries"] += 1` alone would
never be stored and the five-try limit would never bite. The comparison itself is
`hmac.compare_digest`, which takes the same time whether the first character
differs or the last, so the reply speed leaks nothing about the code.

The two small readers (`apps/support/verification.py:106`):

```python
def pending_email(session) -> str | None:
    """The address a code was last sent to, while it is still waiting."""
    pending = session.get(PENDING_KEY)
    return pending["email"] if pending else None


def verified_email(session) -> str | None:
    """The address this session has proved it owns, if any."""
    return session.get(VERIFIED_KEY)
```

What it buys: a guest's proof survives from the help page to the report page and
back, no account is needed, and the six-digit number itself is never stored
anywhere on the server.

### 7.5 `apps/support/tasks.py` — the queued email that carries the code

**This new file holds one queued job, which mails the six-digit code and retries three times if the mail server is down.**

Sending email means waiting on an outside machine. Doing that inside a page request
means the visitor stares at a spinner while the mail server thinks, so it goes
through the queue (§4.14 of the design).

The whole file:

```python
"""Emails support sends, queued through Celery (§4.14: email goes out through SES)."""

from celery import shared_task
from django.core.mail import send_mail


@shared_task(autoretry_for=(OSError,), retry_backoff=True, max_retries=3)
def send_ticket_email_code(email: str, code: str) -> None:
    """The 6-digit code a guest types to prove the address is theirs (D-072)."""
    send_mail(
        subject="Your MaaserMart code",
        message=(
            f"Your code is {code}.\n\n"
            "Type it on the MaaserMart help or report page. It works for 15 minutes.\n"
            "If you did not ask for it, you can ignore this email."
        ),
        from_email=None,
        recipient_list=[email],
    )
```

`autoretry_for=(OSError,)` with `retry_backoff=True` means a network-level failure
is retried after a growing pause, three times, without the caller writing retry
logic. `from_email=None` takes the site's configured sender, so no address is
hard-coded here.

The last line of the email matters as much as the code: "If you did not ask for it,
you can ignore this email." A person who receives a code they did not request has
just learned that somebody typed their address into this form, and the sentence
tells them it is harmless.

What it buys: the visitor's page returns immediately, and a mailbox that is briefly
unreachable does not lose the code.

### 7.6 `apps/support/views.py` — the two pages, and the button that says which step you are on

**This empty file becomes the two page handlers; each is one form, and the pressed button's name decides whether the request is "send a code", "check a code", "find a charity" or "send the note".**

Before the change this file was zero bytes. The two pages had to be written from
nothing, and the interesting decision is how the steps share one form.

Its docstring states the design (`apps/support/views.py:1`):

```python
"""The help and report pages (§6.2, SRS FR 18 and FR 19, D-072).

Both pages are one form posted back to itself. The button pressed names the
step (`action`): a guest sends a code, then types it, then submits; a signed-in
user only submits. Each re-render keeps what was typed, so a step never costs
the visitor their message.
"""
```

One form, posted to the same address, with several buttons. Each button carries a
different `action` value, so the visitor's page never has to juggle separate forms
and never loses the paragraph in progress.

The guest step (`apps/support/views.py:22`):

```python
def _guest_step(request: HttpRequest, action: str) -> tuple[str | None, str | None]:
    """Run a guest's send-code or verify step. Returns (notice, error)."""
    if action == "send_code":
        email = request.POST.get("email", "").strip()
        try:
            validate_email(email)
        except ValidationError:
            return None, "Enter a valid email address."
        result = verification.start(request.session, email)
    else:
        result = verification.confirm(request.session, request.POST.get("code", ""))
    return (result.message, None) if result.ok else (None, result.message)
```

The address is checked by Django's own validator before anything is mailed, so a
typo like `nope` is refused on the page rather than bounced by the mail server.
Nothing is sent on a refusal, which the tests pin down.

Who is filing (`apps/support/views.py:36`):

```python
def _submitter(request: HttpRequest) -> dict:
    """Who files the ticket: the account, or the guest's verified address."""
    if request.user.is_authenticated:
        return {"user_id": request.user.id}
    email = verification.verified_email(request.session)
    if not email:
        raise TicketError("Verify your email address first.")
    return {"email": email}
```

The signed-in check comes first, so a member is never asked to prove the address
their account already holds. For a guest, the address comes from the session — never
from the posted form — so a visitor cannot type one address, verify it, and then
have the ticket claim a different one.

What each page is handed (`apps/support/views.py:46`):

```python
def _context(request: HttpRequest, **extra) -> dict:
    guest = not request.user.is_authenticated
    return {
        "guest": guest,
        "verified_email": verification.verified_email(request.session) if guest else None,
        "pending_email": verification.pending_email(request.session) if guest else None,
        "body": request.POST.get("body", ""),
        "max_body_length": MAX_BODY_LENGTH,
        **extra,
    }
```

`"body": request.POST.get("body", "")` is the line that keeps the visitor's words.
Every step re-renders with whatever was in the box. The length limit is passed to
the page so the textarea carries the same `maxlength` as the rule in `services.py`,
and the two cannot drift apart.

The help page (`apps/support/views.py:58`):

```python
def help_page(request: HttpRequest) -> HttpResponse:
    """Ask the site's admins for help (FR 18)."""
    notice = error = None
    if request.method == "POST":
        action = request.POST.get("action", "submit")
        if action in ("send_code", "verify") and not request.user.is_authenticated:
            notice, error = _guest_step(request, action)
        else:
            try:
                submit_help(request.POST.get("body", ""), **_submitter(request))
            except TicketError as exc:
                error = str(exc)
            else:
                return render(request, "support/sent.html", {"kind": "help"})
    return render(request, "support/help.html", _context(request, notice=notice, error=error))
```

The `and not request.user.is_authenticated` is not decoration: without it, a member
could post a "send a code" step and the site would mail a code for an address that
member does not own. A test covers exactly that.

The report page (`apps/support/views.py:75`):

```python
def report_page(request: HttpRequest) -> HttpResponse:
    """Report a charity to the site's admins (FR 19).

    `?charity=<id>` (the charity page's "Report this charity" link) arrives with
    the charity chosen; otherwise the visitor searches by name and picks one.
    """
    data = request.POST if request.method == "POST" else request.GET
    charity = get_charity_choice(data.get("charity"))
    query = data.get("q", "").strip()
    notice = error = None
    if request.method == "POST":
        action = request.POST.get("action", "submit")
        if action == "search":
            charity = None
        elif action in ("send_code", "verify") and not request.user.is_authenticated:
            notice, error = _guest_step(request, action)
        elif charity is None:
            error = "Choose the charity you are reporting."
        else:
            try:
                submit_report(request.POST.get("body", ""), charity.id, **_submitter(request))
            except TicketError as exc:
                error = str(exc)
            else:
                return render(request, "support/sent.html", {"kind": "report", "charity": charity})
    matches = find_charities_by_name(query) if query and charity is None else ()
    return render(
        request,
        "support/report.html",
        _context(
            request,
            notice=notice,
            error=error,
            charity=charity,
            query=query,
            matches=matches,
        ),
    )
```

Reading it in order: the charity comes from wherever the values are — the query
string on a first visit, the form on a later step — so the link from a charity page
and the pick list share one code path. Pressing **Choose another** sets the action
to `search`, which clears the choice and brings the search box back. The search
itself only runs when there is still no charity, because searching while one is
chosen would throw away the choice.

What it buys: one visitor can report a charity in four clicks from that charity's
own page, and a guest can do it without ever creating an account.

### 7.7 `apps/support/urls.py` and `config/urls.py` — the two addresses exist, and the top bar stops lying

**Support's address list goes from empty to the two pages, and the site's root address list starts including it.**

Before the change `apps/support/urls.py` was an empty list with a suppressed unused
import, and `config/urls.py` did not include it. That empty list is why the Help and
Report links in the top bar were dead: their addresses could not be reversed.

Before (`apps/support/urls.py:1`):

```python
from django.urls import path  # noqa: F401

app_name = "support"

urlpatterns = []
```

After (`apps/support/urls.py:1`):

```python
"""Support's pages under /support/ (D-026)."""

from django.urls import path

from . import views

app_name = "support"

urlpatterns = [
    path("help/", views.help_page, name="help"),
    path("report/", views.report_page, name="report"),
]
```

And one line in the root list (`config/urls.py:11`):

```python
    path("charity/", include("apps.charities.urls")),
    path("support/", include("apps.support.urls")),
    path("django-admin/", admin.site.urls),
```

What it buys: `/support/help/` and `/support/report/` exist, and the navigation
links that pointed at them now go somewhere.

### 7.8 `apps/charities/services.py` — the charity area's new door for other areas

**Two read-only lookups are added for other areas: find charities whose name contains a word, and fetch one charity's number and name.**

Before this change, charities' services could list a page of charities for the
listing page and fetch one for the detail page, and that was all. There was no small
lookup for another area that just needs "which charities match this name".

The new block, with the comment that justifies its existence (`apps/charities/services.py:284`):

```python
# --- Lookups for other apps ---------------------------------------------------
# Small reads other apps need without a whole listing page: support's report form
# picks a charity by name (D-072). They return `CharityChoice`, never a model row.


@dataclass(frozen=True)
class CharityChoice:
    """A charity as a pick list shows it: its id and its name."""

    id: int
    name: str


CHARITY_LOOKUP_LIMIT = 10


def find_charities_by_name(
    term: str, limit: int = CHARITY_LOOKUP_LIMIT
) -> tuple[CharityChoice, ...]:
    """Charities whose name contains `term`, case-insensitively, A to Z.

    An empty or blank term matches nothing, so a pick list never dumps the table.
    """
    term = (term or "").strip()
    if not term:
        return ()
    limit = max(1, min(limit, CHARITY_LOOKUP_LIMIT))
    rows = Charity.objects.filter(name__icontains=term).only("id", "name").order_by("name", "id")
    return tuple(CharityChoice(id=row.id, name=row.name) for row in rows[:limit])


def get_charity_choice(charity_id) -> CharityChoice | None:
    """One charity's id and name, or None when no row has that id."""
    try:
        charity_id = int(charity_id)
    except (TypeError, ValueError):
        return None
    row = Charity.objects.filter(pk=charity_id).only("id", "name").first()
    return None if row is None else CharityChoice(id=row.id, name=row.name)
```

Four small protections, each earning its line. A blank search returns nothing, so
opening the report page does not print the whole charity table. The limit is capped
at ten from above *and* at one from below, so a caller cannot ask for a thousand
rows, and cannot ask for zero. `.only("id", "name")` fetches two columns instead of
the whole record — the object that leaves is a frozen charity choice anyway, so
pulling descriptions and images would be waste. And `get_charity_choice` accepts
anything and answers `None` rather than raising, because its argument comes from a
URL a visitor can type freely.

`CharityChoice` being frozen and made of two plain values is what keeps the app
boundary honest: support receives a name and a number, not a charity record it could
then modify.

What it buys: the report form can name a charity without support knowing anything
about how charities are stored — and the charity page's link can point at one by
number.

### 7.9 The five templates — what the visitor actually sees

**Five new templates: the help page, the report page, a shared "your email" block, a shared two-line message block, and the thank-you page.**

Before this change the support area had no templates at all.

The email block is included by both pages, so the guest steps are written once
(`apps/support/templates/support/_guest_email.html:1`):

```html
{# A guest proves the address before the form will submit (§6.3 Tickets, D-072). #}
<fieldset class="ticket-form__email">
  <legend>Your email</legend>
  {% if verified_email %}
    <p class="ticket-form__verified">Replies go to <strong>{{ verified_email }}</strong> (verified).</p>
  {% else %}
    <label for="ticket-email">Email address</label>
    <div class="ticket-form__row">
      <input id="ticket-email" name="email" type="email" autocomplete="email"
             value="{{ pending_email|default:'' }}">
      <button class="button button--secondary" type="submit" name="action" value="send_code"
              formnovalidate>{% if pending_email %}Send a new code{% else %}Verify{% endif %}</button>
    </div>
    {% if pending_email %}
      <label for="ticket-code">6-digit code</label>
      <div class="ticket-form__row">
        <input id="ticket-code" name="code" inputmode="numeric" autocomplete="one-time-code"
               maxlength="6" pattern="[0-9]{6}">
        <button class="button button--secondary" type="submit" name="action" value="verify"
                formnovalidate>Check code</button>
      </div>
    {% endif %}
  {% endif %}
</fieldset>
```

The code box only appears once a code has been sent (`{% if pending_email %}`), so
the page asks for one thing at a time. `formnovalidate` on the two step buttons lets
a visitor press Verify or Check code while the message box is still empty — the
message is required only when the note itself is sent. `inputmode="numeric"` brings
up a number pad on a phone, and `autocomplete="one-time-code"` lets the phone offer
the digits it just received.

The two-line message block (`apps/support/templates/support/_messages.html:1`):

```html
{% if notice %}<p class="ticket-form__notice" role="status">{{ notice }}</p>{% endif %}
{% if error %}<p class="ticket-form__error" role="alert">{{ error }}</p>{% endif %}
```

`role="status"` and `role="alert"` are how a screen reader is told that something
appeared on the page. A visitor who cannot see the page still hears the sentence.

The help page (`apps/support/templates/support/help.html:1`) is the whole page in
twenty lines:

```html
{% extends "base.html" %}

{% block title %}Help &middot; MaaserMart{% endblock %}

{% block content %}
  <section class="ticket-page">
    <h1>Help</h1>
    <p>Ask a question about MaaserMart and an admin will email you an answer.</p>

    <form class="ticket-form" method="post" action="{% url 'support:help' %}">
      {% csrf_token %}
      {% include "support/_messages.html" %}
      {% if guest %}{% include "support/_guest_email.html" %}{% endif %}

      <label for="ticket-body">How can we help?</label>
      <textarea id="ticket-body" name="body" rows="8" maxlength="{{ max_body_length }}">{{ body }}</textarea>

      <button class="button" type="submit" name="action" value="submit"
              {% if guest and not verified_email %}disabled{% endif %}>Send</button>
    </form>
  </section>
{% endblock %}
```

Two lines carry the behaviour. `{% if guest %}` decides whether the email block is
on the page at all, so a member sees one box and one button. And `disabled` on Send
while a guest is unverified makes the site's rule visible: you can see that sending
is possible, and you can see what is holding it. The `{% csrf_token %}` is the
standard guard that stops another website from posting this form on a visitor's
behalf.

The report page (`apps/support/templates/support/report.html:1`) adds the charity
step:

```html
      <fieldset class="ticket-form__charity">
        <legend>Charity</legend>
        {% if charity %}
          <input type="hidden" name="charity" value="{{ charity.id }}">
          <p class="ticket-form__chosen">
            Reporting <a href="{% url 'charities:detail' charity.id %}">{{ charity.name }}</a>
            <button class="button button--link" type="submit" name="action" value="search"
                    formnovalidate>Choose another</button>
          </p>
        {% else %}
          <label for="ticket-q">Charity name</label>
          <div class="ticket-form__row">
            <input id="ticket-q" name="q" type="search" value="{{ query }}">
            <button class="button button--secondary" type="submit" name="action" value="search"
                    formnovalidate>Find</button>
          </div>
          {% if query %}
            {% if matches %}
              <ul class="ticket-form__matches">
                {% for match in matches %}
                  <li>
                    <label><input type="radio" name="charity" value="{{ match.id }}"> {{ match.name }}</label>
                  </li>
                {% endfor %}
              </ul>
            {% else %}
              <p>No charity matches &ldquo;{{ query }}&rdquo;.</p>
            {% endif %}
          {% endif %}
        {% endif %}
      </fieldset>
```

Once a charity is chosen, its number rides in a hidden field, so every later step
(the code, then the message) still knows which charity is being reported without
the visitor re-picking it. The name is shown as a link to the charity's page, so the
visitor can double-check they picked the right one. And a search that finds nothing
says so, instead of showing an empty list with no explanation.

The thank-you page (`apps/support/templates/support/sent.html:1`) is one page for
both kinds, branching on `kind`:

```html
    <h1>{% if kind == "report" %}Report sent{% else %}Message sent{% endif %}</h1>
    {% if kind == "report" %}
      <p>Thank you. An admin will look into {{ charity.name }} and email you.</p>
      <p><a href="{% url 'charities:detail' charity.id %}">Back to {{ charity.name }}</a></p>
    {% else %}
      <p>Thank you. An admin will email you an answer.</p>
      <p><a href="{% url 'charities:listing' %}">Back to the charities</a></p>
    {% endif %}
```

It names the charity back to the reporter, which doubles as a last chance to
notice a wrong pick, and offers a link back to whatever page makes sense for the
kind of note.

What it buys: a visitor can leave either page knowing exactly what happens next —
an email, from a person.

### 7.10 `apps/charities/templates/charities/detail.html` — one link at the bottom of each charity page

**Five lines are added to the charity page: a "Report this charity" link that arrives at the report form with the charity already chosen.**

Before this change, a visitor who spotted a wrong phone number on a charity's page
had no way to say so from that page — they had to find the top bar, open Report, and
then search for the charity they were already looking at.

Before (`apps/charities/templates/charities/detail.html:124`):

```html
      <p><a href="{% url 'charities:listing' %}">Back to all charities</a></p>
    </footer>
  </article>
{% endblock %}
```

After (`apps/charities/templates/charities/detail.html:127`):

```html
      <p><a href="{% url 'charities:listing' %}">Back to all charities</a></p>
    </footer>

    {# FR 19: the report arrives with this charity already chosen (D-072). #}
    <p class="charity-page__report">
      <a href="{% url 'support:report' %}?charity={{ charity.id }}">Report this charity</a>
    </p>
  </article>
{% endblock %}
```

The link carries the charity's number in the address (`?charity=7`), which is what
`report_page` reads first. What it buys: reporting the page you are looking at takes
one click instead of a search.

### 7.11 `static/css/site.css` — the buttons and notices for the two new pages

**Ninety-one lines of styling are added: the page width, the stacked form, the two kinds of button, and the notice and error bars.**

Before this change the stylesheet had no rules for any of it, so the new pages would
have used the browser's default look.

The two message bars (`static/css/site.css:789`):

```css
.ticket-form__notice {
  background: #eef4fb;
  border-left: 4px solid var(--brand-blue);
  margin: 0;
  padding: 0.5rem 0.75rem;
}

.ticket-form__error {
  background: #fdeeee;
  border-left: 4px solid #b3261e;
  color: #8c1d18;
  margin: 0;
  padding: 0.5rem 0.75rem;
}
```

Blue bar for "here is what just happened", red bar for "that did not work". The two
never appear at once, and the colour is the second signal after the words
themselves.

The disabled button (`static/css/site.css:822`):

```css
.button:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}
```

What it buys: the Send button a guest cannot press yet looks like a button that
cannot be pressed, rather than looking broken.

### 7.12 `tests/unit/test_prod_settings.py` — the first real queue job changes an old test

**One test is renamed and rewritten: it used to prove that no app had a queued job, and now proves the opposite.**

Before the change, the site had no background jobs at all, and a test pinned that
fact so a misconfigured queue would be noticed. This pull request adds the first
job, so the test had to change its claim.

Before (`tests/unit/test_prod_settings.py:140`):

```python
def test_the_celery_app_is_configured_and_discovers_no_tasks_yet():
    """`config/__init__.py` imports this app, so a bad name breaks every command."""
    from config.celery import app
    ...
    assert app.conf.task_always_eager is True
    # No app defines a task yet; the audit's M7 list is where the first one lands.
    assert not [name for name in app.tasks if not name.startswith("celery.")]
```

After (`tests/unit/test_prod_settings.py:140`):

```python
def test_the_celery_app_is_configured_and_discovers_the_apps_tasks():
    """`config/__init__.py` imports this app, so a bad name breaks every command."""
    from config.celery import app
    ...
    assert app.conf.task_always_eager is True
    # Autodiscovery finds each app's tasks.py; support's email code is the first (D-072).
    app.loader.import_default_modules()
    assert "apps.support.tasks.send_ticket_email_code" in app.tasks
```

The `...` in both boxes stands for three unchanged assertions in the middle of the
test — the queue address, and the two settings the test file builds to make the suite
run without a real queue. They are identical before and after.

The old assertion was "the list of jobs is empty". The new one names the job, so the
test now fails if the module is renamed or stops being discovered — a stronger
claim than "not zero".

What it buys: a renamed task file is caught by the test suite instead of by a guest
who never receives a code.

---

## 8. The tests

The new file is `tests/unit/test_support_tickets.py` (44 collected tests). Read the
names as sentences, grouped by what they prove.

**The note itself** — `test_help_from_a_user` (a member's ticket points at the
account, with no separate address), `test_help_from_a_guest_lowercases_the_address`,
`test_report_names_the_charity`, `test_refuses_an_empty_or_huge_body` (four cases:
empty, spaces, missing, 5,001 characters — and no ticket is created in any of them),
`test_needs_exactly_one_submitter` (neither, and both), `test_report_needs_a_charity`.

**Finding a charity** — `test_find_by_name_is_case_insensitive_and_sorted` (searching
"o" returns Bikur Cholim, Hatzolah, Zion Fund, so both the matching and the A-to-Z
order are pinned), `test_blank_term_matches_nothing`, `test_limit_is_capped` (asking
for 500 gets 10), `test_unknown_id_is_none` (four kinds of junk: missing, empty,
text, a number that does not exist), `test_known_id`.

**The six-digit code** — `test_code_is_emailed_and_confirms` walks the whole path;
`test_the_session_never_holds_the_code` is the important one, asserting the code does
not appear anywhere in the stored session; `test_wrong_code`, `test_no_pending_code`,
`test_too_many_tries_drops_the_code`, `test_expired_code` (time is moved forward past
the fifteen minutes), `test_sends_per_address_are_capped` (five go out, the sixth is
refused, and only five emails exist), `test_a_new_code_unverifies`.

**The help page** — `test_guest_sees_the_email_step_and_a_disabled_send`,
`test_guest_flow_files_a_ticket`, `test_guest_cannot_submit_unverified`,
`test_bad_email_is_refused` (and no email is sent), `test_typed_message_survives_a_step`
(the "Keep me" paragraph is still in the box after the code step),
`test_wrong_code_shows_an_error`, `test_signed_in_user_skips_the_email_step`,
`test_signed_in_user_cannot_post_a_code_step`, `test_empty_body_shows_an_error`.

**The report page** — `test_charity_page_links_to_the_report` (the link goes to the
right address with the right number), `test_link_arrives_with_the_charity_chosen`,
`test_search_lists_matches` (and the non-matching charity's name is *absent*, so the
search really filters), `test_search_with_no_match`, `test_choose_another_clears_the_choice`,
`test_guest_report_is_filed`, `test_report_without_a_charity_is_refused`,
`test_nav_shows_help_and_report` (the top bar links are no longer dead).

No test was deleted. One was renamed and given a sharper claim, and that is quoted in
section 7.12.
