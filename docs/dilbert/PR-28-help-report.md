# PR #28 — Help and report pages, with a proof-of-email check for guests

- Branch: `support/help-report` → `main`
- PR #28 merged on 2026-11-24 as `92ab306` (D-072). **This document has been
  rewritten on 2026-11-26 to describe the branch as it stands now.**
- What is left to review: six commits after the merged point (D-078, and the two
  bugs it closes). 15 files, +316 / −108.
- For context only: PR #28 itself was 19 files, +896 / −5.
- Author: Platform Lead (Shaul)

A note on scope, because it is the first question a reviewer asks: the help and
report pages are already in `main`. This document still explains the whole feature
— a reviewer cannot judge a fix to a lock without knowing what the lock is for —
but the code it quotes, and the decisions it explains, are the six commits that
are **not** yet in `main`.

---

## 1. Read this part even if you read nothing else

MaaserMart is a website that lists Jewish charities so people can find one to give
money to. Two of its pages are for talking back to the people who run the site.
One is **Help**: "I have a question." The other is **Report**: "this entry for a
charity is wrong."

Picture a suggestion box in a shop lobby. Anyone walking past can drop a note in,
no purchase needed. That is what these two pages are — except the shop needs to be
able to write back to whoever left the note, and a note with no name on it is
useless.

So a visitor who is not signed in has to prove the email address is really theirs,
before the note is accepted: the site mails a six-digit number, and the visitor
types it back. That is the feature that went live in PR #28.

This change is what happened when two people looked closely at that check and found
two holes in it.

**Hole one: the tally was kept on the visitor's own copy.** Every time you guess a
code, the site adds one to a counter, and after five guesses it throws the code
away. The counter was stored in the visitor's session — the site's short memory of
one browser. The trouble is that the site saves that memory at the *end* of a
request, not during it. So a visitor who sends five guesses at the same moment is
not a visitor who has made five guesses; it is five copies of the same visitor,
each holding the same old number zero, each writing back one. Five guesses become
one. Repeat the trick and the five-guess limit is not a limit at all.

**Hole two: the cap was on the address, not on the building.** The site would only
mail five codes an hour to any one address, which stops someone filling one
mailbox. But it asked nothing about *where the requests came from*. One computer
could ask for a code to five hundred different addresses, an hour after hour. The
per-address cap never fires, because each address is asked once.

The fix has one idea behind it: **the things two separate features both need should
live in one place, and be counted once, properly.** The six-digit code, the email
that carries it, the tally of guesses and the "where did this request come from"
reading now live in one small shared folder that belongs to neither of the two
features. There is one tally, kept somewhere that survives a refresh and cannot be
reset by sending guesses in parallel. And there is now a second cap, counted per
building rather than per mailbox.

Everything below is the same idea in more detail.

---

## 2. How to read this file

This file is for two people at once.

- If you do not write software, read the **glossary** first, then the **story**,
  then the bold one-line summary at the top of each file section. That is the whole
  change.
- If you are reviewing the code, the same sections carry the real code, quoted,
  before and after, with a `file.py:line` address on each box.

Three rules make this work:

1. **Read the glossary before anything else.** Every word in this file is defined
   there or is ordinary English.
2. **Every code box is optional.** The sentence directly above each box says the
   same thing in plain English. Skip all the boxes and you lose nothing.
3. **Skim the bold lines.** Each file section opens with one bold sentence. Those
   sentences alone are a summary of the change.

---

## 3. The glossary

Ten words, and a table for the names that only exist inside the code.

- **Ticket** — the note a visitor drops in the box. It is one row in a database
  table called `TICKET`. It holds the message, who wrote it, and later the answer.
- **Guest** — someone using the site without signing in. The opposite is a
  **signed-in user**, whose identity the site already knows.
- **Verifying an address** — proving you can read the mail sent to an email
  address. Here: the site mails a six-digit number and you type it back.
- **Session** — the site's short memory of one visitor. It lasts while the browser
  keeps its cookie and is thrown away when it goes. This is where a half-finished
  verification waits.
- **Cache** — a shared scratchpad all the site's processes can read and write, kept
  in the database. It outlives a session, so it is the only place a count like
  "five codes per address per hour" can honestly live.
- **Network** — the group of addresses a visitor is coming from. For an ordinary
  cable or phone connection that is one address. For the newer, longer form of
  address (IPv6), it is the first half of it, because one household or one office
  usually owns that whole range.
- **Lock** — a way of making simultaneous requests take turns, so two of them can
  not both read the same number and both write it back unchanged. Here it is the
  database's own lock, held for the length of one saved change.
- **Try** — one typed code, right or wrong. **Send** — one code mailed out. These
  are the two things the site counts, and they are counted in different places,
  for different reasons.
- **Queue** — the site's list of small jobs to do after the page has already
  answered, such as sending an email. It is the "do this soon" tray, run by a tool
  called Celery.
- **Shared part / helper** — code that two features both use, kept in one place so
  there is one copy to fix rather than two to fix twice.

The names that only exist inside the code, in plain words:

| in the code | in this document |
|---|---|
| `TICKET`, `Ticket` | the note |
| session (`request.session`) | the visitor's short memory |
| cache (`caches["login"]`, `cache`) | the shared scratchpad |
| `common/verification.py` | the shared code-and-email helper |
| `common/clients.py` | the shared "where is this request from" reader |
| `spend_try`, `MAX_CODE_TRIES` | the tally, and its limit of five |
| `client_network` | the building, worked out from the address |
| `pg_advisory_xact_lock` | the database lock |
| Celery, `shared_task` | the queue |
| `take_token`, token bucket | a jar of turns that refills slowly |
| `digest`, "hashed" | a one-way scramble: you cannot read the value back out |
| Caddy, "the front door" | the piece of software in front of the site that every request passes through |
| `X-Forwarded-For` | the note the front door leaves saying where a request came from |
| `noqa` | a note to the code checker telling it to leave this line alone |

One more convention, because the code comments are full of it: **a D-number**
(`D-006`, `D-072`, `D-078`) is the house's numbered record of a question that was
decided, kept in `docs/DECISIONS.md`. When a code comment cites one, it is pointing
at the reasoning rather than repeating it.

