# PR 21 — "One address": the listing's whole URL state as a single value, and an answer about accents

- **PR:** [#21](https://github.com/MaaserMart/MaaserMart/pull/21) — `audit/05-url-state` into `audit/04-defects`
- **Size:** 24 files, 582 added lines, 232 removed
- **Position in the stack:** fifth and last.
- **Commits:** `95d49e4` — give the listing one URL state instead of three (D-068, audit S1/S7); `b67842f` — the search folds case but not accents, and pin both (D-069); `e2fe0f6` — record #40 as out of scope and narrow #12 to what `save_review` does.
- **Written for:** the reviewer working without the diff, and anyone who wants to know what these three commits are for.
- **Note on what is not here:** the branch once carried a local task list in `.comtai/`. It was removed from this branch on purpose and is not part of the diff.

---

## 1. Read this part even if you read nothing else

A web page's address is not decoration. On this listing, the address *is* the page: `?q=chesed&domain=3&sort=rating&page=2` means "the charities whose name matches *chesed*, in the Free loans domain, best-rated first, second page". Anyone can copy that address, paste it to a friend, and the friend sees the same list. The design document asks for exactly that, in UC-03's Implementation Constraints: **"everything is
stored in URL parameters"**, next to "full page loads (so back works)".

That promise has an enemy, and it is a small, boring one: **the page has several forms on it, and each form has to remember to carry the other parts of the address.** The search bar must not drop the filters. The filter sidebar must not drop the sort. The sort dropdown must not drop the search. The page-size form must not drop any of the three. Each of those is a line of HTML that somebody has to remember.

Before this PR, that was three separate little modules plus three separate HTML partials:

- `filters.py` had its own way of reading the address, writing its pairs, and building a query string;
- `sorting.py` had its own copies of all three;
- `search.py` had its own copies of all three;
- `services.py` glued the three sets of pairs together **by hand** in one order;
- and three template partials (`filter_state.html`, `search_state.html`, `sort_state.html`) each had to be included, by name, into every form that was not allowed to drop that part.

Three modules, three partials, one hand-written order. Each form included the two partials it needed and not the third. That is thirty little decisions where a form can forget one — and the failure is silent. Drop the search from the sort form and clicking "sort by rating" quietly throws away the word the visitor typed. Nothing errors. The page simply becomes a different list.

**This PR makes the address one value.** `PageState` is a single frozen object holding the search, the filters, the order and the page window. One table says what the parts are and in what order they are read and written. One function turns it into a query string. And the templates now have a single partial that writes the whole state as hidden inputs, with a parameter naming the one slice the form owns:

```
{% include "charities/state.html" with skip="filters" %}
```

The default is *everything*. A new form that forgets the parameter still carries the whole address, so forgetting is no longer possible — it is the wrong way round on purpose.

The second half of the PR is a decision rather than a refactor. An audit question asked: should searching "chesed" find a charity registered as "Chésed"? **The answer is no** — the search ignores upper/lower case, as the design document requires, and does not fold accents (D-069). The reasoning is in section 4.5, and it is a product judgement, not a technical one.

**The claim to check, if you check one thing:** this is a refactor with no behaviour change, and the PR proves it two ways — every listing test passed without being edited, and the addresses the tests pin are byte-identical. One test is new and exists precisely to make the old failure mode impossible to reintroduce: it requests the listing and, for each form on the page, asserts which slices of the state that form is carrying.

---

## 2. How to read this file

Three rules.

1. **Read the glossary first** (section 3). Every term is defined before it is used.
2. **Every grey code box is optional.** The sentence above each box says the same thing in English.
3. **Each file section opens with a bold one-line summary.**

This document explains; it does not grade. Section 6 lists departures from the design document; section 5 lists places where documents disagree with each other or with the code.

---

## 3. The glossary

| word | what it means here |
|---|---|
| **URL state** | Everything the address bar says about what you are looking at: the search term, the ticked filters, the order, and which page. |
| **query string** | The part of an address after the `?` — `q=chesed&domain=3`. |
| **pairs** | The query string seen as an ordered list of (name, value) pairs rather than as text. Building an address means producing pairs and joining them. |
| **hidden input** | An invisible form field. It is how a form "carries" a value the visitor never typed: the browser sends it back on submit. This is the mechanism that stops the sort form from dropping the search. |
| **form** | The search bar, the filter sidebar, the sort dropdown, the page-size box and the jump box are five separate forms on one page. Each submits to the same address. |
| **frozen / immutable** | A value that cannot be changed after it is built. "Change" means "build a copy with one part different", which is why building a link cannot corrupt the page it was built from. |
| **`PageState`** | The one value that holds the whole address. |
| **`PARTS`** | The one table that says what the parts of the address are, in the order they are read and written. |
| **`skip`** | The one slice of the state a form is allowed to leave out of its hidden inputs, because the form prints that slice itself as visible controls. |
| **case-insensitive** | "Chesed", "chesed" and "CHESED" find the same rows. |
| **accent-insensitive** | "chesed" would also find "Chésed". **The search does not do this**, by decision. |
| **regression-proof** | Two ways of showing a refactor changed nothing: the old tests pass untouched, and the outputs (here: the addresses) are unchanged byte for byte. |

The plain words map onto the code like this:

| the code says | this document says |
|---|---|
| `PageState` | the whole address as one value |
| `PARTS`, `Part(name, read, write)` | the one table of parts, and how each is read and written |
| `pairs()`, `query_string()` | joining the parts into an address |
| `replaced(...)`, `with_page(...)` | "the same address with one thing different" |
| `PageState.from_query(request.GET)` | reading the address once, in the view |
| `list_charities(repository, state)` | the listing service now takes the whole address, not six arguments |
| `state.html` with `skip` | the one partial that writes hidden inputs |
| `EveryFormCarriesTheWholeStateTest` | the test that reads each form and says which slices it carries |
| `unaccent`, `pg_trgm` | Postgres add-ons that would make accents fold; neither is installed |

---

## 4. The story

### 4.1 The page whose address is the page

A listing page with search, filters and sorting is a small state machine that lives in the address bar. Somebody types a word, ticks two domains, picks "best rated", goes to page two — and then copies the address and sends it to a friend who is looking for exactly that. The friend opens it and sees the same thing. That is what UC-03's constraint asks for — everything in URL parameters, full page loads so Back works —
and it is why every control on this page is a *form that submits to the address* rather than a piece of
JavaScript that hides rows.

The consequence is that the page has five forms, and **every one of them must carry the parts of the address it does not own.** The sort dropdown submits a `sort` value, so it must also carry the search term, the filters and the page size — as invisible fields — or choosing a sort throws them away.

### 4.2 What was wrong, in one sentence

The parts were stored in three places, joined by hand, and remembered by three separate HTML snippets that each form had to include correctly.

That is three chances to be wrong, and the mistake is invisible:

- **The order could drift.** `services.py` joined search-pairs, then filters, then sort. If a later change joined them differently, two addresses describing the *same* listing would be different text — same page, different link, and no test would notice because both work.
- **A form could forget an include.** The sort form included `search_state.html` and `filter_state.html`. A sixth form added later would need to know which two of three to include. Forgetting one does not error; it silently narrows the page on submit.
- **The third copy of the same line.** `query_string()` — three lines of `urlencode(...)` — existed in `filters.py`, `sorting.py` and `search.py`, identical apart from their argument. Three copies of a line is three places to change it.

### 4.3 What the fix looks like

One module owns the plumbing:

```python
PARTS: tuple[Part, ...] = (
    Part("search", search_from_query, search_pairs),
    Part("filters", filters_from_query, filter_pairs),
    Part("sort", sort_from_query, sort_pairs),
)
```

Each `Part` says three things: what the slice is called (which is also the field name on `PageState`), how to read it from an address, and how to write it back. Because the field name and the part name are the same string, **a part cannot be added without saying where it is stored** — the structural test in `test_page_state.py` checks exactly that.

Reading the whole address is then one call, and every part is still read by its own module, so each feature keeps its own idea of what a junk value means:

```python
    @classmethod
    def from_query(cls, query) -> PageState:
        values = {part.name: part.read(query) for part in PARTS}
        return cls(
            **values,
            page=_positive_int(query.get(PAGE_PARAMETER)) or 1,
            page_size=clamp_page_size(_positive_int(query.get(PAGE_SIZE_PARAMETER))),
        )
```

Writing is the mirror image, with the page window first so every page link spells the address the same way:

```python
    def query_string(self, skip: tuple[str, ...] = (), **window: int) -> str:
        pairs = tuple(window.items()) + self.pairs(skip=skip)
        return urlencode(pairs)
```

And the templates lose three partials in favour of one:

```html
{% for name, pairs in page.state.groups %}{% if name != skip %}{% for key, value in pairs %}<input type="hidden" name="{{ key }}" value="{{ value }}">
{% endfor %}{% endif %}{% endfor %}
```

The three feature modules keep every rule they had — clamping, mechanism/direction pairing, term matching, the option lists — and lose only the duplicated `query_string`. `Page` (the object a rendered page carries) now holds a single `state` instead of three pair-bundles, and its page links are built by asking the state.

### 4.4 Why "no behaviour change" is a claim and not a wish

Refactors of this size are usually followed by a bug hunt. Two facts make this one checkable:

1. **Every existing listing test passed without being edited.** The tests were already written against the page's behaviour (what appears on the page), not against the internals.
2. **The addresses the tests pin are byte-identical.** Several tests assert exact query strings — `test_the_window_goes_first` asserts a full address — so a drift in the order or spelling of any part would fail. Nothing about the order changed; the order simply became explicit.

The one new test is the interesting part, because it addresses the failure mode the old structure allowed:

```python
class EveryFormCarriesTheWholeStateTest(TestCase):
    """D-068 (audit S1): no form on the page can drop a slice it does not own.
    ...
    """
```

It requests the listing with a search term, a filter, a sort and a one-row page size, finds every `<form>` in the HTML, and then asserts, per form, which hidden fields it carries: the search form has `domain` and `sort` but not `q`; the filter form has `q` and `sort` but not `domain`; the sort form has `q` and `domain`; the window forms have all three. A future form that forgets the partial fails a test that names it.

### 4.5 The accent decision

The audit left a question open (Q4): should the search fold accents, so that "chesed" finds "Chésed"?

D-069 answers **no**, and the reasoning is worth reading as a product decision rather than a technical one:

- the design document asks for **case**-insensitivity, not accent-insensitivity;
- people rarely type accents, so the person who types "chesed" is the normal case and the person who types "Chésed" is the unusual one;
- the fix costs a Postgres extension (`unaccent`) plus a migration, and it would **defeat the name index** — Postgres cannot treat `unaccent()` as an immutable expression, so the index the listing relies on would stop being used;
- if accented names ever actually arrive in real data, the cheaper fix is at the *write* side (normalise the name when it is saved) rather than at the read side, because that keeps one spelling in the database.

The decision also comes with a check that both **search modes** fold case — the plain "contains" mode and the whole-word mode, which use different database operators. That second half is a real gap that was closed: a test that only covered "contains" would have said nothing about whole-word matching.

`docs/NOTES.md` records the check as a measurement rather than an opinion: 200 seeded charities, "Chesed"/"chesed"/"CHESED" each returning the same 29 rows, in both modes. Section 5.2 is about what that measurement does and does not prove.

### 4.6 What settled, in one sentence

The listing's whole address is one value built by one table in one order, every form carries everything except the slice it owns, the duplicated helpers are gone, and the search is decided to fold case and not accents — with the tests that pin each of those.

---

## 5. Contradictions — places where documents disagree

### 5.1 The deferral was reversed the same day, by a reason other than its own trigger

D-067 (in PR #20) decided *not* to collapse the three state modules, and recorded the **trigger** that would reopen it:

> The trigger to revisit: a fourth URL state (a date range, or a saved search) or the first "form forgot an include" bug, whichever comes first.

Neither happened. No fourth state was added, and no form-forgot-an-include bug was found. This PR does it anyway, and D-067 is marked *Superseded by D-068* with a new reason:

> the trigger fired: it was the last open audit finding and the per-form test now covers the risk this entry was waiting on

That is honest bookkeeping — the old entry is kept and marked, not rewritten — but the sentence "the trigger fired" is not accurate: a new reason appeared (it was the last open finding, and the new per-form test makes the change safe) and *that* is what fired. The distinction matters because D-067's whole point was that a deferral with a recorded trigger is a decision; if triggers can be reinterpreted two commits later, the habit is worth less than it looks. Nothing is broken. It is a record-keeping slip in a file whose value is precise record-keeping, and one sentence in D-068 would fix it.

### 5.2 The accent decision's evidence is about case, not accents

D-069 and `docs/NOTES.md` N-note say the check was run against the dev database: 200 charities, three spellings, 29 rows each, both modes.

That is a good check of the thing the document requires — **case**-insensitivity — and of the whole-word operator in particular. It says nothing about accents, because the seeded data has no accented names in it. So the decision "accents are not folded" rests on judgement ("nobody types accents") plus a reading of the document ("case-insensitivity only"), not on a measurement. That is a legitimate basis for a product call; it is just worth being clear that the two halves of the entry have different evidence behind them.

A related fact recorded in `docs/NOTES.md` (N12) makes the dev check weaker than it sounds: the seeded database has 200 charities but only 61 distinct names, so "29 rows" is a number over a fairly repetitive sample. None of this changes the decision; it tells you how much weight the measurement deserves.

### 5.3 The `skip` is a string in the template and a tuple in Python

The Python side takes a tuple of names:

```python
    def pairs(self, skip: tuple[str, ...] = ()) -> tuple[tuple[str, object], ...]:
```

The template side compares one name to whatever the form passed:

```html
{% for name, pairs in page.state.groups %}{% if name != skip %}...
```

and every current caller passes a single string (`{% include "charities/state.html" with skip="filters" %}`). That works. But if a form ever owns two slices and passes `skip="filters,sort"`, the comparison is against the literal text `"filters,sort"`, which equals no part name — so **nothing is skipped and the state is written twice**, with duplicate hidden fields. The failure is silent and looks like success.

Not a defect today (every form owns exactly one slice), and cheap to make robust: either pass a list and compare membership, or have the template pass two parameters. Worth naming because the whole point of this PR is that forgetting should be visible, and this is one place where a plausible mistake would not be.

### 5.4 The README's module map is now stale in three lines

This PR adds a correct `state.py` bullet, and then leaves three bullets describing the modules it just emptied:

> `filters.py` — … and rebuilding the query string a page link carries.
> `sorting.py` — … and the same three query-string helpers.
> `search.py` — … and the same three helpers again.

`query_string()` was deleted from all three modules in this PR (it is the duplicated third copy the PR removes). They now have two helpers each — `from_query` and `query_pairs` — and rebuilding the query string is `state.py`'s job. The README was corrected in PR #20 (DOC2) for exactly this kind of drift, so this is the same finding reappearing one commit later. Small, and a one-line fix per bullet.

---

## 6. Departures from the design document

### 6.D1 One `PageState` replaces the document's `list_charities(...)` signature

- **Document says:** §6.2.6 and UC-03 name the listing service as
  `charities.services.list_charities(filters, sort, page, page_size, search)` — five separate arguments.
- **Code does:** `list_charities(repository, state)` — one `PageState` carrying all five.
- **Why:** with five arguments, every caller could pass them in a different combination and only some combinations were meaningful (a page without its page size, a sort without its search). One value cannot be partially passed, and it is the same value the URL decodes to.
- **Judged:** D-068 (Active). The behaviour is identical; the shape changed.
- **Reversible in:** a wrapper function that builds a `PageState` from the five arguments — ten lines, no behaviour to restore.

### 6.D2 Page-size bounds and page counting moved out of the service

- **Document says:** §6.2.3 gives the listing's page and page size parameters, with no statement about where their bounds live.
- **Code does:** `DEFAULT_PAGE_SIZE`, `MAX_PAGE_SIZE`, `clamp_page_size` and `page_count` live in `state.py`, next to the address they belong to, and `PageState` clamps on construction.
- **Why:** a page size is part of the address, so it belongs with the address; clamping at construction means an out-of-range value cannot reach the service at all, from a hand-written URL or a stray call.
- **Judged:** D-068. Not recorded as its own decision — it is the same one.
- **Reversible in:** moving four names back into `services.py`.

### 6.D3 Accents are not folded, and no Postgres extension is added

- **Document says:** §6.2.6 and UC-03 ask for a **case**-insensitive search. Nothing in the document mentions accents.
- **Code does:** case is folded (both modes); accents are not; neither `unaccent` nor `pg_trgm` is installed.
- **Why:** see 4.5. The extension would cost a migration and defeat the name index.
- **Judged:** D-069 (Active), decided by the CEO on task #42, closing the audit's Q4.
- **Reversible in:** a migration plus a settings change plus a change to the lookup; the write-side alternative (normalise names on save) is cheaper and is named in D-069 as the preferred route if accented data ever appears.

### 6.D4 A new form defaults to carrying everything

- **Document says:** "everything is stored in URL parameters" and "full page loads (so back works)"
  (UC-03, Implementation Constraints). It says nothing about how the state is written into a form.
- **Code does:** the state partial writes all three slices unless the form names one to skip. So a form that owns *no* slice (page size, page number, jump) writes everything, and a form that owns one slice names it.
- **Why:** the default has to be the safe one. A forgotten parameter then over-carries (harmless: a hidden field the form also prints visibly just gets replaced on submit) instead of under-carrying (which silently changes the list).
- **Judged:** D-068. A mechanism, not a departure — listed because a reviewer will notice the default is "everything" and wonder why.
- **Reversible in:** inverting the default would break the guarantee, so: do not.

### Not departures, though they may look like it

- **The order of parameters in the address.** Search, then filters, then sort, with the page window first. §6.2.4–6 name the parameters, not their order; the order is now stated in one table (D-046's order, made explicit).
- **`Page` keeping `number`, `page_size` and `sort` as properties.** The template still says `page.number`; those are now read from `page.state`. No template changed for it.
- **The three feature modules surviving.** D-068 keeps `filters.py`, `sorting.py` and `search.py` with their own rules; the PR removes only the duplicated joining.
- **`page` is clamped to at least 1 on construction.** A junk `page=0` meant page 1 before this PR too.

---

### 5.5 The decision's line counts are about the code only

D-068 justifies doing the refactor partly with arithmetic: "it is a deletion rather than an
addition (218 lines added, 226 removed, excluding this entry and the new tests)". GitHub's header for
this PR says **+582 / −232**. Both are true; they count different things. The decision's numbers are the
production code and templates without the new decision entry and without `test_page_state.py` (162
lines) and the new form test (~70 lines). A reviewer comparing the two numbers will think something is
missing; nothing is.

---

## 7. Reading order

| # | file | why it changed | size |
|---|---|---|---|
| 1 | `apps/charities/state.py` | the new module: `PageState`, `PARTS`, the window | +159 |
| 2 | `apps/charities/services.py` | `Page` holds one state; `list_charities` takes it | +55, −76 |
| 3 | `apps/charities/views.py` | the address is read once | +13, −33 |
| 4 | `apps/charities/templates/charities/state.html` | one partial, one `skip` | +12, −5 |
| 5 | `…/filter_state.html`, `…/search_state.html`, `…/sort_state.html` | deleted | −20 |
| 6 | `…/filters.html`, `…/search.html`, `…/sort.html` | each names the slice it owns | +3, −6 |
| 7 | `apps/charities/filters.py`, `sorting.py`, `search.py` | the duplicate `query_string` deleted | −18 |
| 8 | `tests/unit/test_page_state.py` | the new value, tested on its own | +162 |
| 9 | `tests/unit/test_template_contract.py` | the per-form guarantee | +72 |
| 10 | `tests/unit/test_search_repository.py` | whole-word case test (D-069) | +8 |
| 11 | `tests/unit/test_services.py`, `test_filter_service.py`, `test_search.py`, `test_sorting.py` | call sites follow the new signature | +96, −96 |
| 12 | `docs/DECISIONS.md` | D-067 superseded; D-068 and D-069 | +24, −1 |
| 13 | `docs/AUDIT-2026-11-17.md` | the ledger's last three rows settled | +6, −3 |
| 14 | `docs/NOTES.md` | the search check, written down | +8 |
| 15 | `README.md` | a `state.py` bullet | +3, −2 |

---

## 8. The files, one at a time

### 8.1 `apps/charities/state.py` — the new module (+159)

The module docstring is the design, stated before any code:

> `PageState` is that whole address as one immutable value. The three feature modules still own their
> own *rules* (clamping, mechanism pairing, term matching); this module owns the **plumbing that joins
> them** — one list of parts, one reading order, one writing order, one string.

Four pieces, in order of how much they matter.

**The table.** One entry per slice of the address, each saying what it is called, how to read it, and
how to write it:

```python
@dataclass(frozen=True)
class Part:
    name: str
    read: Callable[[Any], Any]
    write: Callable[[Any], tuple[tuple[str, object], ...]]


PARTS: tuple[Part, ...] = (
    Part("search", search_from_query, search_pairs),
    Part("filters", filters_from_query, filter_pairs),
    Part("sort", sort_from_query, sort_pairs),
)
```

`name` is doing double duty on purpose, and the docstring says so: it is the template's word for "leave
this slice out" *and* the field name on `PageState`, "so a part cannot be added without saying where it
is stored".

**The value.** Frozen, with the window clamped as it is built:

```python
    def __post_init__(self) -> None:
        object.__setattr__(self, "page", max(1, self.page))
        object.__setattr__(self, "page_size", clamp_page_size(self.page_size))
```

`object.__setattr__` is the standard trick for a frozen dataclass that needs to normalise its own
fields on construction. The effect is the sentence in the docstring: "the state a caller holds is
always a state the server is willing to serve."

**Reading and writing.** `from_query` reads each part through its own module, so each feature keeps its
own rule about junk; `pairs`/`query_string` write them back in the table's order, with the window first:

```python
    def query_string(self, skip: tuple[str, ...] = (), **window: int) -> str:
        """This state as a query string, with an optional page/page_size window.

        The window goes first and the result set after it, in the one order
        `PARTS` states — the order every link on the page therefore spells the
        same way, so two addresses that describe the same listing are identical
        text (audit S7).
        """
        pairs = tuple(window.items()) + self.pairs(skip=skip)
        return urlencode(pairs)
```

**Changing it.** Two ways, both returning copies: `replaced(**changes)` and `with_page(number)`. There is
no in-place mutation anywhere, which is what makes "build a link from the current state" safe.

The module also now owns `DEFAULT_PAGE_SIZE`, `MAX_PAGE_SIZE`, `clamp_page_size` and `page_count`, which
used to live in `services.py` — the comment says why: "a page size is part of the address, not a rule of
the query."

### 8.2 `apps/charities/services.py` — `Page` holds one state (+55, −76)

The class that a rendered page carries used to hold the search pairs and the filter pairs as two
separate bundles and join them by hand in a private helper:

```python
-    def _state_query(self, *, include_filters: bool = True, **parts: int) -> str:
-        """A query string of `parts`, followed by the search, filters and sort."""
-        base = urlencode(parts)
-        pairs = self.filter_pairs if include_filters else ()
-        state = urlencode(self.search_pairs + pairs + self.sort_pairs)
-        return f"{base}&{state}" if state else base
```

It is replaced by one field and three properties:

```python
items: tuple[CharityCard, ...]
total: int
state: PageState = PageState()


@property
def number(self) -> int:
    return self.state.page


@property
def page_size(self) -> int:
    return self.state.page_size


@property
def sort(self) -> CharitySort:
    return self.state.sort
```

The properties are not decoration: the templates say `page.number` and `page.sort`, so keeping the names
meant **not one template had to change** for the class's internals to be replaced. Each page link is now
built by the state:

```python
    def query(self, number: int) -> str:
        """Query string for another page of this same result set."""
        return self.state.query_string(page=number, page_size=min(self.page_size, MAX_PAGE_SIZE))
```

and the "clear filters" link becomes a one-line statement of intent rather than a flag threaded through
a helper:

```python
    @property
    def clear_filters_query(self) -> str:
        """The page with its size, search and order kept, but no filters (§6.2.4)."""
        return self.state.replaced(filters=CharityFilters()).query_string(page_size=self.page_size)
```

`list_charities` loses five parameters and gains one, and its body stops assembling arguments:

```python
def list_charities(repository: CharityRepository, state: PageState | None = None) -> Page:
    state = state or PageState()
    items, total = repository.page_and_count(
        offset=(state.page - 1) * state.page_size,
        limit=state.page_size,
        filters=state.filters,
        sort=state.sort,
        search=state.search,
    )
```

The past-the-end handling is the one piece of logic that changed shape, and it changed for the better:

```python
    count = page_count(total, state.page_size)
    if state.page > count:
        # The requested page was past the end: the state is answered with the
        # last real page, and only when there are rows is a second read needed.
        state = state.with_page(count)
        if total:
            items = repository.page(...)
    return Page(items=items, total=total, state=state)
```

Before, the "requested page" and the "served page" were two separate numbers threaded through the
constructor. Now the served state *is* the state, and the page number the visitor ends up on is the one
the state says — which is also what the pagination renders, so "page 99 of 3" cannot happen.

### 8.3 `apps/charities/views.py` — the address is read once (+13, −33)

The view used to read three parts by calling three `from_query` functions, plus two ad-hoc integers, and
then pass six arguments to the service. It now reads one value:

```python
    # The whole address as one value; every form below reads its slice of it (D-068).
    state = PageState.from_query(request.GET)
```

and the one adjustment the view still makes — dropping ticked ids that name no row (D-045) — is a
`replaced` on that value:

```python
    state = state.replaced(filters=keep_known_ids(state.filters, options))
```

The local `_positive_int` helper is gone from the view (it moved into `state.py`), along with three
`from_query` imports. What remains in the render context is built from `page.state`, so the templates
render the state the page was actually served with — not the state that was asked for. That is the
subtle half of the past-the-end fix: a visitor who asks for page 99 of a three-page result sees the
sidebar and the forms describing page 3.

### 8.4 `apps/charities/templates/charities/state.html` — one partial, one `skip` (+12, −5)

The whole change from a form's point of view. Before, three partials and three includes; now one partial
and one line per form:

```html
{% for name, pairs in page.state.groups %}{% if name != skip %}{% for key, value in pairs %}<input type="hidden" name="{{ key }}" value="{{ value }}">
{% endfor %}{% endif %}{% endfor %}
```

and the partial's own comment states the rule and its default:

> A form that prints one slice itself includes this with `skip`, naming the slice it owns: …
> The default (no `skip`) writes everything, so a new form that forgets the parameter still carries the
> whole state instead of dropping two thirds of it.

The three forms that own a slice now say so, one line each:

```html
  {% include "charities/state.html" with skip="filters" %}   {# filters.html #}
  {% include "charities/state.html" with skip="search" %}    {# search.html #}
  {% include "charities/state.html" with skip="sort" %}      {# sort.html #}
```

and the two forms that own no slice (the page-size form and the jump form) include it with no argument
at all. Before, the filters form had to remember to include *two* of the three partials; a filter form
that forgot `sort_state.html` would silently reset the order on every filter change. See 5.3 for the one
sharp edge this design still has.

### 8.5 `filters.py`, `sorting.py`, `search.py` — the third copy deleted (−18)

Three identical deletions, one per module:

```python
-def query_string(filters: CharityFilters) -> str:
-    """The filter groups as a query string, so a page link can repeat them."""
-    return urlencode(query_pairs(filters))
```

`query_pairs` stays in all three — that is the module's own rule about *which* parameters name a filter,
a sort or a search. Only the joining was duplicated, and only the joining moved. Each module also drops
its `urlencode` import, which is a small proof that nothing in the module encodes anything any more.

### 8.6 `tests/unit/test_page_state.py` — the value, tested on its own (+162)

Five test classes, each naming one promise. `StructureTest` is the one that keeps the design honest:

```python
def test_every_part_is_a_field_of_the_state(self) -> None:
    """A part that names no field would read and write nothing, silently."""
    names = {field.name for field in fields(PageState)}

    self.assertEqual({part.name for part in PARTS} - names, set())


def test_the_slices_have_a_stated_order(self) -> None:
    """Search, filters, sort: the order a listing URL spells them (D-046)."""
    self.assertEqual(SKIPPABLE, ("search", "filters", "sort"))
```

`WritingTest` pins the ordering with a full literal address, so a change to the order fails with a diff
rather than a shrug:

```python
def test_the_window_goes_first(self) -> None:
    self.assertEqual(
        busy_state().query_string(page=3, page_size=10),
        "page=3&page_size=10&q=chesed&tagline=1&domain=3&min_rating=4&sort=rating&direction=desc",
    )
```

`ClampOnConstructionTest` and `ReplacedTest` cover the two invariant promises — an out-of-range state
cannot exist, and changing one part cannot change another — and `ReplacedTest`'s second test is the one
worth reading as English:

```python
    def test_the_original_is_untouched(self) -> None:
        """Links are built from a state; building one must not change it."""
```

`FromQueryTest` covers the reading side, including the round-trip: an address written from a state reads
back as the same state (`test_an_address_read_back_is_the_same_state`). That is the property UC-03's
URL-parameters constraint actually needs, tested directly rather than through a page render.

### 8.7 `tests/unit/test_template_contract.py` — the per-form guarantee (+72)

`EveryFormCarriesTheWholeStateTest`, previewed in 4.4. It finds every form by its class, then asks the
one question that matters per form:

```python
    def test_the_filter_form_keeps_the_search_and_the_order(self) -> None:
        hidden = self._hidden_names(self._forms()["filters"])

        self.assertIn("q", hidden)
        self.assertIn("sort", hidden)
        self.assertNotIn("domain", hidden, "the sidebar prints its own checkboxes")
```

Four tests, one per form plus the window forms. The `assertNotIn` half is what makes it a precise test:
a form carrying *its own* slice as a hidden field would submit both the visible control and the hidden
one, and the second would win — so "carries everything except the slice it owns" is the property, and it
is asserted from both sides.

### 8.8 `tests/unit/test_search_repository.py` — whole-word folding (+8)

```python
    def test_whole_words_is_case_insensitive_too(self) -> None:
        """Both search modes fold case; the whole-word one is a different operator."""
        Charity.objects.create(name="Lev Chessed")

        for term in ["Chessed", "chessed", "CHESSED", "cHeSsEd"]:
            with self.subTest(term=term):
                self.assertEqual(self.names(Search(term=term, whole_words=True)), ["Lev Chessed"])
```

The reason this is here rather than in the search PR: the two modes use different database operators
(the plain one is case-insensitive "contains"; the whole-word one is a regular-expression match), so a
test written for the first says nothing about the second. `subTest` names the failing spelling instead
of collapsing four checks into one.

### 8.9 The four test files whose call sites followed (96 changed lines)

`test_services.py`, `test_filter_service.py`, `test_search.py` and `test_sorting.py` all call
`list_charities` or build addresses. Every change is mechanical:

```python
-        page = list_charities(self.repository, page=2, page_size=10)
+        page = list_charities(self.repository, PageState(page=2, page_size=10))
```

and, in the three feature tests, the duplicated `query_string` assertions now go through the state:

```python
+self.assertEqual(PageState(sort=sort).query_string(), "sort=rating&direction=desc")
```

The assertions themselves are unchanged. That is the signature-change churn that a service-wide
refactor always produces, and it is worth knowing that no test *behaviour* moved: only how an address is
built in the test.

### 8.10 `docs/DECISIONS.md` — a reversal done in the open (+24, −1)

D-067 keeps its text and gains one changed line:

```
- Status: Active (deliberate deferral, with the trigger recorded)
+ Status: Superseded by D-068 on 2026-11-17 (the trigger fired: it was the last open audit finding
+   and the per-form test now covers the risk this entry was waiting on)
```

D-068 then states the new arrangement, and its "Why" carries the evidence a reviewer wants: "Every
existing page test passed unchanged, and the addresses the tests pin stayed byte-identical — the two
things that would have made this refactor unsafe." See 5.1 for the one sentence in that status line that
is not quite true, and 5.5 for its line counts.

D-069 is short and reads as a product decision: the CEO's call, the reasoning, the measurement, and the
cheaper write-side alternative if accented names ever appear.

### 8.11 `docs/AUDIT-2026-11-17.md` — the last three rows — (+6, −3)

Three ledger rows change in this PR:

- S1/S7 — from *"Filed (#39): deliberate deferral"* to *"Fixed after all (D-068): one `PageState` value,
  one `PARTS` order, one partial with `skip`, plus a per-form test that a slice cannot be dropped"*;
- DOC4/Q1 — from *"Filed (#40): needs a human answer"* to *"Out of scope, decided (comtai#40): the root
  `index.html`/`CNAME` question is about hosting, not about the Django app"*;
- Q4 — from *"Filed (#42)"* to *"Answered: accents are not folded (D-069). Case-insensitivity verified
  live in both search modes"*.

With that, the ledger has no "filed" rows left at all: one row is out of scope (M1/M2/M7), one is an
accepted risk with a named closer (SEC3), one is out of scope by decision (DOC4/Q1), and everything else
is fixed. The audit is closed.

### 8.12 `docs/NOTES.md` — the check, written down (+8)

A short note titled "Search checked against the dev database", which says what was run rather than what
was believed: 200 seeded charities, three spellings, 29 rows each, both modes; and that `unaccent` 1.1
and `pg_trgm` 1.6 are available on the dev cluster and neither is installed. That last sentence is the
useful kind of detail — it tells the next person that choosing the extension is a settings change, not a
provisioning project.

### 8.13 `README.md` — the new module (+3, −2)

One added bullet for `state.py` and one adjusted `services.py` bullet ("the listing rules (page
clamping, page size, page+count as one snapshot)" — "order" removed, because the order now belongs to the
state). Three neighbouring bullets were left describing a `query_string` that no longer exists — see
5.4.

---

## 9. The tests

Read the names as sentences. This PR's tests are unusual in that the *new* ones are few and the *old*
ones are the proof.

**The old tests, untouched.** Every page test from the listing, filter, sort, search and pagination work
passes without an edit. Not one assertion about what a visitor sees was changed. That is the first half
of the "no behaviour change" claim, and it is worth noticing that nothing in the diff touches them.

**The old tests, edited mechanically.** The four unit files that *build* addresses (`test_services.py`,
`test_filter_service.py`, `test_search.py`, `test_sorting.py`) changed only where they construct a
listing request:

```python
-        page = list_charities(self.repository, page=3, page_size=10)
+        page = list_charities(self.repository, PageState(page=3, page_size=10))
```

**`test_page_state.py` — the value's own tests** (five classes, 16 tests):

- `StructureTest`: `test_every_part_is_a_field_of_the_state`, `test_the_skippable_names_are_the_parts`,
  `test_the_slices_have_a_stated_order` — the three structural promises, each one a way the design could
  rot silently.
- `FromQueryTest`: `test_an_empty_address_is_the_default_view`,
  `test_every_part_is_read_through_its_own_module`, `test_junk_in_the_window_is_ignored_not_fatal`,
  `test_an_enormous_page_size_is_capped`.
- `WritingTest`: `test_the_pairs_follow_the_stated_order`, `test_the_window_goes_first`,
  `test_skipping_a_part_drops_exactly_that_part`, `test_the_default_state_writes_no_parameters`,
  `test_an_address_read_back_is_the_same_state`.
- `ClampOnConstructionTest`: `test_page_one_is_the_floor`, `test_page_size_is_bounded_both_ways`.
- `ReplacedTest`: `test_replacing_a_part_keeps_the_rest`, `test_the_original_is_untouched`.

**`EveryFormCarriesTheWholeStateTest`** (four tests) — the one that makes the old failure mode
impossible: `test_the_search_form_keeps_the_filters_and_the_order`,
`test_the_filter_form_keeps_the_search_and_the_order`,
`test_the_sort_form_keeps_the_search_and_the_filters`, `test_the_window_forms_carry_all_three`.

**`test_whole_words_is_case_insensitive_too`** — the D-069 half that was missing: whole-word search is a
different database operator, so case-folding had to be tested for it separately.

---

## 10. The audit

The Dilbert test run against the finished document, and the two-layer check.

**Where he would have fallen off, and what was fixed:**

- **"URL state"** is jargon he would never say. Section 1 avoids it entirely for the first five
  paragraphs — it talks about *the address* and what it means, then introduces the term as a name for
  that. The glossary row says "everything the address bar says about what you are looking at". — fixed.
- **"query string" and "hidden input"** are the two mechanisms the whole PR turns on, so both are
  glossary rows and both are explained by *what they do*: a hidden input is "how a form carries a value
  the visitor never typed". The consequence (the sort form not dropping the search) is stated three
  times, in three different words. — fixed.
- **"frozen / immutable"** would be lost on him. The glossary gives the consequence instead of the
  definition: *"change means build a copy with one part different, which is why building a link cannot
  corrupt the page it was built from"*. — fixed.
- **"refactor"** never appears without an explanation. Section 1 says it in the same breath as the proof
  ("no behaviour change, and the PR proves it two ways"). — checked.
- **The three-partials-to-one-partial change** is the most concrete thing in the PR, so it is the
  headline in section 1 with the `{% include %}` line shown as the before/after, and 8.4 repeats it with
  the three real include lines. — checked.
- **"case-insensitive" vs "accent-insensitive"** are easy to conflate and the decision depends on the
  difference. Both are glossary rows, adjacent, with "the search does not do this, by decision" on the
  second. — fixed.
- **"unaccent defeats the index"** is a Postgres subtlety that could lose him. 4.5 says it in plain
  words ("Postgres cannot treat `unaccent()` as an immutable expression, so the index the listing relies
  on would stop being used") and does not ask him to know what an index is — section 4.2 of PR #18's
  document is where that word is defined for this series, and here it is used only as "the thing that
  makes the search fast". — checked.
- **One sentence in 4.2 had three clauses** ("three modules, three partials, one hand-written order"),
  which is the point, so it was kept as a list and then written again as prose. — fixed.
- **Arithmetic checked:** three modules, three partials, three copies of `query_string`, `skip` used by
  three of five forms, 200 charities / 61 distinct names / 29 rows, `+582 −232` versus D-068's
  `218/226`, and 16 tests in `test_page_state.py`. Every number appears in the diff or in the docs.

**Every code box has an English sentence directly above it.** Walked: the `PARTS` table, `from_query`,
`query_string`, the state partial and the three include lines, the deleted `query_string`, `_state_query`
before/after, the three `Page` properties, `Page.query`, `clear_filters_query`, `list_charities`'s new
signature and its past-the-end block, the view's two lines, the `Part` dataclass, `__post_init__`, the
three structural tests, `test_the_window_goes_first`, `test_the_original_is_untouched`,
`test_the_filter_form_keeps_the_search_and_the_order`, the whole-word test, the call-site churn, the
D-067 status change, and the ledger rows. All covered.

**The two-layer check.**

- *Delete every code box.* The document still contains: the address-as-the-page opening and the promise
  UC-03 makes; the three ways the old structure could fail silently; the fix explained as "one value, one
  table, one partial whose default is everything"; the two proofs that nothing changed; the accent
  decision with its product reasoning; four contradictions; four departures; a reading order; thirteen
  file sections in plain English; and the tests read as sentences. It stands.
- *Read only the code boxes.* The whole change is visible: the `Part` table, the state's construction and
  clamping, reading and writing, the three deleted `query_string` functions, the one partial with `skip`,
  the three forms that name their slice, `Page`'s new single field, `list_charities`'s new signature and
  its past-the-end handling, the view reading once, and the new tests including the full literal address.
  A reviewer could approve from the boxes. It stands.

**Where he still cannot follow, and why that is acceptable:** `object.__setattr__` in `__post_init__`. He
does not need to: the sentence above the box says what it *achieves* ("a frozen dataclass that needs to
normalise its own fields on construction… the state a caller holds is always a state the server is
willing to serve"). The engineer gets the mechanism; he gets the guarantee.

**Bottom line:** the document can be reviewed from, and it explains itself. It does not grade. The
judgement calls it hands back to you are: whether a reversal two commits after its own deferral is
recorded accurately enough (5.1), how much weight the accent measurement deserves (5.2), the `skip`
string-versus-tuple edge (5.3), and three stale README bullets (5.4).
