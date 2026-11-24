# PR 18 — "Schema and writes": the rules move from comments into the walls

- **PR:** [#18](https://github.com/MaaserMart/MaaserMart/pull/18) — `audit/02-schema-and-writes` into `search`
- **Size:** 32 files, 1345 added lines, 56 removed
- **Position in the stack:** second of five. Builds on #17 (the search) and is the base for #19.
- **Commits:** `c8d6a7f` — schema rules the audit found missing (D-055); `68c8450` — every charity write honoured, only trustable images rendered (D-056).
- **Written for:** the reviewer working without the diff, and anyone who wants to know what these rules are for.

---

## 1. Read this part even if you read nothing else

A building can have two kinds of rule.

One is **a sign on the wall**: "maximum occupancy 50". It is a real rule, everyone agrees with it, and
nothing stops a person walking past it with forty-nine friends. The other is **a door that physically
only fits fifty people through**. Both are rules; only one of them is still true at three in the
morning when nobody is reading signs.

This project has plenty of the first kind. Its written decisions say a member reviews a charity once,
that a cleared text box means empty, that a charity's image is a path the site can actually serve,
and that a page shows twenty-five charities with a correct count. Every one of those was true of the
*code paths that existed at the time*. None of them was true of the *database*, or of the one
function every future writer will go through.

Then the project was audited — a full read of every module, template, setting and test, written up as
`docs/AUDIT-2026-11-17.md`, which this PR adds. The audit found about forty issues. This PR takes a
specific slice of them: **the ones where a rule exists only as a sign**. It converts them into doors:

1. **Four schema rules become database constraints and indexes** (D-055): one review per member per
   charity, an index for the two columns every listing page sorts by, a positive amount and a
   required date on a ledger line, and an index for the admin's batch queue.
2. **Eight write-edge and read-edge rules become code at the one door everything passes through**
   (D-056): a cleared field is stored as empty rather than as an empty string, an image is validated
   before it is stored *and* checked again when it is drawn, the admin form refuses to report success
   for a field it cannot actually save, every numeric filter is held inside the range its meaning
   allows, a 10,000-character search term is dropped, a missing reference becomes a clear error, and
   the page and its total are read in one query instead of two.

**The whole change is one idea: a rule that lives in a comment is a rule nobody enforces.** Every
piece below is the same move — take a sentence that was true of the code, and make it true of the
data.

Everything below is the same idea in more detail.

---

## 2. How to read this file

Three rules.

1. **Read the glossary first** (section 3). Every term is defined there before it is used anywhere in
   this document.
2. **Every grey code box is optional.** The sentence directly above each box says the same thing in
   English. Skip all the boxes and you still have the whole story.
3. **Each file section opens with a bold summary line.** Reading only those lines gives you the change
   in a dozen sentences.

This document explains the change. It does not grade it. Where the code departs from the customer's
written design it says so plainly, in section 6, and leaves the judgement to you.

---

## 3. The glossary

| word | what it means here |
|---|---|
| **charity** | One organisation on the site: a name, a tagline, a description, an image, and a visible/hidden switch. |
| **constraint** | A rule the *database itself* refuses to break. If a constraint says an amount must be above zero, then no program, no script and no hand-written SQL can store a zero — the database rejects the write. |
| **index** | A lookup structure the database keeps so it does not have to read every row to answer a question. Without one, finding the 25 charities whose names come first alphabetically means reading two hundred rows and sorting them; with one, the answer is already in order. |
| **migration** | A recorded instruction that changes the database's shape (add a constraint, add an index, require a field). It runs once, in order, on every copy of the database, and it is never edited after it is merged. |
| **the write edge** | The one function through which changes to a charity go in. In this codebase, `update_charity`. Anything that wants to change a charity calls it, so a rule enforced there cannot be bypassed by a caller who did not know about it. |
| **the read edge** | The code that turns a stored value into something a page shows — here, the template filter that decides the image address. |
| **NULL** | The database's word for "no value at all", as opposed to the empty text `""`. Two encodings of "nothing" means every reader has to check for both, and one of them will forget. |
| **allowlist** | A list of things that are permitted, where everything else is refused. Here: the set of hosts a charity image may be loaded from. Empty means "no outside host at all". |
| **window count** | A way of asking the database for a page of rows *and* the total number of matching rows in the same question, so the two answers come from one snapshot of the data. |
| **batch** (of approvals) | A group of approval requests submitted together, which the admin queue decides as a unit. |

The plain words map onto the code like this:

| the code says | this document says |
|---|---|
| `models.UniqueConstraint`, `models.CheckConstraint` | a constraint (a door, not a sign) |
| `models.Index(...)` | an index |
| `EDITABLE_FIELDS`, `NULLABLE_FIELDS` | the list of fields the write edge applies, and the ones where blank means NULL |
| `validate_image`, `image_src` | the write-edge check and the read-edge check |
| `CLAMPS` | the table of allowed ranges, one row per numeric filter |
| `page_and_count`, `Window(Count(...))` | page and total from one question |
| `records_event` errors | a missing row named in the error instead of a raw database failure |

---

## 4. The story

### What the system does all day

1. A visitor opens the listing and pages through charities. The server asks the database: *which
   twenty-five match, and how many match in total?*
2. A charity owner, or the admin, edits a charity's details through the admin form. The change goes
   through one function, `update_charity`, which also records an event saying the charity changed.
3. A member can write one review of a charity they have dealt with. The charity's card shows an
   average rating built from those reviews.
4. A member enters a donation or an income line in the maaser tools, and the site sums them into a
   ledger.
5. The admin works a queue of approval requests — a charity applying to join — deciding whole batches
   of them at once.

Nothing about this is new to this PR. What is new is that the system got a **full audit**: an agent
read every module, template, setting and test, ran the test suite and the checks, and wrote up every
place where a promised rule was not actually enforced, as `docs/AUDIT-2026-11-17.md`. The findings
have ids — `D1`, `D2`, `B3`, `B8`, and so on. This PR is the second batch of fixes from that list.

### The rules that were only signs

**A member can review the same charity twice.** The design document says (§8.6, UC-05) "one review
per member per charity", and the review form's service was *expected* to block duplicates. But the
database had no rule, and the form code did not exist yet. Nothing was stopping a second review from
being written. The effect on the world: a member who reviews a great charity twice pushes the
average up; the card shows a rating nobody else deserves to trust, and a donor is misled about
quality.

**The page and its total are read in two separate questions.** The server first asked *how many
match?*, got, say, 200, then asked *give me rows 40–60*. Between the two questions, if someone adds a
charity, the second question's window has moved. Result: a charity you just saw on page 1 shows up
again on page 2, or is skipped entirely. Rare, invisible, and exactly the kind of bug that gets
reported as "the listing is glitchy" and is nearly impossible to reproduce.

**A cleared box can mean two different things.** The form, when an owner clears the description,
stored an empty string `""`. The database allows "no value at all" too, `NULL`. Now a rule like
"show me charities with a description" has to decide what to do with a row whose description is
`""`. Two encodings of "empty" means one of the checks will forget the other, forever.

**A charity's image is used exactly as it was stored.** The card checked "does it start with `http`?"
and, if so, printed the value into the page as an image address. A charity with an image from a
tracking host would make every visitor's browser fetch that host's pixel — telling a stranger that
everyone who visits this page is watching. And a path with `..` in it could point outside the site's
own image folder.

**The admin form can report "saved" for a field it did not save.** The admin form offers several
fields; the service applies only some of them. If an admin edits a field the service ignores, the
form said "changed successfully" and the value never reached the database. The charity's page shows
the old value, forever, with no error. (Finding **B2**.)

**A ten-thousand-character search term goes straight to the database.** Someone pastes a wall of
text into the search box; it becomes a gigantic pattern the database has to test against every
charity. (Finding **B5**.) **And the whole-word filter could be clamped out of range** — a negative
review count filter would silently be kept "as is", and the note explaining the correction always
talked about the star scale even when it was a different group being clamped. (Finding **B4**.)

### The fix, in one sentence

**Rules that were only described in prose are now enforced where nobody can bypass them.** Four of
them are enforced by the database itself — three new constraints and two new indexes, shipped as
migrations, because a migration is the only change that reaches every copy of the database. The rest
are enforced at the single write door and the single read door, so any future writer gets them by
passing through.

The consequences, listed:

- **Turned on:** one review per member per charity; indexes for the two orderings the listing uses;
  a positive, dated ledger line; an index for the batch queue; NULL for cleared fields; image
  validation both written and drawn; an honest admin form; clamped filters with correct notes; a
  dropped over-long term; a clear error for a missing reference; page and total from one query.
- **Not turned on, and why:** the database schema cannot change without the Platform Lead (project
  rule D-007), so all schema work here was co-authored with that lead as decision D-055.
- **Migrations are involved**, which is why this is a distinct PR and why the four schema changes are
  the commit that must land before the write-edge commit can rely on them.

---

## 5. Contradictions

Four places where a comment, a decision or a finding does not line up with the code or the document.
None is a bug in what the code does; all four are worth knowing so a reviewer does not chase a ghost.

**5.1 — Two comments cite the wrong finding id.** The new index block in `apps/charities/models.py:58`
says:

```python
        # Every listing page sorts by name (the default order) or by created
        # (`newest`), so both columns need an index or each page sorts the whole
        # table (B2, D-055). The `pk` tiebreak rides along in the name index.
```

The finding that asked for these indexes is **D2** ("No index on `CHARITY.name` or
`CHARITY.created`"), not B2. B2 is the unrelated admin-form finding. The seed change makes the same
kind of slip, citing "D-006" where the audit's finding is **D6** (and D-006 is the app-boundaries
decision, not about batches):

```python
# Requests submitted together share one batch (§5.2.5), and the admin queue
# decides a whole batch at once (§7.1.6). Batching the seed the same way gives
# that screen something real to work on in dev (D-055, superseding D-006's own
# single-request batches).
```

**Trust the audit findings, not the labels:** the work is keyed to D2 and D6 as the audit document
writes them; the comments just cite the wrong letter. The behaviour is the same either way.

**5.2 — `record_event`'s promise is narrower than the audit finding it fixes.** Finding **B6** said a
missing charity leaks a raw database error. The fix turns that into a `ValueError` naming the missing
id — but only for a *direct* call. When the same function runs inside a caller's transaction, the
database defers its check until the outer commit, which happens after this function has returned, so
the error cannot be caught here. The function's own docstring says exactly this, and the two callers
that exist today look the charity up first, so the guard covers what actually happens. It is an
honest, written caveat, not a hidden gap — read it as "this fixes the direct call, and the callers
cannot hit the leak anyway."

**5.3 — The audit document is part of this PR, and it describes a defect the code had already
fixed.** `docs/AUDIT-2026-11-17.md` is *added* here, 681 lines, describing findings against the code
at the previous branch tip. Some findings (the listing's count-then-page in B3, for example) are
being fixed in this very PR. So an audit reader will see "B3 — the listing counts and pages in two
queries" and, a few pages later, the code that fixes it. That is the intended shape — the audit is a
living record, and the *disposition* of each finding lands in later PRs (notably PR 20's
"record what happened to each finding" commit) — but it can look self-contradictory on first read.
Trust the sequence: audit first, fixes after.

**5.4 — `UPDATE` of the doc versus the write edge on images.** The design document's data dictionary
says `CHARITY.image` is `unique`; the model comment concedes it is not, citing an older decision
D-013. This PR adds image *validation* but deliberately does not add image *uniqueness*. That is not a
contradiction inside this PR — it is a documented, older choice that this PR leaves standing — but it
sits right next to the new validation code, so it is flagged in section 6 as departure **D5**.

---

## 6. Departures from the design document

### D1 — A ledger line's date is required now, where the document says nullable

**The document says** (`§5.2.18 — TRANSACTION`):

> date — date, nullable

**The code does** make it required and default to today (`apps/tools/models.py:22`):

```python
    # Required: a ledger line without a date cannot be ordered or totalled per
    # period, so an omitted date means today (D-055).
    date = models.DateField(default=timezone.localdate)
```

**Why:** the whole point of a ledger is adding and comparing amounts *per period* (income versus
donation for a given month). A line with no date cannot take part in that, so "no date" was
meaningless. Making it default to today keeps existing callers working while making the rule
provable. The value is set by the database when a writer omits it, so no writer can slip one through.

**Judged:** a deliberate reversal of the data dictionary, authorised by D-055. The safest kind of
departure: it makes a column the document left undefined behave the way the document's own purpose
(for maaser tracking) requires.

**Reversible in:** one migration making the field nullable again, and removing the default.

### D2 — The image write rule is a departure from the "string, nullable, unique" column

**The document says** (`§5.2.9 — CHARITY`):

> image — string, nullable, unique

**The code does** three things at once (via `validate_image`, `apps/charities/services.py:36`):
it keeps the field non-unique (a pre-existing, documented choice), and it *adds* a validation rule
the document never asks for — only http(s) URLs on an allowlisted host, or a path under `static/`,
are accepted.

**Why, for each half:**

- *Not unique:* the document's uniqueness would stop two charities sharing one image file, which
  there is no reason to forbid and which the seed already relies on (several charities share the
  repo's image set). Left as D-013.
- *Host-restricted:* the document describes an image the page shows; it says nothing about where it
  may come from. The new rule exists to stop a stored image turning the public page into a tracking
  beacon or an escape from the static folder (audit **B8**). It is a security choice the document is
  silent on, so it is a gap the project chose to close rather than a contradiction.

**Judged:** the added restriction is a justified closure of a security gap the document did not
anticipate; the dropped uniqueness is an older, separate decision. Both are named here so a reviewer
comparing to the data dictionary does not read either as an oversight.

**Reversible in:** for the restriction, an empty `CHARITY_IMAGE_HOSTS` (the default) and a deletion
of `validate_image`'s URL branch; for uniqueness, a migration adding a unique constraint (which would
require fixing the seed's shared images first).

### D3 — The admin's add form publishes immediately (a reading of the visibility rule)

**The document says** the admin can add a charity and (§6.2.14 area) the creation path
`submit_new_charity` creates the hidden CHARITY row. The code's own decision D-038 says a charity
starts hidden and only `publish_charity` makes it visible.

**The code does** publish an admin-added charity in the same request (`apps/charities/admin.py:27`):

```python
        if not change:
            super().save_model(request, obj, form, change)
            publish_charity(obj.pk, by_user_id=request.user.id)
            return
```

**Why:** finding **B7**. An admin who adds a charity is the approver; there is no pending approval
to wait for. Leaving the charity hidden would require the admin to hunt for a bulk action to show it,
and it would be invisible on the public listing in the meantime. Publishing in the same request makes
"admin adds" mean "admin approves".

**Judged:** a reading of D-038 rather than a contradiction of it — D-038's rule ("starts hidden,
visibility only through the services") is about *who may change visibility*, and here the change goes
through the service as required. The `approvals` side of the doc (an `APPROVAL_REQUEST` for the new
charity) is deliberately *not* created here, because charities may not call approvals under D-006;
that is filed as work for the approvals app rather than crossed across the boundary.

**Reversible in:** deleting the `publish_charity` line.

### D4 — Four empty-message states, batch batching, and the ledger's positive amount

Three smaller items that are additions or interpretations rather than true reversals:

- **`Transaction.amount` must be above zero** (a new check constraint, `apps/tools/models.py:31`).
  The document's column list gives the field no positivity rule; the constraint encodes what a
  ledger means — a zero contributes nothing and a negative would invert income and donation.
- **The seed now batches approval requests** (`seed.py`, `BATCH_SIZE = 10`). The document describes
  real batches (§5.2.5, §7.1.6); the seed previously gave every request its own batch, so the queue
  screen had nothing real to work on. Matching the data to the document, not departing from it.
- **Every numeric filter is clamped by its own bounds** (audit **B4**). The document says a filter
  can narrow by count and rating; it does not say what a negative count means. This PR decides it
  means zero, and makes the sidebar's explanation say so in that group's own words. A resolution of
  an ambiguity, not a departure.

### Not departures — the document actually asked for these

- **One review per member per charity** is enforced by the database now (§8.6/UC-05 literally:
  "one review per member per charity"). The doc asks for it; the database now guarantees it.
- **Indexes on the two ordering columns** the listing sorts by match the document's scalability
  promise ("PostgreSQL indexes on the list/filter/search columns").
- **NULL for cleared fields** matches the data dictionary, where the columns are "nullable" — NULL is
  what the dictionary says, `""` was the deviation being corrected.

---

## 7. Reading order

Each file makes the next one make sense. The order is: what the database will hold, then the code that
writes it, then the code that reads it, then the tests.

| # | file | what it is | why here |
|---|---|---|---|
| 1 | `apps/charities/models.py`, `apps/tools/models.py`, `apps/approvals/models.py` | The declarations: what a charity, a ledger line and an approval request are | The rules start here |
| 2 | `apps/charities/migrations/0002_*`, `apps/tools/migrations/0002_*`, `apps/approvals/migrations/0002_*` | The instructions that make the database match the declarations | Nothing takes effect until these run |
| 3 | `apps/charities/services.py` | The write edge: every charity change goes through it | Where the new normalisation and image rule live |
| 4 | `apps/charities/admin.py` | The admin form that calls the write edge | Where "reported success but saved nothing" is fixed |
| 5 | `apps/charities/templatetags/charity_images.py` | The read edge: stored value → image address | The second half of the image rule |
| 6 | `apps/charities/templates/charities/listing.html` | The card that uses the read edge | One filter replaces a hand-written `if` |
| 7 | `apps/charities/repositories.py` | The one file that talks to the database | Where page and total become one question |
| 8 | `apps/charities/filters.py` | The filter vocabulary | Where one clamp table replaces a rating-specific clamp |
| 9 | `apps/charities/search.py` | The search vocabulary from PR 17 | Two small hardening rules |
| 10 | `apps/events/services.py` | The activity recorder | One clearer error |
| 11 | `config/settings/base.py`, `.env.example` | The new allowlist setting | The image rule's configuration |
| 12 | `apps/dashboards/management/commands/seed.py` | The dev data generator | Batches, so the queue screen has real work |
| 13 | `docs/AUDIT-2026-11-17.md`, `docs/DECISIONS.md` | The audit itself and D-055/D-056 | The reasoning, written down |
| 14 | `tests/…` | The proof | Read after the code |

**The shape of the whole change in one sentence:** three migrations carry the four schema rules into
the database, and one write edge, one read edge and one new query carry the rest into the code.

---

## 8. The files, one at a time

### 8.1 `apps/charities/models.py` — **the charity record gains two indexes and one constraint (+13)**

This file declares what a charity is to the database: its columns, and the rules the database itself
must refuse to break. It had a list of rules already (a rating must be 1–5, a charity has one link of
each kind); this PR adds two more things to that list and a new block of indexes.

#### `Charity.Meta.indexes` — the two orderings the listing uses (new)

**Before:** the model had no `indexes` block at all, so ordering by name or by creation date meant the
database read and sorted every charity for every page. **After:**

```python
    class Meta:
        verbose_name_plural = "charities"
        # Every listing page sorts by name (the default order) or by created
        # (`newest`), so both columns need an index or each page sorts the whole
        # table (B2, D-055). The `pk` tiebreak rides along in the name index.
        indexes = [
            models.Index(fields=["name", "id"], name="charity_name_idx"),
            models.Index(fields=["created"], name="charity_created_idx"),
        ]
```

`["name", "id"]` rather than `["name"]` for a reason worth stating: two charities may share a name,
and when they do, the listing needs a guaranteed order between them or the same charity can appear on
both page 1 and page 2. The second column is the tiebreak, and putting it in the index means the
database can page straight through it instead of sorting.

What this buys: the default listing stops doing work proportional to the number of charities and
starts doing work proportional to the number of rows it shows.

#### `Review.Meta.constraints` — one review per member per charity (new)

**Before:** the only review rules were "the rating is 1–5" and "a review belongs to a charity". The
uniqueness rule lived in prose, waiting for a form that did not exist yet. **After:**

```python
# §8.6 and UC-05: a member has one review per charity. Enforced here
# as well as in the future upsert service, so no writer can add a
# second one (B1 of the schema audit, D-055).
(models.UniqueConstraint(fields=["charity", "author"], name="review_charity_author_uniq"),)
```

The comment says "as well as in the future upsert service", and that phrasing is the whole point:
the form's service will check too, for a friendly message. The database checks because a friendly
message is not a rule.

What this buys: a charity's average rating can only be built from one review per person, so a single
enthusiastic member cannot move the score twice. That is the difference between a rating a donor can
trust and a rating that reflects who clicked hardest.

---

### 8.2 `apps/tools/models.py` — **the ledger line must be positive and dated (+10, −3)**

This file declares one thing: a transaction in the maaser ledger, which is either income or a
donation, with an amount and a date. The maaser tool sums these to work out what a member owes.

**Before:**

```python
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField(null=True, blank=True)
```

**After:**

```python
    # A maaser ledger has no non-positive amounts: `0` contributes nothing and a
    # negative would invert income and donation (D-055).
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    # Required: a ledger line without a date cannot be ordered or totalled per
    # period, so an omitted date means today (D-055).
    date = models.DateField(default=timezone.localdate)
```

and the rule that makes the positivity real:

```python
class Meta:
    indexes = [models.Index(fields=["user", "type"], name="transaction_user_type")]
    constraints = [
        models.CheckConstraint(condition=models.Q(amount__gt=0), name="transaction_amount_gt_0"),
    ]
```

A negative amount is not a small mistake in a ledger: "income of −500" and "donation of 500" produce
the same total by two different routes, so a reporting bug in one of them looks like a user error in
the other. Forbidding it at the database means the arithmetic downstream only ever has one sign to
reason about.

`default=timezone.localdate` is a function, not a value, so each new row gets *its own* today rather
than the day the server started. That distinction is the difference between a ledger that works for a
year and one that silently files everything under the first day.

What this buys: the maaser total is arithmetic over positive, dated numbers, and the "per period"
totals the tools will show cannot be thrown off by an undated line.

---

### 8.3 `apps/approvals/models.py` — **the admin's queue gets a lookup (+3)**

This file declares approval requests: a charity or a user asking to be approved, with a status and a
batch. The admin queue decides a whole batch at once, so it asks "which requests are in batch X and
still pending?".

**Before:** one index, for "pending requests by date". **After**, a second one for the batch question:

```python
        indexes = [
            models.Index(fields=["status", "submitted_at"], name="approval_status_submitted"),
            # §7.1.6's queue groups by batch and decides a whole batch at once, so
            # this lookup needs its own index (D-055).
            models.Index(fields=["batch_id", "status"], name="approval_batch_status"),
        ]
```

Both columns in one index, in that order, because the question is asked in that order: *this batch*,
then *still pending*. An index on `batch_id` alone would find the batch and then read each row to
check its status.

What this buys: the admin's queue screen stays fast as requests accumulate, which matters because it
is the screen the business runs on.

---

### 8.4 The three migrations — **how a rule reaches an existing database (3 new files, 72 lines)**

Declaring a constraint in a model does nothing to a database that already exists. A migration is the
instruction that changes it. Three were generated and are quoted here in full, because a reviewer
approving a migration is approving a change to data that no code review can undo later.

**`apps/charities/migrations/0002_…`** — the charity indexes and the review constraint:

```python
operations = [
    migrations.AddIndex(
        model_name="charity",
        index=models.Index(fields=["name", "id"], name="charity_name_idx"),
    ),
    migrations.AddIndex(
        model_name="charity",
        index=models.Index(fields=["created"], name="charity_created_idx"),
    ),
    migrations.AddConstraint(
        model_name="review",
        constraint=models.UniqueConstraint(
            fields=("charity", "author"), name="review_charity_author_uniq"
        ),
    ),
]
```

**`apps/tools/migrations/0002_…`** — the ledger rules:

```python
operations = [
    migrations.AlterField(
        model_name="transaction",
        name="date",
        field=models.DateField(default=django.utils.timezone.localdate),
    ),
    migrations.AddConstraint(
        model_name="transaction",
        constraint=models.CheckConstraint(
            condition=models.Q(("amount__gt", 0)), name="transaction_amount_gt_0"
        ),
    ),
]
```

**`apps/approvals/migrations/0002_…`** — the batch index:

```python
operations = [
    migrations.AddIndex(
        model_name="approvalrequest",
        index=models.Index(fields=["batch_id", "status"], name="approval_batch_status"),
    ),
]
```

Two things a reviewer should notice rather than assume:

- **There is no data migration.** D-055 records why: no production data exists yet, and the seed and
  factories never create a duplicate review, so the new unique constraint cannot fail on existing
  rows. When there *is* production data, this is the step that needs a cleanup first.
- **The order of the migrations matters and is expressed in their dependencies.** The tools migration
  depends on the charities one, because the ledger row may point at a charity. Getting dependencies
  wrong means a fresh database builds in the wrong order, which is the classic migration bug — one
  nobody notices until a new environment is created.

What this buys: the rules are true of every copy of the database, including the ones nobody
remembers to update by hand.

---

### 8.5 `apps/charities/services.py` — **the write door learns to clean what it is given (+90, −14)**

This file is the only way a charity changes. Everything above it — the admin, the seed, the future
edit form, the future approval queue — calls these functions. That is why rules live here: a rule at
the write door cannot be skipped by a caller who has never heard of it.

#### `NULLABLE_FIELDS`, `IMAGE_SCHEMES`, `validate_image` — one meaning for "no value" (new)

**Before:** `update_charity` passed values straight through. A cleared text box arrived as `""` and
that is what got stored. An image arrived as whatever string the caller sent.

**After**, three new pieces, in the order the file reads:

```python
# Fields whose "absent" value is NULL, not "" (D-013, audit D5). A form submits
# an empty string for a cleared box, and storing it would give one meaning two
# encodings, so both entry points normalise before the row is written.
NULLABLE_FIELDS = ("tagline", "description", "image")

IMAGE_SCHEMES = ("http", "https")


def validate_image(value: str | None) -> str | None:
    """Return an image value the card can render, or refuse it (audit B8).

    Two shapes are allowed: a repo-relative path under `static/` (what D-043's
    seed writes) and an absolute http(s) URL on a host listed in
    `settings.CHARITY_IMAGE_HOSTS`. Anything else is refused at write time, so
    the template never has to guess and a card never loads an arbitrary
    third-party image or a path that escapes `static/`.
    """
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    parts = urlsplit(value)
    if parts.scheme:
        if parts.scheme.lower() not in IMAGE_SCHEMES or not parts.netloc:
            raise ValueError(f"Charity image must be an http(s) URL or a static path: {value!r}")
        if not _image_host_allowed(parts.hostname or ""):
            raise ValueError(
                f"Charity image host {parts.hostname!r} is not in CHARITY_IMAGE_HOSTS: {value!r}"
            )
        return value
    if value.startswith(("/", "\\")) or ".." in value.split("/"):
        raise ValueError(f"Charity image must not leave static/: {value!r}")
    if ":" in value:
        raise ValueError(f"Charity image is neither a URL nor a path: {value!r}")
    return value
```

Four refusals, each for a different reason, and the reasons are the review material here:

1. **A scheme that is not http(s)** — `javascript:alert(1)` is a well-formed address that does
   something entirely different from loading a picture. Refused.
2. **A host that is not allowlisted** — this is the tracking-pixel refusal. The list is a setting, so
   the customer can add their own image host without a code change.
3. **A path starting with `/` or containing `..`** — that is a path that leaves the site's image
   folder. `/etc/passwd` and `../../secret.png` both arrive here.
4. **A colon in a path that is not a URL** — the leftover case, refused rather than guessed at.

And the allowlist check itself, which is small enough to read in full:

```python
def _image_host_allowed(hostname: str) -> bool:
    """Whether `hostname` is on the configured image allowlist.

    An entry starting with "." allows any subdomain (".example.com"). An empty
    list allows no external image at all, which is the safe default.
    """
    hostname = hostname.lower()
    hosts = [host.lower() for host in getattr(settings, "CHARITY_IMAGE_HOSTS", ())]
    return any(
        hostname == host or (host.startswith(".") and hostname.endswith(host)) for host in hosts
    )
```

Note the default: **empty list means no external image at all.** A setting whose absence is safe is a
setting that cannot be misconfigured into a hole.

#### `_clean_value` — the single place a value is normalised (new)

**Before:** each caller decided what "blank" meant. **After:** one function, called for every field
`update_charity` is asked to write.

```python
def _clean_value(field: str, value):
    """Normalise one field value at the entry point: trim, and "" becomes NULL."""
    if isinstance(value, str):
        value = value.strip()
        if field in NULLABLE_FIELDS and not value:
            return None
    if field == "image":
        return validate_image(value)
    return value
```

The `strip()` is not decoration: a description of `"   "` is a blank box with a space in it, and
storing three spaces makes a "has a description" test say yes about a charity with no description.

#### `update_charity` — the clean runs before the write (changed, two lines)

**Before:**

```python
    unknown = set(changes) - set(EDITABLE_FIELDS)
    if unknown:
        raise ValueError(f"Not an editable charity field: {', '.join(sorted(unknown))}")
    with transaction.atomic():
```

**After:**

```python
    unknown = set(changes) - set(EDITABLE_FIELDS)
    if unknown:
        raise ValueError(f"Not an editable charity field: {', '.join(sorted(unknown))}")
    changes = {field: _clean_value(field, value) for field, value in changes.items()}
    with transaction.atomic():
```

One added line, positioned deliberately: **before** the transaction opens and before the row is
locked. So a bad image is refused without ever holding a database lock — which matters, because a
slow validation inside a lock is how one bad request blocks every other writer to that charity.

What this buys: there is exactly one encoding of "absent" in the database, and one place that decides
what an image may be. Every future writer — the edit form, the approval queue, an admin bulk action —
inherits both by calling this function.

#### `list_charities` — page and total from one question (changed)

**Before:** two separate reads, one for the count and one for the page:

```python
    total = repository.count(filters, search=search)
    count = page_count(total, page_size)
    number = max(1, min(page or 1, count))
    offset = (number - 1) * page_size

    return Page(
        items=repository.page(
            offset=offset, limit=page_size, filters=filters, sort=sort, search=search
        ),
        ...
```

**After:**

```python
    # One query answers the page and its total (see `page_and_count`), so a row
    # inserted between two statements cannot make a charity repeat or vanish
    # across a page boundary (audit B3).
    items, total = repository.page_and_count(
        offset=(max(1, page or 1) - 1) * page_size,
        limit=page_size,
        filters=filters,
        sort=sort,
        search=search,
    )
    count = page_count(total, page_size)
    number = max(1, min(page or 1, count))
    if number != max(1, page or 1) and total:
        # The requested page was past the end; only then is a second read needed.
        items = repository.page(
            offset=(number - 1) * page_size,
            limit=page_size,
            filters=filters,
            sort=sort,
            search=search,
        )
```

Read the last paragraph as a sentence: *the page that was asked for is fetched first; if the total
reveals it was past the end, and there is anything at all to show, fetch the last page instead.*

The `and total` is load-bearing. Without it, an empty result set would take the second path, ask for
a page of nothing a second time, and produce a quiet extra query on every search that matches
nothing — which is the most common empty case there is.

What this buys: the count and the rows describe the same instant. A charity cannot appear twice
because a row was inserted between the two questions.

---

### 8.6 `apps/charities/admin.py` — **the form that cannot lie about saving (+25)**

This file configures the Django admin's charity screen — the one place an admin edits charities by
hand. Its `save_model` runs on every save and is where the previous design quietly lost changes.

#### `CharityAdminUnappliedFieldError` — a named error for a real case (new)

**Before:** no such concept existed. **After:**

```python
class CharityAdminUnappliedFieldError(ValueError):
    """The admin form changed a field the charity service will not write (audit B2)."""
```

A specific exception rather than a generic `ValueError`, so the test can assert *this* mistake rather
than *some* mistake.

#### `save_model` — publish an added charity, refuse an unapplied change (changed)

**Before:**

```python
        if not change:
            super().save_model(request, obj, form, change)
            return
        changes = {
            field: form.cleaned_data[field]
            for field in form.changed_data
            ...
```

**After:**

```python
if not change:
    super().save_model(request, obj, form, change)
    publish_charity(obj.pk, by_user_id=request.user.id)
    return
readonly = set(self.get_readonly_fields(request, obj))
unapplied = [
    field for field in form.changed_data if field not in EDITABLE_FIELDS and field not in readonly
]
if unapplied:
    raise CharityAdminUnappliedFieldError(
        "This admin form changed fields the charity service does not apply: "
        + ", ".join(sorted(unapplied))
        + ". Add them to EDITABLE_FIELDS and update_charity, or make them read-only."
    )
```

Two behaviours, each answering a finding:

- **`publish_charity` on add** (finding B7): an admin adding a charity is the approver, so the
  charity goes live in the same request rather than sitting invisible.
- **Refusing an unapplied change** (finding B2): the form is told which fields it tried to change that
  the service cannot store, and fails loudly. The message says what to do about it, which is what
  turns a mystery into a task.

`readonly` is exempted on purpose: a field the admin is not allowed to edit cannot be "a change the
service failed to apply", and flagging it would make every read-only field an error.

What this buys: an admin can no longer be told "changed successfully" about a value the site never
stored. Either the change lands or the screen shows an error naming the field.

---

### 8.7 `apps/charities/templatetags/charity_images.py` — **the read edge (new file, 26 lines)**

This is the second half of the image rule: even with validation at the write edge, a row written
before the rule existed is still in the database. So the same rule runs again when the image is drawn.

**Before:** the template itself decided, with a string test:

```django
                {% if charity.image %}
                  {% if charity.image|slice:":4" == "http" %}
                    {# Seed data and user-supplied images are absolute URLs; {% static %} is for repo files. #}
                    <img class="charity-card__image" src="{{ charity.image }}" alt="" width="96" height="96">
                  {% else %}
                    <img class="charity-card__image" src="{% static charity.image %}" alt="" width="96" height="96">
                  {% endif %}
                {% else %}
```

**After**, one filter that answers "what is this value's usable address, if any?":

```python
"""The one place that turns a stored `Charity.image` into a safe `src` (audit B8).

Write-side validation (`charities.services.validate_image`) is the real gate, but
a database written before that rule existed still has to render safely, so the
same rule runs again here: a relative path becomes a static URL, an allowed
absolute URL is used as it is, and anything else renders as no image at all.
"""

from django import template
from django.templatetags.static import static

from apps.charities.services import validate_image

register = template.Library()


@register.filter
def image_src(value: str | None) -> str:
    """The URL to load a charity image from, or an empty string when it is not usable."""
    try:
        clean = validate_image(value)
    except ValueError:
        return ""
    if not clean:
        return ""
    return clean if "://" in clean else static(clean)
```

The `try/except` returning `""` is the whole safety property: a value that would be refused at write
time is *drawn as no image* rather than drawn as itself. A card with no picture is a cosmetic problem;
a card that loads a stranger's pixel is a data leak.

What this buys: a stored image is only ever one of three things on the page — a repo path made into a
static address, an allowlisted external address, or nothing.

---

### 8.8 `apps/charities/templates/charities/listing.html` — **the card uses the filter (+8, −8)**

The card markup loses its nested conditionals and gains one `with` block. **After:**

```django
                {# One filter decides the src, so an absolute URL and a repo path cannot be confused (B8). #}
                {% with image=charity.image|image_src %}
                  {% if image %}
                    <img class="charity-card__image" src="{{ image }}" alt="" width="96" height="96">
                  {% else %}
                    <span class="charity-card__image charity-card__image--empty" aria-hidden="true"></span>
                  {% endif %}
                {% endwith %}
```

and the file's load line changes to bring the filter in:

```django
{% load charity_images static %}
```

What this buys: the template no longer contains a rule at all — only a question ("is there an
address?") and two shapes. The rule lives in one Python function that has tests.

---

### 8.9 `apps/charities/repositories.py` — **the one database caller gains a single-read method (+37)**

This file is the only place in the charities app that talks to the database. It had `page` and
`count`; the fix for finding B3 is a third method that answers both in one statement.

```python
    def page_and_count(
        self,
        offset: int,
        limit: int,
        filters: CharityFilters | None = None,
        sort: CharitySort = DEFAULT_SORT,
        search: Search | None = None,
    ) -> tuple[tuple[CharityCard, ...], int]:
        """Return a page and its total from one read, so both see one snapshot.

        The total is a window count over the same query, so a row written
        between the count and the page (which used to be two statements) cannot
        make a charity repeat on page 2 or be skipped entirely (audit B3). Only
        an out-of-range page, which returns no rows and so has no window to read
        the total from, falls back to a count.
        """
        rows = self._narrowed(filters, sort=sort, search=search, reviews=True)
        rows = self._with_activity_values(rows, sort)
        rows = self._ordered(rows.annotate(total=Window(Count("pk"))), sort)
        window = list(rows.prefetch_related("domains", "locations")[offset : offset + limit])
        if not window:
            # Past the end: the caller still needs the total to clamp the page.
            return (), self.count(filters, search=search)
        return tuple(self._to_card(row) for row in window), window[0].total
```

`Window(Count("pk"))` is the technical name for "count the rows, but do it in the same pass as the
select". Every row carries the total on it, so the first row's `total` *is* the page's count — no
second statement.

The fallback is the honest part: if the page asked for is past the end, there are no rows to read the
count from, so it asks separately. But that only happens when the page was wrong, which the caller
fixes by clamping to the last page — and the comment is explicit that this is the one case where a
second read is needed, not a quiet regression to the old behaviour.

What this buys: the listing's "25 of 200" and its rows are the same instant in time, so the 
repeat-or-skip-under-writes bug (B3) cannot happen.

---

### 8.10 `apps/charities/filters.py` — **one table of allowed ranges replaces a rating-specific clamp (+47, −13)**

This file builds the filter groups. It had a single function, `clamp_rating`, that held the star
rating inside 1–5, and a note that always described the star scale. The audit (B4) found that other
numeric groups — review count, haskama counts — had **no** clamping at all, and that the note would
be wrong for them.

#### `CLAMPS` — every group's bounds in one place (new)

**Before:** the bounds were buried in `clamp_rating` and applied only to `min_rating`. **After:**

```python
# The bounds each numeric group's value is held inside, so a value is never
# carried off the scale it means. `None` is "no bound in that direction". One
# table for every group: the clamp and the note that explains it read the same
# entry, so a new bounded group cannot print another group's sentence (audit B4).
CLAMPS: dict[str, tuple[int, None] | tuple[int, int] | tuple[None, int]] = {
    "min_rating": (MIN_STAR_RATING, MAX_STAR_RATING),
    "min_reviews": (0, None),
    "min_approving_haskamas": (0, None),
    "max_disapproving_haskamas": (0, None),
}
```

Read the type as: each row is a (low, high) pair, where `None` means "no bound in that direction".
The star rating is bounded both sides (1–5); a count is bounded only at zero; a "maximum" is bounded
only at the top. One table, because the clamp and the human explanation have to agree, and a single
source for both means they cannot drift.

#### `clamp_number` and `clamp_rating` — the generic clamp and its old name kept (changed)

**Before:** `clamp_rating` was the only clamp. **After**, the general one, with `clamp_rating` kept
as a one-line alias so nothing that called the old name breaks:

```python
def clamp_number(parameter: str, value: int | None) -> int | None:
    """Hold one numeric group inside the bounds its meaning allows (D-046, audit B4).

    Clamping happens once, at the edge where the URL is read, so everything
    downstream — the query, the sidebar's input, the page links — sees the same
    number. `?min_rating=99` therefore means "5 stars or more" and the sidebar
    shows that 5, rather than the reader silently getting something else. Each
    group's bounds come from `CLAMPS`, so the rating's star scale is the rating's
    own rule and a negative review count becomes zero instead of "everyone".
    """
    if value is None:
        return None
    low, high = CLAMPS.get(parameter, (None, None))
    if low is not None:
        value = max(low, value)
    if high is not None:
        value = min(high, value)
    return value
```

#### `_adjusted_note` — the note names the group it clamped (changed)

**Before:**

```python
    return f"Kept between {MIN_STAR_RATING} and {MAX_STAR_RATING}; using {value}."
```

**After:**

```python
    low, high = CLAMPS.get(parameter, (None, None))
    if low is not None and high is not None:
        return f"Kept between {low} and {high}; using {value}."
    if low is not None:
        return f"Kept at {low} or more; using {value}."
    if high is not None:
        return f"Kept at {high} or less; using {value}."
    return ""
```

Before this, `?min_reviews=-4` was not clamped at all, and if it had been, the note would have said
"Kept between 1 and 5" about a review count. Now a negative count becomes zero, and the note says
"Kept at 0 or more; using 0." — the message and the rule come from the same row of the same table.

What this buys: every numeric filter means what its label says, and a visitor can see *why* a number
they typed was not the number shown.

---

### 8.11 `apps/charities/search.py` — **the search gets a ceiling (+17, −6)**

Two hardening rules for the search introduced in PR 17.

**A term is capped, and the cap is explained.** `from_query` used to keep whatever was typed. Now a
term longer than 100 characters is treated exactly like a blank one — no search at all:

```python
# A term longer than this is not a search anyone typed; it is dropped like a
# junk `page`, so an over-long URL cannot turn into a multi-megabyte ILIKE
# pattern over every row (audit B5). 100 characters is longer than any charity
# name in §5.2.9 (200) needs to be typed in full and far shorter than a request
# line Caddy would reject.
MAX_TERM_LENGTH = 100
```

and in `from_query`:

```python
    # A repeated `q` keeps the last value (the first is a real term too, but a
    # URL can only mean one); saying so here keeps the choice explicit (B9).
    terms = query.getlist(TERM_PARAMETER)
    term = " ".join((terms[-1] if terms else "").split())
    if not term or len(term) > MAX_TERM_LENGTH:
        return Search()
```

The `getlist` change is the second hardening (B9): a repeated `q` in the address previously used the
last value by accident; now it uses the last value *by an explicit decision that is written down*.
One search bar can only mean one term.

What this buys: the database never sees a search it would have to chew on, and a URL with two `q`s
behaves predictably.

---

### 8.12 `apps/events/services.py` — **a missing reference becomes a named error (+27, −2)**

`record_event` writes one row to the EVENT table — a view, a click, a charity change. **Before:** a
bad action was refused with a clear `ValueError`, but a reference to a charity that does not exist
escaped as the database's own raw error, which says nothing useful. **After:**

```python
    if action not in Event.Action.values:
        raise ValueError(f"Unknown event action {action!r}")
    try:
        with transaction.atomic():
            return Event.objects.create(
                charity_id=charity_id, action=action, link_id=link_id, user_id=user_id
            )
    except IntegrityError as error:
        raise ValueError(
            f"Event refers to a row that does not exist: charity_id={charity_id}, "
            f"link_id={link_id}, user_id={user_id}"
        ) from error
```

The error names the exact id that was wrong. The `from error` keeps the original failure attached, so
a debugging trace still shows the root cause.

What this buys: a caller that passes a bad id gets the same *kind* of error it already handles for a
bad action, and the message tells it which id to fix. (Its one written caveat is in section 5.2.)

---

### 8.13 `config/settings/base.py` and `.env.example` — **the allowlist as a setting (+5)**

The image rule needs its list of permitted hosts to be configuration, not code, so a site owner can
add their own image host without a release.

```python
# Hosts a charity image may be loaded from, besides the repo's own static files
# (D-021, audit B8). An entry starting with "." allows subdomains. Empty means
# only repo-relative paths are allowed, which is the safe default.
CHARITY_IMAGE_HOSTS = env.list("CHARITY_IMAGE_HOSTS", default=[])
```

and the example environment file shows how an operator sets it:

```dotenv
# Comma-separated hosts an external charity image may come from (optional).
# CHARITY_IMAGE_HOSTS=images.example.org,.cdn.example.org
```

`env.list` reads a comma-separated value; the `default=[]` is the safety property — an environment
that never sets it gets the empty allowlist, not an open one.

---

### 8.14 `apps/dashboards/management/commands/seed.py` — **real batches for the queue (+9)**

The seed fills the dev database with sample data. **Before:** every approval request got its own
batch id, so the "decide a whole batch" screen had nothing but single-item batches to show. **After:**

```python
# Requests submitted together share one batch (§5.2.5), and the admin queue
# decides a whole batch at once (§7.1.6). Batching the seed the same way gives
# that screen something real to work on in dev (D-055, superseding D-006's own
# single-request batches).
BATCH_SIZE = 10
```

and in the request loop:

```python
        # One batch id per group of requests, so the queue can decide several at once.
        batch_ids = [uuid.uuid4() for _ in range(-(-(APPROVED + PENDING) // BATCH_SIZE))]
        ...
                approval_request__batch_id=batch_ids[i // BATCH_SIZE],
```

`-(-n // BATCH_SIZE)` is the "round up" idiom: 200 requests at 10 per batch is 20 batches. The
`i // BATCH_SIZE` groups them ten at a time. (The comment's citation of "D-006" is the label slip
noted in section 5.1; the actual source is audit finding D6.)

What this buys: the admin queue, when built, has data shaped the way the document describes it, so
the screen is built against reality rather than against a guess.

---

### 8.15 `docs/AUDIT-2026-11-17.md` and `docs/DECISIONS.md` — **the map and the law (+711)**

This PR is unusual in that it *adds the audit report itself* — 681 lines — alongside the fixes that
answer parts of it. That is deliberate: an audit you cannot look at later is a list of rumours.

The audit's shape (read the summary table first, then jump to a finding's id):

```markdown
| ID | Sev | Area | Finding |
| --- | --- | --- | --- |
| B1 | High | tests | The test suite asserts eight nav links exist; seven of them 404 |
| B2 | Medium | admin | `CharityAdmin.save_model` silently discards any changed field not in `EDITABLE_FIELDS` |
| B3 | Medium | repositories | `Page` and `count` are two separate queries, so a page can repeat or skip rows under writes |
| B4 | Medium | filters | The clamp note is rating-specific text emitted by a group-agnostic helper |
| B5 | Low | search | The search term has no length limit, and an over-long one is passed straight to the database |
| B6 | Low | events | `record_event` raises `ValueError` for a bad action but lets an FK violation escape raw |
| B7 | Low | admin | An admin-added charity is left hidden and has no approval record (D-038 requires both) |
| B8 | Low | template | `charity.image` is used verbatim as an `<img src>` when it starts with `http`, unvalidated |
| B9 | Low | search | Repeated `q` parameters silently use the last one |
| D1 | High | schema | `REVIEW` has no unique (charity, author): a member can review a charity repeatedly |
| D2 | High | schema | No index on `CHARITY.name` or `CHARITY.created`, which every listing page sorts by |
| D3 | Medium | schema | `Transaction.amount` has no check for positivity; `Transaction.date` is nullable with no rule |
| D4 | Medium | schema | `ApprovalRequest.batch_id` is unindexed although the admin queue groups by it |
| D5 | Medium | data | Admin saves write `""` where the schema allows `NULL` (description, tagline, image) |
| D6 | Low | data | The seed gives every approval request its own `batch_id`, so batches are meaningless in dev |
```

And **D-055** and **D-056** record the two decisions this PR applies — the schema set and the
write-edge set — each with its date, its authority ("Platform Lead, applying the audit"), the design
doc references it touches, and its "Why" and "Where in code". A reviewer who wants the reasoning
behind any individual change can read the decision that authorised it. The mapping from finding id
to fix is: this PR covers D1–D4, D6 (via D-055) and B2, B4, B5, B6, B7, B8, B9, D5 (via D-056). The
rest — B1's nav links, S1–S9, SEC1–SEC4, M1 — are answered in later PRs in this stack.

---

## 9. The tests

Read the names as sentences; together they are the change's own summary. Grouped by what they prove.

**The database refuses what it should** (`tests/unit/test_models.py`):
`test_one_review_per_member_per_charity`, `test_a_member_may_review_several_charities`,
`test_transaction_amount_must_be_positive` (parametrised over bad values),
`test_transaction_date_defaults_to_today`, `test_the_listing_columns_are_indexed`,
`test_pending_requests_can_be_read_by_batch`.

The last two are unusual and worth seeing, because they are how a *schema* promise gets tested — by
asking the model what it declares, rather than by asking the database to be slow:

```python
def test_the_listing_columns_are_indexed():
    """The default and `newest` orders sort by columns nothing else indexes (D-055)."""
    indexed = {",".join(index.fields) for index in Charity._meta.indexes}
    assert {"name,id", "created"} <= indexed


def test_pending_requests_can_be_read_by_batch():
    indexed = {",".join(index.fields) for index in ApprovalRequest._meta.indexes}
    assert "batch_id,status" in indexed
```

The second review rule comes in a pair, and the pair is the point: one test proves a duplicate is
refused, the other proves an honest member can still review as many *different* charities as they
like. A constraint tested only one way could be satisfied by forbidding all reviews.

**The write edge cleans what it is given** (`tests/unit/test_charity_services.py`):
`test_a_cleared_field_is_stored_as_null_not_an_empty_string`, `test_a_static_path_is_an_acceptable_image`,
`test_an_unsafe_image_is_refused` (parametrised over five bad values), `test_an_allowlisted_image_host_is_accepted`.

The five refusals, quoted because the list is the specification:

```python
@pytest.mark.parametrize(
    "image",
    [
        "https://tracker.example/pixel.png",  # host not on the allowlist
        "javascript:alert(1)",
        "/etc/passwd",
        "../../secret.png",
        "charities/../../secret.png",
    ],
)
def test_an_unsafe_image_is_refused(image):
    """A card never renders a value the template cannot trust (audit B8)."""
    charity = CharityFactory()
    with pytest.raises(ValueError):
        update_charity(charity.id, image=image)
    charity.refresh_from_db()
    assert charity.image is None
```

The final two lines are the ones a reviewer should notice: the bad value was refused **and the stored
value was unchanged**. A validation that raises after the row is half-written would pass a test that
only checked the exception.

**The admin stops lying** (`tests/integration/test_charity_admin.py`):
`test_an_admin_added_charity_is_published`, `test_an_admin_changed_field_the_service_cannot_apply_is_an_error`.

**The read edge draws nothing it cannot trust** (`tests/unit/test_views.py`):
`test_allowed_absolute_image_url_is_not_wrapped_in_static`, `test_unlisted_image_host_renders_no_image`,
`test_path_that_leaves_static_renders_no_image` — plus hundreds of existing listing tests that still
pass unchanged.

**One test had to be rewritten, and the reason is the change itself.** The old test was:

```python
    def test_absolute_image_url_is_not_wrapped_in_static(self) -> None:
        # Seed data stores a full URL (D-024); {% static %} would mangle it into a 404.
        Charity.objects.create(name="Keren L'Dugma", image="https://placehold.co/600x400.png")
```

Its premise — *any* absolute URL is fine — is exactly what this PR decided was wrong. It is now
`test_allowed_absolute_image_url_is_not_wrapped_in_static`, and it needs the host to be allowlisted
first (`@override_settings(CHARITY_IMAGE_HOSTS=["placehold.co"])`). The behaviour it protects
(don't run a full URL through the static path helper) survives; only the permission to use any host
is gone. Naming this matters: a reviewer seeing a renamed test should know it was rewritten *because
the rule changed*, not because it was inconvenient.

**Page and total from one read** (`tests/unit/test_repositories.py`, the new `PageAndCountTest`):
`test_reports_the_page_and_its_total`, `test_the_page_costs_one_query_plus_the_prefetches`,
`test_a_window_past_the_end_still_reports_the_total`.

The middle one is the money test — it counts queries, so a future refactor that quietly reintroduces
the second read fails here:

```python
    def test_the_page_costs_one_query_plus_the_prefetches(self) -> None:
        with self.assertNumQueries(3):  # page, domains, locations
            self.repository.page_and_count(offset=0, limit=10)
```

Three, not one, because the page also loads each charity's domains and locations for the card. The
number is written out with its reason, so a reviewer can tell a regression from an addition.

**The clamp and its note agree** (`tests/unit/test_filter_service.py`, new `NumericGroupClampTest`):
`test_a_negative_count_is_clamped_to_zero`, `test_the_note_names_the_group_it_clamped`,
`test_a_group_that_asked_for_nothing_has_no_note`. The middle one asserts both halves, and the second
assertion is the one that would have caught audit finding B4:

```python
        self.assertEqual(reviews.adjusted_note, "Kept at 0 or more; using 0.")
        self.assertNotIn("1 and 5", reviews.adjusted_note)
```

**The term has a ceiling** (`tests/unit/test_search.py`, new `SearchTermLimitsTest`):
`test_a_term_longer_than_the_cap_is_dropped`, `test_a_term_at_the_cap_is_kept`,
`test_a_repeated_term_uses_the_last_value`. Both sides of the boundary are tested, so an off-by-one in
the cap cannot pass.

**A missing reference is named** (`tests/unit/test_event_services.py`):
`test_record_event_names_a_reference_that_does_not_exist`, which asserts the error *mentions the id*
(`match="charity_id=999999"`), not merely that an error occurred. It also runs with
`transaction=True`, because the behaviour under test only exists outside an enclosing transaction —
the caveat from section 5.2, made explicit in the test's own setup.

**Six existing test files changed, and every change is the same kind of churn:** a fixture that gave
several reviews to one author is now illegal, so each review gets its own author. The lines look like
this, in `test_filter_repository.py`, `test_sort_repository.py`, `test_template_contract.py` and
`test_repositories.py`:

```python
-        author = UserFactory()
         for rating in (5, 4):
-            Review.objects.create(charity=self.rated, author=author, rating=rating)
+            Review.objects.create(charity=self.rated, author=UserFactory(), rating=rating)
```

That is the correct churn: the constraint made an old fixture nonsense, and the tests were updated to
respect the new rule rather than the rule being weakened to keep the fixtures. It is also why this PR
touches test files that have nothing to do with schema rules — a reviewer should expect it.

---

## 10. The audit

The Dilbert test run against the finished document, plus the two-layer check.

**Where he would have fallen off, and what was fixed:**

- **"constraint" and "index"** were both used in section 1 before being defined. They are now glossary
  rows, and section 1's analogy (sign on the wall versus a door that fits fifty people) gives the
  constraint idea before the word appears in technical clothing. — fixed.
- **`""` versus `NULL`** was the one idea most likely to lose him. Section 1 states it in one plain
  sentence ("two encodings of *nothing*"), the glossary defines both, and the story's "cleared box"
  paragraph re-explains it without the symbols. — checked at three places.
- **"migration"** now has a whole glossary row that ends with *why anyone cares* ("the only change that
  reaches every copy of the database"), because a reader who thinks migrations are plumbing will not
  understand why they are in their own PR. — fixed.
- **Arithmetic:** the numbers used are 25 per page, 200 charities, "10 per batch, 200 requests, 20
  batches", 100 characters, and the diff's 1345/56. The one calculation (`-(-n // BATCH_SIZE)`) is
  explained in words in section 8.14 rather than left as an idiom. — checked.
- **One sentence with three ideas** in section 8.5's "What this buys" was split into two. — fixed.

**Every code box has an English sentence directly above it.** Walked: the model index block, the
review constraint, the two ledger declarations, the three migration bodies, `validate_image`,
`_image_host_allowed`, `_clean_value`, `update_charity`'s one line, `list_charities` before/after,
the admin error class and `save_model`, the template filter, the card markup, `page_and_count`,
`CLAMPS`, `clamp_number`, `_adjusted_note` before/after, `MAX_TERM_LENGTH`, `from_query`,
`record_event`, the setting, the seed batching, the audit summary table, and the two quoted tests. All
covered.

**The two-layer check.**

- *Delete every code box.* The document still contains: the sign-versus-door opening, the glossary,
  the story of five separate rules that were not enforced with their consequences, four
  contradictions, six departures with judgements, the reading order, a plain-English account of every
  file (what it was, what it is now, what it buys), and the tests described in sentences. It stands.
- *Read only the code boxes.* The whole change is visible: the three model files, the three
  migrations in full, the write edge, the admin, the read edge and the card, the single-read query,
  the clamp table, the search cap, the event error, the setting and the seed. A reviewer would not
  need the diff to approve the schema half or the write-edge half. It stands.

**Where he still cannot follow, and why that is acceptable:** section 8.9's `Window(Count("pk"))` and
the prefetch discussion. "A window count over the same query" is as plain as that idea gets without a
drawing; the paragraph after the box explains the *consequence* (one snapshot, no repeat, no skip),
which is what he needs. The engineer gets the real expression. He is never left without a floor: the
docstring quoted above the box says the same thing in different words.

**Bottom line:** the document can be reviewed from, and it explains itself. It does not grade. The
judgement calls it hands back to you are: the ledger date reversal (6.D1), the image rule's two halves
(6.D2), the admin publishing on add (6.D3), and the two miscited finding ids (5.1).