---

## 4. The story

### What the site does all day

1. A visitor walks onto a charity's page and sees a "Report this charity" link.
2. On the Report page they type what is wrong and, if they are not signed in, an
   email address.
3. The site mails a six-digit number to that address. It keeps a hashed copy of
   the number in the visitor's short memory, plus when it expires.
4. The visitor types the number back. If it matches and it has not expired, the
   site marks the address as proven for that visitor and lets the note through.
5. The note becomes a ticket, and an admin answers it later by email.
6. Throughout, the site counts things, so one visitor cannot use the box to flood
   a stranger's mailbox or to walk through a million possible codes.

Step 6 is the part this change is about. Steps 1 to 5 did not change.

### What was wrong

**The guess tally lived in the visitor's short memory, and short memory is written
once, at the end.** Read steps 3 to 4 again and follow the tally. The site loads
the memory as it starts answering a request, adds one to the tally, and saves the
memory back when the request is over.

That works, one guess at a time: the tally goes 1, 2, 3, 4, 5, and on the sixth
guess the code is thrown away.

Now send five guesses at once. Five separate requests each load the same memory,
each sees "0 guesses so far", each writes back "1". The tally is 1. The visitor has
made five guesses and the site believes one. Send nine hundred more the same way
and the tally is still 1. The five-guess limit has become decoration.

The same weakness made a second thing true, which nobody had written down: a code
that had *already been used* could be used again from a copy of the memory. The
copy still had the code in it and the tally that said "not spent".

**The send cap only knew about the address.** There was one count: five codes an
hour per address. Nothing counted per building. A single machine could write down
five hundred addresses and ask for one code each; every one of those is inside its
own address limit, so nothing refused. That is a mailbox-filling machine, and the
only thing it needs is a list of addresses.

Doing the arithmetic makes it concrete. One code allows five guesses. One building
could ask for twenty codes an hour and stay inside the address caps. That is one
hundred guesses an hour, from one machine, against a number with one million
possible values.

### The cost of leaving it

- **A stranger's inbox gets filled**, and the site's mail service starts treating
  MaaserMart as a sender of junk. Once that happens, real verification emails stop
  arriving and nobody can leave a note at all.
- **A six-digit code is a million possibilities, and a machine tries thousands a
  second.** If guesses are not counted reliably, "verify your email" becomes
  theatre: whoever asked for a code to an address they do not own can find the
  number and file a report in that person's name, or about that person.
- **PR #28 is already in `main`.** So this is not a hypothetical. The unchecked
  version is what the live site runs today.

### The fix, in one sentence

The code, the email that carries it, the tally and the "where is this from" reader
now live in one shared place; the tally is kept in the shared scratchpad and
counted behind a database lock, so simultaneous guesses take turns; and a second
count caps guesses and codes per building, not only per mailbox.

What that buys, in order:

1. **Five really is five.** Simultaneous guesses are counted one at a time, so the
   sixth is refused however the guesses are timed.
2. **A used code stays used.** When a code matches, the shared tally for it is set
   past the limit, so a copy of the short memory cannot try it again.
3. **One building cannot flood mailboxes.** Twenty codes and thirty guesses an
   hour per building, on top of five codes per address.
4. **One place to fix, one place to read.** Signup and the guest pages use the same
   six digits, the same email and the same tally, so a change to any of them
   happens once. Signup keeps its own limits, because a signup is a different
   thing from a note in a box.
5. **One number, not three sentences.** The three places that told the visitor "it
   works for 15 minutes" now read that number from one constant, so they cannot
   drift apart.

### What did not change

- The pages themselves, what they say, and what they store.
- How the site finds the charity on the Report page.
- Signup's own limits: five signups an hour per network, three code emails an hour
  per inbox, ten guesses at once then one a minute.
- The ticket queue, and the reply email an admin sends.

---

## 5. Contradictions

Four places where an older description disagrees with the code, and what to trust.

**1. D-072 says the guest check is "support's own, not accounts'".** That was true
of the *policy* and is still true: a guest note creates no account, and the two
flows keep their own rules. It is no longer true of the *code*: the six digits, the
email and the tally now sit in `common`, outside both areas. Trust D-078 for the
code, D-072 for the behaviour.

**2. PR #28's decision text says tries are kept "in the visitor's short memory".**
That sentence is now wrong — it describes the hole, not the fix. Nothing in
`main`'s copy of `apps/support/verification.py` holds a tally in the session any
more. Trust the code, and D-078.

**3. The "it works for 15 minutes" sentence appeared three times** — in the shared
email, in the help page's notice, and in the signup verify page — each
written out by hand. All three are correct today by luck. They now read one
constant, and the middle one is quoted in section 7.10.

**4. The comment on `apps/support/verification.py` still says support "depends on
nothing" (§6.1).** Still true at the area level: support uses only the shared
folder, and the shared folder is not an area of the site. If you are checking the
boundary, check that instead.

---

## 6. Reading order

Read in this order. Each step makes the next one make sense: the shared part, then
the two features using it, then the wiring, then the tests.

| order | file | what it is |
|---|---|---|
| 1 | `common/__init__.py` | the new shared folder, and why it is a folder and not a tenth app |
| 2 | `common/verification.py` | **new** — the code, the tally behind a lock, the email |
| 3 | `common/clients.py` | **new** — where a request came from; moved out of accounts |
| 4 | `apps/support/verification.py` | the guest check: the tally moves out of the session, two caps per building |
| 5 | `apps/support/tasks.py` | the queued email now hands off to the shared one |
| 6 | `apps/support/views.py` | one line: tell the checker where the request came from |
| 7 | `apps/accounts/signup.py` | signup uses the shared code and tally, keeps its own limits |
| 8 | `apps/accounts/tasks.py` | signup's queued email hands off the same way |
| 9 | `apps/accounts/ratelimit.py` | the address reader is now borrowed from `common` |
| 10 | `apps/accounts/views.py`, `templates/accounts/signup_verify.html` | one lifetime constant, read in one place |
| 11 | `config/celery.py` | the queue has to be told the new email job exists |
| 12 | `docs/DECISIONS.md` — D-078 | the decision, quoted |
| 13 | the tests | what is now pinned |

