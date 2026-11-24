# PR #29 — The admin ticket queue at `/admin/tickets/`

- Branch: `support/ticket-queue` → `main`
- Merge commit: `ac90251` (2026-11-24)
- Author: Platform Lead (Shaul)
- Decision recorded: D-073 (amends D-072)
- Size: 13 files, +602 / −34
- Amended after review: branch `docs/dilbert-and-review-fixes` ranks the queue's statuses explicitly (section 7.3). The code quoted below is the amended code, not the merge exactly.

---

## 1. Read this part even if you read nothing else

The previous change (PR #28) put a suggestion box in the lobby. Anyone can drop a
note in: "I have a question", or "this charity's phone number is wrong". Notes pile
up in a database table. **Nobody could read them.** This change builds the desk
where the notes are read.

It is one page, at an address only staff can open. Every note that is not yet
finished appears on it as a card: who wrote it, what they said, which charity it is
about, and a box to type an answer. Two buttons sit under the box. **Send reply**
answers the customer by email and marks the note as answered, but leaves it on the
desk in case a second answer is needed. **Close** takes the note off the desk,
sending anything typed in the box first, so nobody gets closed out with no reply.

There is a second, quieter change in here, and it is the one that took the most
thought. Until now a note from a signed-in member recorded *who* they were but not
*where to write back*. To answer them, the support area would have had to look up
the member's account — and the house rules forbid one area of the site reaching
into another's table. So the note now carries a copy of the member's email address,
taken at the moment they wrote. The reply goes where the person was when they asked.
The cost, stated openly in the decision record: if they change their account email
tomorrow, old notes still reply to the old address.

Two small things go with it. A line is added to the front page of Django's own
built-in admin, so staff have a link to the queue instead of typing the address.
And one new test proves that when the mail server is down for good, the answer is
not lost: the note stays answered on the page, and the failure is written to the
log with the note's number, so somebody can find it and phone the person instead.

Everything below is the same idea in more detail.

---

## 2. How to read this file

This file is for two people at once.

- If you do not write software, read the **glossary**, then the **story**, then the
  bold one-line summary at the top of each file section.
- If you are reviewing the code, those same sections carry the real code, quoted,
  in reading order, with a `file.py:line` address on each box.

Three rules:

1. **Read the glossary first.** Every term is defined there.
2. **Every code box is optional.** The sentence directly above each box says what it
   does in plain English.
3. **Skim the bold lines.** They are the summary.

---

## 3. The glossary

Ten words.

- **Ticket** — a note from a visitor: a question (Help) or a complaint about a
  charity (Report). One row in the table called `TICKET`.
- **The queue** — the list of tickets still being worked on. In this code "still
  being worked on" means literally *not closed*; an answered ticket stays until
  somebody presses Close.
- **Admin** — a member of staff with the power to see the queue. Everyone else gets
  refused, even if signed in.
- **Card** — how one ticket is drawn on the queue page: a box with the details and a
  reply field.
- **Service** — the one door one part of the site is allowed to knock on to use
  another part. No area reads another area's table directly.
- **Transaction** — a group of database changes that either all happen or none do.
  It is how "save the answer" and "email the answer" are kept from disagreeing.
- **Commit** — the moment a transaction's changes become permanent. Anything queued
  to happen "after commit" happens only if the save really succeeded.
- **Celery** — the site's queue for slow work, here: sending mail. Work is handed
  over so the staff member's page does not wait on the mail server.
- **Retry** — trying the same thing again after a failure, with a growing pause. The
  reply email gets three attempts.
- **403** — the web's way of saying "I know who you are, and you may not do this".
  Different from being sent to log in, which is what happens when the site does not
  know who you are yet.

Names that exist only in this code, and the plain word used here:

| in the code | in this file |
|---|---|
| `TicketCard` | card (one ticket as drawn on the page) |
| `get_tickets()` | the queue's contents |
| `resolve_ticket(...)` | answer or close one ticket |
| `RESPOND` / `CLOSE` | the two buttons |
| `from_member` | "this note has an account behind it" |
| `send_ticket_reply` | the queued email job |
| `on_commit` | "only if the save really happened" |
| `select_for_update()` | "lock this row while I change it" |

---

## 4. The story

### What the site does all day

1. A visitor browses charities.
2. Someone asks for help, or reports a wrong charity listing. The note lands in the
   `TICKET` table.
3. An admin reads the notes and replies by email.
4. Somebody with a question about the answer writes back, and the conversation
   continues.

Step 3 did not exist. After PR #28, notes were arriving into a table that only a
database console could read.

### What was wrong, in three pieces

**Nobody could see the notes.** There was no page. The support area had no staff-facing
view at all.

**A note had no address for the reply.** A guest's note had the address they proved
when they wrote it, so that was fine. A signed-in member's note recorded their
account and nothing else. To send the answer, the site would have to read the
member's account row — and the house rule (§6.1, D-034) says the support area may
not touch accounts' tables, not even through the reference the note already holds.
The honest options were: make support depend on accounts, or copy the address onto
the note. The second was chosen.

**Nothing said what happens when a reply cannot be sent.** Email is the least
reliable part of any website. If the mail server is down when an admin presses Send
reply, the naive design loses the answer *and* marks the note answered, so nobody
ever knows the customer was never told.

### The cost of leaving it

A concrete case, carried through. A guest reports that a charity's donation link
goes to the wrong place. The admin opens the queue, types "Thanks — fixed, and
sorry", presses Send reply. If the mail server is having a bad hour, the naive
version saves the text, marks the note answered, and the guest never hears
anything. They conclude the site ignores reports. The bend in the wrong link, on a
site whose whole purpose is routing money to the right charity, stays there.

### The fix, in one sentence

One admin-only page listing every ticket that is not closed, with a reply box and
two buttons on each card; the reply is saved and emailed inside a transaction so
the two cannot disagree; and the note now always carries the address its answer goes
to, copied when it was written.

The consequences, listed plainly:

- A visitor is asked to log in; a member who is not staff is refused outright.
- Unanswered notes come first, oldest first. An admin works top-down and never
  misses an old one.
- An answered note keeps its place in the queue until it is closed. "Open" means
  "not closed", so a second reply is always possible.
- Text typed into a reply box survives a failed attempt, so a rejected answer is not
  retyped.
- If the mail server fails, the note stays answered on the page, and the log records
  the note's number.
- A signed-in member with no email address on their account is told so, instead of
  having a note filed that nobody can answer.

---

## 5. Contradictions

**D-072 said the note's email field is empty for a signed-in user. D-073 says it is
always set.** This is not a mistake in either; it is a decision changing its mind,
and the code comments were updated to say so. Trust the newer one:

Before the change (`apps/support/models.py:30`):

```python
    # A guest's verified address, where the reply goes (§6.3 Tickets). Empty for a
    # signed-in user, whose reply goes to the account's address (D-072).
    email = models.EmailField(null=True, blank=True)
```

After (`apps/support/models.py:30`):

```python
    # Where the reply goes (§6.3 Tickets): a guest's verified address, or a signed-in
    # user's account address as it was when they filed (D-072, D-073).
    email = models.EmailField(null=True, blank=True)
```

Note the field itself is unchanged — same column, same "may be empty". Only the
meaning of "empty" narrowed: it should not happen for a new note any more. Old rows
may still have it empty, which is why the database still allows it.

Nothing else disagrees. The test file's own test names match what the tests assert,
and the pull request lists the three things it deliberately did not do: no
pagination, no link in the site's own top bar, and no link to the approvals queue
that does not exist yet.

---

## 6. Reading order

| # | File | What it is | Why here |
|---|---|---|---|
| 1 | `apps/support/models.py` | the changed comment on the note's email field | the data's meaning comes first |
| 2 | `apps/charities/services.py` | a bulk charity lookup for a page of cards | what the queue needs to draw itself |
| 3 | `apps/support/services.py` | the queue's contents, and answer/close | the rules |
| 4 | `apps/support/tasks.py` | the queued reply email, with retries | how the answer leaves the building |
| 5 | `apps/support/views.py` | the page and the two buttons | permissions, then actions |
| 6 | `apps/support/admin_urls.py`, `config/urls.py` | the addresses | wiring |
| 7 | `apps/support/templates/support/ticket_queue.html` | what an admin sees | rendering |
| 8 | `templates/admin/index.html` | the link from Django's own admin | the doorway |
| 9 | `static/css/site.css` | the card styling | looks |
| 10 | `docs/DECISIONS.md` | the D-073 record: the decision in prose | the argument, not the code |
| 11 | `tests/unit/test_ticket_queue.py`, `tests/unit/test_support_tickets.py` | the proof | last |

The shape in one sentence: **`services.py` decides what the queue contains and what
answering means, `tasks.py` sends the mail, and `views.py` shows the whole thing to
staff only.**

---

## 7. The files

### 7.1 `apps/support/models.py` — the note's email field stops meaning "guests only"

**One comment changes and nothing else: the email column now means "where the reply goes", for everybody.**

This file defines what a ticket is. The only change is a comment, quoted in full
under *Contradictions* above, and it is worth its own section because it is the
whole of D-073's data consequence: no new column, no migration, just a rule that now
always holds.

What it buys: a reader of the model is told that an empty email is a bug, not a
design. Nothing enforces it in the database, because old rows exist.

### 7.2 `apps/charities/services.py` — one lookup for a whole page of cards

**A new bulk lookup fetches the id and name of many charities at once, so drawing twenty cards costs one question to the database instead of twenty.**

Before this change the charities area offered a lookup for a *single* charity by
number (`get_charity_choice`, added in PR #28). A queue page showing twenty reports
would have called it twenty times — one database round trip per card, on a page an
admin refreshes constantly.

The new function (`apps/charities/services.py:325`):

```python
def get_charity_choices(charity_ids) -> dict[int, CharityChoice]:
    """Id and name for each existing charity among `charity_ids`, keyed by id."""
    ids = {int(i) for i in charity_ids if i is not None}
    if not ids:
        return {}
    rows = Charity.objects.filter(pk__in=ids).only("id", "name")
    return {row.id: CharityChoice(id=row.id, name=row.name) for row in rows}
```

It takes a bag of ids and returns a dictionary from id to charity choice. `if i is
not None` is there because most tickets are help requests with no charity at all, and
the caller passes every ticket's charity field. `.only("id", "name")` fetches two
columns. An id with no row simply does not appear in the answer, which is how the
queue page knows to say "a charity that has since been removed" rather than showing
a blank.

What it buys: one query per page instead of one per card, and the queue still knows
nothing about how charities are stored.

### 7.3 `apps/support/services.py` — what the queue contains, and what answering or closing means

**This is the important file: it grows a card-shaped read for the queue, and the answer-or-close action, with the rule that the email only goes out if the save really happened.**

Before the change this file could only file tickets. It had two submitted-by rules
(`_submitter`) that described a guest's note and a member's note as two different
things.

The first change is a merge of those two rules into one (`apps/support/services.py:26`):

Before:

```python
def _clean_body(body: str) -> str:
    body = (body or "").strip()
    if not body:
        raise TicketError("Write your message first.")
    if len(body) > MAX_BODY_LENGTH:
        raise TicketError(f"Keep the message under {MAX_BODY_LENGTH} characters.")
    return body


def _submitter(user_id: int | None, email: str | None) -> dict:
    """Exactly one of a signed-in user or a verified guest address files a ticket."""
    if (user_id is None) == (not email):
        raise TicketError("A ticket needs either a signed-in user or a verified email.")
    if user_id is not None:
        return {"submitted_by_id": user_id, "email": None}
    return {"submitted_by_id": None, "email": email.strip().lower()}
```

After (`apps/support/services.py:26`):

```python
def _clean_text(text: str, empty_message: str) -> str:
    text = (text or "").strip()
    if not text:
        raise TicketError(empty_message)
    if len(text) > MAX_BODY_LENGTH:
        raise TicketError(f"Keep the message under {MAX_BODY_LENGTH} characters.")
    return text


def _reply_to(email: str | None) -> str:
    email = (email or "").strip().lower()
    if not email:
        raise TicketError("A ticket needs an email address for the reply.")
    return email
```

Two swaps, both consequences of always having an address. `_clean_body` becomes
`_clean_text` and takes the "you left it empty" sentence as an argument, because the
same check now guards an admin's reply too ("Write the reply first."). And
`_submitter` becomes `_reply_to`: it no longer chooses between a user and an address,
it simply insists on an address. The either-or rule from PR #28 has no reason to
exist now that a member's note carries one too.

The two filing functions follow (`apps/support/services.py:42`):

Before:

```python
def submit_help(body: str, *, user_id: int | None = None, email: str | None = None) -> int:
    """File a help request (§6.3 Tickets, SRS FR 18). Returns the ticket id."""
    ticket = Ticket.objects.create(
        kind=Ticket.Kind.HELP, body=_clean_body(body), **_submitter(user_id, email)
    )
    return ticket.id
```

After (`apps/support/services.py:42`):

```python
def submit_help(body: str, *, email: str, user_id: int | None = None) -> int:
    """File a help request (§6.3 Tickets, SRS FR 18). Returns the ticket id.

    `email` is where the answer goes: a guest's verified address, or a signed-in
    user's account address (D-073). `user_id` is the account, if there is one.
    """
    ticket = Ticket.objects.create(
        kind=Ticket.Kind.HELP,
        body=_clean_text(body, "Write your message first."),
        email=_reply_to(email),
        submitted_by_id=user_id,
    )
    return ticket.id
```

`email` is now a required keyword argument with no default, so no caller can forget
it and no note can be created without an address. `submit_report` changes the same
way at `apps/support/services.py:57`.

Then the card, which is the shape the queue page draws (`apps/support/services.py:78`):

```python
@dataclass(frozen=True)
class TicketCard:
    """One ticket as the admin queue shows it."""

    id: int
    kind: str
    kind_label: str
    body: str
    email: str | None
    # False for a guest: the queue labels the ticket "guest" (§6.3 failure paths).
    from_member: bool
    charity_id: int | None
    charity_name: str | None
    status: str
    status_label: str
    response: str | None
    responded: datetime | None
    created: datetime
```

A frozen list of plain values, not a database row. Two fields exist only for the
page: `kind_label` and `status_label` are the human words ("Help", "Answered")
worked out here rather than in the template, and `from_member` is a plain yes/no so
the page never has to reach for another area's account.

The queue's contents (`apps/support/services.py:98`):

```python
# The order the queue works in: unanswered first. Spelled out rather than left to
# the alphabet, where "not_responded" happened to sort before "responded"; a new
# status must be ranked here, and `test_every_open_status_has_a_rank` says so.
STATUS_RANK = {
    Ticket.Status.NOT_RESPONDED: 0,
    Ticket.Status.RESPONDED: 1,
}
UNRANKED = 99


def _status_rank():
    """A sortable number per status, 99 for one nobody ranked."""
    return Case(
        *[When(status=status, then=Value(rank)) for status, rank in STATUS_RANK.items()],
        default=Value(UNRANKED),
        output_field=IntegerField(),
    )


def get_tickets() -> list[TicketCard]:
    """Every ticket not yet closed, unanswered first, oldest first within each."""
    rows = list(
        # Ordered by rank rather than by the status word, so the order survives a
        # new status (§5.3's (status, created) index no longer serves it; the queue
        # is small, and being wrong quietly is worse than a sort).
        Ticket.objects.exclude(status=Ticket.Status.CLOSED)
        .annotate(status_rank=_status_rank())
        .order_by("status_rank", "created", "id")
    )
    charities = get_charity_choices(row.charity_id for row in rows)
    cards = []
    for row in rows:
        charity = charities.get(row.charity_id)
        cards.append(
            TicketCard(
                id=row.id,
                kind=row.kind,
                kind_label=row.get_kind_display(),
                body=row.body,
                email=row.email,
                from_member=row.submitted_by_id is not None,
                charity_id=row.charity_id,
                charity_name=charity.name if charity else None,
                status=row.status,
                status_label=row.get_status_display(),
                response=row.response,
                responded=row.responded,
                created=row.created,
            )
        )
    return cards
```

The ordering is the part that was quietly fragile. As first merged, the queue asked
the database to sort by the status *word*, which put unanswered first only because
`not_responded` happens to come before `responded` in the alphabet. It worked, and it
had the nice property of reusing an index the design doc already asks for. But it was
an accident waiting for a third status: a word like `awaiting_info` sorts *before*
`not_responded`, so a change that looked unrelated would have pushed the oldest
unanswered notes to the bottom of the queue, with no error and no failing test.

The fix, from the follow-up review branch, is to rank the statuses explicitly in a
small table, `STATUS_RANK`, and sort by that number. An unranked status sorts last
(99) rather than landing somewhere arbitrary, and a test pins the table to the
model's list of open statuses — so adding a status without ranking it fails the suite
instead of quietly reordering the queue. The trade-off is honest and small: the sort
no longer uses the `(status, created)` index, and this queue is a handful of rows.
`id` is still the final tie-break, so two notes filed in the same second come out in
a fixed order; a queue that shuffles between refreshes is a queue you cannot work
through. And the charity names still arrive in one bulk lookup before the loop,
which is the point of section 7.2.

Answer or close (`apps/support/services.py:133`):

```python
def resolve_ticket(ticket_id: int, user_id: int, text: str, action: str) -> None:
    """Answer or close a ticket (§7.3.10 `resolve_ticket`).

    `respond` emails `text` to the submitter and marks the ticket responded; it
    stays in the queue until closed. `close` takes it out of the queue, emailing
    `text` first when there is any. The email is queued after the commit, so a
    rolled-back answer is never sent; if it fails for good the ticket stays
    answered and the task logs the ticket id (§6.3 failure paths).
    """
    if action not in (RESPOND, CLOSE):
        raise TicketError("Choose to reply or to close.")
    text = (text or "").strip()
    if action == RESPOND:
        text = _clean_text(text, "Write the reply first.")
    elif len(text) > MAX_BODY_LENGTH:
        raise TicketError(f"Keep the message under {MAX_BODY_LENGTH} characters.")

    with transaction.atomic():
        ticket = Ticket.objects.select_for_update().filter(pk=ticket_id).first()
        if ticket is None:
            raise TicketError("That ticket no longer exists.")
        if ticket.status == Ticket.Status.CLOSED:
            raise TicketError("That ticket is already closed.")
        now = timezone.now()
        fields = []
        if text:
            ticket.response = text
            ticket.responded = now
            ticket.responded_by_id = user_id
            ticket.status = Ticket.Status.RESPONDED
            fields += ["response", "responded", "responded_by", "status"]
        if action == CLOSE:
            ticket.status = Ticket.Status.CLOSED
            ticket.closed = now
            fields += ["status", "closed"]
        ticket.save(update_fields=sorted(set(fields)))
        if text and ticket.email:
            transaction.on_commit(lambda: send_ticket_reply.delay(ticket.id))
```

Four decisions to see here.

*The text rules differ by button.* Send reply with an empty box is refused — an
answer with no words is not an answer. Close with an empty box is fine, because
closing a spam note needs no reply. Text over the limit is refused either way.

*The row is locked while it is changed.* `select_for_update()` means two admins
pressing a button at the same instant cannot interleave: the second waits, then sees
the first one's result. Without it, two replies could each overwrite the other's
answer and only one email would carry the truth.

*Closing after answering keeps the answer.* Pressing Close on an already-answered
note adds only the two closing fields; `sorted(set(fields))` exists because both
branches add the status, and asking to save the same field twice is an error in
Django.

*The email is queued only after the save takes effect.* `transaction.on_commit` puts
the job on the queue after the transaction commits, so a rolled-back answer never
reaches a customer's inbox. That is what makes "the note says answered" and "the
customer was told" impossible to disagree in the dangerous direction.

What it buys: a staff member can work a list top-down, and no note can be closed
with an answer that never got out silently.

### 7.4 `apps/support/tasks.py` — the reply email, and what happens when it cannot be sent

**A second queued job is added: it reads the ticket when it runs, emails the answer with the original message quoted underneath, and gives up after three attempts by writing an error to the log.**

Before this change the file held one job — mailing the six-digit code. There was no
way to send an answer at all.

The new job (`apps/support/tasks.py:31`):

```python
@shared_task(bind=True, max_retries=REPLY_MAX_RETRIES)
def send_ticket_reply(self, ticket_id: int) -> None:
    """Email an admin's answer to whoever filed the ticket (§7.3.10, D-073).

    Reads the ticket when it runs, so the email carries the answer as saved. When
    the retries run out the ticket stays answered and the failure is logged at
    ERROR with the ticket id, as §6.3's failure paths ask.
    """
    ticket = Ticket.objects.filter(pk=ticket_id).first()
    if ticket is None or not ticket.email or not ticket.response:
        return
    subject = (
        "Your MaaserMart report"
        if ticket.kind == Ticket.Kind.REPORT
        else "Your MaaserMart question"
    )
    try:
        send_mail(
            subject=subject,
            message=(f"{ticket.response}\n\n----\nYou wrote:\n{ticket.body}\n"),
            from_email=None,
            recipient_list=[ticket.email],
        )
    except OSError as exc:
        if self.request.retries >= REPLY_MAX_RETRIES:
            logger.error("Reply email for ticket %s failed after retries", ticket_id)
            return
        raise self.retry(exc=exc, countdown=2**self.request.retries * 30) from exc
```

The job takes a ticket *number*, not a message. It reads the ticket when it finally
runs, possibly minutes later on a busy queue, so the email always carries what is
actually saved — no chance of a stale copy of the text travelling.

The subject is chosen by kind, so the person who reported a charity gets "Your
MaaserMart report" rather than "question". The body quotes their own words under a
line, which is how a stranger receiving an email can tell what it is about.

The failure path is the part the design asks for by name. `self.request.retries` is
how many attempts have already failed; once it reaches three, the job stops and
writes the ticket number to the error log instead of raising again. Raising again
would only make the queue retry forever. The waiting grows (`2 ** retries * 30`
seconds: 30, then 60, then 120), so a brief outage is ridden out rather than hammered.

What it buys: a lost email is a line in a log with a ticket number in it, not a
silent hole.

### 7.5 `apps/support/views.py` — who may see the queue, and what the two buttons do

**Two handlers are added: the queue page and the resolve action, both behind the same permission check that sends a stranger to log in and refuses anyone who is not staff.**

Before this change the file had only the help and report pages. There was no
staff-facing view anywhere in the support area.

The permission check (`apps/support/views.py:132`):

```python
def _admin_only(request: HttpRequest) -> HttpResponse | None:
    """Send a visitor to log in, refuse a non-admin, let an admin through."""
    if not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path())
    if not getattr(request.user, "is_admin", False):
        raise PermissionDenied
    return None
```

Three outcomes, and they are deliberately different. A stranger is sent to the login
page and brought back to where they were trying to go afterwards. A signed-in member
who is not staff gets a 403 — they are known and told no. An admin gets `None`,
which the two callers read as "carry on".

`getattr(..., "is_admin", False)` is what makes this safe to call on any user
object, including Django's built-in anonymous one: if the property is missing, the
answer is "no".

The queue page (`apps/support/views.py:141`):

```python
def ticket_queue(request: HttpRequest) -> HttpResponse:
    """Every open ticket, with a reply box and a close button on each."""
    if (refusal := _admin_only(request)) is not None:
        return refusal
    return _render_queue(request)
```

Two lines of real work: check the door, draw the page.

The action (`apps/support/views.py:149`):

```python
@require_POST
def resolve(request: HttpRequest, ticket_id: int) -> HttpResponse:
    """Reply to or close one ticket, then return to the queue."""
    if (refusal := _admin_only(request)) is not None:
        return refusal
    action = request.POST.get("action", "")
    text = request.POST.get("text", "")
    try:
        resolve_ticket(ticket_id, request.user.id, text, action)
    except TicketError as exc:
        return _render_queue(request, failed=(ticket_id, str(exc), text), status=400)
    done = "closed" if action == CLOSE else "answered"
    messages.success(request, f"Ticket {ticket_id} {done}.")
    return redirect("support_admin:tickets")
```

`@require_POST` means the address cannot be triggered by a link or a page load; a GET
gets a 405. On success the page redirects back to the queue with a one-line notice —
the redirect is what stops a browser refresh from re-sending the same reply to a
customer. On a refusal the ticket's own card is re-drawn with the error *and the
text the admin typed*, so their paragraph is not lost:

```python
def _render_queue(request: HttpRequest, failed=None, status=200) -> HttpResponse:
    failed_id, error, draft = failed or (None, None, "")
    return render(
        request,
        "support/ticket_queue.html",
        {
            "tickets": get_tickets(),
            "failed_id": failed_id,
            "error": error,
            "draft": draft,
            "max_body_length": MAX_BODY_LENGTH,
        },
        status=status,
    )
```

The status code is 400 for a refused action and 200 for a page view. That matters to
tools and to tests: a refusal is not a normal page.

There is one more change in this file, at `apps/support/views.py:47`, and it is the
one a member will meet:

```python
def _submitter(request: HttpRequest) -> dict:
    """Who files the ticket: the account, or the guest's verified address."""
    if request.user.is_authenticated:
        # The reply goes to the account's address as it is now (D-073).
        if not request.user.email:
            raise TicketError("Your account has no email address for the reply.")
        return {"user_id": request.user.id, "email": request.user.email}
    email = verification.verified_email(request.session)
    if not email:
        raise TicketError("Verify your email address first.")
    return {"email": email}
```

A signed-in member now files with their account address attached. If the account has
none, they are told plainly instead of having an unanswerable note filed.

What it buys: staff can work the queue in one tab, and no visitor can read it.

### 7.6 `apps/support/admin_urls.py` and `config/urls.py` — the queue's address

**A new address list is added because the queue lives under `/admin/`, not `/support/`, and the root list includes it.**

Before this change support had one address list, which sits under `/support/`. The
queue's address is `/admin/tickets/`, so a second list is needed rather than an
awkward condition in the first.

The whole file:

```python
"""The admin ticket queue at /admin/tickets/ (§7.3.10, D-027).

Separate from `urls.py` because it lives under /admin/, not /support/.
"""

from django.urls import path

from . import views

app_name = "support_admin"

urlpatterns = [
    path("", views.ticket_queue, name="tickets"),
    path("<int:ticket_id>/", views.resolve, name="resolve"),
]
```

And the one line in the root list (`config/urls.py:12`):

```python
    path("support/", include("apps.support.urls")),
    path("admin/tickets/", include("apps.support.admin_urls")),
    path("django-admin/", admin.site.urls),
```

Note the order: `/admin/tickets/` is a real page of ours, and Django's own admin is
at `/django-admin/` (D-008), so there is no collision and no chance of our queue
being shadowed by the built-in one.

What it buys: staff have one address to remember.

### 7.7 `apps/support/templates/support/ticket_queue.html` — the page an admin works from

**One template draws every open ticket as a card, with its details, its existing answer if any, and a reply box with the two buttons.**

Before this change the area had no staff page at all.

The whole card, which is the heart of the page (`apps/support/templates/support/ticket_queue.html:9`):

```html
    {% for ticket in tickets %}
      <article class="ticket-card ticket-card--{{ ticket.status }}" id="ticket-{{ ticket.id }}">
        <header class="ticket-card__head">
          <span class="chip">{{ ticket.kind_label }}</span>
          <span class="ticket-card__status">{{ ticket.status_label }}</span>
          <span class="ticket-card__from">
            {% if ticket.from_member %}{{ ticket.email }}{% else %}guest &middot; {{ ticket.email }}{% endif %}
          </span>
          <time datetime="{{ ticket.created|date:'c' }}">{{ ticket.created|date:"j M Y, H:i" }} UTC</time>
        </header>

        {% if ticket.kind == "report" %}
          <p class="ticket-card__charity">
            About:
            {% if ticket.charity_name %}
              <a href="{% url 'charities:detail' ticket.charity_id %}">{{ ticket.charity_name }}</a>
            {% else %}
              a charity that has since been removed
            {% endif %}
          </p>
        {% endif %}

        <p class="ticket-card__body">{{ ticket.body|linebreaksbr }}</p>

        {% if ticket.response %}
          <div class="ticket-card__response">
            <p><strong>Answered {{ ticket.responded|date:"j M Y, H:i" }} UTC</strong></p>
            <p>{{ ticket.response|linebreaksbr }}</p>
          </div>
        {% endif %}

        <form class="ticket-form" method="post" action="{% url 'support_admin:resolve' ticket.id %}">
          {% csrf_token %}
          {% if failed_id == ticket.id %}<p class="ticket-form__error" role="alert">{{ error }}</p>{% endif %}
          <label for="reply-{{ ticket.id }}">Reply by email</label>
          <textarea id="reply-{{ ticket.id }}" name="text" rows="4"
                    maxlength="{{ max_body_length }}">{% if failed_id == ticket.id %}{{ draft }}{% endif %}</textarea>
          <div class="ticket-form__row">
            <button class="button" type="submit" name="action" value="respond">Send reply</button>
            <button class="button button--secondary" type="submit" name="action" value="close">Close</button>
          </div>
        </form>
      </article>
    {% empty %}
      <p>No open tickets.</p>
    {% endfor %}
```

Four things this page does that a first draft would not.

*The removal case is handled out loud.* A report can point at a charity that has
since been deleted from the directory; the card then says so in words, because a
blank space where a name should be looks like a bug.

*The previous answer is shown.* An admin opening a note that was already answered
sees what was said, so a second reply does not contradict the first.

*Two buttons, one form.* Each button carries its own `action` value, so the same
textarea serves both, and pressing Close with text in the box sends that text first.

*A failed attempt keeps its draft.* `{% if failed_id == ticket.id %}` re-fills that
one card's box with the text that was refused, and shows the reason next to it. The
other cards stay empty.

The `id="ticket-{{ ticket.id }}"` on each card gives every ticket a stable bookmark,
which is what lets a link or a support conversation point at one specific note.

What it buys: an admin can clear a day's tickets without leaving one page, and can
see what was already said before adding to it.

### 7.8 `templates/admin/index.html` — a link from Django's own admin page

**A twelve-line template overrides Django's admin front page, adding a "MaaserMart queues" box with a link to the ticket queue.**

Before this change, staff who logged into Django's built-in admin saw only the model
lists, and the queue at `/admin/tickets/` was reachable only by typing its address.
The design (§7.3) asks the two admin surfaces to know about each other.

The whole file:

```html
{% extends "admin/index.html" %}
{# §7.3 Admin Access: the Django admin's front page links to the custom queues (D-073). #}

{% block content %}
  <div class="module" id="maasermart-queues">
    <table>
      <caption>MaaserMart queues</caption>
      <tr><th scope="row"><a href="{% url 'support_admin:tickets' %}">Ticket queue</a></th></tr>
    </table>
  </div>
  {{ block.super }}
{% endblock %}
```

It extends the built-in page and puts the queue box above the existing content, which
`{{ block.super }}` keeps in place. The box is an ordinary admin table, so it looks
like the rest of the page rather than like something bolted on.

What it buys: staff find the queue from the place they already log into.

### 7.9 `static/css/site.css` — the card look

**Thirty-three lines: the queue's width, the card with its coloured left edge, and the grey box around an existing answer.**

Before this change no styling existed for a list of cards.

The one line that carries meaning rather than taste (`static/css/site.css:867`):

```css
.ticket-card--responded {
  border-left-color: #999;
}
```

An unanswered card has a blue left edge; an answered one has grey. Scanning down the
queue, an admin sees at a glance where the work is without reading any words.

What it buys: the page reads as a worklist rather than a wall of text.

---

## 8. The tests

Two files changed. The new one, `tests/unit/test_ticket_queue.py`, holds 22 tests.
The old one, `tests/unit/test_support_tickets.py`, is updated where D-073 changed a
rule.

**What the queue contains** — `test_unanswered_first_then_oldest_and_closed_left_out`
files four notes at controlled times and asserts the exact order, which pins both
rules at once; `test_card_names_the_charity_and_the_guest`; `test_member_ticket`;
`test_every_open_status_has_a_rank`, the guard from the review branch: it compares the
ranking table against the model's own list of statuses, so a status added without a
rank fails here rather than reordering the queue in silence.

**Answering** — `test_respond_saves_and_emails` checks all four saved fields *and*
that the email carried both the answer and the customer's original words;
`test_respond_needs_text` (and no mail is sent); `test_a_closed_ticket_cannot_be_resolved`;
`test_unknown_ticket_or_action` (a number that does not exist, and an action word that
does not exist); `test_huge_text_is_refused`.

**Closing** — `test_close_without_text_sends_nothing`; `test_close_with_text_replies_first`.

**The failure path** — `test_email_failure_keeps_the_answer_and_logs` makes the mail
server fail and asserts the note still says answered *and* the log names the ticket.
This is the test for §6.3's failure path, and it is the reason the design's
"answered but not delivered" case is a known state rather than a surprise.

**The door** — `test_visitor_is_sent_to_log_in` (a 302 to the login page, carrying
`next=/admin/tickets/` so the visitor arrives back where they were headed);
`test_non_admin_is_refused` (a 403 on *both* the page and the action — refusing only
the page would leave the action open to a typed address);
`test_resolve_is_post_only` (a 405 on a plain visit).

**The page itself** — `test_admin_sees_open_tickets` (an open note and its sender are
drawn, a closed one is not, and a guest is labelled "guest"),
`test_empty_queue`, `test_reply_redirects_with_a_notice`,
`test_close_removes_it`, `test_failed_reply_keeps_the_draft` (the refusal sentence and
the typed draft are both on the page),
`test_django_admin_links_to_the_queue`.

**In the older file**, three tests changed because the rule changed.
`test_help_from_a_user` now asserts the ticket carries the member's address (it used
to assert the field was empty). `test_needs_exactly_one_submitter` is replaced by
`test_needs_a_reply_address`, with three cases: empty, spaces and missing. And one
test is new: `test_signed_in_user_without_an_email_is_told`, which proves the polite
refusal instead of an unanswerable note. No test was deleted.

## 9. What the review changed

Writing this walkthrough is what found the ordering problem: the sentence "unanswered
first" was true, and the reason it was true was the alphabet. Two things changed in
branch `docs/dilbert-and-review-fixes`:

- `apps/support/services.py` sorts by an explicit `STATUS_RANK` number instead of by
  the status word, with an unranked status sorting last (section 7.3 quotes it).
- `tests/unit/test_ticket_queue.py` gained `test_every_open_status_has_a_rank`, which
  fails if a status is ever added without being ranked.

What did *not* change: the pages, the views, the guard, the email path, D-073's rules.
The queue looks and behaves exactly as documented above; it just cannot be reordered
by an edit that looks unrelated.
