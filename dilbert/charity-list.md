# The charity listing — a walkthrough of `charity_list`

*Explains one commit: `a9ebf14` "Port the charity listing onto the phase 0 skeleton", the branch `charity_list`, measured against its base `org/phase0-skeleton`. 32 files, 1,208 lines added, 9 removed.*

---

## 1. Read this part even if you read nothing else

MaaserMart is a website for people who give a tenth of their income to charity — that tenth is called *maaser* — and who want to find charities worth giving it to, and check them out first. A visitor arrives, gets a page full of charity names, and picks one to look at. That page full of names is the "listing", and it is the front door of the whole product. Without it there is nothing to visit.

Before this change, the project was a working workshop with no product in it. It could start, it had a database, it had a navigation bar across the top, and it had a place to put each feature. But if you opened the site in a browser, there was no charity list. The page that was supposed to hold the list was an empty signpost pointing at nothing.

This change builds the list. It adds the four pieces of machinery a listing needs: a way to ask the database for charities, a set of plain records to hold what the page will show, the rules about paging and ordering, and the web page itself with its styling. It also makes the site's front page — the plain `maasermart.com` address — send visitors straight to the list.

There is one deliberate oddity, and it is the thing to remember about this change. The database has a switch on every charity that says whether the public may see it. Every charity currently has that switch turned **off**, because the tool that turns it on — the administrator's approval screen — has not been built yet. So if the list obeyed the switch, the list would be empty. An empty list is not a listing anyone can check. This change therefore makes the list ignore the switch for now, and records that decision in writing so it cannot be forgotten. It is one argument in one place, and it gets flipped back when the approval screen exists.

Everything below is the same idea in more detail.

---

## 2. How to read this file

This document has two complete layers, and neither one is a summary of the other.

- **If you do not read code**, read the glossary, the story, and the bold one-line summary at the top of each file section, plus the plain sentence that sits directly above every code box. You will lose nothing.
- **If you are reviewing the change**, the code boxes are the change itself, quoted generously enough that you should be able to approve or reject it without opening a side-by-side comparison of changed lines.

Three rules:

1. **Read the glossary first.** Every term used here is defined there before it is used anywhere else.
2. **Every code box is optional.** The sentence directly above each box says the same thing in English. Skip every box and the document still stands.
3. **Each file section opens with a bold one-line summary.** Skim only those summaries and you have the shape of the whole change.

There is one section that is not part of the standard walkthrough: **section 8, departures from the design document.** It lists, in one place, every spot where this code does something the customer's written design does not describe, or describes differently. That section was asked for explicitly and it is worth reading even if you skip the file-by-file detail.

This document explains; it does not grade. There is no verdict and no recommendation.

---

## 3. The glossary

Eleven words, each defined by what it does and why anyone cares.

| term | plain words | what it is and why it matters |
|---|---|---|
| **Django** | the website-building toolkit | The Python software that turns a folder of code into a website. It receives a browser's request, picks which code should answer, and sends back a page. |
| **app** | one feature's folder | Django's unit of organisation. Each area of the product lives in its own folder under `apps/`. This change does all its work inside `apps/charities/`. |
| **the listing** | the front page full of charities | The page a visitor lands on. One row per charity: picture, name, one-line description, and small labels for what the charity does and where it works. This entire change is about this page. |
| **row** | one charity's record in the database | What the database stores for a charity: its name, its one-line description, its picture address, whether it is visible, and links to its labels. Code calls this a *model*. |
| **card** | what the page shows for one charity | A plain bundle of exactly the facts a single row on the page needs. It is *not* the database record. Making it a separate thing is the point — see "why a card is not a row" in the story. |
| **repository** | the only code allowed to ask the database | A small object with two jobs: hand back a window of cards, and say how many charities there are in total. Nobody else in the app is allowed to write a database question. |
| **page size** | how many charities per screen | The number of rows shown at once. The visitor can change it. Default 20, maximum 100. |
| **page number** | which screenful you are on | 1 for the first, 2 for the second, and so on. If a visitor asks for page 99 of a list that has 3 pages, they get page 3 rather than an error. |
| **visibility switch** | the may-the-public-see-this switch | An on/off flag stored on every charity. Off by default. Only the app's own publishing functions may change it. This change deliberately ignores it for now, and that is the one thing to remember. |
| **decision record** | the written note that overrides the blueprint | A numbered entry in `docs/DECISIONS.md`, referred to as `D-042` and so on. The company's rule is that when code disagrees with the customer's design document, a numbered note in this file is the authority. |
| **fixture / sample image** | a stand-in picture | One of twelve identical-shaped grey pictures shipped with the project so the listing has something to display before real charity photos exist. |

Plain-word substitutions used throughout the code sections. The mapping is here so a reviewer can always get back to the real names.

| code type or name | plain word used in this document |
|---|---|
| `Charity` (the model class) | a stored charity, or a row |
| `CharityCard` | a card |
| `DomainTag`, `LocationTag` | a label (what it does, or where it works) |
| `CharityRepository` (job description) | the repository's job description |
| `DjangoCharityRepository` | the repository itself |
| `Page` | one screenful, plus its links |
| `Charity.objects` | the database query tool |
| `is_visible` | the visibility switch |
| `published_only` | obey-the-visibility-switch, an on/off setting on the repository |

---

## 4. The story

### What the system does all day