One thing to read before the files: the pull request also carries Yosef's member
signup, which is an open pull request of its own. Section 8 says which of its files
belong there and why. Read the fifteen files below; send everything else to #16.

The one-sentence shape of the change: **the parts of email verification that two
areas both need moved into `common`, and the move is what made the two holes
visible and fixable.**

---

## 7. The files

### 7.1 `common/__init__.py` — a new drawer that is not a room

**A plain folder, not a tenth area of the site, because the site's rule says areas talk to each other through their front doors only, and this is not an area.**

MaaserMart is built out of areas — accounts, charities, support, and so on. The
house rule (recorded as D-006) is that one area may only reach another through that
area's front door, its `services.py`. So when support needed the same six-digit
code signup already had, putting the code in either area would have meant one area
reaching into another. The way out is a third thing that belongs to neither.

A Django "app" is a room with its own models, migrations and settings. This is not
that. It is a folder of plain Python that both areas may import.

`common/__init__.py:1`

```python
"""Primitives shared by apps that may not import each other (§6.1, D-006).

This is a plain package, not a tenth Django app: it holds only code that two
apps need and neither may own.
"""
```

What that buys: the boundary rule survives, and the queue registration is a single
line instead of a new app to install, migrate and configure.

---

### 7.2 `common/verification.py` — the shared code, tally and email (new file)

**Six digits, a tally that simultaneous guesses cannot cheat, and one email — the three things signup and the guest pages both need.**

Before this file, each area had its own copy of all three. Signup's copy is at
`apps/accounts/signup.py` in Yosef's branch; support's copy was at
`apps/support/verification.py` and is quoted in 7.4. The two copies had already
drifted: signup counted guesses behind a database lock, support counted them in the
session. One of those is a real limit and one is a decoration, and nothing said
which was which until they sat side by side.

The four numbers, with the reasoning that matters:

`common/verification.py:19`

```python
CODE_LENGTH = 6
CODE_LIFETIME_SECONDS = 15 * 60
MAX_CODE_TRIES = 5

_TRIES_TIMEOUT = CODE_LIFETIME_SECONDS + 60
_LIFETIME_MINUTES = CODE_LIFETIME_SECONDS // 60
```

Fifteen minutes, five tries, six digits. The try count is kept a minute longer than
the code lives, so a guess arriving just as the code expires does not find the tally
already gone.

#### `new_code` — one fresh number

**Makes a six-digit number, from a source meant for secrets.**<br>`common/verification.py:32`**

```python
def new_code() -> str:
    """A fresh 6-digit code; each code gets its own try count."""
    return f"{secrets.randbelow(10**CODE_LENGTH):0{CODE_LENGTH}d}"
```

Before, this was `_new_code()` in `apps/accounts/signup.py`, and support wrote the
same expression inline:

```python
# apps/accounts/signup.py:106, before (Yosef's branch)
def _new_code():
    return f"{secrets.randbelow(10**CODE_LENGTH):0{CODE_LENGTH}d}"

# apps/support/verification.py:71, before, written out inside start()
    code = f"{secrets.randbelow(1_000_000):06d}"
```

Same idea, two spellings, and only one of them would have noticed if the length
changed. The padding `%06d` is what keeps a number like `42` from arriving as `42`
instead of `000042`: without it, a short code would be refused as malformed and the
visitor would be stuck.

#### `spend_try` — the tally, counted where parallel guesses cannot tie

**Adds one to the count of guesses for one code, behind a database lock, and returns the new count.**<br>`common/verification.py:37`**

```python
def spend_try(key: str) -> int:
    """Count one attempt against `key`, returning the count including this one.

    PostgreSQL's advisory lock makes simultaneous guesses take turns, so they
    cannot all read the same old count and stay under the limit (D-078).
    """
    store = caches["login"]
    lock_id = int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big", signed=True)
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [lock_id])
        tries = store.get(key, 0) + 1
        store.set(key, tries, timeout=_TRIES_TIMEOUT)
    return tries
```

Read it in four steps, because every line is load-bearing.

1. `caches["login"]` is the shared scratchpad for anything to do with proving who
   you are — a separate database table from the one used for traffic limits, so a
   flood of one kind of count cannot push out the other.
2. The key is turned into a number so the database can lock on it. Two different
   codes almost never collide here; if they do, they simply take turns, which costs
   nothing but a few milliseconds.
3. `with transaction.atomic(), connection.cursor()` opens one database transaction,
   and `pg_advisory_xact_lock` waits for anyone else holding the same lock. The
   lock is released when the transaction ends, so nobody can be left holding it.
4. The read, the add and the write all happen inside that lock. This is the whole
   point: a second guess cannot read the old count until the first guess has
   written the new one.

This is the same idea that already existed in signup (`_spend_try`), moved here so
support gets it too. Section 7.7 shows signup's before.

#### `exhaust_tries` — a used code stays used

**Pushes a code's count past its limit, so a copy of the visitor's memory cannot offer the same code again.**<br>`common/verification.py:52`**

```python
def exhaust_tries(key: str) -> None:
    """Mark the code behind `key` used up, so a copy of the session cannot retry it."""
    caches["login"].set(key, MAX_CODE_TRIES + 1, _TRIES_TIMEOUT)
```

Setting the count to six (limit plus one) means every later guess is refused at the
"too many tries" check, without needing a separate "used" flag. Before this, both
areas wrote that same line themselves:

```python
# apps/accounts/signup.py:229, before
    caches["login"].set(_tries_key(pending), MAX_CODE_TRIES + 1, CODE_LIFETIME_SECONDS + 60)
```

One expression, in two files, with the timeout written out again in each. Now it is
one function with a name that says what it is for.

#### `send_verification_code` — one email, three wordings that do not drift

**A queued job that mails the code, told which flow asked for it so the wording fits.**<br>`common/verification.py:58`**

