# PR 17 — "Search": the charity listing learns to be searched

- **PR:** [#17](https://github.com/MaaserMart/MaaserMart/pull/17) — `search` into `full_charity_listing`
- **Size:** 18 files, 970 added lines, 30 removed
- **Position in the stack:** first of five. Nothing depends on it being merged first except the four PRs above it.
- **Written for:** someone reviewing this change without opening the diff, and someone non-technical who wants to know what it does.
- **Decision record:** D-054 (the search), D-069 (case but not accents). Notes N9–N12.

---

## 1. Read this part even if you read nothing else

MaaserMart lists charities for people who want to give charity money. The listing page is a long
shelf of charity cards. Three controls already decide which cards are on the shelf: a **filter
sidebar** on the left (only charities that work in food, only ones with a good rating, and so on), a
**sort dropdown** (alphabetical, most popular, and so on), and the page number at the bottom.

This change adds a fourth control: a **search box** across the top. A visitor types a word, presses
Search, and only charities whose name contains that word are shown.

If that were all, this would be a small feature. It is not, and the reason is worth understanding
because it is what most of the 970 lines are about.

**Every control on this page writes its choice into the web address, and re-reads it from the
address when the page comes back.** That is how the page remembers what you chose, and it is why
pressing Back works. A control does not get to keep a secret: if the address does not say it, the
next page load has forgotten it.

So the moment a search exists, all the older controls become dangerous. Suppose a visitor types
"chessed" and then clicks Sort A→Z. The sort control builds a new address holding the sort choice.
If it does not also carry the typed word, the address arrives at the server with no search in it,
and the shelf comes back with every charity on it. The visitor's own action silently deleted what
they typed. They will conclude the site ignored their search, and they will be right.

**The whole change is one idea: a new word that has to travel with the whole page.** The search box
adds the word; the rest of the work is teaching every other control — sort, filters, page links, the
page-size box, the "jump to page" box, the Clear-filters link — to carry it along. One of them
forgetting is the failure this PR exists to prevent.

Everything below is the same idea in more detail.

---

## 2. How to read this file

Three rules make this document work for both kinds of reader.

1. **Read the glossary first** (section 3). Every word this document uses is defined there, before
   it is used. If you meet a word that is not in it, that is a defect in this document, not in you.
2. **Every grey code box is optional.** The sentence directly above each box says the same thing in
   English. Skip every box and you lose no story — the boxes are there for the engineer, who cannot
   review code they cannot see.
3. **Every file section opens with one bold summary line.** Reading only those summary lines gives
   you the whole change in ten breathless sentences.

This document explains. It does not grade: no findings, no verdict. It will tell you where the code
departs from the customer's written design, and let you decide what to do about it.

---

## 3. The glossary

Ten words, defined by what they do, not by what they are called in the code.

| word | what it means here |
|---|---|
| **charity** | The thing the site lists. Every charity has a **name** ("Lev Chessed") and a **tagline** (one line of description, like "Interest-free loans"). |
| **the listing** | The page that shows charity cards. Everything in this PR happens on that one page. |
| **the address** | The web address in the browser's bar. It has two parts: the page (`/charity/`), and everything after a `?`, which is how a page is told what to show. |
| **a parameter** | One named value in the address, like `q=chessed` or `page=2`. The name is on the left, the value on the right. |
| **the term** | What the visitor typed into the search box. This change stores it under the parameter name `q`, short for query. |
| **a form** | A block of the page that collects values and sends them to the server. Every control on this page is one: the search box, the sort dropdown, the filter sidebar. "Sending a form" here means the browser builds an address from the values and asks for that page. |
| **a hidden value** | A value inside a form that the visitor never sees. It exists only so that sending the form carries something along. This is the mechanism that stops a sort from deleting a search. |
| **match** | What counts as the search finding a charity. By default the typed letters are looked for **anywhere** inside the name, so "chess" finds "Lev Chessed". With the **whole words** option on, the typed text has to appear as complete words, so "chess" finds "Chess Club" but not "Lev Chessed". |
| **case-insensitive** | Capital letters are ignored, so "chessed", "CHESSED" and "Chessed" all find the same charities. |
| **the page state** | The sum of everything the address says about the current view: the term, the filters, the order, and which page you are on. Every control sends the whole state, so nothing is lost by accident. |

The plain words above map onto the code like this. Use this table to go from this document back to
the source.

| the code says | this document says |
|---|---|
| `Search` | the search slip — one small object holding the term and the two switches |
| `SearchForm` | the search bar, worded and ready to draw |
| `icontains` | "find those letters anywhere" |
| `iregex`, `\y` | "find those letters as whole words" |
| `Q` | one condition handed to the database query |
| `query_pairs`, `search_pairs` | the search written back out as (name, value) pairs, for a link or a hidden box |
| `Page` | one screenful of results, plus every link that belongs to it |
| `is_empty`, `is_active` | nothing typed / something typed |

---

## 4. The story

### What the page does all day

1. A visitor asks for `/charity/`. There is nothing after the `?`, so the server assumes: no search,
   no filters, alphabetical order, page 1, twenty-five cards.
2. The server asks the database for that screenful and gets back a list of charity cards, plus a
   count of how many charities matched at all.
3. The server builds the page: the search bar, the filter sidebar, the sort dropdown, the cards, the
   page links. Every link it builds has the current page state written into it, so that clicking a
   page link keeps everything else the visitor chose.
4. The visitor changes something. The browser sends the whole page state back as one address, the
   server starts again at step 1, and this time the address arrives carrying choices.

That loop is the entire design of this page. There is no stored session, no cookie, no JavaScript
required. The address *is* the memory.

### What was missing, and the trap in adding it

The design document's §6.2.6 asks for a search bar below the sort section: the visitor types, presses
submit, matches are shown, page 1 of the results is shown, "and filters and sort remain on".

That last clause is the trap. It is easy to write a search box that works when used alone. It is
easy, too, for it to quietly break the other way round: the search box would keep the filters and
the sort, but the sort and filter forms would not keep the search, because they were written before
the search existed and know nothing about it.

The story with a name:

> Devorah wants to give to a *gemach* (a free-loan fund). She types `chessed` into the search box
> and presses Search. The page shows six matching charities. She then clicks the sort dropdown and
> picks A→Z, because she wants them alphabetical. The page comes back showing **two hundred**
> charities, alphabetical. Her search is gone.
>
> From her side, the site forgot. From the code's side, nothing forgot anything: the sort form sent
> the sort, the page size and the filters — the three things it was written to send — and the search
> had never been added to that list. There is no error and no warning. The address simply no longer
> mentions the search.

### The cost, stated plainly

- **A visitor is misled about what the site found.** They will believe the search failed and stop
  using it, which is the one thing a search box must not teach.
- **Every control has the same failure inside it.** Sort, filters, page size, jump-to-page,
  next/previous page, Clear filters. Six places, each independently capable of dropping the term,
  each invisible until someone tries that exact combination.
- **It cannot be fixed later by patching one place.** If each control is taught separately, the
  seventh control added next year will forget too. The fix has to be a rule, not six patches.

### The fix, in one sentence

**The search becomes part of the page state, and the page state is the only thing any control
sends.** Concretely, in this PR:

1. A new file, `apps/charities/search.py`, knows everything about the search: its parameter name,
   its two switches, how the typed text is matched, and how to write itself back out as
   (name, value) pairs.
2. The page state (`Page`, in `services.py`) gains one field holding those pairs, so every link the
   page builds — next page, previous page, clear filters — carries the search with no per-link work.
3. The repository (`repositories.py`) turns the term into one condition handed to the database, the
   same way the filter groups are conditions.
4. The view (`views.py`) reads the term out of the address and passes it to the service.
5. Five templates learn to include one small new partial (`search_state.html`), which is the search
   written out as hidden values. That partial is the whole reason a sort no longer deletes a search.

The consequences, listed:

- **Turned on:** searching by name, with two advanced options — whole words only, and searching the
  tagline as well as the name.
- **Combines with:** the filters (searching inside a filtered set) and the sort (sorting the search
  results), because all three are conditions on the same query and all three ride in the address.
- **Not turned on:** searching by some other column (domain names, locations), live results as you
  type, accent folding ("chesed" will not find "Chésed"), and any database index to make it fast.
  The last two are written down in `docs/NOTES.md` as N9 and N10 rather than quietly left.

---

## 5. Contradictions

There is one place where something this change *says about itself* does not match the customer's
document, and one place where an earlier reading of this file got it wrong. Neither is a bug in the
code, and both are worth knowing before you read further.

**5.1 — A code comment cites UC-03; here is the check that the rule really is there.**

`apps/charities/search.py:96` says:

```python
        """The Django lookup that matches the term, from the advanced options.

        Both are case-insensitive, which UC-03 requires. A whole-word match is a
        regular expression because a word boundary is not a `contains` test; the
        escaped term is matched as one contiguous piece of text, so a multi-word
        term has to appear as typed rather than as scattered words.
        """
```

**Correction — this citation checks out, and an earlier draft of this file said otherwise.** UC-03 is
§8.5, and its body contains a table whose last row is the requirement list. Quoted from the document:

> **Implementation Constraints** — Full page loads (so back works), everything is stored in URL
> parameters, checks only for published charities, uses Django's annotate, parameters are clamped,
> **case-insensitive search**.

So "which UC-03 requires" and D-054's "UC-03's 'case-insensitive search'" are both correct, and the
behaviour they name is tested (`tests/unit/test_search_repository.py` — the plain and the whole-word
modes).

Why the earlier draft got this wrong, and why it is worth telling you: the document's §8.5 appears twice
— once in the table of contents at the front, where it is a bare heading followed immediately by §8.6,
and once as the actual use case, some pages later. Reading the table of contents looks exactly like
reading a section with no text under it. **If you are checking this yourself, search the document for
"case-insensitive" rather than trusting the section number.**

The same constraint list is worth holding on to for the rest of this stack, because two of its other
items are not honoured yet: "checks only for published charities" is wired but switched off in every
view (D-042, and see PR #20's section 5.6), and the use case's step 2 says "by default in no particular
order" while the listing defaults to alphabetical A→Z (D-048).

**5.2 — The design document names the shape of one service argument, and the code uses a different
shape.**

§6.2.6 says the service "takes search, a dict, holding the term and advanced options". The code takes
a `Search` object — a small frozen dataclass with a term and two switches — everywhere that dict
would go. See section 8.2 and departure **D1** below.

This is a deliberate, recorded departure rather than a disagreement to arbitrate: D-054 decides the
shape, and the reason is that the search is read by four places (the query, the bar, the links, the
hidden boxes), and a bare dict would let any of them invent a key. It is listed here so that a
reviewer comparing code to document finds the difference already explained rather than wondering.

---

## 6. Departures from the design document

Asked for explicitly, and worth reading even if you skip the file-by-file detail. Each entry says
what the document asks for, what the code does instead, why, and how it could be undone.

### D1 — The search is an object, not the dict §6.2.6 names

**The document says** (`§6.2.6 — Service functions`):

> `charities.services.list_charities(filters, sort, page, page_size, search)`, which takes search, a
> dict, holding the term and advanced options.

**The code does** pass a `Search` object in exactly that position, and so does the repository
(`apps/charities/repositories.py:93`, `apps/charities/services.py:170`).

**Why:** the term and the two switches are read in four places — the database query, the search bar
the visitor sees, every page link, and every other form on the page. With a dict, each of those four
places would spell the keys itself; one typo would be a silently ignored option, not an error. A
frozen object with named fields makes the fourth reader fail loudly instead.

**Judged:** a departure from a service signature the document states literally, authorised by D-054,
and cheap to reverse — the object is built from the address in one function
(`apps/charities/search.py:110`), so a dict in front of it is a two-line adapter if the customer ever
insists.

**Reversible in:** one adapter function; the four readers do not change.

### D2 — The document promises an index on the search column; this PR ships none

**The document says** (§5's non-functional table, the scalability row):

> PostgreSQL indexes on the list/filter/search columns; paginated queries

**The code does** no indexing for search at all. A search is a `contains` test with a wildcard on
both ends, and a normal database index cannot answer that kind of question. The query therefore
reads every charity row.

**Why:** doing it properly needs the database's trigram extension, a new index, and a migration — and
migrations belong to the Platform Lead (D-007). `docs/NOTES.md` N9 records the reason and the fix
(a `pg_trgm` GIN index on `name`, and on `tagline` once more than a handful of searches use it).

**Judged:** a real, named departure from the document's scalability mechanism, with its exit written
down. On a dev database of 200 charities it is invisible. On thousands it is a slow page, not a wrong
one — the answer stays correct, it just takes longer.

**Reversible in:** one migration adding the extension and the index. No code change.

### D3 — A whole-word search is the database's regular-expression syntax, not Python's

**The document says** nothing about this. It says the option exists ("like full words only").

**The code does** build `\yname\y` and hand it to the database, where `\y` is a **word boundary** in
the database's own regex dialect. In Python the same idea is written `\b`.

**Why:** the term has to appear as complete words, and the database is the only place that can decide
that without loading rows into Python. `reset_search.py`-style escaping (`re.escape`) makes a term
that contains a regex character — `(`, `*`, `+` — match as text instead of as a pattern.

**Judged:** not a departure from the document; an implementation detail recorded as N11 so the next
reader does not "fix" `\y` into `\b` and break it. The project is Postgres-only.

**Reversible in:** a replacement pattern builder; one function.

### D4 — Four "nothing found" messages where the document asks for one

**The document says** (`§6.2.6 — Failure paths`):

> Nothing found → Message saying nothing was found.

**The code does** choose between four messages (`apps/charities/templates/charities/listing.html:152`):

```django
      {% elif search_form.is_active and form.is_active %}
        <p class="empty">No charities match that search and those filters.</p>
      {% elif search_form.is_active %}
        <p class="empty">No charities match that search.</p>
      {% elif form.is_active %}
        <p class="empty">No charities match those filters.</p>
      {% else %}
        <p class="empty">No charities found.</p>
      {% endif %}
```

**Why:** with several controls on the page, "nothing was found" is unhelpful — it does not say what
to loosen. The four messages tell the visitor which combination came up empty. Two of the four
already existed from the filter PR (N6); this PR adds the two that mention the search.

**Judged:** an addition, not a departure from the document's requirement: every state that the
document describes still produces a message saying nothing was found. Nothing in the document asks
for the messages to be identical.

**Reversible in:** deleting two branches.

### D5 — Search reads the name only unless asked otherwise (the document is ambiguous)

**The document says** two things in different places. §6.2.2's service list says `list_charities`
"searches the name column of the CHARITY DB"; §6.2.6 offers "searching in the tagline" as an
advanced option.

**The code does** search the name by default, and name-or-tagline when the tagline switch is on
(`apps/charities/search.py:83`):

```python
    @property
    def fields(self) -> tuple[str, ...]:
        """The CHARITY columns the term is matched against.

        §6.2.2 says list_charities "searches the name column"; the tagline is
        only read when the reader asks for it (§6.2.6).
        """
        return ("name", "tagline") if self.tagline else ("name",)
```

**Why:** the tagline is described as an option, so it cannot be the default; reading it always would
make the option meaningless. OR-ing the two rather than replacing one with the other means the
tagline option can only ever show *more* charities, never fewer.

**Judged:** an ambiguity resolved, not a departure. D-054 records the reading.

**Reversible in:** one line in `fields`.

### Not departures, but close enough to be worth saying

- **No results as you type.** §6.2.6 says the visitor "types in it, and presses submit", so
  submit-only is what the document describes. §6.2.1 describes a *different* search bar (the signup
  page's) as searching on every character. Do not read that into this page.
- **No accent folding.** "chesed" will not find "Chésed". The document asks for case-insensitivity
  only (see 5.1, where the constraint list is quoted), so this matches the document as written; N10
  records it as a known, unasked-for gap rather than an oversight. **Decided in a later PR of this
  stack:** D-069 (PR #21) settles it — accents stay unfolded, with the reasoning and the evidence.
- **The advanced panel is a `<details>` toggle, not a checkbox labelled "advanced".** The document
  says "There is a toggle for advanced search". `<details>` *is* a toggle and needs no JavaScript,
  which the no-CDN, no-framework rule (D-029) requires.

---

## 7. Reading order

Read in this order and each file explains the next one.

| # | file | what it is | why here |
|---|---|---|---|
| 1 | `apps/charities/search.py` *(new)* | Everything about a search: the words, the switches, the matching rules, the pairs | It is the vocabulary. Every other file speaks it. |
| 2 | `apps/charities/repositories.py` | The only code that talks to the database | Turns the search into a database condition |
| 3 | `apps/charities/services.py` | The listing's rules: how much fits on a page, how links are built | Gives the search a place in the page state |
| 4 | `apps/charities/views.py` | The function that answers the `/charity/` address | Reads the search and hands it over |
| 5 | `.../templates/charities/search.html` *(new)* | The search bar | The visible half |
| 6 | `.../templates/charities/search_state.html` *(new)* | The search as hidden values | The invisible half, and the actual fix |
| 7 | `.../templates/charities/{listing,filters,sort,state}.html` | The page and the other three controls | Where the copies of the hidden values are wired in |
| 8 | `static/css/site.css` | Styling | Cosmetic; skim |
| 9 | `docs/DECISIONS.md`, `docs/NOTES.md` | D-054 and N9–N12 | The reasoning, written down |
| 10 | `tests/unit/test_search.py`, `test_search_repository.py`, `test_views.py`, `test_services.py`, `test_filter_service.py` | The proof | Read after the code, not instead of it |

**The shape of the whole change in one sentence:** a new `Search` object is read from the address,
turned into one database condition, and written back into every link and every form on the page.

---

## 8. The files, one at a time

### 8.1 `apps/charities/search.py` — **the new file that owns the word "search" (new file, 206 lines)**

This file is the only place that knows how a search is spelled. The bar, the database query, the
page links and the hidden boxes all ask it. If someone later renames the parameter from `q` to
`search`, or adds a third advanced option, this is the one file that changes.

**The module's own statement of purpose**, quoted because it is the argument for the whole shape:

```python
"""The listing's search, as §6.2.6 defines it (D-054).

This is the one place that knows the doc's search parameter, the advanced options
it offers and how a typed term is matched. The view, the search bar, the page
links and the repository read a `Search` from here, so adding or renaming an
option is a change in this file and nowhere else.

`Search` is a value object rather than a bare string because the term and the
advanced options are read by three different places: the query is narrowed by
them (§6.2.6), the bar shows them back, and every other control on the page has
to carry them so that filtering or sorting does not silently drop the search.
"""
```

#### The parameter name, chosen and explained

Nothing named the address parameters, so the file names them and says why (`search.py:21`):

```python
# §6.2.6 names neither the search parameter nor the advanced ones; `q` is the
# conventional short search parameter, and the options are named for what they
# switch on (D-054).
TERM_PARAMETER = "q"
```

#### `Option` and `OPTIONS` — the two advanced switches, as one table (new)

**Before:** there were no advanced options and no place to put them. **After:** each option is one
row of data holding the three things that must agree — the address parameter, the field on the
`Search` object, and the English label the visitor reads.

```python
@dataclass(frozen=True)
class Option:
    """One switch in the advanced panel: its URL parameter and where it is stored.

    One table for the two facts that must agree — the parameter the URL uses and
    the attribute on `Search` — so adding or renaming an option is one entry here.
    """

    parameter: str
    attribute: str
    label: str
    note: str = ""


# §6.2.6's advanced options ("like full words only, or searching in the tagline"),
# in the order the panel shows them. They are additions to the default search,
# which matches part of a word anywhere in the name (§6.2.2).
OPTIONS: tuple[Option, ...] = (
    Option(
        "whole_words",
        "whole_words",
        "Full words only",
        "Off matches part of a word.",
    ),
    Option(
        "tagline",
        "tagline",
        "Search the tagline too",
        "Off matches the name only.",
    ),
)
```

What this buys: adding a third option is one entry in this tuple, and every other file — the bar, the
query, the links, the hidden boxes — picks it up without being edited.

#### `Search` — the search slip (new)

**Before:** the listing took no search at all. **After:** a search is a term plus one switch per
option, and it knows three things about itself: whether it is empty, whether any option is on, and
which columns and matching rule it implies.

```python
@dataclass(frozen=True)
class Search:
    """A typed term and the advanced options that shape how it is matched.

    An empty term searches for nothing: §6.2.6 has the listing show every charity
    until something is typed, so an empty search must not narrow the page. The
    options are meaningless without a term, so `is_empty` is decided by the term
    alone.
    """

    term: str = ""
    whole_words: bool = False
    tagline: bool = False

    @property
    def is_empty(self) -> bool:
        return not self.term

    @property
    def is_advanced(self) -> bool:
        """True when an advanced option is on, so the panel opens showing why."""
        return any(getattr(self, option.attribute) for option in OPTIONS)
```

**The matching rule is two properties, and this is where the reviewer should look hardest**
(`search.py:83` and `search.py:92`). The first says which columns; the second says which comparison.
The term itself is escaped so that a typed `*` is text, not a pattern:

```python
@property
def fields(self) -> tuple[str, ...]:
    """The CHARITY columns the term is matched against.

    §6.2.2 says list_charities "searches the name column"; the tagline is
    only read when the reader asks for it (§6.2.6).
    """
    return ("name", "tagline") if self.tagline else ("name",)


@property
def lookup(self) -> str:
    """The Django lookup that matches the term, from the advanced options.

    Both are case-insensitive, which UC-03 requires. A whole-word match is a
    regular expression because a word boundary is not a `contains` test; the
    escaped term is matched as one contiguous piece of text, so a multi-word
    term has to appear as typed rather than as scattered words.
    """
    return "iregex" if self.whole_words else "icontains"


@property
def pattern(self) -> str:
    """The value `lookup` compares against: the term, bounded to whole words if asked."""
    if not self.whole_words:
        return self.term
    return rf"\y{re.escape(self.term)}\y"
```

What this buys: the difference between "find those letters anywhere" and "find those letters as
whole words" is one property, tested separately, rather than a branch buried inside a query builder.

#### `from_query` — reading the search out of the address (new)

**Before:** nothing read a search. **After:** whitespace is tidied, an empty term means no search at
all, and the options are dropped along with it.

```python
def from_query(query) -> Search:
    """Read the term and the advanced options from a request query.

    A blank or whitespace-only term, and one that is only whitespace once
    normalised, is no search at all: the listing shows every charity, and the
    advanced options are dropped with it rather than left on with nothing to
    match. Runs of whitespace collapse to one space, so a doubled space in an
    address still matches the single space in the text.
    """
    term = " ".join((query.get(TERM_PARAMETER) or "").split())
    if not term:
        return Search()
    values = {option.attribute: _switched_on(query.get(option.parameter)) for option in OPTIONS}
    return Search(term=term, **values)
```

Two behaviours here are worth noticing, because both were choices rather than accidents:

- **`" ".join(...split())`** collapses runs of spaces. Without it, a name with one space in the
  database would not match a term typed with two, and the visitor would see an empty page for a
  charity they can plainly see on the screen.
- **Options are dropped when the term is empty.** A URL of `?whole_words=1` with no term is not a
  narrow search; it is no search. Keeping the switch on with nothing to match would make the bar
  look broken.

#### `query_pairs` and `query_string` — writing the search back out (new)

This is the mechanism that makes every other control able to carry the search. An empty search
produces nothing at all, so a plain page keeps a plain address.

```python
def query_pairs(search: Search) -> tuple[tuple[str, str], ...]:
    """The search as (parameter, value) pairs, empty when nothing was typed.

    An absent search keeps a plain page link plain, and makes every URL that
    describes the same view spell it the same way — the same rule the sort and
    the filter groups follow (D-046, D-048).
    """
    if search.is_empty:
        return ()
    parts: list[tuple[str, str]] = [(TERM_PARAMETER, search.term)]
    for option in OPTIONS:
        if getattr(search, option.attribute):
            parts.append((option.parameter, "1"))
    return tuple(parts)


def query_string(search: Search) -> str:
    """The search as a query string, so a page link can repeat it."""
    return urlencode(query_pairs(search))
```

#### `SearchOption`, `SearchForm` and `search_form` — the bar, already worded (new)

**Before:** there was no bar, and no rule about where its wording lives. **After:** the template
holds no search vocabulary at all — not the parameter name, not one label, not the placeholder.

```python
@dataclass(frozen=True)
class SearchOption:
    """One switch in the advanced panel, ready to render."""

    parameter: str
    label: str
    note: str
    checked: bool


@dataclass(frozen=True)
class SearchForm:
    """The search bar, ready to render.

    The bar carries the term back to the reader and the advanced switches in
    their current state. The parameter name and the three labels come from here
    too, so the template holds no search vocabulary at all.
    """

    term: str = ""
    options: tuple[SearchOption, ...] = ()
    is_advanced: bool = False
    parameter: str = TERM_PARAMETER
    label: str = "Search"
    placeholder: str = "Charity name"
    submit_label: str = "Search"
    advanced_label: str = "Advanced search"

    @property
    def is_active(self) -> bool:
        """True when a term is applied, which is what changes the empty message."""
        return bool(self.term)


def search_form(search: Search) -> SearchForm:
    """Assemble the search bar from the search the URL asked for."""
    return SearchForm(
        term=search.term,
        options=tuple(
            SearchOption(
                parameter=option.parameter,
                label=option.label,
                note=option.note,
                checked=getattr(search, option.attribute),
            )
            for option in OPTIONS
        ),
        is_advanced=search.is_advanced,
    )
```

What this buys: the listing template never contains the string `q`, so renaming the parameter cannot
leave the page with a dead box. `is_active` is a separate question from `is_empty` for a reason
worth stating plainly: they currently mean the same thing, and the moment they stop meaning the same
thing (say, a search that is only an option), the empty message still needs to know whether a term
was applied.

#### `_switched_on` — reading a checkbox from a hand-edited address (new)

A checkbox sends `1`. A person editing the address can send anything, and "on" must not be the
accidental answer.

```python
def _switched_on(raw: str | None) -> bool:
    """Whether an advanced option is on, read as a checkbox-style flag.

    The bar sends `1`; `0`, `false`, `off` and `no` all mean off, so an address
    someone hand-edited cannot switch an option on by accident.
    """
    if raw is None:
        return False
    return raw.strip().lower() not in ("", "0", "false", "off", "no")
```

---

### 8.2 `apps/charities/repositories.py` — **the one file that talks to the database learns one more condition (+36, −8)**

This file is the only place in the charities app that writes database queries. It receives the
filters, the order and now the search, and returns charity cards or a count. Nothing above it — no
view, no template — ever sees a query.

#### `_search_condition` — the search as one condition (new)

**Before:** the file knew how to turn filter groups into conditions, and nothing else. **After:** one
new helper turns a search into a single OR-ed condition, or into `None` when there is nothing to
search for.

```python
def _search_condition(search: Search | None) -> Q | None:
    """§6.2.6's term as one condition, or None when nothing was typed.

    The term is matched against the columns `search.fields` names, OR-ed
    together, so a charity whose tagline matches is a match even when its name
    does not. An empty search is not a condition at all: the listing is then
    unfiltered, which is what the page shows before anything is typed.
    """
    if search is None or search.is_empty:
        return None
    condition = Q()
    for field in search.fields:
        condition |= Q(**{f"{field}__{search.lookup}": search.pattern})
    return condition
```

The `Q()` object is the database library's way of saying "this condition, or that one". Built empty
and OR-ed in a loop, it produces `name matches OR tagline matches` when the tagline switch is on, and
just `name matches` when it is off. Returning `None` rather than an always-true condition matters:
an empty search must add no clause to the query at all, so that the query the page runs before
anything is typed is byte-for-byte the query it ran before this PR.

#### The repository's contract gains the search

**Before:** `page` and `count` knew about filters and order. **After:** both accept a search, so the
list of cards and the total agree about what was searched.

```python
def page(
    self,
    offset: int,
    limit: int,
    filters: CharityFilters | None = None,
    sort: CharitySort = DEFAULT_SORT,
    search: Search | None = None,
) -> tuple[CharityCard, ...]:
    """Return cards for the given window of the filtered set, in the chosen order."""
    ...


def count(self, filters: CharityFilters | None = None, search: Search | None = None) -> int:
    """Return how many charities the filters and the search keep."""
    ...
```

The `...` is the protocol — the agreed shape, not the implementation. Two implementations exist: the
real one, and the fakes in the tests.

#### `page` and `count` pass it down

**Before:** both called `_narrowed` with the filters and nothing else. **After:** the search is one
more thing to narrow by.

```python
def page(
    self,
    offset: int,
    limit: int,
    filters: CharityFilters | None = None,
    sort: CharitySort = DEFAULT_SORT,
    search: Search | None = None,
) -> tuple[CharityCard, ...]:
    rows = self._narrowed(filters, sort=sort, search=search, reviews=True)
    rows = self._with_activity_values(rows, sort)
    rows = self._ordered(rows, sort)
    rows = rows.prefetch_related("domains", "locations")[offset : offset + limit]
    return tuple(self._to_card(row) for row in rows)


def count(self, filters: CharityFilters | None = None, search: Search | None = None) -> int:
    return self._narrowed(filters, search=search).count()
```

#### `_narrowed` — where the clause is added (changed)

**Before:** `_narrowed` applied the filter groups and nothing else. **After:** the same method ends
with the search, as one more AND.

```python
    def _narrowed(
        self,
        filters: CharityFilters | None,
        *,
        sort: CharitySort | None = None,
        search: Search | None = None,
        reviews: bool = False,
    ) -> QuerySet[Charity]:
        """Apply §6.2.4's groups and §6.2.6's search: OR inside a group, AND between them.
```

and, at the end of that method:

```python
        condition = _search_condition(search)
        if condition is not None:
            rows = rows.filter(condition)
        return rows
```

The docstring's phrase **"OR inside a group, AND between them"** is the whole logic of the page in six
words: several domains in one filter group mean *any of these*, while the search, the filters and the
rating range all have to hold at once. That is why searching inside a filtered set narrows it rather
than replacing it, which is exactly what §6.2.6's "filters and sort remain on" asks for.

What this buys: one extra `filter()` call on the same query. The search does not fetch rows and sift
them, so it costs one query, and the count and the page cannot disagree about what matched.

---

### 8.3 `apps/charities/services.py` — **the page state grows a fourth thing to remember (+22, −11)**

This file holds the listing's rules that are not about the database: how big a page is, how many
pages there are, and — the part that matters here — how to build a link that describes the same view
one page over. If a link is built anywhere else, this file has been bypassed.

#### `Page.search_pairs` — the search, remembered (new field)

**Before:** a `Page` remembered the items, the total, the page size, the order and the filter pairs.
**After:** it also remembers the search pairs, so every query string the object can build carries
them without any per-link work.

```python
    sort: CharitySort = DEFAULT_SORT
    # The search as (parameter, value) pairs, for replaying it as hidden inputs.
    search_pairs: tuple[tuple[str, object], ...] = ()
    # The filters as (parameter, value) pairs, for replaying them as hidden inputs.
    filter_pairs: tuple[tuple[str, object], ...] = ()
```

#### `_state_query` — one line changed, six links fixed (changed)

**Before:**

```python
        state = urlencode(pairs + self.sort_pairs)
```

**After** — the pair variable renamed to say what it now holds, and the search prepended:

```python
    def _state_query(self, *, include_filters: bool = True, **parts: int) -> str:
        """A query string of `parts`, followed by the search, filters and sort."""
        base = urlencode(parts)
        pairs = self.filter_pairs if include_filters else ()
        state = urlencode(self.search_pairs + pairs + self.sort_pairs)
        return f"{base}&{state}" if state else base
```

Every link on the page that moves within the same result set goes through this one method: the
numbered page links, next, previous, and jump-to-page. Adding one term to this line is what makes
`test_the_search_is_replayed_by_every_page_link` pass for all of them at once. The ordering is
deliberate too — search, then filters, then sort — so the same view always spells its address the
same way, which is the rule the sort and filter PRs already followed.

#### `clear_filters_query` — Clear filters keeps the search (changed, docstring only)

**Before:** "The page with its size and order kept, but no filters (§6.2.4)." **After:**

```python
    @property
    def clear_filters_query(self) -> str:
        """The page with its size, search and order kept, but no filters (§6.2.4)."""
        return self._state_query(include_filters=False, page_size=self.page_size)
```

Clear filters means clear **the filters**. A visitor who searched, filtered, then decided the filter
was too narrow, expects their word to still be there. The behaviour came free from `_state_query`;
only the promise in the docstring had to catch up.

#### `list_charities` — the service the design document names (changed)

**Before:**

```python
def list_charities(
    repository,
    filters: CharityFilters | None = None,
    sort: CharitySort = DEFAULT_SORT,
    page: int | None = 1,
    page_size: int | None = None,
) -> Page:
    """Return one page of the charities `filters` keep, ordered by `sort`.

    §6.2.5: choosing an order shows page 1, which the view gets by not passing a
    `page` for a sort change; an explicit page in the URL is still honoured so a
    shared link keeps its whole state (UC-03). A filter change works the same
    way (§6.2.4).
    """
    filters = filters or CharityFilters()
    page_size = clamp_page_size(page_size)
    total = repository.count(filters)
    ...
        items=repository.page(offset=offset, limit=page_size, filters=filters, sort=sort),
    ...
```

**After:**

```python
def list_charities(
    repository,
    filters: CharityFilters | None = None,
    sort: CharitySort = DEFAULT_SORT,
    page: int | None = 1,
    page_size: int | None = None,
    search: Search | None = None,
) -> Page:
    """Return one page of the charities `filters` and `search` keep, ordered by `sort`.

    §6.2.6: the search is a term plus the advanced options that shape it, and it
    narrows the same set the filters do rather than starting a new one, so the
    two combine. §6.2.6 also shows page 1 of a search, which the view gets by not
    passing a `page` when the term changes; an explicit page in the URL is still
    honoured so a shared link keeps its whole state (UC-03). §6.2.5's sort change
    and §6.2.4's filter change work the same way.
    """
    filters = filters or CharityFilters()
    search = search or Search()
    page_size = clamp_page_size(page_size)
    total = repository.count(filters, search=search)
    count = page_count(total, page_size)
    number = max(1, min(page or 1, count))
    offset = (number - 1) * page_size

    return Page(
        items=repository.page(
            offset=offset, limit=page_size, filters=filters, sort=sort, search=search
        ),
        total=total,
        number=number,
        page_size=page_size,
        sort=sort,
        search_pairs=search_query_pairs(search),
        filter_pairs=filter_query_pairs(filters),
    )
```

Three things to notice, in plain words:

1. **`search or Search()`** means a caller that forgets the search gets "no search", not a crash. It
   also keeps every existing test and caller working unchanged.
2. **The count and the page are given the same search** in the same call, so the number under the
   results cannot promise results the list does not contain.
3. **`search_pairs=search_query_pairs(search)`** is where the search enters the page state. Every
   link built later reads it from there.

What this buys: the service the design document names now takes the argument the design document
names, and a search of an empty database page 9 still shows page 1 rather than an empty screen,
because the page number is clamped to the count *of the searched set*.

---

### 8.4 `apps/charities/views.py` — **the door: reading the address and handing the search on (+9, −2)**

The view is the function that answers `/charity/`. It reads the address, asks the services for what
the page needs, and hands one dictionary to the template. It contains no rules of its own, and this
PR keeps it that way: three lines in, one line out.

**Before:**

```python
def listing(request: HttpRequest) -> HttpResponse:
    """Render the paginated list of charities, narrowed and ordered as chosen."""
    sort = read_sort(request.GET)
    options_repository = DjangoFilterOptionsRepository()
    ...
        sort=sort,
        page=_positive_int(request.GET.get("page")),
        page_size=_positive_int(request.GET.get("page_size")),
    )
    ...
    return render(
        request,
        "charities/listing.html",
        {"page": page, "form": form, "sort_form": sort_form(sort)},
    )
```

**After:**

```python
def listing(request: HttpRequest) -> HttpResponse:
    """Render the paginated list of charities, searched, narrowed and ordered as chosen."""
    sort = read_sort(request.GET)
    search = read_search(request.GET)
    ...
        sort=sort,
        page=_positive_int(request.GET.get("page")),
        page_size=_positive_int(request.GET.get("page_size")),
        search=search,
    )
    ...
    return render(
        request,
        "charities/listing.html",
        {
            "page": page,
            "form": form,
            "sort_form": sort_form(sort),
            "search_form": search_form(search),
        },
    )
```

The imports say the same thing (`views.py:11`):

```python
from .search import from_query as read_search
from .search import search_form
```

Notice what the view does **not** do: it does not check whether the term is blank (the search's own
reader does), it does not decide the matching rule (the `Search` object does), and it does not
remember the search for the links (the `Page` does). A view that did any of that would be the place
where the next control gets forgotten.

What this buys: one place reads the search, so a term arriving in any form — `?q=x`, `?q=+++`, no
`q` at all — is decided once, in `search.py`, where it is tested without a browser.

---

### 8.5 `apps/charities/templates/charities/search.html` — **the bar itself (new file, 46 lines)**

This is the visible half of the change: a text box, a Search button, and a collapsed "Advanced
search" that opens to two checkboxes. It is a plain form, which means the browser sends an address
and the server answers a page — no JavaScript, no live requests.

The template's own opening comment states the three rules it is obeying:

```django
{% comment %}
The listing's search bar (§6.2.6, D-054). A plain GET form, like the sort and
filter controls, so the term lives in the URL and the browser's Back button
works (UC-03). The page size, the filters and the order ride along as hidden
inputs, and no `page` is sent, so a new search starts at page 1 (§6.2.6).
The advanced options sit behind a <details> toggle, which needs no JavaScript.
{% endcomment %}
```

The form's opening and its carried values:

```django
<form class="search" method="get" action="{% url 'charities:listing' %}" role="search">
  <input type="hidden" name="page_size" value="{{ page.page_size }}">
  {% include "charities/filter_state.html" %}
  {% include "charities/sort_state.html" %}
```

Read those four lines as a sentence: *this form, when sent, carries the page size, the filters and
the order, and deliberately carries no page number.* The absent page number is §6.2.6's "page 1 of
the search is shown" — a missing page means page 1. Note what is **not** included: `search_state.html`.
This form carries the term in its own visible box, so repeating it as a hidden value would send it
twice.

The box and the button:

```django
  <div class="search__bar">
    <label class="search__label" for="{{ search_form.parameter }}">{{ search_form.label }}</label>
    <input
      class="search__input"
      id="{{ search_form.parameter }}"
      name="{{ search_form.parameter }}"
      type="search"
      value="{{ search_form.term }}"
      placeholder="{{ search_form.placeholder }}"
      autocomplete="off"
    >
    <button class="search__submit" type="submit">{{ search_form.submit_label }}</button>
  </div>
```

Every word and the parameter name come from `search_form`, so the template holds no search
vocabulary. `value="{{ search_form.term }}"` is what keeps the term in the box after the page comes
back — without it the visitor would type, press Search, and watch their word disappear while the
results change.

The advanced panel:

```django
  {% comment %}Opened when an option is on, so the reader can see why the
  results are narrowed differently than the term alone would explain.{% endcomment %}
  <details class="search__advanced"{% if search_form.is_advanced %} open{% endif %}>
    <summary class="search__toggle">{{ search_form.advanced_label }}</summary>
    <div class="search__options">
      {% for option in search_form.options %}
        <label class="search__option">
          <input
            type="checkbox"
            name="{{ option.parameter }}"
            value="1"
            {% if option.checked %}checked{% endif %}
          >
          <span class="search__option-label">{{ option.label }}</span>
        </label>
        <span class="search__note">{{ option.note }}</span>
      {% endfor %}
    </div>
  </details>
```

`<details>` is a built-in browser element that collapses and expands with no script. The ` open`
attribute is added when an option is on, so a visitor who returns to a page where the tagline is
being searched can see *why* the results differ from a plain name search. A panel that closed itself
would leave the visitor unable to explain what they are looking at.

What this buys: a working search with no JavaScript, so the page keeps working on a slow connection,
and the browser's Back button returns the previous results because they are addresses, not state.

---

### 8.6 `apps/charities/templates/charities/search_state.html` — **the eight lines that fix the six controls (new file)**

This is the smallest new file and the most important one. It writes the active search out as hidden
values, and every other form on the page includes it.

```django
{% comment %}
The active search as hidden inputs. A form that changes the filters, the order,
the page size or the page number includes this so it cannot silently drop the
term (§6.2.6). The search bar itself is the exception: it carries the term in
its own input.
{% endcomment %}
{% for name, value in page.search_pairs %}<input type="hidden" name="{{ name }}" value="{{ value }}">
{% endfor %}
```

Read it as: *for every (name, value) pair the page state remembers about the search, add an invisible
box to this form.* When there is no search, `search_pairs` is empty and not one byte is added, which
is why a page with no search looks exactly as it did before this PR.

What this buys: Devorah's story cannot happen. The sort form now contains
`<input type="hidden" name="q" value="chessed">`, so sorting her search returns her search sorted.

---

### 8.7 The other templates — **three lines of wiring each (+13, −6 across four files)**

Four existing templates changed, and every change is the same two ideas: include the new partial, or
mention the search in a comment.

**`filters.html`** — the sidebar form now carries the search, and its comment says so:

```django
  {% comment %}Keep the page size, the search and the order the reader chose; a
  filter resets the page to 1 (§6.2.4), which is what a missing `page` parameter
  means.{% endcomment %}
  <input type="hidden" name="page_size" value="{{ page.page_size }}">
  {% include "charities/search_state.html" %}
  {% include "charities/sort_state.html" %}
```

**`sort.html`** — the same include, above the filters, so the address reads search-then-filters:
its comment changed from "The active filters ride along as hidden inputs, so sorting never drops
them." to "…as does the search term, so sorting never drops either."

```django
  <input type="hidden" name="page_size" value="{{ page.page_size }}">
  {% include "charities/search_state.html" %}
  {% include "charities/filter_state.html" %}
```

**`state.html`** — the one-line partial that the page-size and jump-to-page forms include, now three
partials instead of two. This is why those two forms needed no change of their own:

```django
{% include "charities/search_state.html" %}{% include "charities/filter_state.html" %}{% include "charities/sort_state.html" %}
```

**`listing.html`** — the bar is placed above both columns, and the two new empty messages join the
two that existed:

```django
  <div class="listing">
    {# §6.2.6 Search: a bar across the top of the listing, above both columns. #}
    {% include "charities/search.html" %}

    {# §6.2.4 Filter: the sidebar narrows the listing, Amazon-style. #}
```

What this buys: the state travels in the address from every control, not just from the search box,
and the visitor is told which combination came up empty instead of a generic "nothing found".

---

### 8.8 `static/css/site.css` — **the bar spans the page and stacks on a phone (+74)**

Styling only; no behaviour lives here. It is listed so a reviewer knows nothing was hidden in it.

The one line that means something structural:

```css
.search {
  background: #fafafa;
  border: 1px solid #e2e2e2;
  border-radius: 0.5rem;
  grid-column: 1 / -1;
  padding: 0.875rem 1rem;
}
```

`grid-column: 1 / -1` says *stretch from the first column to the last*, so the bar sits above the
sidebar **and** the results rather than beside them. §6.2.6 says "a search bar on top", and on a
phone the same rule keeps it first, above everything, which is where a visitor looking for one
charity will go first. The remaining rules (`flex: 1 1 12rem` on the input, a two-column grid for
the option labels and their notes) make the bar narrow on a phone instead of pushing the button off
the screen.

---

### 8.9 `docs/DECISIONS.md` and `docs/NOTES.md` — **the reasoning, written down (+49)**

This PR is unusual in that a decision was recorded *for* it (D-054) and four notes (N9–N12) were
written while building it. They are part of the change on purpose: they are what let a future
engineer tell a deliberate choice from an oversight.

**D-054** is the search's constitution. Read its "Decision:" bullet and you have the whole PR. The
parts worth quoting because they pin choices that would otherwise look like bugs:

> The URL is `?q=<term>` plus one parameter per option, `whole_words=1` and `tagline=1`.

> Search and the six filter groups AND together (a search does not clear the filters), and page 1 of
> a search is shown because the search bar form sends no `page`; a URL with an explicit `page` still
> keeps it, the same rule as the filter and sort forms (D-045, D-048, N5).

That second sentence is the spine of this entire PR stated in one breath, and it matches what the
code does — which is worth stating because D-054 was written alongside the code, not after it.

**N9–N12** are the notes, quoted at the top of the section. The two a reviewer should register:

- **N9** — search uses no index and is a sequential scan; the fix (`pg_trgm`) needs a migration and
  a Platform Lead. This is departure **D2** above.
- **N10** — search folds case but not accents. "chesed" does not find "Chésed". Matches the document
  as written; known gap, recorded, not buried.
- **N11** — whole-word uses Postgres regex syntax, not Python's.
- **N12** — the local dev database is stale: it has 200 charities but only 61 distinct names, so the
  search will look wrong (five "Lev Chaim" cards per page) until `./dev.sh --fresh` reseeds it. This
  one is a trap for anyone *eyeballing* this PR's feature locally without running the tests, and it
  belongs in the walkthrough so no reviewer "discovers" it.

---

### 8.10 The tests — **157 new in three files, plus additions in two more**

Read as sentences, the test names are the change's own summary of itself. Grouped by what they
prove:

**What the search means** (`tests/unit/test_search.py`, no database needed):
`test_nothing_typed_is_no_search`, `test_a_blank_term_is_no_search`, `test_the_term_is_read_from_the_url`,
`test_surrounding_space_is_not_part_of_the_term`, `test_inner_whitespace_collapses_to_one_space`,
`test_an_advanced_option_is_off_unless_the_url_says_so`, `test_each_advanced_option_is_recognized`,
`test_an_option_saying_no_is_off`, `test_options_without_a_term_are_dropped`,
`test_the_default_searches_the_name_only`, `test_the_tagline_option_adds_the_tagline`,
`test_the_default_matches_part_of_a_word`, `test_whole_words_match_bounds_the_term`,
`test_whole_words_escapes_a_regex_character_in_the_term`, `test_advanced_is_true_only_when_an_option_is_on`,
`test_an_empty_search_adds_no_parameters`, `test_the_term_is_one_parameter`,
`test_each_option_is_one_parameter`, `test_a_query_survives_a_round_trip`,
`test_the_bar_shows_the_term_and_the_submit_button`, `test_every_advanced_option_is_offered`,
`test_chosen_options_render_as_checked`, `test_an_empty_search_is_not_active_so_the_empty_message_can_differ`.

**What the query actually does to real rows** (`tests/unit/test_search_repository.py`, needs Postgres):
`test_an_empty_search_keeps_every_charity`, `test_the_name_is_matched_case_insensitively`,
`test_a_term_matches_part_of_a_word_by_default`, `test_a_term_that_matches_nothing_returns_nothing`,
`test_whole_words_only_rejects_a_partial_word`, `test_whole_words_matches_a_multi_word_term_as_typed`,
`test_whole_words_rejects_words_in_a_different_order`, `test_whole_words_treats_the_term_as_text_not_a_pattern`,
`test_a_wildcard_in_the_term_is_text`, `test_the_tagline_is_not_searched_by_default`,
`test_the_tagline_option_searches_the_name_and_the_tagline`, `test_a_charity_matching_either_column_is_kept`,
`test_the_search_combines_with_a_filter`, `test_the_count_reads_the_search_too`,
`test_a_searched_page_still_carries_every_card_value`.

Two of these deserve to be seen in full, because they test the two things that *look* like bugs and
are actually the point.

**A term typed with wildcard characters is the characters, not a pattern.** The whole-word option
uses the database's regex; the default uses `LIKE`, where `%` and `_` have special meaning. Without
this test, a visitor typing "100%" could search for "anything" instead of a charity literally named
"100% Chessed".

```python
    def test_a_wildcard_in_the_term_is_text(self) -> None:
        """`%` and `_` are LIKE wildcards; a reader typing them means the characters."""
        Charity.objects.create(name="100% Chessed")
        Charity.objects.create(name="100x Chessed")
        Charity.objects.create(name="A_B Fund")
        Charity.objects.create(name="AxB Fund")

        self.assertEqual(self.names(Search(term="100%")), ["100% Chessed"])
        self.assertEqual(self.names(Search(term="a_b")), ["A_B Fund"])
```

**The search and a filter narrow the same set.** This is §6.2.6's "filters and sort remain on" made
provable. Both must hold at once; the searched charity outside the Food domain does not appear.

```python
    def test_the_search_combines_with_a_filter(self) -> None:
        """§6.2.6 keeps the filters on, so both narrow the same set (D-045's AND)."""
        food = Domain.objects.create(name="Food")
        chessed = Domain.objects.create(name="Chessed")
        first = Charity.objects.create(name="Chessed Food Bank")
        second = Charity.objects.create(name="Chessed Loans")
        first.domains.add(food)
        second.domains.add(chessed)

        found = self.names(Search(term="chessed"), CharityFilters(domains=(food.id,)))

        self.assertEqual(found, ["Chessed Food Bank"])
```

**The whole page, end to end** (`tests/unit/test_views.py`, the new `ListingSearchPageTest`):
`test_the_search_bar_is_on_the_page_for_every_visitor`, `test_every_advanced_option_is_offered`,
`test_a_typed_term_narrows_the_page`, `test_the_term_stays_in_the_box`,
`test_the_search_form_sends_no_page_so_a_search_starts_at_page_one`,
`test_a_shared_url_keeps_its_page_and_search`, `test_pagination_links_keep_the_search`,
`test_the_page_size_form_keeps_the_search`, `test_the_sort_form_keeps_the_search`,
`test_the_filter_form_keeps_the_search`, `test_the_jump_form_keeps_the_search`,
`test_the_search_and_a_filter_narrow_together`, `test_clearing_filters_keeps_the_search`,
`test_an_empty_result_says_the_search_found_nothing`, `test_an_empty_result_names_both_the_search_and_the_filters`,
`test_an_empty_database_still_says_no_charities_found`, `test_a_whole_word_search_is_applied`,
`test_a_tagline_search_is_applied`, `test_a_blank_term_searches_for_nothing`.

This is where Devorah's story is tested. `test_the_sort_form_keeps_the_search`,
`test_the_filter_form_keeps_the_search`, `test_the_page_size_form_keeps_the_search`,
`test_the_jump_form_keeps_the_search` and `test_pagination_links_keep_the_search` each assert that
the given form carries `name="q" value="chessed"`. They are the tests that would have caught the
silent-drop failure, and they are the reason the PR changes six templates instead of one.

**The service layer** (`tests/unit/test_services.py`, the new `ListCharitiesSearchTest`):
`test_no_search_is_an_empty_search`, `test_the_search_reaches_the_repository`,
`test_the_search_is_replayed_by_every_page_link`. The third is the one worth noticing — it asserts
`q=chessed` appears in the next link, the previous link, and the Clear-filters link at once, which is
the property `_state_query` gives for free.

**The one deleted test of note:** none. The change is additive. The only test edits outside the new
files are to two fakes — `tests/unit/test_filter_service.py` and the `FakeCharityRepository` in
`test_services.py` — whose `page` and `count` methods grew the same `search=None` argument as the
real repository, so the service's contract and the fakes that stand in for it cannot drift apart.
Adding the argument to a fake is itself a small contract test: if the service ever calls the
repository differently, these fakes fail loudly.

The design document asked for "white box → unit test, with different strings and advanced options"
and "black box → have users search different words". The white-box half is the repository test file;
the black-box half is the view test file, which drives the whole page through the test client. Both
halves of the document's test section are present.

---

## 9. The audit

This is the Dilbert test run against the finished document — the pointy-haired boss's-eye view — and
the two-layer check. It is here so you can see what was looked at, not as a guarantee that a given
human will follow everything.

**Did he fall off anywhere, and what was fixed?**

- **"case-insensitive"** was used in section 1 before being defined. It is now in the glossary
  (section 3) *and* used only after the glossary is required reading. — fixed.
- **"hidden value"** was used in section 1's plain-English summary before the glossary named it. It
  now has its own row. — fixed.
- **The word "state"** appears in "page state" many times. It is defined (glossary) and the opening
  gives a concrete image of it ("the address is the memory") so it does not stay abstract. — checked,
  left, because the image carries it.
- **Arithmetic:** the only numbers are page-1, page-9, "two hundred", "twenty-five cards", and the
  970/30 diff. None require him to divide or subtract. — checked.
- **A sentence with more than one idea** at section 1's summary paragraph and at "D3 — Why": both
  were split into shorter sentences. — fixed.
- **Every code box has an English sentence above it.** Walking the document: the module docstring
  (8.1), the four `Search` properties, `from_query`, `query_pairs`, `SearchForm`, `_switched_on`,
  `_search_condition`, the protocol, `page`/`count`, `_narrowed`, the `Page` field, `_state_query`,
  `clear_filters_query`, `list_charities` before/after, the view before/after, `search.html` (three
  boxes), `search_state.html`, the four wiring templates, and the two quoted tests. — checked, all
  have a plain-English sentence immediately above.

**The two-layer check.**

- *Delete every code box.* What remains is: the opening with the story of Devorah, the glossary,
  the full story with its cost, all six departures with their judgements, the reading-order table,
  and a prose explanation of every file that names the before and after and the consequence without
  needing the code. It stands. The two-layer test passes on the prose side.
- *Read only the code boxes.* The change is fully visible: the new `Search` vocabulary, the
  database condition, the page-state wiring, the before/after of the service and the view, the bar,
  the eight-line fix, the four template wirings, and the two pivotal tests. A reviewer would not
  need to open the diff to see how the search is read, matched, and carried. It stands.

**Where he still cannot follow, and why that is acceptable:** section 8.2's `_narrowed` and the
database-query discussion. `Q()`, `queryset`, `annotate` and the difference between a join and a
subquery are real terms with no plain equivalent, and the glossary does not paper over them. The
section is written for the engineer; what matters for the boss is that he can read the docstring
("OR inside a group, AND between them") and the English sentence, and never *silently* falls off
with no floor under him. He is told plainly at the top of 8.2 that this is the one file that talks
to the database, and everything above it does not.

**Bottom line:** this document both explains and can be reviewed from. It does not grade the change
— that is the reviewer's job, and section 6 hands them the departures (one genuine, documented one:
no search index; one signature-shaped one: the object-vs-dict; the rest are readings of a document
that was deliberately open on these points).