1. A visitor types `maasermart.com` into a browser.
2. The site answers with a page of charities, twenty at a time, in alphabetical order.
3. Each row shows a picture, a name, a one-line description, and small labels saying what the charity does and where it works.
4. If there are more than twenty, the visitor sees page links at the bottom and can move between them, or ask for a different number per screen.
5. The visitor clicks a charity to read more about it. *(Clicking does not work yet in this change — see the story's ending.)*

That is the whole product's front door. Everything else — reviews, approvals, dashboards, recommendations — hangs off a visitor finding a charity here first.

### What was missing

The project's foundation existed. It had a database with a table for charities, a navigation bar, styling, an automated test suite, and the company's written rules. The charities folder existed too, with the publishing and hiding functions already written and tested.

What it did not have was anything a visitor could look at. The charities folder's address table was literally empty:

```python
# apps/charities/urls.py — before (base commit 0eeb207, line 6)
urlpatterns = []
```

So `maasermart.com/charity/` was a dead end, and the front page served a placeholder page with no charities on it.

### The bug, told as a story

Picture the person checking whether the project is worth continuing. They start the site, open it, and see... a page with a navigation bar and nothing under it. Is the database connected? Is the styling working? Does a charity row survive the round trip from database to browser? Nobody can tell, because there is nothing to look at.

That is the cost, and it is not a small one. Every later feature — filtering, sorting, the charity's own page, reviews — is built on the assumption that a charity can get from the database onto a screen. While that assumption is untested, every one of those features is being built on a foundation nobody has inspected.

There was a second, quieter cost. The list of charities has to be *read* from the database somehow. If the first piece of code that reads charities is written inside a web page, then every future feature will copy that pattern, and the "which charities may I show" question will be answered in five places with five slightly different answers. This change exists partly to answer that question once.

### The fix in one sentence

Add a real, paginated, alphabetically-ordered charity listing at `/charity/`, wired to the database through a single dedicated reader, and send the front page there.

What that buys, stated as consequences in the world:

- Someone can now open the site and see whether the whole stack works, end to end, in one glance.
- The question "how do I get charities out of the database" has exactly one answer, in one file, which later features must reuse.
- The web page cannot accidentally start depending on database behaviour, because it is handed plain cards, not database rows.
- The "which charities may I show" question is answered in one place, with a written note explaining the temporary answer, so flipping it later is one word.

### Why this is a whole change and not several

It is one idea with four mechanical parts. The parts are not independent: a card type with nothing to fill it is dead weight, a repository with no page to serve is unused code, and a page with no data source does not render. Four files that only make sense together, plus the wiring and the tests.

### What this change deliberately does not do

- **Clicking a charity does nothing.** Each card links to `#`, with a marker in the code saying to point it at the charity's page once that exists. The charity's own page is a separate piece of work.
- **There is no filtering, sorting or searching.** Those are written in the design document as three separate features. Alphabetical order is the default this change implements.
- **There are no ratings on the cards.** The design document's listing mentions rating filters, which implies ratings are visible. They are not on the card yet.
- **The visibility switch is ignored.** Described at length in section 1 and again, formally, in section 8.

---

## 5. Contradictions

Three places where a description disagrees with the code. Trust the code.

### 5.1 The old branch's code was not carried over, it was re-written into the new layout

The commit message says the listing "was built in the old `src/` layout" and this commit "moves it onto Yosef's skeleton". Read literally, that sounds like a file move. It is not. The base commit `0eeb207` already has the new `apps/` layout, and the listing arrives as *new files* in that layout. The old `src/` tree is not in this branch's history at all — it lives on the unrelated `feat/charity-list` branch, which shares no history with this one.

Practical consequence for a reviewer: `git diff` shows additions, not moves, and there is no rename to inspect. Nothing is hidden; the code is simply new here.

### 5.2 The commit message says "the listing reads every charity for now", the design document says otherwise

The message says it plainly, and D-042 records it as a formal, temporary departure. The design document's listing section does not mention visibility at all. The *real* conflict is with decision D-038, which made the visibility switch the public gate. So this is a code-versus-decision disagreement with a written, dated, reversible resolution — not a code-versus-message disagreement. See section 8.5.

### 5.3 `per_page` in the web address, `page_size` in the code

The design document is internally inconsistent here. Section 6.2.3 says the amount per page is a `per_page=` attribute in the address. Section 6.2.4, one page later, lists the address parameters and calls it `page_size`. The code picks `per_page` for the address and `page_size` for the function argument, which is the only choice that satisfies both halves. Not a defect; worth knowing so a reviewer does not "fix" one of them.

---

## 6. Reading order

Read in this order. Each file makes the next one make sense: first the shape of the data, then the thing that fetches it, then the rules, then the page, then the wiring, then the proof.

| # | file | what it is |
|---|---|---|
| 1 | `apps/charities/contracts.py` | **new** — the plain bundles the page is allowed to see: cards and labels |
| 2 | `apps/charities/repositories.py` | **new** — the only code that asks the database for charities |
| 3 | `apps/charities/services.py` | **added to** — the paging and ordering rules, appended below the existing publish/hide functions |
| 4 | `apps/charities/views.py` | **new** — reads the visitor's page request and renders the page |
| 5 | `apps/charities/urls.py` | **filled in** — `/charity/` now points at the view |
| 6 | `apps/charities/templates/charities/listing.html` | **new** — the page itself |
| 7 | `static/css/site.css` | **added to** — how the cards and page links look |
| 8 | `templates/base.html` | **one line** — the shared frame now loads the style sheet |
| 9 | `config/urls.py` | **changed** — the front page redirects to `/charity/` |
| 10 | `config/settings/prod.py` | **added to** — refuse to start production with a placeholder secret |
| 11 | `docs/DECISIONS.md` | **added to** — D-042, the written note about the visibility switch |
| 12 | `README.md`, `CLAUDE.md` | **added to** — how the listing is arranged, and a rule about the design document |
| 13 | `static/charities/img/charity-01.svg` … `-12.svg` | **new** — twelve stand-in pictures |

**The shape of the whole change in one sentence:** a page asks a rules-object for a screenful, the rules-object asks the repository for cards, the repository is the only thing that touches the database, and the visibility switch is ignored on purpose with a numbered note to prove it was deliberate.

---

## 7. One section per file

### `apps/charities/contracts.py` — **the plain bundles the page is allowed to see**

This file is new, and it is 32 lines long. It defines three small record types — a charity card, and two kinds of label — that hold exactly the facts a single row on the page needs, and nothing else. They carry no database behaviour at all, which is what makes the page unable to accidentally depend on how the data was fetched.

Why anyone wanted this. The obvious way to build a listing is to hand the web page raw database records and let the page reach into them. That works, and it is what most projects do. The problem arrives six months later, when the page has quietly grown a dependency on a database detail — say, that a charity's labels always arrive pre-sorted, or that a related object can be assumed to exist. Now the database structure cannot change without breaking the page, even though the two things have nothing to do with each other.

A card breaks that link. The page is handed a finished bundle of facts. It cannot reach back through it to the database, because there is nothing to reach through.

**The card, newly added** — what one row on the page is built from. Five facts, plus the charity's number, plus its labels as plain lists that the page can loop over.

```python
# apps/charities/contracts.py:23-32 — new in this change
@dataclass(frozen=True)
class CharityCard:
    """What the listing shows for one charity."""

    id: int
    name: str
    tagline: str
    image: str
    domains: tuple[DomainTag, ...]
    locations: tuple[LocationTag, ...]
```

`frozen=True` means the bundle cannot be modified after it is made. That is a small extra guarantee: nothing can hand a card to the page and then change it underneath.

**The two labels, also new** — a domain is what the charity does, a location is where it works. Both are a single word wrapped in a named type, so that a domain name and a location name cannot be passed to the wrong place by accident.

```python
# apps/charities/contracts.py:13-20 — new in this change
@dataclass(frozen=True)
class DomainTag:
    name: str


@dataclass(frozen=True)
class LocationTag:
    name: str
```

**What that buys.** The page can be written and reviewed against six named facts. If the database later moves a charity's picture out of the charity table into its own table, this file absorbs the change and the page does not notice. There is no way for the template to issue a database query, because a card has no way to ask one.

---

### `apps/charities/repositories.py` — **the only code that asks the database for charities, and the place the visibility switch is documented**

Also new, 71 lines. It contains two things: a short written job description for "the thing that reads charities", and the one real implementation of that job, which talks to the project database. This is the file that decides which charities the listing is allowed to see.

Why anyone wanted it. "Which charities may I show?" is a question that will be asked by the listing, by the search box, by the recommendation engine and by the dashboard. If each of those writes its own database question, the answer drifts. One reader, one answer. The second reason is testability: the paging rules can be tested against a pretend reader that returns made-up cards, with no database involved at all.

**The job description, newly added** — two jobs, named so that anything claiming to be a charity reader must provide both. A "protocol" is Python's word for a job description that does not need to be formally inherited; anything shaped like it qualifies.

```python
# apps/charities/repositories.py:18-27 — new in this change
class CharityRepository(Protocol):
    """Read access to charities, in the terms the listing needs."""

    def page(self, offset: int, limit: int) -> tuple[CharityCard, ...]:
        """Return cards for the given window, ordered by name."""
        ...

    def count(self) -> int:
        """Return the total number of charities."""
        ...
```

`offset` means "skip this many" and `limit` means "give me at most this many". Those two numbers are how a window into a long list is expressed, and they are why the listing can show page 3 without loading pages 1 and 2.

**The implementation, and the note that matters most** — the class docstring is the argument for ignoring the visibility switch, written where the next reader will find it.

```python
# apps/charities/repositories.py:30-42 — new in this change
class DjangoCharityRepository:
    """Reads charities from the project database.

    D-038 makes `is_visible` the public visibility switch: the listing reads it
    and never touches the approvals tables. Nothing publishes a charity yet
    (the admin approval queue is still to come), so every row is hidden and a
    filtered listing would render empty. `published_only` is therefore off by
    default and the caller flips it when the queue starts publishing. See
    D-042.
    """

    def __init__(self, *, published_only: bool = False) -> None:
        self.published_only = published_only
```

`published_only=False` in the default is the whole of the temporary exception. One word, in one constructor, where the next person will trip over it. The keyword-only star (`*`) means a caller must write `published_only=True` explicitly — it cannot be passed positionally by mistake.

**The question the listing asks, newly added** — normally every charity; if the switch is being obeyed, only the visible ones. This is the single place where "which charities may I show" is answered.

```python
# apps/charities/repositories.py:44-49 — new in this change
    def _rows(self) -> QuerySet[Charity]:
        """The charities the listing may show."""
        rows = Charity.objects.all()
        if self.published_only:
            rows = rows.filter(is_visible=True)
        return rows
```

**Fetching one window, newly added** — take the allowed charities, fetch their labels in two extra batched questions rather than one question per charity, sort by name, then cut out the requested slice.

```python
# apps/charities/repositories.py:51-57 — new in this change
    def page(self, offset: int, limit: int) -> tuple[CharityCard, ...]:
        rows = (
            self._rows()
            .prefetch_related("domains", "locations")
            .order_by("name")[offset : offset + limit]
        )
        return tuple(self._to_card(row) for row in rows)
```

`prefetch_related` is the load-bearing word. Without it, showing twenty charities each with three labels would ask the database sixty-one times — once for the charities, then three times per charity. With it, it asks three times in total. A test in section 9 pins this, so the batching cannot be removed by accident.

**The total count, newly added** — how many charities there are in total, needed to work out how many pages exist.

```python
# apps/charities/repositories.py:59-60 — new in this change
    def count(self) -> int:
        return self._rows().count()
```

Note that it counts the same allowed set that `page` reads, so the two can never disagree about what is in scope.

**Converting a stored row into a card, newly added** — the one place where database records become the plain bundles the page is allowed to see.

```python
# apps/charities/repositories.py:62-71 — new in this change
    @staticmethod
    def _to_card(row: Charity) -> CharityCard:
        return CharityCard(
            id=row.id,
            name=row.name,
            tagline=row.tagline,
            image=row.image,
            domains=tuple(DomainTag(name=d.name) for d in row.domains.all()),
            locations=tuple(LocationTag(name=loc.name) for loc in row.locations.all()),
        )
```

This is the boundary. Everything above it is database; everything below it is plain facts.

**What that buys.** The listing, and every feature after it, has exactly one way to ask for charities. Testing the paging rules needs no database. And the visibility question is answered in a method that is eight lines long, in a file whose docstring explains why the answer is currently "show everything".

---

### `apps/charities/services.py` — **added to: the paging and ordering rules, sitting below the existing publish/hide functions**

This file already existed and already held the app's two publishing functions. This change appends a second concern to it: the rules that turn "the visitor asked for page 3, fifty per screen" into a finished screenful with working links. The two concerns share a file because this is the app's public interface — the rules other apps are allowed to call.

Why anyone wanted the rules separated from the fetching. Paging rules are pure arithmetic, and arithmetic is where off-by-one errors live. Keeping them away from the database means they can be tested exhaustively in milliseconds, against a pretend reader, with no database running at all.

**Nothing in the existing publish/hide code changed.** Lines 18 to 38 are identical before and after; the diff only adds lines below them. The change to that file is purely additive, which is worth confirming once so nobody hunts for a modification that is not there.

**Three constants, newly added** — the default screenful and the ceiling the server will agree to.

```python
# apps/charities/services.py:45-46 — new in this change
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
```

**Counting pages, newly added** — how many screens a given number of charities needs, with a floor of one so that an empty list still has a page 1.

```python
# apps/charities/services.py:49-51 — new in this change
def page_count(total: int, size: int) -> int:
    """Pages needed for `total` rows; at least one, so a page always exists."""
    return max(1, -(-total // size))
```

The `-(-total // size)` is integer division that rounds up rather than down. 41 charities at 20 per screen needs 3 pages; plain division would say 2 and lose the last charity. The `max(1, ...)` handles the empty list: zero charities is one page containing the message "No charities found", not zero pages.

**One screenful, newly added** — a bundle holding the cards, the total, which page this is, and how big a screenful is. Plus the derived answers the page needs: whether there is a previous or next, and what web address reaches them.

```python
# apps/charities/services.py:54-66 — new in this change
@dataclass(frozen=True)
class Page:
    """One page of results, plus the links needed to move between pages."""

    items: tuple[CharityCard, ...]
    total: int
    number: int
    size: int

    @property
    def page_count(self) -> int:
        return page_count(self.total, self.size)
```

**The two questions the paging bar asks, newly added** — is there a screen before this one, and is there one after it.

```python
# apps/charities/services.py:67-73 — new in this change
    @property
    def has_previous(self) -> bool:
        return self.number > 1

    @property
    def has_next(self) -> bool:
        return self.number < self.page_count
```

A "property" is a value the page reads like a plain fact, but which the code computes on demand. The page asks `page.has_next` and gets an answer; it never does arithmetic itself.

**Building the web address for another page, newly added** — the bit after the question mark in a web address, called the query string, that reaches a given page while keeping the visitor's chosen screenful.

```python
# apps/charities/services.py:75-85 — new in this change
    def query(self, number: int) -> str:
        """Query string for another page of this same result set."""
        return urlencode({"page": number, "per_page": self.size})

    @property
    def previous_query(self) -> str:
        return self.query(self.number - 1)

    @property
    def next_query(self) -> str:
        return self.query(self.number + 1)
```

`urlencode` is the standard function that escapes values for a web address. Doing it here, in one place, is why the page's links are correctly escaped. There is a test that specifically catches double-escaping, which is the classic version of this bug: `per_page=2` arriving as `amp;amp;per_page=2`.

**The page numbers to display, newly added** — a window of page numbers around the current one, clipped so it never offers page 0 or a page past the end.

```python
# apps/charities/services.py:87-91 — new in this change
    def numbers(self, window: int = 2) -> list[tuple[int, str]]:
        """(page number, query string) pairs to render as links."""
        first = max(1, self.number - window)
        last = min(self.page_count, self.number + window)
        return [(n, self.query(n)) for n in range(first, last + 1)]
```

On page 5 of 9 this offers pages 3 through 7. On page 1 it offers 1, 2 and 3 — the `max(1, ...)` clips the left edge. Both clips have their own test.

**Bounding the requested screenful, newly added** — a visitor may ask for any number; the server agrees to between 1 and 100.

```python
# apps/charities/services.py:94-98 — new in this change
def clamp_page_size(requested: int | None) -> int:
    """Bound a requested page size to a range the server is willing to serve."""
    if requested is None:
        return DEFAULT_PAGE_SIZE
    return max(1, min(requested, MAX_PAGE_SIZE))
```

"Clamp" means to squash a value into an allowed range. Asking for 5,000 per screen gives you 100. Asking for 0 or a negative gives you 1. Asking for nothing gives the default 20. Without the ceiling, one visitor could ask for a million rows and make the server build a page nobody will read.

**The whole job, newly added** — the function the page calls. It works out the size, the total, the real page number, and the offset, then asks the repository for exactly one window.

```python
# apps/charities/services.py:101-118 — new in this change
def list_charities(
    repository: CharityRepository,
    page: int | None = 1,
    page_size: int | None = None,
) -> Page:
    """Return one page of charities, alphabetically by name."""
    size = clamp_page_size(page_size)
    total = repository.count()
    count = page_count(total, size)
    number = max(1, min(page or 1, count))
    offset = (number - 1) * size

    return Page(
        items=repository.page(offset=offset, limit=size),
        total=total,
        number=number,
        size=size,
    )
```

The reader is passed in rather than created here. That is what lets the tests hand it a pretend reader. The line `number = max(1, min(page or 1, count))` is the clamping of the page number: page 0 becomes 1, page 99 of 3 becomes 3, and a missing page becomes 1.

**What that buys.** Every awkward address a visitor can type is handled in one place: nonsense page numbers, zero, past-the-end, absurd screen sizes. The page template never does arithmetic. And the arithmetic is proved correct by tests that need no database.

---

### `apps/charities/views.py` — **new: the page logic that reads the visitor's request and hands back a rendered page**

This file was empty before this change — it existed, with zero bytes, as a placeholder in the skeleton. It now holds two functions: a small helper that reads a whole number from the web address and shrugs off nonsense, and the view that builds the screenful and renders it.

Why anyone wanted it. Something has to translate a browser's request — the text after the `?` in the address — into the arguments the paging rules expect. That translation is where junk from the outside world arrives, so it deserves its own small, tested function.

**Before**, the file was an empty placeholder. Quoting it is quick:

```python
# apps/charities/views.py — before (base commit 0eeb207)
# (empty file)
```

**Reading an optional whole number from the address, newly added** — three outcomes: nothing was asked for, something sensible was asked for, or junk was asked for. Junk and nothing are treated alike, so a visitor who types `?page=abc` sees the first page rather than an error.

```python
# apps/charities/views.py:12-20 — new in this change
def _positive_int(raw: str | None) -> int | None:
    """Read an optional positive whole number, treating junk as absent."""
    if raw is None:
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    return value if value > 0 else None
```

Note the deliberate refusal to distinguish "junk" from "absent". Both become `None`, and `None` later becomes the default. An error page for a mistyped web address would be a worse experience than quietly showing page 1, and it would be an easy way to make the site fall over.

**The view itself, newly added** — build the reader, read the two numbers out of the address, ask the rules for one screenful, render the page with it.

```python
# apps/charities/views.py:23-32 — new in this change
def listing(request: HttpRequest) -> HttpResponse:
    """Render the paginated list of charities."""
    page: Page = list_charities(
        # published_only stays False until the admin approval queue publishes
        # charities; see D-042.
        repository=DjangoCharityRepository(published_only=False),
        page=_positive_int(request.GET.get("page")),
        page_size=_positive_int(request.GET.get("per_page")),
    )
    return render(request, "charities/listing.html", {"page": page})
```

Three things are worth pointing at. First, `published_only=False` is written out explicitly, with a comment, rather than left to the default — so the temporary exception is visible at the exact line where the listing is assembled, not only buried in the repository. Second, the address parameter is `per_page` while the function argument is `page_size`; that mismatch is deliberate, and section 5.3 explains why. Third, the view passes only one name into the page: `page`. The template receives the screenful bundle and nothing else, which is a narrow, easily reviewed surface.

**What that buys.** A visitor can type anything into the address bar and the site still shows a page. The temporary visibility exception is legible at the call site. And the template cannot see the database, because it is handed a finished bundle.

---

### `apps/charities/urls.py` — **filled in: `/charity/` now points at the listing instead of nowhere**

This file is the app's address table: a list mapping web addresses to the code that answers them. It existed in the skeleton with an empty list and a comment excusing an unused import.

Why anyone wanted it. An address table with no entries means the app has no reachable pages. This is the file that ends that.

**Before** — an empty table and a suppression comment standing in for content:

```python
# apps/charities/urls.py — before (base commit 0eeb207)
from django.urls import path  # noqa: F401

app_name = "charities"

urlpatterns = []
```

The `# noqa: F401` comment tells the code checker "yes, this import is unused, ignore it". Its whole purpose was to keep the file lintable while it did nothing.

**After** — one real entry, and the suppression is gone because the import is now used:

```python
# apps/charities/urls.py — after (head of charity_list)
"""URL table for the charities app."""

from django.urls import path

from . import views

app_name = "charities"

urlpatterns = [
    path("", views.listing, name="listing"),
]
```

The empty string means "the app's own prefix, with nothing after it", which combined with the mounting in section 7's `config/urls.py` gives `/charity/`. `name="listing"` gives the address a nickname other code can refer to, so a later change to the address does not have to hunt down every hard-coded link.

**What that buys.** The charities app has a page. The lint suppression that existed only to excuse an empty file is gone, which is a small honest win: the file no longer lies about being finished.

---

### `apps/charities/templates/charities/listing.html` — **new: the page itself, one card per charity plus the paging controls**

115 lines of markup. It is the page a visitor actually sees: a heading, a per-page control, a list of charity cards, and a row of page links at the bottom. It inherits the shared frame from `templates/base.html`, so the navigation bar is not repeated here.

Why anyone wanted it. The three files above exist so that this file can be simple. Everything it does is read named facts off the bundle it was handed and print them.

**It builds on the shared frame** — the first line says this page plugs into the site's outer frame rather than being a page of its own.

```html
{# apps/charities/templates/charities/listing.html:1-4 #}
{% extends "base.html" %}
{% load static %}

{% block title %}Charities &middot; MaaserMart{% endblock %}
```

**The per-page control, newly added** — a small form with a number box, showing the current screenful, so the visitor can ask for a different one. It carries the current page number along as a hidden field when the visitor is past page 1.

```html
{# apps/charities/templates/charities/listing.html:11-27 #}
      <form class="per-page" method="get">
        {% if page.number > 1 %}
          <input type="hidden" name="page" value="1">
        {% endif %}
        <label class="per-page__label" for="per-page">Per page</label>
        <input
          class="per-page__input"
          id="per-page"
          name="per_page"
          type="number"
          inputmode="numeric"
          min="1"
          max="100"
          value="{{ page.size }}"
        >
        <button class="per-page__submit" type="submit">Go</button>
      </form>
```

The hidden `page` field is a deliberate reset: changing the screenful sends the visitor back to page 1, because "page 4 of the old screenful" is not a meaningful place in the new one. The `max="100"` in the markup mirrors the server's ceiling — the form is a courtesy, and the server still clamps, because markup can be edited by anyone with a browser.

**The card loop, newly added** — one list item per charity. The picture falls back to an empty grey block when a charity has none, the honest name of the charity is printed, the one-line description is printed only if there is one, and the labels are printed as small chips.

```html
{# apps/charities/templates/charities/listing.html:30-64 #}
    {% if page.items %}
      <ul class="charity-list">
        {% for charity in page.items %}
          <li>
            {# TODO(comtai): point at the charity page once that bullet exists. #}
            <a class="charity-card" href="#">
              {% if charity.image %}
                <img class="charity-card__image" src="{% static charity.image %}" alt="" width="96" height="96">
              {% else %}
                <span class="charity-card__image charity-card__image--empty" aria-hidden="true"></span>
              {% endif %}

              <span class="charity-card__body">
                <span class="charity-card__name">{{ charity.name }}</span>

                {% if charity.tagline %}
                  <span class="charity-card__tagline">{{ charity.tagline }}</span>
                {% endif %}
```

The `href="#"` and the `TODO(comtai)` marker on line 34 are the clearest admission in the change: clicking a charity does nothing yet, and the marker is filed as a tracked task rather than a comment that rots. The `alt=""` on the picture is deliberate, not lazy — the charity's name is printed as text right beside it, so describing the picture again would make a screen reader (the software a blind visitor uses to hear a page) repeat itself.

**The labels and the divider between them, newly added** — what the charity does, then a vertical divider, then where it works. The divider appears only when there are labels on both sides of it.

```html
{# apps/charities/templates/charities/listing.html:49-61 #}
                <span class="charity-card__meta">
                  {% for domain in charity.domains %}
                    <span class="chip">{{ domain.name }}</span>
                  {% endfor %}

                  {% if charity.domains and charity.locations %}
                    <span class="chip-divider" role="separator" aria-orientation="vertical"></span>
                  {% endif %}

                  {% for location in charity.locations %}
                    <span class="chip chip--location">{{ location.name }}</span>
                  {% endfor %}
                </span>
```

The condition `{% if charity.domains and charity.locations %}` is what stops a stray floating divider beside a charity that only has one kind of label. Two tests pin it, in both directions.

**The paging bar, newly added** — previous and next links, a window of page numbers with the current one marked, and a "go to" box. It is hidden entirely when there is only one page.

```html
{# apps/charities/templates/charities/listing.html:68-93 #}
      {% if page.page_count > 1 %}
        <nav class="pagination" aria-label="Pagination">
          {% if page.has_previous %}
            <a class="pagination__step" href="?{{ page.previous_query }}" rel="prev">&larr; Prev</a>
          {% else %}
            <span class="pagination__step" aria-disabled="true">&larr; Prev</span>
          {% endif %}

          <ul class="pagination__pages">
            {% for number, query in page.numbers %}
              <li class="pagination__item">
                {% if number == page.number %}
                  <span class="pagination__page pagination__page--current" aria-current="page">{{ number }}</span>
                {% else %}
                  <a class="pagination__page" href="?{{ query }}">{{ number }}</a>
                {% endif %}
              </li>
            {% endfor %}
          </ul>
```

On the first page, "Prev" is a non-clickable span rather than a link, so it cannot send anyone to page 0. The `aria-` labels throughout are notes for screen readers — the software a blind visitor uses to hear a page — saying things like "this step is disabled" or "this is the page you are on", which a sighted visitor gets from the styling instead. The page numbers come pre-built and pre-escaped from `Page.numbers()`, which is why no arithmetic appears in the markup.

**The empty case, newly added** — when there are no charities at all, one plain sentence instead of an empty list.

```html
{# apps/charities/templates/charities/listing.html:111-113 #}
    {% else %}
      <p class="empty">No charities found.</p>
    {% endif %}
```

The design document asks for exactly this: "No charities returned — a message saying no charities found."

**What that buys.** A visitor sees charities, can move between screens, can choose how many per screen, and is told plainly when there are none. Every value printed comes from the card bundle, so the page cannot reach the database.

---

### `static/css/site.css` — **added to: 204 lines of styling for the cards, chips and paging bar**

This file already existed for the site's base look. This change appends a styling section for the listing: a centred column, bordered card rows with a hover state, small rounded labels, and the paging bar's layout.

Why anyone wanted it. Unstyled markup renders as a column of raw text and default-blue links. It would "work" and be unusable. The styling is what turns a list of facts into rows a person can scan.

**The card row, newly added** — a bordered rounded box, laid out horizontally, with the picture at a fixed size on the left and the text flowing beside it.

```css
/* static/css/site.css:34-43 — new in this change */
.charity-card {
  align-items: flex-start;
  border: 1px solid #ddd;
  border-radius: 0.5rem;
  color: inherit;
  display: flex;
  gap: 1rem;
  padding: 0.75rem;
  text-decoration: none;
}
```

`color: inherit` and `text-decoration: none` are the two lines that make a whole card look clickable without turning the entire row blue and underlined. The hover state beneath it is what confirms the card is a target:

```css
/* static/css/site.css:45-49 — new in this change */
.charity-card:hover,
.charity-card:focus-visible {
  background: #f7f7f7;
  border-color: #bbb;
}
```

`focus-visible` matters: it gives keyboard users the same confirmation that mouse users get. A card that highlights on hover but not on keyboard focus is a card a keyboard user cannot see they have reached.

**The picture** — a fixed square either way, so rows line up whether or not a charity has a photo. Sizes here are in `rem`, a unit that means "the width of one letter" and so scales with the reader's own text-size setting rather than being frozen at a pixel count.

```css
/* static/css/site.css:51-57 — new in this change */
.charity-card__image {
  border-radius: 0.375rem;
  flex: 0 0 6rem;
  height: 6rem;
  object-fit: cover;
  width: 6rem;
}
```

**And the grey block shown when a charity has no picture at all**, newly added — the same six-rem square, so the rows still line up.

```css
/* static/css/site.css:59-60 — new in this change */
.charity-card__image--empty {
  background: #eee;
```

`flex: 0 0 6rem` means "never grow, never shrink, always six rem". Without the shrink-proofing, a long charity name would squash the picture into a sliver. `object-fit: cover` crops a non-square photo instead of distorting it.

**What that buys.** Rows a person can scan, a consistent grid whether or not pictures exist, and a hover/focus state that tells everyone — mouse or keyboard — that a card is clickable.

---

### `templates/base.html` — **one added line: the shared frame now loads the listing's stylesheet**

This file is the outer frame every page on the site plugs into: the page head, the script tags, and the navigation bar. It changed by exactly one line.

Why anyone wanted it. The style sheet was being shipped but never loaded, because the frame that every page inherits did not reference it. The listing's 204 lines of styling would have been invisible without this.

**Before and after, in full** — the single inserted line.

```html
<!-- templates/base.html:7 — before -->
  <title>{% block title %}MaaserMart{% endblock %}</title>
  <script src="{% static 'vendor/htmx-2.0.4.min.js' %}"></script>
```

**After**, with the style sheet loaded on the line above the scripts so styling is ready before the page draws:

```html
<!-- templates/base.html:7-8 — after -->
  <title>{% block title %}MaaserMart{% endblock %}</title>
  <link rel="stylesheet" href="{% static 'css/site.css' %}">
  <script src="{% static 'vendor/htmx-2.0.4.min.js' %}"></script>
```

**What that buys.** Every page on the site is now styled, including the listing. One line, and the styling written for it becomes real.

---

### `config/urls.py` — **changed: the front page redirects to `/charity/` instead of serving a placeholder**

This is the site's top-level address table. It decides what the bare `maasermart.com` address does, and which prefix belongs to which app.

Why anyone wanted it. Before this change, `maasermart.com` served `home.html`, a six-line placeholder with no content. With a real listing built, sending visitors to the placeholder is sending them to the wrong door — and the design document says the landing page shows the listing.

**Before** — the front page rendered a placeholder template:

```python
# config/urls.py — before (base commit 0eeb207)
from django.contrib import admin
from django.urls import path
from django.views.generic import TemplateView

urlpatterns = [
    path("", TemplateView.as_view(template_name="home.html"), name="home"),
    path("django-admin/", admin.site.urls),
]
```

**After** — the front page redirects, and the charities app is mounted at `/charity/`:

```python
# config/urls.py — after (head of charity_list)
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    # D-028: the listing is the front page; `/` redirects to it while home.html is unused.
    path("", RedirectView.as_view(url="/charity/", permanent=False), name="home"),
    path("charity/", include("apps.charities.urls")),
    path("django-admin/", admin.site.urls),
]
```

Two details. `permanent=False` means the redirect is marked temporary (`302`, not `301`), so browsers will not cache it forever — important, because once `home.html` becomes a real marketing page, this needs to change back and a cached permanent redirect would follow visitors around. The comment names the decision, D-028, that put the redirect here.

**What that buys.** Typing the site's address lands a visitor on the charity list, which is what the design document says the landing page is. And the charities app is reachable at last.

---

### `config/settings/prod.py` — **added to: refuse to start production with a placeholder secret**

This is the file that configures the site for the live server. This change adds an eight-line guard at the top of it.

Why anyone wanted it. A Django site has a secret key used to sign login sessions and forms. The project ships a development placeholder for that key so laptops work out of the box. If that placeholder ever reached production, anyone who has read the source code could forge a login session for any account, including administrators. This is not a theoretical risk; it is the single most common way a Django site gets taken over.

**The guard, newly added** — refuse to boot if the key is the placeholder or is too short, and refuse to boot with no allowed host names set.

```python
# config/settings/prod.py:10-16 — new in this change
# Refuse to boot with a development secret or no allowed hosts. Checked here,
# in production settings only, so local and test runs are unaffected.
_INSECURE_KEY = "insecure-development-key-change-me"
if SECRET_KEY == _INSECURE_KEY or len(SECRET_KEY) < 32:  # noqa: F405
    raise RuntimeError("DJANGO_SECRET_KEY must be a real secret (32+ chars) in production.")
if not ALLOWED_HOSTS:  # noqa: F405
    raise RuntimeError("DJANGO_ALLOWED_HOSTS must be set in production.")
```

The guard lives in the production settings file and nowhere else. That placement is the whole design: a developer's laptop and the test suite keep working with the placeholder, while a production boot with it fails loudly at startup, before any visitor arrives. Failing at boot is the cheapest possible failure — the alternative is a site that starts fine and is quietly compromised.

This is a port of a guard that existed in the earlier prototype's settings file. It arrives here because the skeleton's production settings did not have it yet.

**What that buys.** A misconfigured production deployment stops at startup with a sentence explaining what is missing, instead of going live with a secret taken from the source code.

---

### `docs/DECISIONS.md` — **added to: D-042, the written note that makes ignoring the visibility switch legitimate**

This is the company's decision log. The project's rules say that when code disagrees with the customer's design document, a numbered entry here is the authority. This change adds entry D-042.

Why anyone wanted it. The listing ignores the visibility switch, and that is a temporary, deliberate exception. An exception that lives only in code comments is an exception that a future reader will "fix" and thereby break the demo, or else silently keep for years. The decision log is where it becomes a decision with a date, a reason, and an exit.

**The entry, newly added in full** — the argument, the reason, and the one-word reversal:

```markdown
## D-042: The listing shows every charity until something can publish one

- Date: 2026-11-12
- Decided by: builder, pending CEO/COO confirmation
- Status: Active
- Design doc ref: §6.2.3
- Decision: `charities.repositories.DjangoCharityRepository` takes `published_only`, default `False`, so the listing reads all charities. It flips to `True` when the admin approval queue lands, since that queue is what calls `publish_charity` (D-038). The option is a constructor argument, not a setting or a class attribute, so the behaviour is explicit at the call site and testable in both directions.
- Why: D-038 makes `is_visible` the visibility switch and gives every charity `False` by default. Nothing calls `publish_charity` yet, because the admin approval queue is not built. Reading `is_visible` literally would render an empty listing and make the tracer bullet unverifiable. This is a deliberate, temporary departure from D-038 and it is undone by one argument when the queue exists.
- Where in code: `apps/charities/repositories.py` (`published_only`), `apps/charities/views.py` (`listing`)
```

Note "Decided by: builder, pending CEO/COO confirmation". The entry is honest that it is not yet signed off by the people who own the product. That is the correct way to record a temporary call, and it is the item a reviewer should actually act on.

**What that buys.** The exception is dated, reasoned, attributed, and has a stated exit condition. A future reader who wants to obey the visibility switch finds the argument for why that is not yet possible, in writing, one `git grep D-042` away.

---

### `README.md` and `CLAUDE.md` — **added to: how the listing is arranged, and a rule about the design document**

Two documentation files gained short sections. `README.md` is the human's guide to running the project; `CLAUDE.md` is the instruction file for whoever — human or AI — writes the next piece of code.

Why anyone wanted it. The listing is split across four files on purpose, and that split is not obvious to someone arriving fresh. A short map saves them rediscovering it. Separately, the design document lives in the repo as a Word file belonging to the customer, and someone needs to be told not to edit it.

**The map, newly added to the README** — four bullet points naming the four layers, plus the visibility caveat:

```markdown
## The charity listing

The listing lives in `apps/charities/` and is split into four layers, each with its own tests:

- `contracts.py` — plain read models (`CharityCard`, `DomainTag`, `LocationTag`). No ORM behaviour, so the template cannot depend on how rows were fetched.
- `repositories.py` — `CharityRepository` protocol and `DjangoCharityRepository`, the only code that queries Postgres.
- `services.py` — the listing rules (order, page clamping, page size) plus `publish_charity` / `hide_charity` (D-038).
- `views.py` / `urls.py` — `GET /charity/` takes `page` and `per_page`, clamping both.

The listing currently shows every charity, including unpublished ones. Nothing publishes a charity yet, so reading `is_visible` would render an empty page; see D-042 for why, and what flips it back.
```

**The rule, newly added to `CLAUDE.md`** — one line telling future contributors the Word documents are read-only:

```markdown
- The design doc (docs/design.docx, docs/requirements.docx) is the customer's document. Never edit it, and never edit any .docx, without asking the human first. Record changes as a D-entry in docs/DECISIONS.md instead.
```

The README also changed one line to record the redirect:

```markdown
Open http://localhost:8000. `/` redirects to the charity listing at `/charity/` (D-028). …
```

**What that buys.** A new contributor learns the four-layer split in thirty seconds instead of reverse-engineering it, and nobody edits the customer's document by accident.

---

### `static/charities/img/charity-01.svg` … `charity-12.svg` — **new: twelve stand-in pictures**

Twelve small vector images, seven lines each, all identical in shape. They exist so the listing has something to display before real charity photographs are uploaded.

Why anyone wanted them. An empty grey box where every picture should be makes it impossible to tell a styling bug from missing data. Sample images make a layout problem visible as a layout problem.

They are vector images — pictures stored as drawing instructions rather than dots, so they stay sharp at any size and weigh almost nothing. They are addressable by name from a charity's `image` field, and the listing's test suite refers to `charity-01.svg` by name, so they are also the fixture the picture test depends on.

**What that buys.** The picture path — from a database field, through the card, through `{% static %}`, to a file on disk — is exercised end to end by a real file, not a mock.

---

## 8. Departures from the design document

*This section is not part of the standard walkthrough. It was added on request.*

The design document is the customer's description of what the product should be. It is a Word file in `docs/`, and the project's rules say it is never edited. When the code needs to do something differently, the difference is written up as a numbered entry in `docs/DECISIONS.md` instead. That is the mechanism this section checks.

The relevant section of the design document is **§6.2.3 Charity List**. Its specification for the listing, in the customer's own terms, is:

- **Address:** `/listing/`, with the page number as a `page=` attribute and the amount per page as a `per_page=` attribute
- **Permissions:** open to everyone
- **Models read:** `CHARITY`, `REVIEW`, `NEW_CHARITY_REQUEST`, `APPROVAL_REQUEST`; writes none
- **Service function:** `charities.services.list_charities(filters, sort, page, page_size, search)` returning `(items, total)`, "by default returned in alphabetical order"
- **View:** "holds a variable holding amount of items per page", sent along with the page number
- **Template:** `Listing_Page`, "a page similar to amazon's product page", rows one per charity
- **Failure path:** "No charities returned — a message saying no charities found"
- **Tests:** a unit test of `list_charities`' default run, plus a black-box test that users reach the page, set different page amounts and cycle between pages

Here is every place this change differs from that, with what authorises the difference and what it costs.

### 8.1 The address is `/charity/`, not `/listing/`

The design document says `/listing/`. The code serves `/charity/`, and the site's front page redirects there.

**Authorised by:** D-009 (every app's pages live under the app's own hyphenated prefix) and D-028 (the listing is the front page while `home.html` is unused). Both predate this change.

**Why it is the better reading:** the design document's own later sections are inconsistent about this. §6.2.3 says `/listing/`, while §7.2's navigation tab is called "charity listing" and sits alongside `/charity/add/` and `/charity/<id>/`. Putting the listing itself at `/charity/` keeps the charity family of addresses together rather than giving the list one address and its siblings another.

**Cost if it is wrong:** one line in `config/urls.py`. Nothing else refers to the address except tests and the navigation bar.

**Judged:** a departure, formally recorded, low cost, and arguably what the customer meant.

### 8.2 The service function's signature is much smaller than specified

The design document specifies `list_charities(filters, sort, page, page_size, search)`. The code implements `list_charities(repository, page, page_size)`.

Three of the five specified arguments — filters, sort and search — are absent. They are absent because the design document defines each as its own separate feature: §6.2.4 Filter, §6.2.5 Sort, §6.2.6 Search. Building them here would be building four features in one change, which the project's rules forbid.

The shape changed in a second way that is not just subtraction. The function takes a `repository` argument the design document does not mention, and it returns a `Page` bundle rather than the `(items, total)` pair the document specifies. The `Page` bundle carries the same two facts and adds the links between screens, so the template does no arithmetic.

**Authorised by:** nothing explicit. This is an ordinary consequence of building one feature at a time, and the alphabetical default the document asks for is what the code does.

**Cost if it is wrong:** adding filters, sort and search later means changing this function's signature and every caller. There is exactly one caller today.

**Judged:** a deliberate gap rather than a contradiction, but a reviewer should ask whether the final signature will still fit when the three missing words arrive.

### 8.3 The listing reads only charities, not reviews or approval requests

The design document says the listing reads four things: `CHARITY`, `REVIEW`, `NEW_CHARITY_REQUEST`, `APPROVAL_REQUEST`. The code reads charities, plus their domain and location labels, and nothing else.

The reviews are absent because nothing on the card shows a rating — ratings exist to support the rating filters in §6.2.4, which are not built. The approval records are absent because the approval queue is not built and the listing does not consult it at all (see 8.5).

**Authorised by:** the same incremental reasoning as 8.2, plus D-038, which deliberately makes the listing read the visibility switch rather than any approvals table. D-038 is the stronger authority here: it explicitly forbids the listing from touching approval records.

**Cost if it is wrong:** none now. When ratings appear on cards, the repository gains a second query.

**Judged:** correct for now, and the D-038 reasoning is the interesting part — the customer's design had the listing consult the approvals tables, and the project deliberately moved that responsibility onto a single switch on the charity itself.

### 8.4 Two layers exist that the design document does not describe

The code splits the listing into `contracts.py` (plain bundles) and `repositories.py` (the database reader), neither of which appears in the design document. §6.1's module responsibilities describe `services.py` as the app's interface, and this change keeps that true — other apps still call `services.py` only.

**Authorised by:** §4.4 (the product is a modular monolith, and modules should be able to change their internals) and D-006. The internal split is this app's own business; the rule constrains what crosses *between* apps, and nothing here crosses.

**Why it is worth having:** the template is handed plain bundles, so it cannot issue a query, and the paging rules can be tested with no database.

**Judged:** an addition inside one app's boundary, not a departure from anything the document requires. Worth naming so a reviewer does not look for it in the design document and conclude it is missing.

### 8.5 The listing shows charities the public may not see

This is the significant one, and it is a departure from a *project decision*, not from the design document — the design document says nothing about visibility on this page at all.

The database has a visibility switch on every charity. D-038 made that switch the gate for public display, and every charity starts with it off. Nothing currently turns it on, because the administrator's approval queue — which is what calls the publishing function — does not exist yet. A listing that obeyed the switch would therefore be empty, and an empty listing proves nothing about whether the stack works.

So the repository takes a setting, `published_only`, defaulting to **off**, and the view passes it explicitly as `False`. The listing shows every charity including hidden ones.

**Authorised by:** D-042, which records the exception, its reason, its date, its author ("pending CEO/COO confirmation"), and its exit condition.

**Cost if it is wrong — and this is the sentence a reviewer should weigh.** This is a live site with no login on the listing. If the project ships to production while `published_only` is still `False`, hidden charities become publicly browsable. The mitigation is entirely in the written record plus one explicit line at the call site; there is no runtime guard that stops the temporary behaviour reaching production. Whether that is acceptable is a judgement about process, not about code, which is why it is listed here rather than argued.

**Judged:** a deliberate, documented, reversible departure with a named exit. The one-word reversal is `published_only=True`.

### 8.6 The page-size ceiling of 100 is not in the design document

The document lets the visitor set the amount per page and puts no upper bound on it. The code clamps any request to between 1 and 100, and the form's markup mirrors that limit.

**Authorised by:** nothing explicit. It is a defensive default.

**Why it exists:** without a ceiling, one visitor can ask for a million rows per screen and make the server assemble a page nobody will read. The clamp is also what makes a hand-edited address bar harmless.

**Judged:** a hardening addition. A reviewer should ask whether 100 is the right number, and whether the customer wants the limit visible to visitors.

### 8.7 The design document disagrees with itself on `per_page` versus `page_size`

§6.2.3 says the amount per page is a `per_page=` attribute in the address. §6.2.4, one page later, lists the same address parameters and calls it `page_size`. The code uses `per_page` in the address and `page_size` as the function argument.

**Judged:** not a departure, a resolution of an ambiguity. Recorded here so the next reader does not "fix" one of the two and break the other.

### 8.8 The cards carry no rating

The design document's `Listing_Page` is "similar to amazon's product page", and its filter section offers a minimum-rating filter, which implies a rating is visible per charity. The card shows a picture, a name, a one-line description, a domain label and a location label. No rating and no review count.

**Authorised by:** no decision. It is an omission.

**Cost if it is wrong:** the card will need a ratings field and the accompanying query, which means the card shape and the repository both change. That is a small, contained change, but it is a change to the file this document says the template is not allowed to depend on.

**Judged:** a real gap against the customer's picture of the page. It belongs in the follow-up list, not in this change.

### 8.9 Clicking a charity does nothing

Each card links to `#`. The design document has the charity page as §6.2.7, a separate feature, and this change does not build it. The code marks the spot with a tracked task rather than a comment.

**Authorised by:** the feature boundary. The project builds one feature at a time.

**Judged:** correct, and honestly marked. Worth flagging only because the listing is being put in front of people, and a front page whose rows do not go anywhere invites the question.

### 8.10 What the code matches, for completeness

Not every line of the specification was departed from. These parts match exactly, and it is worth knowing which, so the reviewer's attention goes where the differences are:

- **Open to everyone.** No login required, as specified.
- **Alphabetical order by default.** The repository orders by name; the design document asks for exactly that.
- **The empty message.** "No charities found." is the specified failure path, word for word.
- **The page-number and per-page address attributes.** Both present and both honoured, as specified.
- **A black-box test that cycles pages at different page amounts.** Present, and one of the larger test groups.

### 8.11 The summary a reviewer actually needs

| # | departure | authorised by | reversible in |
|---|---|---|---|
| 8.1 | `/charity/` not `/listing/` | D-009, D-028 | one line |
| 8.2 | three of five service arguments absent | feature boundary | one function signature, one caller |
| 8.3 | no reviews or approval records read | D-038, feature boundary | adds one query |
| 8.4 | two extra internal layers | D-006, §4.4 | internal to the app |
| **8.5** | **hidden charities are shown** | **D-042, pending sign-off** | **one argument — but it can reach production** |
| 8.6 | page size capped at 100 | none, defensive | one constant |
| 8.7 | `per_page` vs `page_size` | resolves a doc inconsistency | nothing to do |
| 8.8 | no rating on cards | none, an omission | card shape plus one query |
| 8.9 | cards link to `#` | feature boundary, tracked | one attribute |

One departure is not like the others. Eight of the nine are reversible by editing a line or two in code. **8.5 is reversible in code but not in consequence** — a hidden charity that was publicly browsable for a week cannot be un-browsed. That is the item this section exists to surface, and it is the one worth a decision before the site goes public.

---

## 9. The tests

The repository's test names read as sentences, and read together they are the change's own summary of what it believes about itself. There are roughly sixty of them across five files. Grouped by what they actually prove.

### What the paging arithmetic does — `tests/unit/test_services.py`, 165 lines

These run without a database, against a pretend reader (`FakeCharityRepository`) that hands back made-up cards. That is the point of the separation described in section 7: arithmetic proved in milliseconds.

- *returns every charity alphabetically* — the default ordering the design document asks for.
- *reports no charities when none exist* — zero charities is a page, not a crash.
- *default page size is used* — the 20.
- *second page continues the ordering* — the offset is not repeating the first screen.
- *last page may be partial* — 41 charities at 20 per screen leaves a page of one, not a page of twenty with nineteen blanks.
- *first page has no previous* — the flag that stops a link to page 0.
- *page below one is clamped to the first page*, *absent page defaults to the first page*, *page past the end is clamped to the last page* — the three awkward addresses from section 7, each with its own test.
- *empty result still reports page one* — the empty list has a page 1 so the message has somewhere to render.
- *absent size falls back to the default*, *size is capped*, *size is at least one*, *size within range is kept* — the clamp, from all four sides.
- *next query carries page and size*, *previous query carries page and size* — links keep the visitor's chosen screenful.
- *page count rounds up* — the 41-at-20 case at the arithmetic level.
- *page count is one when empty*.
- *numbers window around the current page*, *clipped at the start*, *clipped at the end*, *carry a usable query string* — the window of page numbers, including both edges.

### What the database reader does — `tests/unit/test_repositories.py`, 102 lines

- *returns cards in name order* — the ordering, at the database level this time.
- *maps domains and locations* — the conversion into labels works, so the chips have something to print.
- *window skips preceding rows* — the offset really skips.
- *count matches rows*.
- *card does not leak model behaviour* — the boundary holds. This is the test that pins the argument in section 7: a card cannot be used to reach the database.
- *loads relations without extra queries* — the batching test. This is the one that keeps the listing from issuing sixty-one database questions to show twenty charities.
- *default shows every charity* and *published_only hides unpublished charities* — both settings of the visibility switch, in both directions. These two tests are what make D-042 a tested choice rather than a comment.

### What the page template can rely on — `tests/unit/test_template_contract.py`, 91 lines

The name is the point: a contract between the code and the template. If the card's shape changes, these fail.

- *every card field reaches the page* — the five facts plus the two label lists.
- *domain names render*, *location names render*.
- *card type has the attributes the template uses* — a direct check that the template's assumptions about the bundle are still true.
- *empty relations do not render a divider* — the floating-divider bug, pinned.

### What a visitor actually sees — `tests/unit/test_views.py`, 166 lines, 18 tests

These render the real page. They are the largest group, which is appropriate: this is the feature whose whole purpose is to be looked at.

- *lists charity details* — name, description, domain, location, all present in the response.
- *empty listing explains itself* — the specified "No charities found."
- *charity without tagline still renders* — a real data case; the description is optional in the database.
- *root redirects to the listing* — D-028, end to end.
- *page parameter selects a page*, *nonsense page parameter falls back to the first page*.
- *per page is capped*, *per page input shows the current size*, *per page accepts an arbitrary number* — the control works in both directions.
- *pagination links appear only when needed* — no paging bar on a single page.
- *page numbers are linked*, *jump form is present*.
- *divider sits between domain and location chips*, *no divider when a charity has no domains* — the two halves of the divider rule, checked by position in the rendered output rather than by string presence, which is the stricter version.
- *image is served from static* — the picture path end to end, which is what the twelve sample images are for.
- *next link is html escaped* — and specifically *not* double-escaped. The `amp;amp;` bug, caught by name.
- *first page has next but no previous link*, *last page has previous but no next link* — both ends of the paging bar, including that the disabled step is a span rather than a link.

### What the shared frame does — `tests/integration/test_base_template.py`, changed

One test added and three changed.

**Added:** *root redirects to the charity listing* — asserts a `302` and that the destination is exactly `/charity/`.

**Changed:** three existing tests — navigation bar contents, logged-in logout button, and nav pinned to the top — previously fetched the front page (`/`). They now fetch `/charity/`. The changed line is the same in all three:

```python
# tests/integration/test_base_template.py:13 — before
    html = client.get("/").content.decode()
```

```python
# tests/integration/test_base_template.py:21 — after (also 41 and 48)
    html = client.get("/charity/").content.decode()
```

And the new redirect test, quoted in full:

```python
# tests/integration/test_base_template.py:12-17 — new in this change
def test_root_redirects_to_the_charity_listing(client):
    """D-028: now that the listing exists, `/` redirects to it."""
    response = client.get("/")

    assert response.status_code == 302
    assert response.headers["Location"] == "/charity/"
```

That change is small and easy to skim past, but it is load-bearing. Once the front page redirects, fetching `/` returns a redirect rather than a page, so those three tests would have been asserting about a `302` response body — passing or failing for reasons that have nothing to do with the navigation bar. Pointing them at the real page keeps them honest. The alternative, following the redirect, would have left them testing two things at once.

No tests were deleted in this change.

---

## Where this leaves the change

The listing works. A visitor can reach it from the site's front page, see charities twenty at a time in alphabetical order, choose a different number per screen, and move between pages. The arithmetic behind all of that is proved without a database, the database reader is proved with one, and the page itself is checked by eighteen tests that look at what a visitor actually receives.

The one thing to carry away is 8.5. The listing deliberately shows charities the visibility switch is meant to hide, because nothing can turn that switch on yet. It is written down, dated, attributed and reversible by one word — and it is the single item in this change whose cost is measured in what has already been seen rather than in lines of code.