```python
_PURPOSES = {
    "signup": "finish signing up",
    "support": "verify your email for the help or report form",
}


def send_verification_code(email: str, code: str, purpose: str) -> None:
    """Email a verification code; `purpose` is 'signup' or 'support' (D-078)."""
    send_mail(
        subject="Your MaaserMart code",
        message=(
            f"Your code is {code}.\n\n"
            f"Type it on MaaserMart to {_PURPOSES[purpose]}. "
            f"It works for {_LIFETIME_MINUTES} minutes. "
            "If you did not ask for it, ignore this email."
        ),
        from_email=None,  # DEFAULT_FROM_EMAIL
        recipient_list=[email],
    )
```

One behaviour change a reviewer should notice, because it is the only place the
visitor sees something new: **signup's email used to put the code in the subject
line** (`"Your MaaserMart code: 123456"`) and has lost it, so both flows now share
one subject. Nothing in the tests, the templates or the decision record asked for
the code in the subject, and a code in a subject line is visible in a phone's
notification shade and in mail-server logs. Worth a word from the reviewer if they
would rather keep it.

The `_PURPOSES` dictionary is a small, deliberate choice: an unknown purpose raises
an error at the moment the email is built, which is a loud failure in a queue job
rather than a visitor staring at a page that silently mailed nothing.

---

### 7.3 `common/clients.py` — where the request came from (moved, not new)

**Works out the visitor's address, believing the forwarding header only from the site's own front door, and groups the long form of address by the half a household owns.**

This code is not new. It lived in `apps/accounts/ratelimit.py` and was needed by
signup's limits. Support needs the identical answer for its new per-building caps,
and support may not import accounts, so it moved here and accounts now borrows it
back (section 7.9).

**Before**, `apps/accounts/ratelimit.py:35` (Yosef's branch, and still the shape of
`main`):

```python
def client_ip(request):
    """The visitor's IP address.

    Behind Caddy, REMOTE_ADDR is Caddy's own address and the visitor's is the
    last entry Caddy appended to X-Forwarded-For. The header is believed only
    when the request comes from a trusted proxy; anyone else could send a fake
    one to get a fresh bucket on every request.
    """
    remote = request.META.get("REMOTE_ADDR", "")
    if remote not in settings.TRUSTED_PROXY_IPS:
        return remote
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    last = forwarded.split(",")[-1].strip()
    try:
        return str(ipaddress.ip_address(last))
    except ValueError:
        return remote
```

**After**, `common/clients.py:15` and `common/clients.py:27` — the same two
functions, with the docstrings tightened and the "why" moved into the module header:

```python
"""Visitor addresses used for rate limits (D-078).

Behind Caddy, REMOTE_ADDR is the proxy and the visitor is the last entry in
X-Forwarded-For. The header is believed only from a trusted proxy, and an IPv6
visitor is keyed by their /64 because a household usually owns the whole range.
"""

import ipaddress

from django.conf import settings


def client_ip(request) -> str:
    remote = request.META.get("REMOTE_ADDR", "")
    if remote not in settings.TRUSTED_PROXY_IPS:
        return remote
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    last = forwarded.split(",")[-1].strip()
    try:
        return str(ipaddress.ip_address(last))
    except ValueError:
        return remote


def client_network(request) -> str:
    ip = client_ip(request)
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return ip
    if address.version == 6:
        return str(ipaddress.ip_network(f"{address}/64", strict=False))
    return ip
```

Two refusals are baked into those nine lines, and both matter to the new caps:

- **The forwarding header is only believed from the site's own front door.** Anyone
  can put anything in that header. Believing it from a stranger would let a stranger
  claim a fresh identity per request and never hit any cap at all.
- **The long form of address is grouped by its first half (the /64).** One household
  or one office commonly owns a whole range of them, so counting single addresses
  there would hand one visitor billions of fresh turns.

---

### 7.4 `apps/support/verification.py` — the guest check, with the tally moved out and two caps added

**The guest's side of the box: send a code, then check the code typed back — now with the tally in the shared scratchpad and a per-building cap on both sends and guesses.**

This file is support's own policy and stays in support: a guest note creates no
account, and the two flows differ in what happens after a code matches. What moved
out is the code itself, the email and the tally.

The limits, each with its reasons:

`apps/support/verification.py:39`

```python
MAX_TRIES = MAX_CODE_TRIES
# Codes a single address may be sent per hour, whoever asks: stops the form being
# used to flood someone's inbox from many sessions.
MAX_SENDS_PER_EMAIL_PER_HOUR = 5
# Codes one network may cause per hour, across all addresses (D-078). The
# per-address cap alone can be walked around by trying many different addresses.
MAX_SENDS_PER_IP_PER_HOUR = 20
# Code tries one network may spend per hour, across all its codes (D-078). Each
# code already allows 5 tries, but a network can ask for 20 codes an hour, so
# without this it could spend 100 guesses an hour here. Generous next to the 5 a
# careful visitor uses, so a shared address (an office, a school) is not refused.
MAX_TRIES_PER_NETWORK_PER_HOUR = 30
# Both limits are hourly buckets in the default cache.
LIMIT_WINDOW_SECONDS = 60 * 60
```

The arithmetic in one place, since the code comment says it in a sentence: 20
codes an hour times 5 guesses each is 100 guesses an hour for one building. The
cap that closes that is 30 an hour. It is deliberately five times what a careful
visitor uses (one code, a couple of fumbles), because offices and schools share an
address and a cap that bites real people gets removed by the next person on
support duty.

#### The counting helper, shared by the three caps

**Spends one from each bucket, or none of them, and says which limit refused.**<br>`apps/support/verification.py:85`**

**Before** — one bucket only, and it spent before it decided:

```python
# apps/support/verification.py:58, before
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
```

**After:**

```python
def _spend(limits) -> str | None:
    """Spend one from every bucket.

    Returns None when all of them had room, otherwise the message of the first
    full bucket, and spends nothing: a refused send must not eat the others.
    Two sends racing can both pass a full check, which the caps can live with;
    they are spam limits, not the try count (which is locked, D-078).
    """
    for key, cap, message in limits:
        if cache.get(key, 0) >= cap:
            return message
    for key, _, _ in limits:
        cache.add(key, 0, LIMIT_WINDOW_SECONDS)
        try:
            cache.incr(key)
        except ValueError:  # Expired between add and incr: start a fresh window.
            cache.set(key, 1, LIMIT_WINDOW_SECONDS)
    return None
```

