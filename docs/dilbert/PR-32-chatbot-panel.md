# PR #32 — The chatbot panel: ask a question, wait for the answer, look things up

- Branch: `chatbot/panel` → `main`
- Merge commit: `cf7694e` (2026-11-24)
- Author: Platform Lead (Shaul)
- Decision recorded: D-076
- Size: 25 files, +1252 / −4
- Amended after review: branch `docs/dilbert-and-review-fixes` stops a late failure from erasing an answer (section 7.2). The code quoted below is the amended code, not the merge exactly.

---

## 1. Read this part even if you read nothing else

The previous change (PR #31) built the chat box's engine: a swappable model, and a
conversation loop that may ask the site for facts. This change puts a **door** on
that engine, and the door is in the corner of every page.

Picture a shop with a knowledgeable assistant behind a hatch. The visitor presses a
button in the corner, the hatch opens, and they type a question: "which charity in
Jerusalem helps with clothing?" The assistant goes to look at the shop's own
records, comes back, and answers. The visitor can ask a follow-up, and the assistant
remembers the last few exchanges.

Two things about that hatch are worth knowing before anything else, because they
explain almost every file here.

**First: nobody waits inside the hatch.** Asking a real AI model takes seconds —
sometimes several. A page that freezes for eight seconds feels broken, so the box
does not wait. It takes your question, says "Thinking…", hands the question to a
background worker, and then asks "done yet?" once a second until the answer
appears. That is why there are two addresses here instead of one: one to *ask*, and
one to *check*.

**Second: the answer has to be somewhere while it is being made.** The site's
background queue, by design, has no memory of results — it carries work in, and
carries nothing back. So the box keeps the half-finished question in the site's
shared scratchpad (the same one the maaser limits use), under a random name, and
the checking address looks it up. That way the chatbot needs no database table of
its own, which the design requires.

The rest of the change is everything that makes those two things safe and pleasant:
what the model is allowed to look up (four read-only questions about charities and
the member's own maaser), how long an answer may take before the box gives up (two
minutes), how many questions a member gets per day (thirty), what a link in an
answer is allowed to look like (a charity page on this site, or a Sefaria source —
nothing else), and a small notice for the whole site that appears when the visitor's
internet connection drops mid-request.

Two of those numbers and one architectural choice are flagged in the pull request
for the Platform Lead to confirm, and that is honest of it: the design document does
not give them.

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

Ten words, one table.

- **Panel** — the small chat box in the corner of every page. It opens and closes;
  it is not a page of its own.
- **Polling** — asking "is it ready yet?" over and over at a fixed rhythm. Here:
  once a second, until the answer arrives.
- **Background worker** — a separate program that does slow jobs (sending email,
  asking a model) so the visitor's page does not wait. It takes jobs from a queue.
- **Job** — one question in flight: its state (waiting, answered, failed), the
  question, and the answer when there is one.
- **Cache** — the site's shared scratchpad, readable by every process. It is where
  jobs and the daily count live, so that no new database table is needed.
- **Task id** — the random name a job is filed under. Random, so it cannot be
  guessed; that is what stops one member reading another's answer.
- **Lookup (tool)** — one read-only question the model is allowed to ask the site,
  such as "find charities matching this word". Never a database command.
- **Escape** — turning text that happens to look like code into harmless text, so a
  model cannot inject anything into a page. Here it happens before any link is made
  clickable.
- **CSP** — the rule the site gives the browser about what may run on a page. This
  site's rule forbids inline scripts, which is why the panel's few lines of
  behaviour live in a separate file.
- **Retry** — trying the same request again, here when the network drops. The
  answer to "should we retry?" is decided by whether the model's failure was
  temporary.

Names that exist only in this code, and the plain word used here:

| in the code | in this file |
|---|---|
| `jobs.Job` | the job (question in flight) |
| `pending` / `answered` / `failed` | waiting / answered / failed |
| `services.Status` | the answer to a "done yet?" check |
| `enqueue_question` | "put the question on the queue" |
| `poll_status` | "the done-yet check" |
| `ToolFunction` / `functions_for` | the lookup menu offered to the model |
| `chat_text` | the filter that escapes text and makes only approved links clickable |
| `HISTORY_KEY` / `HISTORY_TURNS` | the remembered conversation / how many exchanges |
| `htmx` | the small library that lets a page swap part of itself without reloading |
| `<details>` | the browser's own open/close widget, used as the panel |

---

## 4. The story

### What the site does all day

1. A visitor browses charities, reads a charity page, keeps their maaser ledger.
2. A signed-in member presses a button in the corner and asks a question.
3. The model looks up charities (or the member's own maaser figures) through
   read-only calls, and answers in a sentence or two.
4. The member asks a follow-up, which works because the box remembers the last six
   exchanges.

Before this change steps 2–4 could not happen: the engine existed, but nothing on
any page could reach it. There was no panel, no endpoint, no task, no tools, no
prompt.

### What was wrong — the four problems this change had to solve

**First: a page cannot wait on a model.** A browser request that sits for eight
seconds looks broken, and a slow model would tie up the site's web workers. The
design already answers this — queue the question, then poll — but the design does
not say where the answer is kept while it is being made.

**Second: the queue does not keep answers.** The site sends background work through
Amazon's queue, which has no memory of results. There is nowhere to put an answer
without inventing one.

**Third: a chatbot that cannot look things up will invent charities.** Every fact
it states about a charity would come from training data, and training data does not
know about the charities listed here. The design's rule — the model asks the
database through read-only service calls — needs lookups to exist.

**Fourth: an answer is text written by a machine.** Rendered as-is, a model's reply
could contain a script tag, or a link to a phishing site dressed up as a charity
page. Neither is acceptable on a site about giving money away.

### The cost of leaving it

The concrete case, carried through. A member asks "which charity does kosher food
distribution in Boro Park?" Without lookups, the model answers with a plausible name
and a plausible phone number, both invented. The member calls the number. On a site
whose whole purpose is routing money to the right charity, a confident fabrication
is the worst possible answer — worse than "I don't know", worse than silence.

With this change, the same question makes the model ask the lookup, the lookup runs
the same code the listing page runs, and the answer names a charity that is really
listed, with a link that really works.

### The fix, in one sentence

A corner panel on every page for signed-in members, which queues the question to a
background worker, polls a random job name in the shared cache once a second until
there is an answer, offers the model four read-only lookups into the charities and
tools services, escapes and link-restricts the answer, caps each member at thirty
questions a day and each question at two minutes, and shows a "Connecting…" notice
when the network drops.

The consequences, listed plainly:

- One question is answered without ever blocking a page, and a stopped worker ends
  in "couldn't get an answer" instead of a bubble that polls forever.
- A member's own maaser figures can be asked about, and only their own: the lookup
  is wired to the asking member on the server, so no wording can make the model ask
  for somebody else's.
- A question about a charity gets a real listing, because it comes from the same
  code the listing page uses.
- An answer can link to a charity page or a Torah source, and nothing else.
- A member gets thirty questions a day, and "thirty" is a setting.
- The conversation remembers the last six exchanges, so "and how much is that in
  shekels?" makes sense.
- Every answer is logged by *quantity* — provider, rounds, tool names, token counts
  — and never by content.

---

## 5. Contradictions

The pull request and the D-076 entry agree with the code almost everywhere. Three
points are worth naming, in order of how much they cost a reader.

**1. The retry count is described two ways, and both are true.** The summary says
"two retries". The code sets `MAX_RETRIES = 2` and the waits are `2 ** (retries+1)`
seconds: 2 s, then 4 s. So: one first attempt plus two retries, three attempts in
all, waiting two then four seconds. The D-076 entry says the same. The test
`test_gives_up_after_the_retries` pins the giving-up case by injecting the maximum
retry count directly. Trust the code; "two retries" is right.

**2. "The pending bubble re-polls every second" is true but not a loop in the
code.** The re-poll is done by the page itself: each pending bubble carries
instructions to fetch the status address one second after it appears, and the answer
to that fetch is either the answer or *another* bubble with the same instructions.
That is why the polling looks like a loop but no line of code loops. Trust the
templates (`_pending.html`).

**3. The PR flags three things for review and the code does all three.** The two new
dependencies (chatbot → charities, chatbot → tools) and the default limits (30 a
day, 120 seconds, 6 remembered exchanges) are declared in D-076 as decisions, not
assumptions. They are the parts the design document left blank. This is not a
contradiction — it is the thing to approve or change, and the settings make the
limits cheap to change.

One cosmetic detail: `templates/base.html` ends without a final newline in this
commit ("\ No newline at end of file"). Harmless, but a `diff` on that file will
always show it.

---

## 6. Reading order

| # | File | What it is | Why here |
|---|---|---|---|
| 1 | `apps/charities/services.py` | the reading doors the chatbot will knock on | the data first |
| 2 | `apps/chatbot/jobs.py` | jobs and the daily count, in the cache | where a question waits |
| 3 | `apps/chatbot/services.py` | the two functions §6.1 names | the rules around the job |
| 4 | `apps/chatbot/lookups.py` | the four lookups the model may ask for | what it may know |
| 5 | `apps/chatbot/prompt.py` | the model's standing instructions | what it should say |
| 6 | `apps/chatbot/tasks.py` | the worker that asks the model | where the answer is made |
| 7 | `apps/chatbot/templatetags/chat_text.py` | escaping and the two allowed links | how an answer is made safe |
| 8 | `apps/chatbot/views.py`, `urls.py` | the four addresses | the door |
| 9 | `apps/chatbot/templates/chatbot/*` (5 files) | the panel and its pieces | what the member sees |
| 10 | `templates/base.html`, `apps/support/context_processors.py` | the corner on every page | how it gets there |
| 11 | `static/js/chat.js`, `static/js/retry.js` | the two small scripts | the page's behaviour |
| 12 | `config/settings/base.py`, `config/urls.py`, `.env.example`, `static/css/site.css` | settings, wiring, styling | glue |
| 13 | `docs/DECISIONS.md` | the D-076 record: the decision in prose | the argument, not the code |
| 14 | `tests/unit/test_chatbot_panel.py` | the proof | last |

The shape in one sentence: **a question goes into the cache as a job, a worker
answers it with read-only lookups, and the panel polls until the answer can be shown
safely.**

---

## 7. The files

### 7.1 `apps/charities/services.py` — the three reading doors the chatbot knocks on

**Three new read-only functions are added to the charities area: search charities, fetch one charity in full, and list the cause names — all returning the same shapes the listing page uses, never database rows.**

Before this change the charities area could already search for the *listing page*
(`list_charities`, with a page state, filters and sort) and look charities up by
name for the support report form. It had no single call answering "give me up to
five charities matching this word, domain and place, best first" — which is what a
chat question needs.

The limit and the matching helper (`apps/charities/services.py:377`):

```python
CHAT_RESULT_LIMIT = 5


def _matching_ids(options, wanted: str) -> tuple[int, ...] | None:
    """Ids of the options whose label contains `wanted`; None when nothing is asked."""
    wanted = (wanted or "").strip().lower()
    if not wanted:
        return None
    return tuple(o.id for o in options if wanted in getattr(o, "label", o.name).lower())
```

Five, not the listing's twenty, because a chat answer quoting twenty charities is
not an answer. And the helper's return value is deliberately three-valued: `None`
means "no restriction asked for", `()` means "a restriction was asked for and
nothing matched", and a tuple means "these are the matching causes". That
distinction is what lets the search tell "the model did not ask about a cause" apart
from "the model asked about a cause that does not exist" — and the second must
return nothing rather than quietly dropping the filter.

The search itself (`apps/charities/services.py:388`):

```python
def search_charities(
    term: str = "",
    *,
    domain: str = "",
    location: str = "",
    sort: str = RATING.value,
    limit: int = CHAT_RESULT_LIMIT,
) -> tuple[CharityCard, ...]:
    """Up to `limit` charities matching a name, a domain and a location, best first.

    `domain` and `location` are matched by name, case-insensitively, against the
    filter options; one that matches no option yields no charities rather than
    being ignored. `sort` is a §6.2.5 mechanism value; an unknown one means
    highest rated.
    """
    options = DjangoFilterOptionsRepository()
    domains = _matching_ids(options.domains(), domain)
    locations = _matching_ids(options.locations(), location)
    if domains == () or locations == ():
        return ()
    mechanism = next((m for m in MECHANISMS if m.value == sort), RATING)
    # published_only follows the listing's view until D-042 flips it.
    return DjangoCharityRepository(published_only=False).page(
        offset=0,
        limit=max(1, min(limit, CHAT_RESULT_LIMIT)),
        filters=CharityFilters(domains=domains or (), locations=locations or ()),
        sort=CharitySort(mechanism, mechanism.descending_by_default),
        search=Search(term=(term or "").strip()),
    )
```

Every piece of this is reuse, and that is the point: the same repository, the same
filters, the same sort mechanisms, the same search as the listing page. The chatbot
therefore cannot show a charity that a visitor cannot see, or exclude one that is
listed. Three details earn their lines. `if domains == () or locations == ()`
implements the "unknown cause matches nothing" rule. `next((m for m in MECHANISMS if
m.value == sort), RATING)` means an invented sort word from a model falls back to
"highest rated" instead of raising. And `limit` is clamped to be at least 1 and at
most five, so a model asking for a thousand gets five, and a model asking for zero
gets one rather than an error.

The other two doors (`apps/charities/services.py:419`):

```python
def get_charity(charity_id) -> CharityPage | None:
    """One charity in full, as its page shows it, or None."""
    try:
        charity_id = int(charity_id)
    except (TypeError, ValueError):
        return None
    return DjangoCharityRepository(published_only=False).detail(charity_id)


def domain_names() -> tuple[str, ...]:
    """Every domain's name, as the Domain filter offers them."""
    return tuple(o.name for o in DjangoFilterOptionsRepository().domains())
```

`get_charity` reuses the charity page's own detail call, so the model sees exactly
the page a visitor sees — the same description, links, reviews and haskamos — and
answers `None` for anything that is not a number or not a charity. `domain_names`
gives the model the vocabulary for its "which cause?" question, taken from the real
filter options, which is why the prompt can tell it to look the list up rather than
invent cause names.

What it buys: the chatbot's view of charities is the visitor's view, produced by the
visitor's code.

### 7.2 `apps/chatbot/jobs.py` — where a question waits, and the daily count

**This new file keeps each question as a small record in the shared cache — waiting, answered or failed — plus a per-member daily counter, so the chatbot needs no database table of its own.**

Before this change nothing anywhere held a question in flight.

The file's docstring is the argument for the design (`apps/chatbot/jobs.py:1`):

```python
"""Where a question waits for its answer, and the daily usage count (D-076).

Celery's SQS transport has no result backend (design doc concurrency decision),
so a job's state lives in Django's default cache, which is database-backed and
shared by the web processes and the worker. No model and no migration: the
chatbot owns no models (§6.1). A job outlives any answer a visitor waits for, and
then expires.
"""
```

The record and its states (`apps/chatbot/jobs.py:19`, `:32`):

```python
PENDING = "pending"
ANSWERED = "answered"
FAILED = "failed"

JOB_SECONDS = 60 * 60
DAY_SECONDS = 24 * 60 * 60


@dataclass
class Job:
    user_id: int
    question: str
    state: str = PENDING
    answer: str = ""
    created: float = 0.0
```

An hour is generous for a job that will be answered in seconds — deliberately so,
because the cost of keeping it is trivial and the cost of losing an answer the panel
is still asking about is a confusing "couldn't get an answer" for no reason.

Creating and reading (`apps/chatbot/jobs.py:44`):

```python
def create(user_id: int, question: str) -> str:
    job_id = uuid.uuid4().hex
    _cache().set(_key(job_id), asdict(Job(user_id, question, created=time.time())), JOB_SECONDS)
    return job_id


def get(job_id: str) -> Job | None:
    raw = _cache().get(_key(job_id)) if job_id else None
    return Job(**raw) if raw else None
```

The job's name is a random 32-character string from `uuid4`, not a counter, because
the name is the secret: whoever has the name can ask for the status. A guessable
name would let one member poll another's questions. `if job_id else None` handles an
empty name without a pointless cache lookup.

Settling a job (`apps/chatbot/jobs.py:55`):

```python
def _settle(job_id: str, state: str, answer: str = "") -> None:
    job = get(job_id)
    if job is None:
        return
    if job.state == ANSWERED and state != ANSWERED:
        # An answer that arrived beats a poll that gave up: a stale poll which
        # failed the job microseconds earlier must not erase the answer.
        return
    job.state, job.answer = state, answer
    _cache().set(_key(job_id), asdict(job), JOB_SECONDS)


def answer(job_id: str, text: str) -> None:
    _settle(job_id, ANSWERED, text)


def fail(job_id: str) -> None:
    _settle(job_id, FAILED)


def delete(job_id: str) -> None:
    _cache().delete(_key(job_id))
```

Note the quiet `if job is None: return`: a worker may finish after the job has
already expired or been deleted, and "the job vanished" is not an error worth
raising in a background worker at 3 a.m.

The second guard — never turning an answered job into a failed one — came from the
review branch, and it closes a real race. Two writers touch this one key: the worker,
which stores the answer, and the page's poll, which may decide the job has waited too
long and fail it. Read-then-write is not atomic, so imagine the answer landing in the
instant the poll has already read a "waiting" job: the poll writes "failed" over the
answer, and the member is told to try again although a perfectly good answer had just
arrived. The guard makes the downgrade impossible — an answer is final. What it does
not do is make the pair atomic (that would need a lock the shared cache does not
offer); it makes the *bad* outcome unreachable, which is the one that costs a user.

The daily count (`apps/chatbot/jobs.py:75`):

```python
def _usage_key(user_id: int) -> str:
    return f"chatbot:uses:{user_id}:{timezone.now().date().isoformat()}"


def uses_today(user_id: int) -> int:
    return _cache().get(_usage_key(user_id), 0)


def count_use(user_id: int) -> int:
    """Add one question to today's (UTC) count and return the new total."""
    key = _usage_key(user_id)
    _cache().add(key, 0, DAY_SECONDS)
    try:
        return _cache().incr(key)
    except ValueError:  # expired between add and incr
        _cache().set(key, 1, DAY_SECONDS)
        return 1
```

The date is *in the key*, so yesterday's count does not need clearing: a new day is
a new key, and the old one expires. The `add`-then-`incr` pattern (the same one the
guest verification code uses in PR #28) avoids two simultaneous questions each
starting a fresh counter. And the counter is incremented *after* a question is
successfully queued, so a failed submission never counts against the member.

What it buys: the chatbot owns no tables, survives being answered by a different
process than the one that asked, and cannot be tricked into reading another
member's job.

### 7.3 `apps/chatbot/services.py` — the two functions the design names

**The file goes from an empty docstring to the two functions §6.1 requires — queue a question, check its status — with the daily cap, the queue-failure message and the stale-job cutoff.**

Before this change the file was a docstring and nothing else. §6.1 said the chatbot
"exposes `enqueue_question` and `poll_status`" — names, no code.

The two errors a visitor can see (`apps/chatbot/services.py:23`):

```python
class ChatbotError(Exception):
    """A question that could not be put on the queue. The message is for the visitor."""


class LimitReached(ChatbotError):
    def __init__(self):
        super().__init__("You've reached the chatbot limit")


class SubmitFailed(ChatbotError):
    def __init__(self):
        super().__init__("Could not submit, try again")
```

Two different failures, two different sentences, both from §6.3's list of chatbot
failure paths — and both written *for the visitor*, which is why the sentences live
in the class rather than being assembled in a view.

The status shape (`apps/chatbot/services.py:38`):

```python
@dataclass(frozen=True)
class Status:
    """Where a question stands: pending, answered (with `answer`) or failed."""

    state: str
    question: str
    answer: str = ""

    @property
    def done(self) -> bool:
        return self.state != jobs.PENDING
```

`done` is one word that saves every caller from comparing three string constants.

Queueing (`apps/chatbot/services.py:50`):

```python
def clean_question(text: str) -> str:
    return " ".join((text or "").split())[:MAX_QUESTION_CHARS]


def enqueue_question(user_id: int, question: str, history: Sequence[tuple[str, str]] = ()) -> str:
    """Put a question on the queue and return the task id to poll.

    `history` is the earlier (question, answer) pairs of this conversation, so
    the model can follow up. Raises LimitReached past the daily cap and
    SubmitFailed when the queue cannot take the job (§6.3).
    """
    from .tasks import answer_question  # the task module imports the providers

    if jobs.uses_today(user_id) >= settings.CHATBOT_DAILY_LIMIT:
        logger.info("Chatbot limit reached for user %s", user_id)
        raise LimitReached()
    turns: list[list[str]] = []
    for asked, answered in history:
        turns += [["user", asked], ["assistant", answered]]
    turns.append(["user", question])
    job_id = jobs.create(user_id, question)
    try:
        answer_question.delay(job_id, user_id, turns)
    except Exception:
        logger.exception("Chatbot question could not be queued")
        jobs.delete(job_id)
        raise SubmitFailed() from None
    jobs.count_use(user_id)
    return job_id
```

Reading it in order. `clean_question` collapses every run of whitespace to one
space and cuts at 1,000 characters — a member pasting a page of text gets a
question-shaped question. The limit is checked *before* anything is created, so a
member past the cap leaves no debris. The conversation is flattened into alternating
"user" and "assistant" turns with the new question at the end. The job is created,
then handed to the worker; the import is inside the function and carries a comment
explaining why — the task module pulls in the providers, and this file is imported
by views, so the import stays lazy to keep that chain short. If the queue refuses
the job, the job is deleted (no ghost pending job) and the visitor gets "Could not
submit, try again"; and the count only increments once the question really is on
the queue.

Checking on it (`apps/chatbot/services.py:81`):

```python
def poll_status(user_id: int, task_id: str) -> Status | None:
    """The question's state, or None for an unknown task or another user's (§6.3: 404).

    A job still pending after CHATBOT_ANSWER_SECONDS is reported failed, so a
    stopped worker ends in "try again" instead of polling forever.
    """
    job = jobs.get(task_id)
    if job is None or job.user_id != user_id:
        logger.warning("Chatbot status asked for an unknown or foreign task by user %s", user_id)
        return None
    if job.state == jobs.PENDING and time.time() - job.created > settings.CHATBOT_ANSWER_SECONDS:
        logger.error("Chatbot job %s got no answer in time; is the worker running?", task_id)
        jobs.fail(task_id)
        job.state = jobs.FAILED
    return Status(state=job.state, question=job.question, answer=job.answer)
```

The ownership check is the interesting line: the task id must belong to the member
asking. A wrong id and somebody else's id are answered identically (`None`, which
the view turns into a 404), so the check leaks nothing about whether a job exists.
And the timeout is *lazy*: nothing runs on a timer; the moment somebody asks about a
job that has been waiting too long, it is failed on the spot and logged as an error
wondering aloud whether the worker is running. That single line is what guarantees a
member is never left with a bubble that says "Thinking…" forever.

What it buys: the two named entry points exist, with the design's failure messages on
the visitor's side and the operator's question ("is the worker running?") in the log.

### 7.4 `apps/chatbot/lookups.py` — the four questions the model may ask

**This new file defines the lookup menu — search charities, fetch one charity, list causes, and the asking member's own maaser figures — each a thin read-only wrapper over another area's services, with the maaser one wired to the member on the server.**

Before this change the loop (PR #31) could offer tools, but there were none to offer.

The file's docstring states the boundary rule (`apps/chatbot/lookups.py:1`):

```python
"""What the model may look up, and how (D-076).

Each tool is read-only and calls another app's `services.py`. The model never
sends SQL and never sees a model row. The member's own figures come from a tool
bound to their user id here, so the model cannot ask for anyone else's.
"""
```

The cut, which keeps an answer's ingredients small (`apps/chatbot/lookups.py:19`):

```python
DESCRIPTION_CHARS = 1200
REVIEW_CHARS = 300
REVIEWS_SHOWN = 3


def _cut(text: str | None, limit: int) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[:limit].rstrip() + "…"
```

Three reviews, three hundred characters each, a description cut at 1,200: enough
for the model to answer well, small enough that one lookup does not swallow the
conversation.

Searching (`apps/chatbot/lookups.py:33`):

```python
def search_charities(query: str = "", domain: str = "", location: str = "", sort: str = "rating"):
    cards = charities.search_charities(query, domain=domain, location=location, sort=sort)
    return [
        {
            "id": card.id,
            "name": card.name,
            "tagline": card.tagline or "",
            "page": _page_url(card.id),
            "domains": [d.name for d in card.domains],
            "locations": [loc.label for loc in card.locations],
            "average_rating": card.reviews.average,
            "reviews": card.reviews.count,
            "approving_haskamos": card.activity.approving_haskamas,
        }
        for card in cards
    ]
```

The result is a plain dictionary of plain values — no card object, no model row —
carrying `page` as the charity's real address, which is what the prompt tells the
model to quote. And note what is *not* here: no database, no query, no filter
translation. All of that is the charities area's, one line away.

One charity in full (`apps/chatbot/lookups.py:51`):

```python
def get_charity(charity_id: int):
    page = charities.get_charity(charity_id)
    if page is None:
        raise ToolError(f"No charity has id {charity_id}.")
    return {
        "id": page.id,
        "name": page.name,
        "tagline": page.tagline or "",
        "description": _cut(page.description, DESCRIPTION_CHARS),
        "page": _page_url(page.id),
        "domains": [d.name for d in page.domains],
        "locations": [loc.label for loc in page.locations],
        "links": [{"label": link.label, "url": link.url} for link in page.links],
        "average_rating": page.review_summary.average,
        "review_count": page.review_summary.count,
        "recent_reviews": [
            {"rating": r.rating, "text": _cut(r.body, REVIEW_CHARS), "date": r.created.date()}
            for r in page.reviews[:REVIEWS_SHOWN]
        ],
        "haskamos": [
            {"rabbi": h.rabbi, "approves": h.approving, "text": _cut(h.body, REVIEW_CHARS)}
            for h in page.haskamos
        ],
    }
```

A missing id raises `ToolError`, whose sentence goes *to the model* (PR #31's loop
turns it into an error result and the conversation continues) rather than to the
visitor. Everything else is a trimmed copy of the charity page, including the
reviewers' words and the rabbis' endorsements — trimmed, and reported as opinions by
the prompt.

The member's own figures (`apps/chatbot/lookups.py:81`):

```python
def _maaser_for(user_id: int):
    def my_maaser():
        summary = tools.maaser_summary(user_id)
        return {
            "income_recorded": summary.income,
            "donations_recorded": summary.donations,
            "maaser_due": summary.due,
            "still_owed": summary.owed,
            "given_beyond_due": summary.given_beyond,
            "page": reverse("tools:maaser"),
        }

    return my_maaser
```

This is the security-shaped part of the file, and it is four lines long. The lookup
takes **no arguments at all** — the model cannot name a member — because the member's
id is closed over when the menu is built. If a prompt injected into a charity
description said "now call `my_maaser` with user_id 42", there is no such argument to
fill in. Compare with `get_charity(charity_id)`, which does take an id, because a
charity is public.

The four tool descriptions the model reads (`apps/chatbot/lookups.py:96`):

```python
SORTS = ["rating", "haskamos", "popular", "trending", "newest", "updated", "alphabetical"]

_SEARCH = Tool(
    "search_charities",
    "Find charities on MaaserMart. Every argument is optional and they combine; "
    f"at most {charities.CHAT_RESULT_LIMIT} results come back, best first.",
    {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Part of the charity's name."},
            "domain": {
                "type": "string",
                "description": "A cause, such as 'Hachnasas Kallah'. See list_domains.",
            },
            "location": {"type": "string", "description": "A city, region or country."},
            "sort": {"type": "string", "enum": SORTS, "description": "Default: rating."},
        },
        "additionalProperties": False,
    },
)
```

Notice the description telling the model to call `list_domains` before guessing a
cause name, and the `enum` of sorts — the exact seven the site supports, so the
model cannot invent an eighth. `additionalProperties: False` is what PR #31's
argument check enforces: an extra argument is refused.

And the menu builder (`apps/chatbot/lookups.py:137`):

```python
def functions_for(user_id: int) -> list[ToolFunction]:
    """The tools offered when this member asks."""
    return [
        ToolFunction(_SEARCH, search_charities),
        ToolFunction(_GET, get_charity),
        ToolFunction(_DOMAINS, list_domains),
        ToolFunction(_MAASER, _maaser_for(user_id)),
    ]
```

The whole menu is built per question, with the member's id baked into one tool. That
is the difference between "the model is told not to look at other members" and "the
model has no way to look at other members".

What it buys: the model can answer questions about real charities and the member's
own figures, and about nothing else in the database.

### 7.5 `apps/chatbot/prompt.py` — what the assistant is told to be

**One system prompt, in plain text: the site's purpose, the scope, four rules about charity data and Torah sources, the tone, and today's date.**

Before this change the model would have been asked a bare question with no
instructions, and would have answered as a general-purpose assistant — inventing
charities, or writing an essay about tzedakah in unrelated depth.

The prompt, quoted in full because it is the whole file's substance
(`apps/chatbot/prompt.py:7`):

```python
SYSTEM_PROMPT = """\
You are the assistant on MaaserMart, a site where Jewish donors find charities \
(tzedakah organisations), read reviews and rabbis' haskamos, and keep track of \
their maaser (the tenth of income given to tzedakah).

Scope:
- Help the member find and compare charities on MaaserMart, understand their own \
maaser figures, and answer questions about the laws and customs of tzedakah and maaser.
- Politely decline anything unrelated.

Charity data:
- Never invent a charity, a rating, a review or a haskama. Use the tools to look \
them up, and say so plainly when nothing matches.
- When you mention a charity, give its MaaserMart page exactly as the tool returned \
it, for example /charity/12/.
- Reviews and haskamos are people's opinions; report them as such.

Torah sources:
- When you cite a source, link it on Sefaria as https://www.sefaria.org/<Ref>, for \
example https://www.sefaria.org/Shulchan_Arukh,_Yoreh_De'ah.249.1. Cite only \
sources you are confident of.
- For a practical halachic question, give the general view and suggest the member \
ask their own rav.

Tone: warm, respectful and brief. Plain English; Hebrew terms in common use are \
fine. A few short paragraphs at most. Plain text only: no Markdown, no tables.

Today is {today} (UTC)."""
```

Four instructions correspond directly to code in this change. "Never invent a
charity" is why the lookups exist. "Give its MaaserMart page exactly as the tool
returned it" is why the answer renderer only links `/charity/<id>/` paths — the
prompt and the renderer agree on one link shape. "Link it on Sefaria" is why Sefaria
addresses are the second, and only other, link shape allowed. And "suggest the member
ask their own rav" is the same advice shown under the panel.

The date at the end is filled in per question (`apps/chatbot/prompt.py:36`):

```python
def system_prompt() -> str:
    return SYSTEM_PROMPT.format(today=timezone.now().date().isoformat())
```

A model has no clock. Giving it today's date stops the confident "as of 2024" in
an answer about a charity listed this week.

What it buys: the assistant behaves like the site's assistant — narrow, sourced,
brief, and honest when it finds nothing.

### 7.6 `apps/chatbot/tasks.py` — the worker that asks the model, and knows when to give up

**This new file is the background job: it builds the conversation, asks the model, keeps the retry policy (two retries for temporary failures, none for permanent ones), and logs how much was used without logging what was said.**

Before this change a question had nowhere to be answered.

The retry policy (`apps/chatbot/tasks.py:19`):

```python
# Timeouts, rate limits and the vendor's 5xx get two more tries before the
# visitor is told "couldn't get an answer" (§6.3).
MAX_RETRIES = 2


@shared_task(bind=True, max_retries=MAX_RETRIES, ignore_result=True)
def answer_question(self, job_id: str, user_id: int, history: list[list[str]]) -> None:
    """Answer the last user turn of `history` ([role, text] pairs) into the job."""
    messages = [Message("system", system_prompt())]
    messages += [Message(role, text) for role, text in history]
    try:
        provider = get_provider()
        outcome = converse(provider, messages, functions_for(user_id))
    except ProviderConfigError as exc:
        logger.error("Chatbot is not configured: %s", exc)
        jobs.fail(job_id)
        return
    except ProviderError as exc:
        if exc.retryable and self.request.retries < MAX_RETRIES:
            raise self.retry(countdown=2 ** (self.request.retries + 1)) from None
        logger.error("Chatbot could not get an answer for job %s: %s", job_id, exc)
        jobs.fail(job_id)
        return
    if not outcome.text:
        logger.error("Chatbot model gave an empty answer for job %s", job_id)
        jobs.fail(job_id)
        return
    jobs.answer(job_id, outcome.text)
    # §3.4.2 logs chatbot use: who, how much, which lookups. Never the text.
    logger.info(
        "Chatbot use: user=%s provider=%s rounds=%s tools=%s tokens=%s+%s",
        user_id,
        provider.name,
        outcome.rounds,
        ",".join(outcome.tools_called) or "-",
        outcome.prompt_tokens,
        outcome.completion_tokens,
    )
```

`ignore_result=True` is what the "no result backend" problem forces: the answer goes
into the cache, not into the queue's own record. The three failure shapes are
handled differently and deliberately:

*Not configured* — no key, unknown provider — fails at once with an error log,
because retrying a configuration mistake three times just wastes time.

*Temporary* — timeout, rate limit, vendor 5xx, exactly the ones PR #31 marked
`retryable` — is retried, waiting 2 seconds then 4 (`2 ** (retries + 1)` with retries
at 0 then 1). Anything not retryable, or a retry run out, logs and fails the job.

*Empty answer* — the model returned nothing at all — is also a failure, because a
silent nothing in a chat box reads as a bug.

The success log is the design's §3.4.2 requirement in one statement: who, which
provider, how many rounds, which lookups, how many tokens. The comment says the rest:
never the text. A test asserts exactly this by using a question and an answer both
containing the word "secret" and asserting the word is absent from the log.

What it buys: one answer per question, with a failure policy that knows the
difference between "try again" and "stop", and a usage record that can be counted
without reading anyone's conversation.

### 7.7 `apps/chatbot/templatetags/chat_text.py` — how a machine-written answer is made safe

**This new filter escapes everything the model wrote and then makes exactly two kinds of link clickable: a charity page on this site, and a Sefaria source.**

Before this change there was no way to render an answer. Rendered raw, a model's
text could carry a script tag or a phishing link.

The docstring states the two-link rule and the reason (`apps/chatbot/templatetags/chat_text.py:1`):

```python
"""Render a chatbot answer safely (D-076).

The model's text is escaped like any user input. Only two kinds of link are
then made clickable: a MaaserMart charity page (`/charity/<id>/`, as the lookup
tools return it) and a Sefaria source. Any other URL the model writes stays
plain text, so an answer cannot send a member somewhere unexpected.
"""
```

The pattern, and why it is written the way it is (`apps/chatbot/templatetags/chat_text.py:21`):

```python
# Matched against the *escaped* text, so `&` arrives as `&amp;` and a quote as
# `&#x27;`; neither can end the attribute the match is written into.
_LINK = re.compile(
    r"(?P<sefaria>https://www\.sefaria\.org/[^\s<>\"]+?)(?=[.,;:!?)]*(?:\s|$))"
    r"|(?<![\w/.])(?P<charity>/charity/\d+/)"
)


def _link(match: re.Match) -> str:
    url = match.group(0)
    if match.group("sefaria"):
        return f'<a href="{url}" rel="noopener noreferrer" target="_blank">{url}</a>'
    return f'<a href="{url}">{url}</a>'


@register.filter
def chat_text(value: str | None) -> str:
    """Escaped paragraphs, with charity and Sefaria links made clickable."""
    if not (value or "").strip():
        return ""
    escaped = escape(value)
    linked = _LINK.sub(_link, escaped)
    return mark_safe(linebreaks(linked, autoescape=False))
```

The whole security argument is in three lines of this, and they are worth spelling
out because they are easy to get backwards:

*Escape first, then link.* `escape(value)` runs before the pattern does, so any
angle bracket the model wrote is already `&lt;` by the time links are formed. The
comment explains the consequence: a quote is already `&#x27;`, so a URL that tries to
end the attribute early cannot. That is why the pattern matches the *escaped* text —
`test_cannot_break_out_of_the_attribute` stages exactly this attack with a
`onmouseover=` fragment and asserts it does not appear.

*Two shapes, both anchored.* The Sefaria alternative demands the exact host and
refuses trailing punctuation (so a sentence-ending period is not part of the link).
The charity alternative demands a literal `/charity/` followed by digits, and the
look-behind `(?<![\w/.])` stops it matching in the middle of some other URL.
`test_leaves_other_urls_as_text` proves `https://evil.example/charity/1/` stays text:
it starts with a foreign host, so no alternative matches it.

*External links are marked.* Sefaria opens in a new tab with
`rel="noopener noreferrer"`, which stops the new page from reaching back into this
one.

Finally, `linebreaks` gives paragraphs, so an answer with a blank line becomes two
paragraphs rather than one wall — and `mark_safe` is applied only to the already
escaped and already limited result.

The other new file in this directory is an empty `apps/chatbot/templatetags/__init__.py`.
It exists only to mark the folder as a package, which is what lets Django find the
filter; there is no code in it to review.

What it buys: an answer can be shown with confidence, and the worst a hostile prompt
can achieve in the page is plain text.

### 7.8 `apps/chatbot/views.py` and `urls.py` — four addresses, all members only

**The empty views file becomes the panel, the ask, the status check and the clear — each members-only, each with its own method — and the empty URL list becomes their four addresses.**

Before this change the chatbot had no reachable address at all.

The conversation memory (`apps/chatbot/views.py:13`):

```python
# The session keeps the last few exchanges, so a follow-up has its context.
HISTORY_KEY = "chatbot_history"
HISTORY_TURNS = 6


def _history(request: HttpRequest) -> list[dict]:
    return request.session.get(HISTORY_KEY, [])
```

Six exchanges live in the visitor's own session — not in a shared store — so a
follow-up works and an abandoned conversation evaporates with the tab.

The panel (`apps/chatbot/views.py:23`):

```python
@login_required
@require_GET
def panel(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "chatbot/panel.html",
        {"history": _history(request), "max_length": services.MAX_QUESTION_CHARS},
    )
```

It renders the conversation so far and the box, with the same 1,000-character limit
the service enforces. Guests never reach it: `login_required` sends them to the
login page.

Asking (`apps/chatbot/views.py:33`):

```python
@login_required
@require_POST
def ask(request: HttpRequest) -> HttpResponse:
    question = services.clean_question(request.POST.get("question", ""))
    if not question:
        return render(request, "chatbot/_notice.html", {"notice": "Type a question first."})
    pairs = [(turn["question"], turn["answer"]) for turn in _history(request)]
    try:
        task_id = services.enqueue_question(request.user.pk, question, pairs)
    except services.ChatbotError as exc:
        return render(request, "chatbot/_notice.html", {"question": question, "notice": str(exc)})
    return render(request, "chatbot/_exchange.html", {"question": question, "task_id": task_id})
```

Three outcomes, three small pieces of page: an empty question gets a notice, a
refusal (the daily cap, a queue failure) gets a notice *with the question kept on
screen* so the member can retry after reading why, and success gets the question
plus a "Thinking…" bubble that knows its job's name. Every failure is a small
fragment of HTML, because the panel swaps fragments in rather than reloading.

Checking (`apps/chatbot/views.py:47`):

```python
@login_required
@require_GET
def status(request: HttpRequest, task_id: str) -> HttpResponse:
    found = services.poll_status(request.user.pk, task_id)
    if found is None:
        raise Http404("No such question.")
    if found.state == "answered":
        history = [turn for turn in _history(request) if turn["id"] != task_id]
        history.append({"id": task_id, "question": found.question, "answer": found.answer})
        request.session[HISTORY_KEY] = history[-HISTORY_TURNS:]
    return render(request, "chatbot/_reply.html", {"status": found, "task_id": task_id})
```

The polling endpoint both returns the fragment *and* records the finished exchange in
the session. Two details: the history is filtered for the same task id before
appending, so a member whose browser polls twice (a reload, two tabs) does not get
the same exchange twice — `test_ask_and_poll` proves this by polling again and
checking the length; and `history[-HISTORY_TURNS:]` keeps only the newest six, so the
session cannot grow without bound. The 404 for an unknown or another member's task
is the design's requirement, and it is a 404 rather than a "forbidden" precisely so
that it reveals nothing.

Clearing (`apps/chatbot/views.py:60`):

```python
@login_required
@require_POST
def clear(request: HttpRequest) -> HttpResponse:
    request.session.pop(HISTORY_KEY, None)
    return render(request, "chatbot/_notice.html", {"notice": "Conversation cleared."})
```

And the four addresses (`apps/chatbot/urls.py:9`):

```python
urlpatterns = [
    path("", views.panel, name="panel"),
    path("ask/", views.ask, name="ask"),
    path("clear/", views.clear, name="clear"),
    path("status/<str:task_id>/", views.status, name="status"),
]
```

The panel is at `/chatbot/` — not a page in the navigation, because §7 asks for a
corner panel on every page rather than a destination.

What it buys: one member's conversation is theirs alone, in four addresses, with
method restrictions that make a stray link or a refresh harmless.

### 7.9 The five chatbot templates — the panel and its pieces

**Five small templates: the panel itself, the "Thinking…" bubble that re-asks for the status, the answer fragment, the just-sent exchange, and the two-line notice.**

The panel (`apps/chatbot/templates/chatbot/panel.html:1`):

```html
{% load chat_text %}{# The panel's body, loaded into base.html's corner panel on first open (D-076). #}
<div class="chat" id="chat">
  <ol class="chat__log" id="chat-log" aria-live="polite">
    {% for turn in history %}
      <li class="chat__msg chat__msg--me">{{ turn.question }}</li>
      <li class="chat__msg chat__msg--bot">{{ turn.answer|chat_text }}</li>
    {% empty %}
      <li class="chat__msg chat__msg--bot">Ask me about charities on MaaserMart, your maaser figures, or the halachos of tzedakah.</li>
    {% endfor %}
  </ol>
  <form class="chat__form" hx-post="{% url 'chatbot:ask' %}" hx-target="#chat-log" hx-swap="beforeend"
        data-chat-form>
    {% csrf_token %}
    <label class="visually-hidden" for="chat-question">Your question</label>
    <textarea id="chat-question" name="question" rows="2" maxlength="{{ max_length }}" required
              placeholder="Ask a question"></textarea>
    <button type="submit">Send</button>
  </form>
  <form class="chat__clear" hx-post="{% url 'chatbot:clear' %}" hx-target="#chat-log" hx-swap="innerHTML">
    {% csrf_token %}
    <button type="submit" class="chat__clear-btn">Clear conversation</button>
  </form>
  <p class="chat__note">Answers come from an AI and can be wrong. For a practical halachic question, ask your rav.</p>
</div>
```

Three details. `aria-live="polite"` tells a screen reader to announce new messages
as they arrive, without interrupting whatever it is currently reading. The questions
are shown unescaped-by-hand (`{{ turn.question }}` — Django escapes by default) while
the answers go through the `chat_text` filter, which does its own escaping. And the
closing note is the honest disclaimer the design asks for, in the same words the
prompt tells the model to use.

The polling bubble (`apps/chatbot/templates/chatbot/_pending.html:1`):

```html
<li class="chat__msg chat__msg--bot chat__msg--pending" hx-get="{% url 'chatbot:status' task_id %}"
    hx-trigger="load delay:1s" hx-target="this" hx-swap="outerHTML">Thinking…</li>
```

This is the whole polling mechanism, in two lines of HTML: when this bubble appears,
wait one second, then fetch the status address and replace *myself* with the answer.
Because the pending fragment is also what the status endpoint returns while a job is
still waiting, the bubble re-arms itself each time — the loop is made of the page
replacing itself, not of any code looping.

The answer fragment (`apps/chatbot/templates/chatbot/_reply.html:1`):

```html
{% load chat_text %}{% if status.state == "answered" %}<li class="chat__msg chat__msg--bot">{{ status.answer|chat_text }}</li>
{% elif status.state == "failed" %}<li class="chat__msg chat__msg--bot chat__msg--error" role="alert">Sorry, I couldn't get an answer. Please try again.</li>
{% else %}{% include "chatbot/_pending.html" %}{% endif %}
```

Three states, one template: the answer, the apology, or another turn of waiting. The
apology is §6.3's "couldn't get an answer" sentence, with `role="alert"` so a screen
reader announces it rather than waiting for a pause.

The just-sent fragment, which is what typing a question puts on the page, is two
lines (`apps/chatbot/templates/chatbot/_exchange.html:1`):

```html
{% if question %}<li class="chat__msg chat__msg--me">{{ question }}</li>
{% endif %}<li class="chat__msg chat__msg--notice" role="status">{{ notice }}</li>
```

```html
{# A question just sent, and the bubble that polls for its answer (D-076). #}
<li class="chat__msg chat__msg--me">{{ question }}</li>
{% include "chatbot/_pending.html" %}
```

A refusal keeps the member's question visible above the reason, which is why the
`{% if question %}` is there: the empty-question case has no question to show.

What it buys: the panel's entire behaviour is visible in five short files, and a
reviewer can follow a question from typing to answer without reading any Python.

### 7.10 `templates/base.html` and `apps/support/context_processors.py` — the corner panel on every page

**Twelve lines in the base template put a native open/close widget in the corner for signed-in members, and the nav context processor learns the panel's address so a page can find it.**

Before this change no page had a chat panel, and the base template's only scripts
were the two vendor libraries.

The nav addition (`apps/support/context_processors.py:43`):

```python
# The chatbot is a corner panel on every page, not a nav link (§7, D-076).
CHATBOT_URL_NAME = "chatbot:panel"
...
            "chatbot_url": _url_of(CHATBOT_URL_NAME),
```

The `...` in that box is the middle of the existing `nav()` function, unchanged; only
the two lines shown are new.

The same "resolve the address if it exists, or say nothing" machinery that already
keeps the nav from advertising unbuilt pages now carries the panel's address. That
means the panel appears only when its address exists — the site cannot end up with a
dead corner button.

The panel itself (`templates/base.html:50`):

```html
  {# The chatbot (§7, D-076): a corner panel for signed-in members. A native #}
  {# <details> opens it, so no inline script is needed under the CSP (D-062); #}
  {# htmx fetches the panel the first time it opens. #}
  {% if user.is_authenticated and nav.chatbot_url %}
    <details class="chatbot" hx-get="{{ nav.chatbot_url }}" hx-trigger="toggle once"
             hx-target="find .chatbot__body">
      <summary class="chatbot__toggle">Ask the assistant</summary>
      <div class="chatbot__body"><p class="chat__note">Loading…</p></div>
    </details>
    <script defer src="{% static 'js/chat.js' %}"></script>
  {% endif %}
```

Three words do the work, and each one is a constraint turned into a design.

`<details>` is the browser's own open/close widget — no JavaScript is needed to open
the panel, which matters because production's security rule (D-062) forbids inline
scripts and eval. `hx-trigger="toggle once"` fetches the panel body the first time it
opens, and only the first time — an unopened panel costs nothing, and a re-opened one
does not fetch again (the conversation is already in the page). `if
user.is_authenticated` keeps guests from seeing a panel they cannot use.

And `static/js/retry.js` is loaded for everyone in the page's head (quoted in
section 7.12), while `chat.js` loads only for members, because only they have a
panel.

What it buys: a member sees a corner button on whatever page they are on, and a guest
sees nothing.

### 7.11 `static/js/chat.js` — the three bits of behaviour the CSP allows

**The panel's only script: empty the box after sending, scroll to the newest message, and send on Enter while Shift+Enter starts a new line.**

Before this change none of that behaviour existed; the panel's HTML alone would send
messages and then leave stale text in the box.

The whole file (`static/js/chat.js:6`):

```js
  document.addEventListener("htmx:afterRequest", function (event) {
    var form = event.detail.elt;
    if (form instanceof HTMLFormElement && form.matches("form[data-chat-form]") &&
        event.detail.successful) {
      form.reset();
    }
  });

  document.addEventListener("htmx:afterSwap", function () {
    var log = document.getElementById("chat-log");
    if (log) {
      log.scrollTop = log.scrollHeight;
    }
  });

  // Enter sends; Shift+Enter starts a new line.
  document.addEventListener("keydown", function (event) {
    var box = event.target;
    if (event.key === "Enter" && !event.shiftKey && box instanceof HTMLTextAreaElement &&
        box.form && box.form.matches("form[data-chat-form]")) {
      event.preventDefault();
      box.form.requestSubmit();
    }
  });
```

Each listener is a small courtesy rather than a feature. The box is emptied only
after a *successful* request, so a failed send does not lose the question. The log
scrolls after any swap, so a new answer is in view. And Enter sends while
Shift+Enter makes a new line — with `event.preventDefault()` so the newline does not
also get inserted, and `instanceof` checks so the listeners cannot misfire on other
pages' forms.

The comment at the top of the file explains the whole reason this file exists at all:
"Production's CSP allows no inline script, so the panel's one bit of behaviour lives
here."

What it buys: the panel feels like a chat box, with no inline script and no Alpine.

### 7.12 `static/js/retry.js` — the network retry indicator (D-035)

**This new script is loaded on every page: when a request to the server gets no response at all, it shows "Connecting…" and tries again each second for five seconds, then says it could not reach the site.**

Before this change a lost connection mid-request meant a page that simply did
nothing — pressing Send on the chat box with a flaky connection looked like a broken
box.

The retry handler (`static/js/retry.js:25`):

```js
  document.addEventListener("htmx:sendError", function (event) {
    var detail = event.detail;
    var config = detail.requestConfig || {};
    var started = detail.elt._netRetryStarted || Date.now();
    if (Date.now() - started > RETRY_FOR_MS) {
      detail.elt._netRetryStarted = null;
      show("Couldn't reach MaaserMart. Check your connection and try again.");
      return;
    }
    detail.elt._netRetryStarted = started;
    show("Connecting…");
    window.setTimeout(function () {
      window.htmx.ajax(config.verb.toUpperCase(), config.path, {
        source: detail.elt,
        target: detail.target,
        // The source element supplies its own values and CSRF token again.
        swap: detail.elt.getAttribute("hx-swap") || undefined
      });
    }, RETRY_EVERY_MS);
  });
```

The distinction that makes this the right behaviour: this listener is `sendError` —
the request could not be *sent* or got no response at all. A server error (a 500) is
not this event, and the script's own header says so: server errors arrive as pages
and messages from the server and are not retried here, because retrying them would
just repeat the failure.

The five-second window (`static/js/retry.js:10`):

```js
  var RETRY_FOR_MS = 5000;
  var RETRY_EVERY_MS = 1000;
```

After that, the banner stops saying "Connecting…" and says plainly that the site
could not be reached. The banner is created once and reused, and finishing any
successful request hides it:

```js
  document.addEventListener("htmx:afterRequest", function (event) {
    if (event.detail.successful) {
      event.detail.elt._netRetryStarted = null;
      hide();
    }
  });
```

`_netRetryStarted` on the element is how the five seconds are counted per request
rather than globally: two different requests do not confuse each other's clocks.

What it buys: a flaky connection produces a visible, honest "Connecting…" instead of
a dead button, and never a silent retry storm.

### 7.13 The glue — settings, wiring, styling, and the environment file

**Two settings (the daily cap and the answer cutoff), one URL line, four lines in `.env.example`, and 123 lines of styling.**

The settings (`config/settings/base.py:186`):

```python
# Questions per member per UTC day (§6.3 "chatbot limit"), and how long a
# question may wait before the panel says "couldn't get an answer" (D-076).
CHATBOT_DAILY_LIMIT = env.int("CHATBOT_DAILY_LIMIT", default=30)
CHATBOT_ANSWER_SECONDS = env.int("CHATBOT_ANSWER_SECONDS", default=120)
```

Both are the numbers the pull request asks to have confirmed, and both are settings
rather than constants precisely so that confirming them is a one-line change in an
environment file.

The address (`config/urls.py:13`):

```python
    path("chatbot/", include("apps.chatbot.urls")),
```

And the environment documentation (`.env.example:44`):

```text
#   CHATBOT_DAILY_LIMIT=30     # questions per member per UTC day
#   CHATBOT_ANSWER_SECONDS=120 # then the panel says "try again"
```

The styling is 123 lines of ordinary CSS, and two rules carry the panel's physical
shape (`static/css/site.css:966` for the corner, `:1002` for the open state):

```css
.chatbot[open] {
  display: flex;
  flex-direction: column-reverse;
}
```

`column-reverse` is the trick that puts the button above the panel body without
duplicating markup: in the document order the button comes first, and reversing the
column turns it into the bottom-most element when open — exactly how a corner chat
widget should sit.

And the notice for a lost connection (`static/css/site.css:1075`):

```css
.net-status {
  background: #333;
  border-radius: 0.25rem;
  bottom: 1rem;
  color: #fff;
  left: 1rem;
  margin: 0;
  padding: 0.5rem 0.8rem;
  position: fixed;
  z-index: 30;
}
```

Bottom-left, dark, above the panel's corner — a status that cannot be mistaken for
part of the conversation.

What it buys: the numbers are changeable by whoever deploys the site, and the panel
sits in the corner where §7 says it should.

---

## 8. The tests

The new file is `tests/unit/test_chatbot_panel.py` (44 collected tests). No test
reaches a network: the task's provider is replaced with the fake from PR #31 in every
test that answers a question.

**Rendering an answer** — `test_escapes_html`; `test_links_a_charity_page`;
`test_links_sefaria_but_not_trailing_punctuation`; `test_leaves_other_urls_as_text`
(a foreign host is *not* linked); `test_cannot_break_out_of_the_attribute` (the
`onmouseover=` injection attempt); `test_paragraphs_and_empty`;
`test_usable_in_a_template`.

**The job store** — `test_lifecycle` walks waiting → failed → answered → deleted (in
that order now that an answer is final);
`test_an_answer_is_never_downgraded_to_a_failure` (the review-branch test: answer the
job, then fail it, and the answer is still there and still an answer);
`test_unknown_and_empty_ids`; `test_counts_uses_per_user` (one member's count does
not touch another's).

**The two services** — `test_clean_question`; `test_enqueue_answers_and_counts`;
`test_enqueue_sends_history` proves the conversation is sent in order *after* the
system message; `test_daily_limit` (with the limit set to one, the second question
is refused and the log says so); `test_queue_failure` (a broken queue gives
"Could not submit", no count is added, and the log names it); `test_unknown_or_foreign_task`
(both look identical from outside); `test_a_stale_pending_job_fails` (time is pushed
past the cutoff and the job becomes failed with "is the worker running?" logged);
`test_a_fresh_pending_job_waits`.

**The worker** — `test_retries_a_retryable_error_then_answers` (two provider calls,
then success); `test_gives_up_after_the_retries`; `test_a_permanent_error_fails_at_once`
(one call only); `test_missing_configuration_fails`; `test_an_empty_answer_fails`;
and the one that matters most for privacy: `test_logs_use_without_the_text` — the
question and answer both contain "secret", and the log line is asserted to contain
the counts and *not* the word.

**The lookups** — `test_search_by_domain` (the domain filter really filters, and the
page address is right); `test_unknown_domain_finds_nothing`; `test_search_by_name_and_limit`
(seven matches return five); `test_get_charity` (a 5,000-character description comes
back at about 1,200); `test_get_missing_charity`; `test_list_domains`; and
`test_my_maaser_is_bound_to_the_member`, which creates another member with 1,000 of
income and proves the asking member's figures are zero — and that the tool takes no
property at all, so there is nowhere to type a user id.

**The four addresses** — `test_guests_are_sent_to_log_in`; `test_panel`;
`test_ask_and_poll` (the question is echoed, "Thinking" appears, the answer arrives
with a clickable charity link, the session records exactly one exchange, and a
repeated poll does not duplicate it); `test_pending_keeps_polling` (the pending
fragment still carries `load delay:1s`); `test_failed`; `test_empty_question`;
`test_limit_notice`; `test_another_members_task_is_404`; `test_history_is_capped`
(eight exchanges asked, six remembered, the newest present); `test_clear`;
`test_wrong_methods` (a plain visit to ask is a 405, as is a form post to the panel).

**The corner panel on real pages** — `test_members_get_the_corner_panel` (the panel's
address is in the page, and both scripts are loaded);
`test_guests_do_not` (neither the panel's class nor `chat.js` appears for a guest).