Three things changed here and all three are visible in the diff:

1. **Two passes, not one.** With one bucket, spending first and asking later was
   fine. With two buckets it is not: a visitor who is over their address limit
   would still have used up one of their building's turns. So the check runs over
   every bucket first, and nothing is spent unless every bucket has room.
2. **The message travels with the bucket.** The old version had to work out
   afterwards which limit had refused — which meant reading the scratchpad twice,
   and saying "too many codes to that address" when it was really the building.
3. **The race is admitted, in the comment, and left alone.** Two simultaneous sends
   can both pass a full check and both spend. That is one extra email in a rare
   tie, and closing it would mean a lock and a round trip on every guest page view.
   The guess tally is the one that has to be exact, and it is locked.

#### `start` — send a code

**Mails a fresh code and remembers it in the visitor's session, after spending both send buckets.**<br>`apps/support/verification.py:109`**

**Before** — one cap, no building, the tally started in the session, and the code
written out inline:

```python
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

**After:**

```python
def start(session, email: str, network: str = "") -> CheckResult:
    """Email a fresh code to `email` and remember it in the session as pending.

    `network` is the visitor's rate-limit key from `common.clients`; an empty
    value skips the per-IP cap, for callers with no request (such as unit tests).
    """
    email = _normalise(email)
    limits = [
        (
            _send_count_key(email),
            MAX_SENDS_PER_EMAIL_PER_HOUR,
            "Too many codes were sent to that address. Try again in an hour.",
        )
    ]
    if network:
        limits.append(
            (
                _ip_count_key(network),
                MAX_SENDS_PER_IP_PER_HOUR,
                "Too many codes were sent from this network. Try again in an hour.",
            )
        )
    if refused := _spend(limits):
        return CheckResult(False, refused)

    code = new_code()
    session[PENDING_KEY] = {
        "id": secrets.token_urlsafe(16),
        "email": email,
        "digest": _digest(email, code),
        "expires": time.time() + CODE_LIFETIME_SECONDS,
    }
    session.pop(VERIFIED_KEY, None)
    send_ticket_email_code.delay(email, code)
    return CheckResult(
        True,
        f"We sent a {CODE_LENGTH}-digit code to {email}. "
        f"It works for {CODE_LIFETIME_SECONDS // 60} minutes.",
    )
```

Four changes worth naming:

- **`"id": secrets.token_urlsafe(16)` is new in the session.** It is the random
  name the tally is filed under. It did not exist before because the tally was in
  the session; now the session carries only the name, and the number lives in the
  shared scratchpad under it. A new code gets a new name, which gives it a fresh
  count of five.
- **`"tries": 0` is gone.** That single deleted line is the bug from section 4.
- **The address cap is checked before anything is spent**, so a visitor over their
  building's limit does not lose one of their address turns.
- **`network` defaults to empty, and empty skips the building cap.** This is for
  callers with no request — the unit tests, and any future job — and it is the one
  place where a cap can be switched off. Section 7.6 shows the view that always
  passes a real value.

#### `confirm` — check the typed code

**Checks the typed code, spending one turn from the building and one from the code, and marks the address proven on a match.**<br>`apps/support/verification.py:150`**

**Before** — the tally was read, bumped and written back into the session, which is
the write that parallel requests each performed on their own copy:

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

**After:**

```python
def confirm(session, code: str, network: str = "") -> CheckResult:
    """Check `code` against the pending one; on a match the address is verified.

    `network` is the visitor's rate-limit key, as in `start`. A try refused by
    that cap does not use up one of the code's own 5, so a shared address is not
    punished twice.
    """
    pending = session.get(PENDING_KEY)
    if not pending:
        return CheckResult(False, "Ask for a code first.")
    if time.time() > pending["expires"]:
        session.pop(PENDING_KEY, None)
        return CheckResult(False, "That code has expired. Ask for a new one.")

    if network:
        refused = _spend(
            [
                (
                    _network_try_key(network),
                    MAX_TRIES_PER_NETWORK_PER_HOUR,
                    "Too many code tries from this network. Try again in an hour.",
                )
            ]
        )
        if refused:
            return CheckResult(False, refused)

    key = _tries_key(pending)
    tries = spend_try(key)  # Counted under a lock; parallel guesses cannot tie (D-078).
    if tries > MAX_TRIES:
        session.pop(PENDING_KEY, None)
        return CheckResult(False, "Too many wrong codes. Ask for a new one.")

    code = (code or "").strip()
    if not hmac.compare_digest(pending["digest"], _digest(pending["email"], code)):
        return CheckResult(False, "That code is not right. Check the email and try again.")

    # A copy of this session elsewhere must not try the same code again.
    exhaust_tries(key)
    session.pop(PENDING_KEY, None)
    session[VERIFIED_KEY] = pending["email"]
    return CheckResult(True, f"{pending['email']} is verified.")
```

The order is the argument, so read the order:

1. **No pending code, no turn spent.** A visitor who never asked for a code cannot
   burn their building's turns by posting a page of guesses.
2. **Expired, no turn spent.** Same reasoning; the code is already dead.
3. **Building cap, before the code's own tally.** A try refused here does not use
   one of the code's five. Otherwise one busy office would lock out a visitor who
   had done nothing wrong, which is a support ticket nobody can answer.
4. **The code's tally, behind the lock.** This is hole one closed. Note that the
   tally is spent *before* the comparison, so a burst cannot outrun it.
5. **The comparison is constant-time** (`hmac.compare_digest`), so the time a
   refusal takes does not tell an attacker how much of the code they got right.
6. **A match burns the tally** (`exhaust_tries`) and only then clears the pending
   code. Burning first is what stops a copy of the visitor's memory from trying the
   same code a second time.

The two remaining lines of note: `pending["tries"]` and the reassignment
`session[PENDING_KEY] = pending` are both gone, and with them the only writes to the
session inside this function that mattered to security.

#### The new bucket names

`apps/support/verification.py:73`

```python
def _send_count_key(email: str) -> str:
    return "support:email-code-sends:" + hashlib.sha256(email.encode()).hexdigest()


def _ip_count_key(network: str) -> str:
    return "support:email-code-sends-ip:" + hashlib.sha256(network.encode()).hexdigest()


def _network_try_key(network: str) -> str:
    return "support:code-tries-ip:" + hashlib.sha256(network.encode()).hexdigest()
```

Addresses are hashed rather than written into the scratchpad, so the table does not
become a list of everyone who used the help page. The three prefixes keep the three
counts apart; support's name is in each so they cannot collide with accounts' keys.

---

### 7.5 `apps/support/tasks.py` — the queued email hands off to the shared one

**Support's email job keeps its name and its retry behaviour, and lets the shared job do the writing.**

**Before**, whole file:

```python
@shared_task(autoretry_for=(OSError,), retry_backoff=True, max_retries=3)
def send_ticket_email_code(email: str, code: str) -> None:
    """The 6-digit code a guest types to prove the address is theirs (D-072)."""
    send_mail(
        subject="Your MaaserMart code",
        message=(
            f"Your code is {code}.\n\n"
            "Type it on MaaserMart to the help or report page. It works for 15 minutes.\n"
            "If you did not ask for it, you can ignore this email."
        ),
        from_email=None,
        recipient_list=[email],
    )
```

**After**, whole file:

```python
"""Emails support sends, queued through Celery (§4.14: email goes out through SES)."""

from celery import shared_task

from common.verification import send_verification_code


@shared_task(autoretry_for=(OSError,), retry_backoff=True, max_retries=3)
def send_ticket_email_code(email: str, code: str) -> None:
    """The shared verification-code email, worded for help and report (D-078)."""
    send_verification_code(email, code, "support")
```

Two things a reviewer should check here, because they are the kind of thing that
looks like a no-op and is not:

- **The job keeps its name.** A test asserts that the queue really discovers
  `apps.support.tasks.send_ticket_email_code`, and existing callers in
  `apps/support/verification.py` still say `.delay(email, code)`. Renaming the
  wrapper would have quietly broken both.
- **The retry decoration stays on the wrapper.** The shared job has no retry
  behaviour of its own; when the mail service fails, the error comes back up into
  this wrapper, which is the thing that waits and tries again. Moving the retry to
  the shared job would have changed signup's behaviour too (signup never retried).

---

### 7.6 `apps/support/views.py` — one line that says where the request came from

**The page tells the checker which building the visitor is in, once, for both steps.**

**Before**, `apps/support/views.py:23`:

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

**After:**

```python
def _guest_step(request: HttpRequest, action: str) -> tuple[str | None, str | None]:
    """Run a guest's send-code or verify step. Returns (notice, error)."""
    network = client_network(request)
    if action == "send_code":
        email = request.POST.get("email", "").strip()
        try:
            validate_email(email)
        except ValidationError:
            return None, "Enter a valid email address."
        result = verification.start(request.session, email, network)
    else:
        result = verification.confirm(request.session, request.POST.get("code", ""), network)
    return (result.message, None) if result.ok else (None, result.message)
```

Worked out once, at the top, so the two steps can not disagree about which building
the request came from. Both pages — help and report — go through this function, so
both get the caps. A signed-in user never reaches it (the caller checks), which is
why the caps cannot be spent by people who do not need a code at all.

---

### 7.7 `apps/accounts/signup.py` — signup keeps its own limits and borrows the shared parts

**Signup loses its private copy of the code, the tally and the "be used up" line, and keeps every limit it chose for itself.**

Signup is the second feature that verifies an email address. It already had the
good version of the tally — behind the database lock — which is why the shared part
is shaped the way it is. What it did not have was one place to keep it.

**Before**, three definitions in one file (Yosef's branch, `apps/accounts/signup.py`):

```python
CODE_LENGTH = 6
CODE_LIFETIME_SECONDS = 15 * 60
MAX_CODE_TRIES = 5
```

```python
def _new_code():
    return f"{secrets.randbelow(10**CODE_LENGTH):0{CODE_LENGTH}d}"
```

```python
def _spend_try(pending):
    """Count one code try for this code. Returns the count, this try included.

    The count lives in the "login" cache, not the session. Django saves the whole
    session when a request ends, so guesses sent in parallel would each read 0 and
    write back 1. A PostgreSQL lock on the code's id makes concurrent tries take
    turns, so every try is counted.
    """
    store = caches["login"]
    key = _tries_key(pending)
    lock_id = int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big", signed=True)
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [lock_id])
        tries = store.get(key, 0) + 1
        store.set(key, tries, timeout=CODE_LIFETIME_SECONDS + 60)
    return tries
```

That comment is the honest history of hole one: signup's author had already found
the session-tally problem inside signup, written it down, and fixed it there.
Support's copy was written separately and kept the weak version. The lesson is the
whole reason `common` exists — one copy cannot drift from itself.

**After**, the import line and the three replacements:

`apps/accounts/signup.py:28`

```python
from common.verification import (
    CODE_LIFETIME_SECONDS,
    MAX_CODE_TRIES,
    exhaust_tries,
    new_code,
    spend_try,
)
```

`apps/accounts/signup.py:132` — one call instead of a local `_new_code`:

```python
def _save_and_send(request, pending):
    """Give the signup a fresh code, save it in the session, then email the code."""
    # A new id gives the new code its own try count, starting at zero.
    pending.update(id=secrets.token_urlsafe(16), code=new_code(), sent_at=_now())
    request.session[SESSION_KEY] = pending
    enqueue_signup_code(pending["email"], pending["code"])
```

`apps/accounts/signup.py:199` — the tally function is now two lines, and the long
comment lives with the code it describes:

```python
def _spend_try(pending):
    """Count one code try for this code, with the shared atomic counter (D-078)."""
    return spend_try(_tries_key(pending))
```

`apps/accounts/signup.py:229` — the "be used up" line becomes the shared function:

```python
    # Used up: a copy of this session elsewhere can't try the code again.
    exhaust_tries(_tries_key(pending))
```

What did **not** change in signup, and a reviewer should confirm it:

- The five-signups-an-hour-per-building limit, the three-emails-an-hour-per-inbox
  limit (aliases of one Gmail inbox counted as one), the ten-guesses-then-one-a-minute
  building limit, and the order the checks run in. Those are signup's own policy and
  stayed put.
- `_tries_key` stays local: signup files its tally under `signup:tries:<id>` and
  support under `support:tries:<id>`, so one flow can never spend another's count.

---

### 7.8 `apps/accounts/tasks.py` — same hand-off as support

**Signup's email job keeps its name and drops its own copy of the message.**

**Before**, whole file:

```python
@shared_task
def send_signup_code(email, code):
    send_mail(
        subject=f"Your MaaserMart code: {code}",
        message=(
            f"Your MaaserMart signup code is {code}.\n\n"
            "It works for 15 minutes. If you didn't sign up, ignore this email."
        ),
        from_email=None,  # DEFAULT_FROM_EMAIL
        recipient_list=[email],
    )
```

**After**, whole file:

```python
"""Emails accounts sends, through Celery (§4.14)."""

from celery import shared_task

from common.verification import send_verification_code


@shared_task
def send_signup_code(email, code):
    """The shared verification-code email, worded for signup (D-078)."""
    send_verification_code(email, code, "signup")
```

The subject line is the visible loss: `Your MaaserMart code: 123456` becomes
`Your MaaserMart code`. See section 7.2 for why that is worth a decision rather than
a shrug.

Note the retry decoration is **absent, on purpose**: signup never retried a failed
email, and it still does not. Support's wrapper is the one with retries. Keeping the
difference visible in two small files is better than one shared job with an argument
that says "retry, but only for support".

---

### 7.9 `apps/accounts/ratelimit.py` — the address reader is borrowed back

**Accounts stops owning the address parsing and imports it from the shared folder, so existing imports keep working.**

**Before**, `apps/accounts/ratelimit.py:14` — the module imported `ipaddress` and
`settings`, and defined both readers itself (quoted in full in section 7.3).

**After**, the whole module head:

```python
"""Per-client rate limiting with a token bucket (D-YOSEF-accounts-login).

A bucket holds `capacity` tokens and gains one every `refill_seconds`. Each
request spends one; with none left the request is refused. Buckets live in the
shared cache (D-YOSEF-shared-cache), so every Gunicorn worker sees the same count.
The visitor's address comes from `common.clients`, shared with support (D-078).
"""

import hashlib
import time

from django.core.cache import cache

from common.clients import client_ip, client_network

__all__ = ["client_ip", "client_network", "take_token"]
```

Three deliberate details:

- **`client_ip` is re-exported, not deleted.** `apps/accounts/login.py` and
  `apps/accounts/signup.py` import `client_network` from this module, and the
  rate-limit tests import both names from here. Nothing at the call sites moved.
- **`__all__` says what the module offers**, so a reader knows the two borrowed
  names are part of the deal and not leftovers.
- **`take_token` and `_now` stay.** They are the token-bucket limiter, used only by
  accounts. Moving them was not needed, and the tests patch `_now` in this module
  to fake the clock — a move would have quietly defeated those patches.

---

### 7.10 `apps/accounts/views.py` and the verify page — one number, read not retyped

**The signup verify page is told the code length and the lifetime from the shared constants instead of three numbers typed by hand.**

**Before**, `apps/accounts/views.py:120` — and this is also the line that broke when
the constants moved:

```python
        "code_length": signup.CODE_LENGTH,
        "max_tries": signup.MAX_CODE_TRIES,
```

**After:**

```python
    context = {
        "email": signup.masked_email(pending["email"]),
        "next": pending["next"],
        "error": error,
        "notice": notice,
        "tries_left": signup.tries_left(request),
        "code_length": CODE_LENGTH,
        "code_lifetime_minutes": CODE_LIFETIME_SECONDS // 60,
        "max_tries": MAX_CODE_TRIES,
    }
```

with `from common.verification import CODE_LENGTH, CODE_LIFETIME_SECONDS, MAX_CODE_TRIES`
at the top of the file (`apps/accounts/views.py:8`).

**And the template**, `templates/accounts/signup_verify.html:6`. Before, the
minutes were typed out by hand:

```html
  <p class="empty">We sent a {{ code_length }}-digit code to <strong>{{ email }}</strong>. It works for 15 minutes.</p>
```

After:

```html
  <p class="empty">We sent a {{ code_length }}-digit code to <strong>{{ email }}</strong>. It works for {{ code_lifetime_minutes }} minutes.</p>
```

Small, and worth naming for one reason: `signup.CODE_LENGTH` stopped existing the
moment the constants moved. This is the sort of break that only the test suite
catches — sixteen tests went red until this line was pointed at the new home — and
it is why the reading order puts the shared file first.

---

### 7.11 `config/celery.py` — the queue has to be told the new job exists

**One import line, because automatic job discovery only looks inside the site's own areas, and the shared email job is not in one.**

**Before**, the whole file — five lines, and no knowledge that a shared job
exists:

```python
import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

app = Celery("maasermart")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
```

**After**, the whole file:

```python
import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

app = Celery("maasermart")
app.config_from_object("django.conf:settings", namespace="CELERY")
# The shared verification task lives outside the apps (D-078), so autodiscovery
# cannot find it; importing it registers it with this Celery app.
import common.verification  # noqa: E402, F401

app.autodiscover_tasks()
```

A reviewer should know why the import sits below the app is built and carries a
`noqa`: the queue is constructed first, and importing a task before the queue exists
would be the wrong order. The two `noqa` codes (F401 "imported and unused", E402
"import not at the top") are the honest record that this line looks unused and out
of place and is neither. A test pins the result: the job named
`apps.support.tasks.send_ticket_email_code` must appear in the queue's list of known
jobs.

---

### 7.12 `docs/DECISIONS.md` — D-078, the decision itself

**The house rule that says where shared code lives, and why the two caps are the numbers they are.**

This project records decisions that fill a gap or bend a rule in the design
document. The relevant part of the new entry, quoted:

`docs/DECISIONS.md:826`

```markdown
## D-078: Verification codes and visitor addresses are shared from `common`, outside the apps
- Date: 2026-11-26
- Status: Active
- Design doc ref: §6.1, §6.2.2, §6.3, §8.4; picks up D-072 and D-YOSEF-member-signup
- Decision:
  - `common/` is a plain package, not a tenth Django app. It owns the parts of email
    verification that signup and guest support both need and neither may own under D-006 …
  - `config/celery.py` imports `common.verification` explicitly; autodiscovery only
    looks inside installed apps.
  - A guest's code tries are counted in the `login` cache under a random id per code,
    behind a PostgreSQL advisory lock, not in the session. Session counters let
    parallel guesses each read the same old value (issue #45).
  - Code emails stay capped at 5 per address per hour and are also capped at 20 per
    client network per hour (issue #33). …
  - Guest code tries are capped at 30 per client network per hour … A try refused by
    this cap does not use up one of the code's own 5. Signup keeps its separate bucket
    (10 tries at once, then one a minute).
```

Two GitHub issues are named in it: **#45**, "Guest code tries can be bypassed with
parallel requests", and **#33**, "Guest verification codes have no per-IP send
limit". Those are the two holes from section 4.

---

## 8. What else rides in this branch, and is not this document

**One branch, two features: this one, and Yosef's member signup, which is still an open pull request of its own.**

A reviewer opening the pull request will see far more files than the fifteen this
document walks through. That is deliberate and worth understanding before reviewing
anything.

The shared helper exists **because signup already had this code**. There is no way to
demonstrate "two areas had the same code, now they share one" without both copies in
the same branch. So the branch merges `accounts/signup` (pull request #16, Yosef's,
still open) and builds on top of it.

What that means in numbers, and what to do about it:

| what | how many | where to review it |
|---|---|---|
| my commits (D-078 and the two fixes) | 6 | this document |
| Yosef's signup work, genuinely new | ~10 | pull request #16 |
| replays of commits already in `main` | ~28 | nowhere — they are already merged, under other commit names |
| files changed by the whole branch | 30 | 15 here, 15 in #16 |

The 28 replays are worth a sentence, because they look alarming in a commit list and
are not: `main` merged those branches with merge commits, and later branches were
built on top of them, so old commits appear twice under two names. `git cherry` is
the tool that shows which is which.

**`apps/accounts/services.py`** is the one file where this change touches something
of Yosef's and changes nothing: one blank line moved, no behaviour. Its new
functions — `submit_member_signup` and `enqueue_signup_code` — belong to #16.

So: review the six commits here against this document, and send anything about
signup's own behaviour to #16. If #16 merges first and `main` is merged back into
this branch, the review shrinks to exactly the fifteen files quoted below.

---

## 9. Where the rest of the help and report feature lives

The help and report pages were reviewed and merged as PR #28, and their walkthrough
is still accurate for everything this change did not touch. Rather than quote 900
lines of unchanged code again, here is the map — one line per file, so a reviewer
who wants the whole picture knows where to look.

| file (already in `main`) | what it does, in one line |
|---|---|
| `apps/support/migrations/0002_ticket_email_response.py` | gives the note table an address, an answer and a "when answered" |
| `apps/support/models.py` | the note: kind, charity, guest address, body, status, admin's answer |
| `apps/support/services.py` | the only way to file a note, and who is allowed to |
| `apps/support/urls.py`, `config/urls.py` | the two addresses exist under `/support/` |
| `apps/charities/services.py` | `find_charities_by_name` and `get_charity_choice`, so support can pick a charity without reading its tables |
| `apps/support/templates/support/` | what the visitor sees: the form, the code step, the "sent" page |
| `apps/charities/templates/charities/detail.html` | the "Report this charity" link |
| `static/css/site.css` | the buttons and notices for the two pages |
| `tests/unit/test_support_tickets.py` | everything above, pinned |

What this document quotes instead is every line the six new commits change.

---

## 10. The tests

Read the new test names as sentences; together they are the change's own summary.

**The tally can no longer be dodged by timing** — `tests/unit/test_support_tickets.py`:

- `test_copies_of_one_session_share_the_five_tries` — six copies of one visitor's
  memory, five wrong guesses, then the right one: refused. This is hole one, written
  down as a test.
- `test_a_used_code_cannot_be_used_from_a_copy` — the right code works once, and the
  copy of the memory that still holds it is refused. This is the "a used code stays
  used" promise from section 4.
- `test_parallel_guesses_are_all_counted` (already existed, in
  `tests/integration/test_signup.py`) — real threads, each with its own database
  connection. The one test that would catch a lock that only looked like a lock.

**A building is capped, on sends and on guesses**:

- `test_sends_per_network_are_capped` — twenty codes from one building, then a
  refusal, and a different building still allowed.
- `test_tries_per_network_are_capped` — walks exactly one hour of guesses (six codes
  of five) and asserts every one was allowed, then that the next is refused. It also
  asserts the refused try did **not** eat one of that code's five: the correct code
  from a different building still verifies in the same session.
- `test_the_form_caps_codes_by_client_network` and
  `test_the_form_caps_tries_by_client_network` — the same two caps, through the real
  page with a real address, so a view that forgets to pass the address fails here.

**The shared parts are shared** — `tests/unit/test_verification_helper.py`, new file:

- `test_new_code_is_six_digits` — one number, six digits, nothing else.
- `test_spend_try_counts_every_guess` — the tally returns 1, 2, 3.
- `test_both_app_tasks_use_the_shared_email` — both jobs put the right code in front
  of the right address, and each says what it is for ("finish signing up" versus
  "help or report"). This is the test that would fail if one of the two wrappers
  quietly kept its own copy of the message.

**The old ones that had to keep passing**, because the refactor touched their
plumbing: the signup integration tests (sixteen of them went red for a few minutes
when `signup.CODE_LENGTH` moved), the rate-limit tests (they import the address reader
from `apps/accounts.ratelimit` and patch its clock), and the queue test that asserts
the support email job is discovered.

Full suite at the time of writing: 723 passed, 61 subtests, coverage 95.29%.
