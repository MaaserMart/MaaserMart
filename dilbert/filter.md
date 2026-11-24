# The filter sidebar — a walkthrough of `filter`, PR #5

*Explains pull request #5: branch `filter` at `dbb2bde`, measured against its base `full_charity_listing` at `8fb5204`. Seven commits, 17 files, 1,989 lines added, 148 removed. The base branch is not `main`; it is the branch that holds the charity listing.*

---

## 1. Read this part even if you read nothing else

MaaserMart is a website for people who give a tenth of their income to charity — that tenth is called *maaser* — and who want to find charities worth giving it to, and check them out first. The front door of the site is one long page of charities: a picture, a name, a one-line description, and a few labels saying what each charity does and where it works. That page is called the listing.

Before this change, the listing was a fixed alphabetical stack. It showed every charity, in order, and that was the only thing it could do. If you wanted a charity that works on food in Lakewood, and that other people have rated well, you had one tool: scroll and read. With hundreds of charities that tool stops working. The charity you would have given to is on page nine, and you never get there.

This change puts a panel down the left side of that page with seven questions you can ask: what cause does it work on, where does it work, which rabbi has endorsed it, what star rating does it have, how many reviews does it have, how many rabbis have endorsed it, and how many have objected to it. Answer any of them and the stack on the right shrinks to the charities that match. Answer several and it shrinks further. The answers live in the web address itself, so you can bookmark a narrowed list or send it to a friend, and the Back button does what you expect.

The second half of the change is the part that makes the panel trustworthy. Until now each charity's entry said nothing about quality. This branch makes each entry say "4.5 out of 5 (2 reviews)", or "No reviews yet" when nobody has reviewed it. That number is not decoration: it is computed from the same reviews the rating question asks about, by the same pass over the data. The printed number and the question can never disagree, because they are the same arithmetic.

The other thing worth knowing before you read further is what happens when someone types a silly rating into the web address. `?min_rating=99` used to be a question with no honest answer; now the site quietly treats it as "five stars", shows the five in the box, and prints a line beside it saying "Kept between 1 and 5; using 5." So a made-up number still gets you a sensible list, and you are told what you actually got instead of being left to wonder.

Everything below is the same idea in more detail.

---

## 2. How to read this file

This document has two complete layers. Neither is a summary of the other.

- **If you do not read code**, read the glossary, the story, and the bold one-line summary at the top of each file section. Then read the plain sentence that sits directly above every code box. Those sentences say the same thing as the box below them, so if you skip every box you lose nothing.
- **If you are reviewing the change**, the code boxes are the change itself, quoted with before and after wherever behaviour moved. You should be able to approve or reject this pull request without opening GitHub's side-by-side view of the changed lines.

Three rules:

1. **Read the glossary first.** Every term the document uses is defined there, before it is used anywhere else.
2. **Every code box is optional.** The sentence directly above each box carries the same content in plain English. That is a promise I have to keep in every single instance, and it is what lets the code be quoted generously without costing the non-reading reader anything.
3. **Each file section opens with a bold one-line summary.** Skim only those summaries and you have the shape of the whole change.

This document explains. It does not grade. There are no findings, no nitpicks, no verdict, and no recommendation. Where the pull request's own documents disagree with its code, section 5 says so and says which to trust; that is the one place the document takes a side, and it takes it on the facts, not on quality.

There is one section that is not part of the standard walkthrough: **section 9, departures from the design document.** It lists, in one place, every spot where this code does something the customer's written design does not describe, or describes differently, and what authorises each difference. It was added on request.

---

## 3. The glossary

Ten words. Each is used in the sense given here for the rest of the document.

**Charity** — an organisation a giver can give maaser to. The site stores one row per charity, with a name, a tagline, a picture, and labels.

**Listing** — the page at `/charity/` that shows charities as cards. It is the site's front door.

**Card** — the small box on the listing that holds one charity's picture, name, tagline, labels and, as of this change, its rating.

**Filter** — a question you ask the listing so that it keeps only some charities. "Show me only food charities" is a filter.

**Filter group** — one question in the left-hand panel, with one way of answering it. There are seven groups; each is either a set of tick boxes or a single number box.

**Tick-box group** — a filter group you can answer with more than one choice at once, by ticking boxes. Ticking two causes means "either one", not "both at once". In the code these are called *repeatable* groups, because the same name appears in the web address more than once.

**Number box** — a filter group you answer with one whole number, such as "at least 4 stars".

**Star rating** — the average of a charity's review scores, on a scale of 1 to 5. A charity with no reviews has no rating at all; it is not rated zero.

**Review** — one member's score of 1 to 5 for one charity, optionally with a comment.

**Haskama** — a rabbi's public endorsement of a charity, or public objection to it. A rabbi is a religious authority whose judgement givers may trust. The panel can ask for charities endorsed by a particular rabbi, and can also count endorsements and objections. (The design document calls this table HASKAMA, which is the Hebrew word.)

The other code words, and the plain words this document uses for them:

| code word | plain word used here |
| --- | --- |
| `dataclass` (frozen) | record — a bundle of named values that cannot be changed after it is made |
| `Protocol` | promise — a list of what a helper must be able to do |
| `QuerySet` | a question about the database that has not been asked yet |
| `annotate(...)` | add a computed column to every row a question returns |
| `.filter(...)` | keep only the rows that match a condition |
| `repository` | the database helper — the one part that talks to the database |
| `template` | the page's fill-in-the-blanks file |
| `TestCase` / `SimpleTestCase` | an automated test |
| query string | the `?name=value` part of a web address |
| `id` | the whole number that names one stored record |
| row / table | one stored record / the collection those records live in |

Two more words the document uses in passing, because the code comments use them: *parameter* is one `name=value` pair in a web address, and *seed data* is the sample charities the developers load into their own copy of the database.

One more piece of shorthand: the design document numbers itself with **§** for section, **FR 2** for functional requirement 2 and **UC-03** for use case 3. This document uses the same codes so a reader can find the passage in the customer's file. A code such as **D-045** names an entry in the project's decision log, `docs/DECISIONS.md`; that log is where the project records a choice that departs from the design document, and it is the authority a departure is checked against.

---

## 4. The story

### What the site does all day

1. A visitor opens `/charity/`. The site asks the database for charities, alphabetically, twenty at a time.
2. For each charity, the site builds a card: picture, name, tagline, cause labels, place labels.
3. It puts twenty cards on the page and draws page links underneath.
4. The visitor scrolls, or clicks to page two, and reads.

That is the whole of the front door before this change. It is honest and it is complete, and it is useless once the list is longer than a person's patience.

### The visitor this change is for

Rivka is looking for somewhere to give her maaser. She has two conditions she can state in a sentence: the charity should work on food, and it should be near Lakewood, New Jersey. She has a third condition she can feel but not act on: she would rather give to one that other people have rated well.

Before this change, all three conditions are things she must check by eye. She reads the cause label and the place label on every card, on every page, and she keeps a running list in her head. With 595 review rows in the developer's database and a charity list longer than one page, that is a bad afternoon. If a good food charity in Lakewood happens to be alphabetically late, she never sees it. That is the cost, and it is paid in money given to a worse fit.

### What this change does about it

It turns the labels Rivka was reading by eye into questions she can click. Tick "Food" and the list keeps only food charities. Tick "Lakewood, New Jersey, USA" and it keeps only charities there. Set the rating box to 4 and it keeps only charities averaging 4 stars or more. Each of those facts was already on the card; the change makes the card's facts askable.

It does that with one structural idea: **the list of groups, the names they use in the web address, and whether they repeat all live in one place, and everything else reads that place.** The panel that draws the boxes, the page that reads the address, the database helper that narrows the rows, and the page links that carry the answers forward all consult the same short table. Add a group later and you change that table and the words beside it; you do not hunt through five files for the places that must agree.

Three consequences follow, and they are the arguments for doing it this way rather than a quicker way:

- **The address is the state.** Every answer is in the web address. Nothing is kept on the server between clicks. So a narrowed list can be bookmarked, shared, reloaded, and reached with the Back button. The design document requires this (UC-03).
- **One pass over the data.** The card's rating and the rating question are computed in the same database question, not by two separate counts that could drift apart. The note in `docs/NOTES.md` records the cost: the listing page now cannot render if the review rows are unavailable, which is new.
- **Silly input is answered, not obeyed.** A rating outside 1 to 5 is pulled into the scale once, where the address is read, and the panel says what it did. The number the panel shows, the number the database compares, and the number the page links carry are the same number, because there is only one place that decides it.

The panel's third question — "which rabbi endorsed it" — is wired all the way through and cannot be answered yet. The list of rabbis belongs to another part of the site (accounts) that has no way to list them. So the group renders with the note "Rabbi search is not available yet", and the pull request records that instead of hiding the gap.

---

## 5. Contradictions

There are four disagreements and one silence, all worth knowing before you read the code. In each case, trust the code.

The names in quotation marks in this section are file and function names; each is explained where it first appears in section 7. Nothing here depends on understanding them.

**1. The pull request has no description.** The body is empty. The title is "Filter". A reader arriving from GitHub learns nothing about the rating work or the database audit also inside this branch. Trust the commit messages and the code; they are detailed and they agree with each other, except where item 4 below says otherwise.

**2. D-045 says "six groups" and then lists seven.** The entry opens "narrows the listing by **six** of §6.2.4's seven groups", lists seven names, and then writes "— that is all seven". The code implements seven, the tests pin seven, and the doc's own list is seven. Trust the code and the list: seven.

**3. D-045 points at code that does not exist.** Its "Where in code" line names `apps/charities/views.py` (`_read_filters`) and `apps/charities/contracts.py` (`CharityFilters`). There is no `_read_filters` in the view — the address is read by `from_query` in `filters.py` — and `CharityFilters` lives in `filters.py`, not `contracts.py`. Trust the code's file layout.

**4. Two documents still describe the rule the branch abandoned.** Commit `5d1ab32`'s message says an out-of-range `min_rating` is "ignored as no filter", and D-046's title says "an out-of-range rating filters nothing". The final commit `dbb2bde` and D-046's own body both say the rating is clamped into 1–5 and the correction is shown, which is what the code does. Trust the final code: clamped, with a note.

**5. D-046's opening count is short.** It says "Four corrections ... three of which change what is built", then lists six bullet points, five of which describe changes (the sixth is the history of the ignored-versus-clamped reversal). The bullets are accurate; the count in the first line is not. Trust the bullets.

---

## 6. Reading order

| # | file | what it is |
| --- | --- | --- |
| — | `apps/charities/models.py` *(unchanged)* | The shape of the tables. Read it first only to know what a review and a haskama are; nothing in it changed. |
| 1 | `apps/charities/contracts.py` | The plain records the listing hands to the page. Everything downstream is written against these. |
| 2 | `apps/charities/filters.py` | New. The seven groups, the address reader, the clamping rule, and the panel's data. This is the centre of the change. |
| 3 | `apps/charities/repositories.py` | Changed. The database helper: turns the groups into one question, and computes the numbers the cards print. |
| 4 | `apps/charities/services.py` | The listing's rules — paging, ordering, page links — now carrying filters through. |
| 5 | `apps/charities/views.py` | The page's entry point: reads the address, calls the service, renders. |
| 6 | `apps/charities/templates/charities/filters.html` | New. The panel itself. |
| 7 | `apps/charities/templates/charities/listing.html` | The page: panel on the left, results on the right, rating on the card. |
| 8 | `static/css/site.css` | The layout and the panel's styling, including the scrolling option list. |
| 9 | `docs/DECISIONS.md` | The written decisions D-044, D-045 and D-046, and three new open questions. |
| 10 | `docs/NOTES.md` | New. Observations that are not decisions, including the database audit and eight findings. |
| 11 | `.gitignore` | One line: keep throwaway screenshots out of git. |
| 12 | `tests/unit/test_filter_service.py` | New. Pins the address reader and the panel's data without a database. |
| 13 | `tests/unit/test_filter_repository.py` | New. Pins the narrowing and the counts against real rows. |
| 14 | `tests/unit/test_repositories.py` | Updated calls, plus the rating mapping. |
| 15 | `tests/unit/test_services.py` | Updated stand-in types for the new card shape. |
| 16 | `tests/unit/test_template_contract.py` | Pins what the templates are allowed to read. |
| 17 | `tests/unit/test_views.py` | Black-box tests of the page: tick a box, see fewer charities. |

The shape of the whole change in one sentence: **a short table of seven questions becomes a panel, a web address, a database question and a set of page links — and the numbers the panel asks about are the numbers the cards print.**

---

## 7. The files, one by one

### 7.1 `apps/charities/contracts.py` — the records the page is allowed to read

**Every label on a card now carries enough detail to be unambiguous, and every card now carries its review summary.**

This file holds the small read-only records that the listing hands to the page. They are deliberately free of database behaviour, so the page can only see plain values.

#### `LocationTag` — a place label, before and after

Before, a place record held only a name. Anyone wanting a label wrote `location.name`, and a name alone is ambiguous: the design decision D-032 makes a place unique only by name *and* region *and* country, so two different Lakewoods can exist.

Before — `apps/charities/contracts.py:19`:

```python
@dataclass(frozen=True)
class LocationTag:
    name: str
```

After, it holds the three parts and can produce the full label itself, so the card and the panel cannot word the same place differently.

After — `apps/charities/contracts.py:19`:

```python
@dataclass(frozen=True)
class LocationTag:
    """A location as it is shown: name alone is not unique (D-032, D-045)."""

    name: str
    region: str
    country: str

    @property
    def label(self) -> str:
        """The full identity, identical to what the filter offers as one choice."""
        return f"{self.name}, {self.region}, {self.country}"
```

#### `ReviewSummary` — new

Before, a card had nowhere to put a rating, so the page could not show one. The new record holds the two numbers the card prints, and deliberately allows "no rating" to be different from "a rating of zero".

New — `apps/charities/contracts.py:33`:

```python
@dataclass(frozen=True)
class ReviewSummary:
    """A charity's reviews, as the listing shows them (§5.2.15, §5.3).

    `average` is None when there are no reviews, so a card with no reviews
    cannot be mistaken for one rated 0. §5.3 derives both values from REVIEW
    rows; nothing is stored.
    """

    count: int
    average: float | None
```

#### `CharityCard` — gains one field

The card record gains `reviews`, so a page that receives a card has the rating and the count without asking the database anything else.

Before — `apps/charities/contracts.py:24`:

```python
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

After — `apps/charities/contracts.py:46`:

```python
@dataclass(frozen=True)
class CharityCard:
    """What the listing shows for one charity."""

    id: int
    name: str
    tagline: str
    image: str
    domains: tuple[DomainTag, ...]
    locations: tuple[LocationTag, ...]
    reviews: ReviewSummary
```

#### `DomainOption`, `LocationOption`, `RabbiOption` — new

Before, the panel had nothing to draw choices from: the only records were about charities already on the page. These three describe one tickable choice each. The location one repeats the full-identity label for the same reason as `LocationTag`, and the rabbi one carries RABBI_PROFILE's two parts and joins them, so the eventually-real rabbi list only has to hand over its rows.

New — `apps/charities/contracts.py:59`:

```python
@dataclass(frozen=True)
class DomainOption:
    """One choice in the Domain filter group (§6.2.4)."""

    id: int
    name: str


@dataclass(frozen=True)
class LocationOption:
    """One choice in the Location filter group, labelled by its full identity (D-045)."""

    id: int
    name: str
    region: str
    country: str

    @property
    def label(self) -> str:
        return f"{self.name}, {self.region}, {self.country}"


@dataclass(frozen=True)
class RabbiOption:
    """One choice in the Haskamos filter group, a rabbi's public identity (§6.2.4, D-045).

    `id` is the **user** id, not the profile's: HASKAMA stores `rabbi_user`,
    which is what the filter compares against. The two parts of the identity
    come from RABBI_PROFILE (§5.2.3); `title` is optional there, so the label
    has to cope with its absence.
    """

    id: int
    display_name: str
    title: str | None

    @property
    def label(self) -> str:
        return f"{self.title} {self.display_name}" if self.title else self.display_name
```

What it buys: the card and the panel now offer a place as the same three-part string, so "Lakewood" on a card can no longer mean a different Lakewood from the one in the panel. And the card's rating is a value the page can print without reaching for the database.

---

### 7.2 `apps/charities/filters.py` — the seven questions, and the one place that knows how to ask them

**This new file is the change's spine: it names the seven groups, reads them out of a web address, holds them as a value, and builds the panel's display data.**

Nothing in this file touches the database or the page. It is the shared vocabulary that the view, the template and the database helper all speak, which is why adding a group is a one-file change.

#### The group table — new

The file's first idea is that three facts must agree for every group: the name it uses in the web address, where the answer is stored, and whether you may tick several. Keeping them in one table is what stops a later group from being half-added.

New — `apps/charities/filters.py:19`:

```python
@dataclass(frozen=True)
class Group:
    """One of §6.2.4's filter groups: its URL parameter and where it is stored.

    One table for all three facts that must agree — the parameter the URL uses,
    the attribute on `CharityFilters`, and whether the group repeats — so adding
    or renaming a group is a single entry here.
    """

    parameter: str
    attribute: str
    repeatable: bool


# §6.2.4 Filter: the seven groups, in the order the sidebar shows them. The
# parameter names are the doc's, verbatim, including its singular
# `haskama_rabbi` (D-046).
GROUPS: tuple[Group, ...] = (
    Group("domain", "domains", repeatable=True),
    Group("location", "locations", repeatable=True),
    Group("haskama_rabbi", "haskama_rabbis", repeatable=True),
    Group("min_rating", "min_rating", repeatable=False),
    Group("min_reviews", "min_reviews", repeatable=False),
    Group("min_approving_haskamas", "min_approving_haskamas", repeatable=False),
    Group("max_disapproving_haskamas", "max_disapproving_haskamas", repeatable=False),
)

# The parameter a repeatable group's option list is looked up under.
OPTION_SOURCES: dict[str, str] = {
    "domain": "domains",
    "location": "locations",
    "haskama_rabbi": "rabbis",
}

# §5.2.15 REVIEW.rating is 1–5, and D-044 prints the average out of 5.
MIN_STAR_RATING, MAX_STAR_RATING = 1, 5
```

Note the third row: the web-address name is singular (`haskama_rabbi`) and the stored name is plural (`haskama_rabbis`). That is deliberate. D-046 says the address must match the design document's spelling exactly, while the internal name may read naturally, and the tests pin both.

#### `CharityFilters` — new

This record is "the answers to the seven questions, as a value you can pass around". Empty means "no question asked", which is why the empty record is also the way the listing says "show everything".

New — `apps/charities/filters.py:57`:

```python
@dataclass(frozen=True)
class CharityFilters:
    """Which charities the listing should keep. Empty means "every charity".

    Each tuple is one group: charities matching *any* value in it are kept (OR),
    and every non-empty group must match (AND), exactly as §6.2.4 states.
    """

    domains: tuple[int, ...] = ()
    locations: tuple[int, ...] = ()
    haskama_rabbis: tuple[int, ...] = ()
    min_rating: int | None = None
    min_reviews: int | None = None
    min_approving_haskamas: int | None = None
    max_disapproving_haskamas: int | None = None

    @property
    def is_empty(self) -> bool:
        """True when nothing is filtered, so the listing shows every charity.

        `0` is a real filter value (D-045), so each group is tested for being
        unset rather than for truthiness.
        """
        return all(getattr(self, group.name) in ((), None) for group in fields(self))

    def selected(self, parameter: str) -> tuple[int, ...]:
        """The ids ticked in a repeatable group; empty for the numeric groups."""
        group = next((g for g in GROUPS if g.parameter == parameter), None)
        if group is None or not group.repeatable:
            return ()
        return getattr(self, group.attribute)

    def active_count(self) -> int:
        """How many groups narrow the listing, for the sidebar's summary line."""
        return sum(1 for group in GROUPS if getattr(self, group.attribute) not in ((), None))
```

The `is_empty` test is the small but load-bearing part. Python treats zero and "nothing at all" as interchangeable when you ask "is this set?", so the obvious test would read "zero disapproving haskamas" as "no question asked". The code compares against `()` and `None` instead, so a zero is a real answer.

#### `query_pairs` and `query_string` — new

These turn answers back into web-address pieces, in the document's order, so a page link can repeat them. The pairs are also used directly as hidden form fields, which is why the file offers both a string and the pairs.

New — `apps/charities/filters.py:93`:

```python
def query_pairs(filters: CharityFilters) -> tuple[tuple[str, object], ...]:
    """The filter groups as (parameter, value) pairs, in the doc's order."""
    parts: list[tuple[str, object]] = []
    for group in GROUPS:
        value = getattr(filters, group.attribute)
        if group.repeatable:
            parts.extend((group.parameter, item) for item in value)
        elif value is not None:
            parts.append((group.parameter, value))
    return tuple(parts)


def query_string(filters: CharityFilters) -> str:
    """The filter groups as a query string, so a page link can repeat them."""
    return urlencode(query_pairs(filters))
```

The `is not None` check is the same zero problem in another place: a chosen `0` must appear in the address, and a test of whether the value is zero would drop it.

#### `from_query` — new

`from_query` is the only place a web address is turned into answers. It reads a repeated name as a list of values rather than one (so `?domain=2&domain=5` yields two ids), reads the number groups, and treats unusable values as absent.

New — `apps/charities/filters.py:110`:

```python
def from_query(query) -> CharityFilters:
    """Build filters from request query parameters, ignoring anything unusable.

    A value that names no row is not an error: it is dropped, which is the same
    treatment the listing already gives a junk `page`. `min_rating` is the one
    exception: it is clamped to the star scale rather than dropped, so a shared
    `?min_rating=99` still means "the highest rating".
    """
    values: dict[str, tuple] = {}
    for group in GROUPS:
        if group.repeatable:
            values[group.attribute] = _token_ids(query.getlist(group.parameter))
        elif group.parameter == "min_rating":
            values[group.attribute] = clamp_rating(_number(query.get(group.parameter)))
        else:
            values[group.attribute] = _number(query.get(group.parameter))
    return CharityFilters(**values)
```

#### `clamp_rating` — new

The one rule for an out-of-range rating, written once so the panel's input, the database comparison and the page links cannot disagree. `?min_rating=99` becomes 5; `?min_rating=0` becomes 1; anything in between is untouched.

New — `apps/charities/filters.py:129`:

```python
def clamp_rating(rating: int | None) -> int | None:
    """Hold `min_rating` inside the star scale, so the value is never off it.

    Clamping happens once, at the edge where the URL is read, so everything
    downstream — the query, the sidebar's input, the page links — sees the same
    number. `?min_rating=99` therefore means "5 stars or more" and the sidebar
    shows that 5, rather than the reader silently getting something else (D-046).
    """
    if rating is None:
        return None
    return max(MIN_STAR_RATING, min(rating, MAX_STAR_RATING))
```

#### `requested_numbers` — new

The panel needs to tell the reader when the number it is showing is not the number the address asked for. That comparison needs the raw numbers, so this function reads them again, without clamping, purely for display.

New — `apps/charities/filters.py:142`:

```python
def requested_numbers(query) -> dict[str, int | None]:
    """The numeric groups exactly as the URL asked, before any clamping."""
    numbers: dict[str, int | None] = {}
    for group in GROUPS:
        if not group.repeatable:
            numbers[group.parameter] = _number(query.get(group.parameter))
    return numbers
```

#### `_token_ids` and `_number` — new

Two small readers with strict rules. Ids must be positive whole numbers, are kept in the order given, and duplicates vanish. A blank or unreadable number means "no answer", which matters because the panel submits every number box even when it is empty.

New — `apps/charities/filters.py:151`:

```python
def _token_ids(raw_values) -> tuple[int, ...]:
    """Positive whole ids from repeated query values, in the order given, no repeats."""
    seen: list[int] = []
    for raw in raw_values:
        try:
            value = int(raw)
        except (TypeError, ValueError):
            continue
        if value > 0 and value not in seen:
            seen.append(value)
    return tuple(seen)


def _number(raw: str | None) -> int | None:
    """An optional whole number; a blank input and junk both mean "absent".

    The sidebar always submits every number input, so an unticked group arrives
    as an empty string. Treating that as no filter keeps a submitted URL as clean
    as a hand-written one.
    """
    if raw is None or raw.strip() == "":
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None
```

#### `FilterForm`, `FilterOption`, `FilterGroup` — new

These are the panel's own records: what the template is allowed to read, and nothing more. `FilterGroup` is deliberately a little wide, because it must describe both a checkbox group and a number box; the `kind` field says which, and the template branches on it.

New — `apps/charities/filters.py:180`:

```python
@dataclass(frozen=True)
class FilterForm:
    """The sidebar, ready to render (D-045).

    `groups` is the doc's order, each with its options or its single input;
    `filters` is what the URL asked for, so the sidebar shows the live state.
    """

    filters: CharityFilters
    groups: tuple[FilterGroup, ...] = ()

    @property
    def is_active(self) -> bool:
        return not self.filters.is_empty


@dataclass(frozen=True)
class FilterOption:
    """One tickable choice, already carrying the label it is shown with."""

    id: int
    label: str


@dataclass(frozen=True)
class FilterGroup:
    """One group in the sidebar, ready to render as checkboxes or one number input.

    `kind` is "checkboxes" or "number". A number group carries the bounds its
    input accepts (`min`, `max`, may be None) and a `label` for the input; a
    checkbox group carries `options` and the `selected` ids from the URL.
    """

    parameter: str
    legend: str
    kind: str
    options: tuple[FilterOption, ...] = ()
    selected: tuple[int, ...] = ()
    value: int | None = None
    # True when this group narrows the listing. A chosen `0` is a real filter, so
    # the template needs this rather than testing `value` for truthiness.
    is_set: bool = False
    label: str = ""
    min: int | None = None
    max: int | None = None
    empty_note: str = ""
    none_note: str = ""
    # Set when the value shown is not the one the URL asked for, so the reader is
    # told the filter they got, not left to guess.
    adjusted_note: str = ""
```

#### The words on the panel — new

Every group's heading and every number box's label lives here, beside the group table, so a group cannot be added without saying what it is called. Two more tables supply the "nothing to choose from" messages, including the honest one for rabbis.

New — `apps/charities/filters.py:234`:

```python
# The legends and input labels, in the doc's order (§6.2.4). Kept beside the
# groups so a new group cannot be added without saying what it is called.
# Keyed by §6.2.4's parameter names, in the doc's order.
LEGENDS: dict[str, str] = {
    "domain": "Domains",
    "location": "Locations",
    "haskama_rabbi": "Haskamos",
    "min_rating": "Rating",
    "min_reviews": "Reviews",
    "min_approving_haskamas": "Approving haskamos",
    "max_disapproving_haskamas": "Disapproving haskamos",
}

NUMBER_LABELS: dict[str, str] = {
    "min_rating": "stars or more",
    "min_reviews": "reviews or more",
    "min_approving_haskamas": "at least",
    "max_disapproving_haskamas": "at most",
}

NONE_NOTES: dict[str, str] = {
    "max_disapproving_haskamas": "Leave blank for no limit.",
}

EMPTY_NOTES: dict[str, str] = {
    # D-045: the group is real but its options come from accounts, which has no
    # rabbi search yet. Saying so beats an empty box that looks broken.
    "haskama_rabbi": "Rabbi search is not available yet.",
}
```

#### `sidebar_groups` — new

This builds the panel's seven groups from two inputs: the answers already chosen, and the available choices. It is the only function that knows a group's `kind`, and it also computes the clamping note. Because `options` is keyed by the list a group draws from (`domains`, `locations`, `rabbis`) rather than by the web-address name, the view never has to know which question asks for which list.

New — `apps/charities/filters.py:262`:

```python
def sidebar_groups(
    filters: CharityFilters,
    options: dict[str, tuple],
    requested: dict[str, int | None] | None = None,
) -> tuple[FilterGroup, ...]:
    """Build the sidebar's groups from the URL's filters and the option lists.

    `options` is keyed by what a group draws its choices from (`domains`,
    `locations`, `rabbis`), not by URL parameter, so the view does not have to
    know which parameter asks for which list. `requested` holds the raw numbers
    the URL asked for, so a clamped value can be called out.
    """
    requested = requested or {}
    groups: list[FilterGroup] = []
    for group in GROUPS:
        parameter = group.parameter
        if group.repeatable:
            choices = tuple(
                FilterOption(id=option.id, label=_option_label(option))
                for option in options.get(OPTION_SOURCES[parameter], ())
            )
            groups.append(
                FilterGroup(
                    parameter=parameter,
                    legend=LEGENDS[parameter],
                    kind="checkboxes",
                    options=choices,
                    selected=filters.selected(parameter),
                    is_set=bool(filters.selected(parameter)),
                    empty_note=EMPTY_NOTES.get(parameter, "Nothing to choose from."),
                )
            )
            continue
        value = getattr(filters, group.attribute)
        groups.append(
            FilterGroup(
                parameter=parameter,
                legend=LEGENDS[parameter],
                kind="number",
                value=value,
                is_set=value is not None,
                label=NUMBER_LABELS[parameter],
                min=MIN_STAR_RATING if parameter == "min_rating" else 0,
                max=MAX_STAR_RATING if parameter == "min_rating" else None,
                none_note=NONE_NOTES.get(parameter, ""),
                adjusted_note=_adjusted_note(parameter, requested, value),
            )
        )
    return tuple(groups)


def _adjusted_note(parameter: str, requested: dict[str, int | None], value: int | None) -> str:
    """Say so when the URL asked for a value the sidebar is not showing."""
    asked = requested.get(parameter)
    if asked is None or asked == value:
        return ""
    return f"Kept between {MIN_STAR_RATING} and {MAX_STAR_RATING}; using {value}."


def _option_label(option) -> str:
    """A location states its full identity; anything else has one name (D-045)."""
    return getattr(option, "label", None) or getattr(option, "name", str(option.id))
```

What it buys: the reader sees every group in the document's order, with their own answers ticked or filled in; a group with nothing to offer says why; and a corrected rating is explained instead of silently applied.

---

### 7.3 `apps/charities/repositories.py` — one question, one set of numbers

**The database helper now narrows the rows by the seven groups and computes the ratings the cards print, in the same database question.**

The file is the only place that talks to the database for the listing. It exposes a promise (`CharityRepository`) and one implementation, and the listing never sees a database instruction.

#### The promise — before and after

Before, the promise was "give me a page of cards" with no notion of narrowing, so a filtered listing could not be asked for at all.

Before — `apps/charities/repositories.py:18`:

```python
class CharityRepository(Protocol):
    """Read access to charities, in the terms the listing needs."""

    def page(self, offset: int, limit: int) -> tuple[CharityCard, ...]:
        """Return cards for the given window, ordered by name."""
        ...

    def count(self) -> int:
        """Return the total number of charities."""
        ...
```

After, both methods take the answers, so the helper cannot return a page of a different set than the one it counted.

After — `apps/charities/repositories.py:27`:

```python
class CharityRepository(Protocol):
    """Read access to charities, in the terms the listing needs."""

    def page(self, offset: int, limit: int, filters: CharityFilters) -> tuple[CharityCard, ...]:
        """Return cards for the given window of the filtered set, ordered by name."""
        ...

    def count(self, filters: CharityFilters) -> int:
        """Return how many charities the filters keep."""
        ...
```

#### `_counted` — new

This is the function that makes the card and the questions agree. It attaches four computed columns to every charity row: how many reviews, the average score, how many approving haskamas, and how many disapproving ones. The card prints two of them; the filters compare against all four. Because they are attached in the same pass, the card cannot show 4.5 while the rating filter compares against something else.

New — `apps/charities/repositories.py:64`:

```python
def _counted(self) -> QuerySet[Charity]:
    """Rows annotated with the review and haskama numbers the filters read.

    The counts are over all of a charity's rows, not just published ones:
    while D-042 lists unpublished charities, the filters treat them the same.
    """
    return self._rows().annotate(
        review_count=Count("reviews", distinct=True),
        average_rating=Avg("reviews__rating"),
        approving_haskamas=Count(
            "haskamas", filter=Q(haskamas__verdict=Haskama.Verdict.APPROVE), distinct=True
        ),
        disapproving_haskamas=Count(
            "haskamas", filter=Q(haskamas__verdict=Haskama.Verdict.DISAPPROVE), distinct=True
        ),
    )
```

#### `page` — before and after

Before, the page was a window into every charity, alphabetically. After, it is a window into the narrowed set, with the same alphabetical order and the same relationship loading.

Before — `apps/charities/repositories.py:51`:

```python
def page(self, offset: int, limit: int) -> tuple[CharityCard, ...]:
    rows = (
        self._rows()
        .prefetch_related("domains", "locations")
        .order_by("name")[offset : offset + limit]
    )
    return tuple(self._to_card(row) for row in rows)
```

After — `apps/charities/repositories.py:81`:

```python
def page(self, offset: int, limit: int, filters: CharityFilters) -> tuple[CharityCard, ...]:
    rows = (
        self._narrowed(filters)
        .prefetch_related("domains", "locations")
        .order_by("name")[offset : offset + limit]
    )
    return tuple(self._to_card(row) for row in rows)
```

#### `count` — before and after

Before, the count was of every charity. After, it is of the narrowed set, so the "Page 1 of N" links are computed from the same set the visitor is actually browsing.

Before — `apps/charities/repositories.py:59`:

```python
def count(self) -> int:
    return self._rows().count()
```

After — `apps/charities/repositories.py:89`:

```python
def count(self, filters: CharityFilters) -> int:
    return self._narrowed(filters).count()
```

#### `_narrowed` — new

This is the translation from the seven answers to database conditions. Each answer becomes one "keep only" condition; several answers become several conditions, so a charity must satisfy all of them. Within a tick-box group, "any of these ids" is one condition, so two ticked causes mean either cause.

New — `apps/charities/repositories.py:92`:

```python
def _narrowed(self, filters: CharityFilters) -> QuerySet[Charity]:
    """Apply §6.2.4's groups: OR inside a group, AND between groups."""
    rows = self._counted()
    if filters.domains:
        rows = rows.filter(domains__in=filters.domains)
    if filters.locations:
        rows = rows.filter(locations__in=filters.locations)
    if filters.haskama_rabbis:
        rows = rows.filter(haskamas__rabbi_user__in=filters.haskama_rabbis)
    if filters.min_rating is not None:
        # The scale is stars (D-045), and `from_query` has already clamped the
        # value into it, so this compares like with like. No reviews means no
        # average, and a charity with no average cannot clear a minimum rating.
        rows = rows.filter(review_count__gt=0, average_rating__gte=filters.min_rating)
    if filters.min_reviews is not None:
        rows = rows.filter(review_count__gte=filters.min_reviews)
    if filters.min_approving_haskamas is not None:
        rows = rows.filter(approving_haskamas__gte=filters.min_approving_haskamas)
    if filters.max_disapproving_haskamas is not None:
        rows = rows.filter(disapproving_haskamas__lte=filters.max_disapproving_haskamas)
    return rows.distinct() if self._joins_rows(filters) else rows
```

The `review_count__gt=0` half of the rating condition is the "no reviews is not zero stars" rule, written where it matters. An unreviewed charity has no average, and a missing number never satisfies "four stars or more"; the count check states that intent rather than leaving it to how the database handles a missing number.

#### `_joins_rows` — new

Ticking a cause, a place or a rabbi makes the database produce more than one row per charity — a charity with three causes would appear three times. That is fine for reading, but it would inflate the count and duplicate cards, so the code asks for distinct charities only when one of those three groups was used.

New — `apps/charities/repositories.py:115`:

```python
@staticmethod
def _joins_rows(filters: CharityFilters) -> bool:
    """True when a filter multiplies rows, so DISTINCT is needed to count charities."""
    return bool(filters.domains or filters.locations or filters.haskama_rabbis)
```

#### `_to_card` — before and after

Before, the card was built from the charity row plus its labels. After, it also carries the two review numbers computed by `_counted`, and the place labels now hold all three parts.

Before — `apps/charities/repositories.py:63`:

```python
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

After — `apps/charities/repositories.py:120`:

```python
@staticmethod
def _to_card(row: Charity) -> CharityCard:
    return CharityCard(
        id=row.id,
        name=row.name,
        tagline=row.tagline,
        image=row.image,
        domains=tuple(DomainTag(name=d.name) for d in row.domains.all()),
        locations=tuple(
            LocationTag(name=loc.name, region=loc.region, country=loc.country)
            for loc in row.locations.all()
        ),
        reviews=ReviewSummary(count=row.review_count, average=row.average_rating),
    )
```

#### `DjangoFilterOptionsRepository` — new

The panel's choices come from the shared list of causes and places, not from the charities currently matching. That is a deliberate difference: if the choices were built from the results, ticking one box would make the other boxes vanish under your cursor. This small helper reads the three lists; the rabbi list is honestly empty for now.

New — `apps/charities/repositories.py:135`:

```python
class DjangoFilterOptionsRepository:
    """The sidebar's choices: the domains, locations and rabbis one can filter by.

    Options come from the shared lists rather than from the charities currently
    matching, so ticking one option cannot make the others disappear under the
    user's cursor. Domains and locations that no charity uses are still offered,
    because the domain and location lists are managed on their own (§5.2.10–11).
    """

    def domains(self) -> tuple[DomainOption, ...]:
        return tuple(
            DomainOption(id=row.id, name=row.name) for row in Domain.objects.order_by("name")
        )

    def locations(self) -> tuple[LocationOption, ...]:
        rows = Location.objects.order_by("name", "region", "country")
        return tuple(
            LocationOption(id=row.id, name=row.name, region=row.region, country=row.country)
            for row in rows
        )

    def rabbis(self) -> tuple[RabbiOption, ...]:
        """Empty for now: the rabbi list belongs to accounts (§6.1, D-045).

        `HASKAMA` is read in its real shape, but a rabbi's public identity comes
        from `accounts.services.search_rabbis`, which does not exist yet. When it
        lands, this method returns its results and no other code changes.
        """
        return ()
```

What it buys: narrowing happens in the database rather than on the page, so a filtered page is still twenty rows and one question to the database, and the numbers on the cards are computed by the same question that decided which cards to show.

---

### 7.4 `apps/charities/services.py` — the list's rules, now carrying answers forward

**The service now passes the answers to the database helper and puts them into every page link, so paging never silently drops a filter.**

This file holds the listing's rules — ordering, page clamping, page sizes — and nothing about where rows come from. The database helper is handed in, which is why the tests can use a stand-in.

#### `Page` — before and after

Before, a page knew its items, total, number and size, and could build a link for another page. After, it also knows the answers as a web-address string and as name/value pairs, so links and forms can repeat them.

Before — `apps/charities/services.py:55`:

```python
@dataclass(frozen=True)
class Page:
    """One page of results, plus the links needed to move between pages."""

    items: tuple[CharityCard, ...]
    total: int
    number: int
    page_size: int
```

After — `apps/charities/services.py:56`:

```python
@dataclass(frozen=True)
class Page:
    """One page of results, plus the links needed to move between pages.

    `filters_query` is the query string a page link must repeat so the reader
    keeps the filters they chose; empty when nothing is filtered.
    """

    items: tuple[CharityCard, ...]
    total: int
    number: int
    page_size: int
    filters_query: str = ""
    # The same filters as (name, value) pairs, for replaying them as hidden inputs.
    filter_pairs: tuple[tuple[str, object], ...] = ()
```

#### `Page.query` — before and after

Before, a link to page two said only "page two, this size", so following it lost every filter. After, the answers are appended to the link, so page two is page two of the same narrowed list.

Before — `apps/charities/services.py:75`:

```python
def query(self, number: int) -> str:
    """Query string for another page of this same result set."""
    return urlencode({"page": number, "page_size": self.page_size})
```

After — `apps/charities/services.py:83`:

```python
def query(self, number: int) -> str:
    """Query string for another page of this same result set."""
    parts = {"page": number, "page_size": min(self.page_size, MAX_PAGE_SIZE)}
    if self.filters_query:
        return f"{urlencode(parts)}&{self.filters_query}"
    return urlencode(parts)
```

The order is visible here and it is tested: `page`, then `page_size`, then the filters. The size is capped again on the way out, so a hand-edited address cannot put an unbounded number into a link.

#### `list_charities` — before and after

Before, it counted every charity and fetched a window. After, it counts the narrowed set, clamps the requested page against that count, and puts the answers on the returned page.

Before — `apps/charities/services.py:101`:

```python
def list_charities(
    repository: CharityRepository,
    page: int | None = 1,
    page_size: int | None = None,
) -> Page:
    """Return one page of charities, alphabetically by name."""
    page_size = clamp_page_size(page_size)
    total = repository.count()
    count = page_count(total, page_size)
    number = max(1, min(page or 1, count))
    offset = (number - 1) * page_size

    return Page(
        items=repository.page(offset=offset, limit=page_size),
        total=total,
        number=number,
        page_size=page_size,
    )
```

After — `apps/charities/services.py:112`:

```python
def list_charities(
    repository: CharityRepository,
    page: int | None = 1,
    page_size: int | None = None,
    filters: CharityFilters | None = None,
) -> Page:
    """Return one page of the charities `filters` keep, alphabetically by name."""
    filters = filters or CharityFilters()
    page_size = clamp_page_size(page_size)
    total = repository.count(filters)
    count = page_count(total, page_size)
    number = max(1, min(page or 1, count))
    offset = (number - 1) * page_size

    return Page(
        items=repository.page(offset=offset, limit=page_size, filters=filters),
        total=total,
        number=number,
        page_size=page_size,
        filters_query=query_string(filters),
        filter_pairs=query_pairs(filters),
    )
```

`filters = filters or CharityFilters()` is the compatibility line: callers that know nothing about filtering keep working and get "show everything".

#### `list_domains`, `list_locations`, `list_rabbis`, `filter_form` — new

Four small functions that give the view a way to ask for the panel's choices and to assemble the panel, without the view touching the database helper's methods directly. Each is a one-line door; the point is that the view's vocabulary is the app's public one.

New — `apps/charities/services.py:143`:

```python
def list_domains(repository) -> tuple[DomainOption, ...]:
    """The Domain filter group's choices (§5.2.11)."""
    return repository.domains()


def list_locations(repository) -> tuple[LocationOption, ...]:
    """The Location filter group's choices (§5.2.10, D-045)."""
    return repository.locations()


def list_rabbis(repository) -> tuple[RabbiOption, ...]:
    """The Haskamos filter group's choices (§6.1, D-045)."""
    return repository.rabbis()


def filter_form(
    filters: CharityFilters,
    options: dict[str, tuple],
    requested: dict[str, int | None] | None = None,
) -> FilterForm:
    """Assemble the sidebar from the chosen filters and the option lists."""
    return FilterForm(filters=filters, groups=sidebar_groups(filters, options, requested or {}))
```

What it buys: a reader on page three who ticks a box, or who jumps to page five, stays inside their narrowed list. And a listing call that passes no answers behaves exactly as it did before this branch.

---

### 7.5 `apps/charities/views.py` — the page's entry point

**The view now reads the answers from the address, passes them to the service, and hands the panel's data to the page.**

The view is the only place that knows about an incoming web request. It reads, calls the service, and renders; the rules stay downstairs.

#### `listing` — before and after

Before, the view read a page number and a page size, called the service, and rendered with one value. After, it also reads the seven answers, reads the panel's choices through the service, and renders with a second value.

Before — `apps/charities/views.py:23`:

```python
def listing(request: HttpRequest) -> HttpResponse:
    """Render the paginated list of charities."""
    page: Page = list_charities(
        # published_only stays False until the admin approval queue publishes
        # charities; see D-042.
        repository=DjangoCharityRepository(published_only=False),
        page=_positive_int(request.GET.get("page")),
        page_size=_positive_int(request.GET.get("page_size")),
    )
    return render(request, "charities/listing.html", {"page": page})
```

After — `apps/charities/views.py:31`:

```python
def listing(request: HttpRequest) -> HttpResponse:
    """Render the paginated list of charities, narrowed by the sidebar's filters."""
    filters = from_query(request.GET)
    options_repository = DjangoFilterOptionsRepository()
    page: Page = list_charities(
        # published_only stays False until the admin approval queue publishes
        # charities; see D-042.
        repository=DjangoCharityRepository(published_only=False),
        page=_positive_int(request.GET.get("page")),
        page_size=_positive_int(request.GET.get("page_size")),
        filters=filters,
    )
    form = filter_form(
        filters,
        {
            # Keyed by the list each group draws from, not by URL parameter.
            "domains": list_domains(options_repository),
            "locations": list_locations(options_repository),
            "rabbis": list_rabbis(options_repository),
        },
        # Passed so the sidebar can say when a value was clamped into range.
        requested=requested_numbers(request.GET),
    )
    return render(request, "charities/listing.html", {"page": page, "form": form})
```

Note that the address is read once, at the top. Everything after that — the database question, the panel, the links — uses the same answers, which is how the clamp stays consistent.

What it buys: a visitor with any combination of ticks and numbers in their address gets one narrowed page, and the panel draws itself in the same request. No second request, no JavaScript.

---

### 7.6 `apps/charities/templates/charities/filters.html` — the panel

**The new sidebar template draws the seven groups without knowing which group is which.**

The file is one plain web form. Everything it shows comes from the `form` value the view hands it, so it contains no list of groups and no knowledge of any group's name.

The whole file, because it is the panel and there is no part of it a reviewer should have to imagine. In one form it collects every group, keeps the reader's page size, and offers Apply and Clear; each group draws its heading, choices or single box from the data it is given — `apps/charities/templates/charities/filters.html:1`:

```html
{% comment %}
The listing's filter sidebar (§6.2.4, D-045). Amazon-style: groups on the left,
results on the right. Everything is a plain GET form, so filters live in the URL
and the browser's Back button works (UC-03's implementation constraints).
{% endcomment %}
<form class="filters" method="get" action="{% url 'charities:listing' %}">
  <div class="filters__head">
    <h2 class="filters__title">Filters</h2>
    {% if form.is_active %}
      <span class="filters__count">{{ form.filters.active_count }} group{{ form.filters.active_count|pluralize }} on</span>
    {% endif %}
  </div>

  {% comment %}Keep the page size the reader chose; a filter resets the page to 1
  (§6.2.4), which is what a missing `page` parameter means.{% endcomment %}
  <input type="hidden" name="page_size" value="{{ page.page_size }}">

  {% comment %}Each group is an open panel like Amazon's. <details> needs no
  JavaScript and keeps the page working if Alpine fails to load.{% endcomment %}
  {% for group in form.groups %}
    <details class="filters__group" open>
      <summary class="filters__summary">{{ group.legend }}</summary>

      {% if group.kind == "checkboxes" %}
        {% comment %}The option list scrolls instead of growing without limit: a
        real location list can run to thousands of rows, and an unrolled sidebar
        would push the Apply button off the page.{% endcomment %}
        <div class="filters__options" tabindex="0" role="group" aria-label="{{ group.legend }}">
          {% for option in group.options %}
            <label class="filters__option">
              <input
                type="checkbox"
                name="{{ group.parameter }}"
                value="{{ option.id }}"
                {% if option.id in group.selected %}checked{% endif %}
              >
              <span class="filters__option-label">{{ option.label }}</span>
            </label>
          {% empty %}
            <p class="filters__none">{{ group.empty_note }}</p>
          {% endfor %}
        </div>
      {% else %}
        <div class="filters__number">
          <label class="filters__option" for="{{ group.parameter }}">
            <input
              id="{{ group.parameter }}"
              name="{{ group.parameter }}"
              type="number"
              inputmode="numeric"
              {% if group.min is not None %}min="{{ group.min }}"{% endif %}
              {% if group.max is not None %}max="{{ group.max }}"{% endif %}
              {% if group.is_set %}value="{{ group.value }}"{% endif %}
            >
            <span class="filters__option-label">{{ group.label }}</span>
          </label>
          {% if group.adjusted_note %}
            <p class="filters__adjusted" role="status">{{ group.adjusted_note }}</p>
          {% elif group.none_note %}
            <p class="filters__none">{{ group.none_note }}</p>
          {% endif %}
        </div>
      {% endif %}
    </details>
  {% endfor %}

  <div class="filters__actions">
    <button class="filters__apply" type="submit">Apply filters</button>
    {% if form.is_active %}
      <a class="filters__clear" href="{% url 'charities:listing' %}?page_size={{ page.page_size }}">Clear filters</a>
    {% endif %}
  </div>
</form>
```

Four details in that file are worth pointing at:

- **`method="get"`.** The form sends its answers in the web address, which is the whole "bookmark and share" requirement. Nothing is stored on the server.
- **The page-size field.** It is hidden and carries the current size, so applying a filter does not reset a reader's chosen page size. There is deliberately no `page` field, so applying a filter lands on page one — which is what "setting a filter resets the page" means.
- **`is_set` instead of a test of whether the value is zero.** The number box prints its value only when `is_set` is true. That is what makes a chosen `0` render as `0` rather than an empty box.
- **`adjusted_note` before `none_note`.** When a value was clamped, the correction wins over the ordinary helper text, so the reader cannot see both and wonder which applies.

What it buys: adding or renaming a group requires no template change at all. The template loops over whatever it is given, and a group with no choices explains itself instead of showing an empty box.

---

### 7.7 `apps/charities/templates/charities/listing.html` — the page, rearranged

**The page is now a panel beside the results, with the rating on each card and the answers repeated in every page link and form.**

The file is the listing page itself, and it is the only place the pieces meet. Most of the change is re-indentation: the old content moved inside a results column, so the panel could take the left side.

#### The page's frame — before and after

Before, the page was one column with a header and a list. After, it is a two-part layout: the panel, then the results. The panel is included as a separate file so the page does not contain it.

Before — `apps/charities/templates/charities/listing.html:6`:

```html
{% block content %}
  <div class="listing">
    <div class="listing__header">
      <h1>Charities</h1>

      <form class="page-size" method="get">
```

After — `apps/charities/templates/charities/listing.html:5`:

```html
{% block content %}
  <div class="listing">
    {# §6.2.4 Filter: the sidebar narrows the listing, Amazon-style. #}
    <aside class="listing__sidebar">
      {% include "charities/filters.html" %}
    </aside>

    <div class="listing__results">
      <div class="listing__header">
        <h1>Charities</h1>

        <form class="page-size" method="get">
```

Everything that followed moved one level to the right; the rest of this section quotes only the parts whose behaviour changed.

#### The page-size form — before and after

Before, changing the page size kept the page number but not the answers, so a narrowed list snapped back to the whole list. After, every chosen answer is carried as a hidden field.

Before — `apps/charities/templates/charities/listing.html:11`:

```html
<form class="page-size" method="get">
  {% if page.number > 1 %}
    <input type="hidden" name="page" value="1">
  {% endif %}
  <label class="page-size__label" for="page-size">Page size</label>
```

After — `apps/charities/templates/charities/listing.html:17`:

```html
<form class="page-size" method="get">
  {% if page.number > 1 %}
    <input type="hidden" name="page" value="1">
  {% endif %}
  {# Keep the filters when the reader changes the page size. #}
  {% for name, value in page.filter_pairs %}
    <input type="hidden" name="{{ name }}" value="{{ value }}">
  {% endfor %}
  <label class="page-size__label" for="page-size">Page size</label>
```

#### The rating on the card — new

Before, the card had a name, a tagline and labels. After, it also states the average and the number of reviews, or says there are none. The empty case is deliberate: "0 out of 5" would read as a terrible charity rather than an unrated one.

New — `apps/charities/templates/charities/listing.html:64`:

```html
{# §5.3: the average rating on the list page, derived from the reviews. #}
{% if charity.reviews.count %}
  <span class="charity-card__rating">
    <span class="rating__value">{{ charity.reviews.average|floatformat:1 }} out of 5</span>
    <span class="rating__count">
      ({{ charity.reviews.count }} review{{ charity.reviews.count|pluralize }})
    </span>
  </span>
{% else %}
  <span class="charity-card__rating charity-card__rating--empty">No reviews yet</span>
{% endif %}
```

The `floatformat:1` is the rounding rule: one decimal place, so 11 divided by 3 prints as 3.7 rather than 3.6666667. `pluralize` supplies "review" or "reviews" so the page does not have to say "1 reviews".

#### The place label on the card — before and after

Before, the card printed a place's name alone, which was ambiguous. After, it prints the same three-part string the panel offers as a choice, so the label a visitor reads is the label a visitor ticks.

Before — `apps/charities/templates/charities/listing.html:63`:

```html
{% for location in charity.locations %}
  <span class="chip chip--location">{{ location.name }}</span>
{% endfor %}
```

After — `apps/charities/templates/charities/listing.html:86`:

```html
{# A location's name is not unique, so the chip states its full identity (D-045). #}
{% for location in charity.locations %}
  <span class="chip chip--location">{{ location.label }}</span>
{% endfor %}
```

#### The jump-to-page form — before and after

Before, the "Go to page" form kept only the page size. After, it keeps the answers too, so jumping within a narrowed list stays in that list.

Before — `apps/charities/templates/charities/listing.html:99`:

```html
<form class="jump" method="get">
  <input type="hidden" name="page_size" value="{{ page.page_size }}">
  <label class="jump__label" for="jump-page">Go to</label>
```

After — `apps/charities/templates/charities/listing.html:122`:

```html
<form class="jump" method="get">
  <input type="hidden" name="page_size" value="{{ page.page_size }}">
  {% for name, value in page.filter_pairs %}
    <input type="hidden" name="{{ name }}" value="{{ value }}">
  {% endfor %}
  <label class="jump__label" for="jump-page">Go to</label>
```

The Prev, Next and page-number links needed no template change, because `Page.query` now includes the answers; the template already printed `?{{ page.previous_query }}`.

#### The two empty states — before and after

Before, there was one empty message, for an empty database. After, there are two: one for "your filters matched nothing" and one for "there are no charities at all". They are different situations and the reader should not have to guess which they are in.

Before — `apps/charities/templates/charities/listing.html:116`:

```html
{% else %}
  <p class="empty">No charities found.</p>
{% endif %}
```

After — `apps/charities/templates/charities/listing.html:141`:

```html
{% elif form.is_active %}
  <p class="empty">No charities match those filters.</p>
{% else %}
  <p class="empty">No charities found.</p>
{% endif %}
```

What it buys: a narrowed list survives changing the page size, jumping to a page, and following a page link. The rating on the card is the same figure the rating box compares against, and an unrated charity says so rather than wearing a zero.

---

### 7.8 `static/css/site.css` — the two-column page and the panel

**The stylesheet gains the panel's layout and look, a bounded scrolling list of choices, and the rating's styling.**

The file is the site's single stylesheet. The listing styles changed from "one narrow centred column" to "a sidebar and a results column, with the sidebar moving above the results on small screens".

#### The listing layout — before and after

Before, the listing was a centred column 56rem wide (a rem is the page's base text size, so 56rem is about 896 pixels here). After, it is a grid: a 14rem sidebar — about 224 pixels — and a results column that takes the rest, up to 72rem wide. Below 48rem, about 768 pixels, the grid becomes one column, so a phone gets the panel above the results instead of a squeezed card.

Before — `static/css/site.css:50`:

```css
/* Charity listing */
.listing {
  margin: 0 auto;
  max-width: 56rem;
  padding: 2.5rem 1.5rem 4rem;
}
```

After — `static/css/site.css:49`:

```css
/* Charity listing. §6.2.4 puts the filters in checkboxes on the side of the
   listing page, so the page is a sidebar beside the results. Below 48rem the
   sidebar moves above the results instead of squeezing the cards. */
.listing {
  align-items: start;
  display: grid;
  gap: 2rem;
  grid-template-columns: 14rem minmax(0, 1fr);
  margin: 0 auto;
  max-width: 72rem;
  padding: 2.5rem 1.5rem 4rem;
}

@media (max-width: 48rem) {
  .listing {
    grid-template-columns: minmax(0, 1fr);
  }
}

.listing__sidebar {
  position: sticky;
  top: 4.5rem;
}

.listing__results {
  min-width: 0;
}
```

The sidebar is sticky, so the panel stays in view while the results scroll. `minmax(0, 1fr)` on the results column is what stops a long charity name from widening the column and pushing the page sideways.

#### The panel — new

The panel gets a light background and a border so it reads as a tool rather than as part of the results. Its headings are clickable, its choices scroll inside a fixed height, and its two messages — "nothing to choose from" and "the value was corrected" — have different colours.

New — `static/css/site.css:78`:

```css
/* Filter sidebar (§6.2.4, D-045) */
.filters {
  background: #fafafa;
  border: 1px solid #e2e2e2;
  border-radius: 0.5rem;
  display: block;
  padding: 0.875rem 1rem;
}

.filters__head {
  align-items: baseline;
  display: flex;
  gap: 0.5rem;
  justify-content: space-between;
}

.filters__title {
  font-size: 1rem;
  margin: 0;
}

.filters__count {
  color: #777;
  font-size: 0.8125rem;
}

.filters__group {
  border-top: 1px solid #e7e7e7;
  margin-top: 0.75rem;
  padding-top: 0.5rem;
}

.filters__summary {
  cursor: pointer;
  font-size: 0.9375rem;
  font-weight: 600;
  padding: 0.25rem 0;
}

/* A bounded, scrolling list of choices. The domain and location lists are
   managed on their own and can grow without limit, so the panel must not. */
.filters__options {
  max-height: 14rem;
  overflow-y: auto;
  padding-right: 0.25rem;
}

.filters__options:focus-visible {
  outline: 2px solid #1a4d8f;
  outline-offset: 2px;
}

.filters__option {
  align-items: baseline;
  color: #333;
  display: flex;
  font-size: 0.875rem;
  gap: 0.5rem;
  padding: 0.1875rem 0;
}

.filters__option input[type="checkbox"] {
  flex: 0 0 auto;
  margin: 0;
}

.filters__option input[type="number"] {
  border: 1px solid #ccc;
  border-radius: 0.25rem;
  font: inherit;
  padding: 0.1875rem 0.375rem;
  width: 4.5rem;
}

.filters__option-label {
  min-width: 0;
}

.filters__none {
  color: #777;
  font-size: 0.8125rem;
  margin: 0.25rem 0 0.5rem;
}

/* A value the URL asked for that had to be clamped into range (D-046). */
.filters__adjusted {
  color: #8a5300;
  font-size: 0.8125rem;
  margin: 0.25rem 0 0.5rem;
}

.filters__actions {
  align-items: center;
  border-top: 1px solid #e7e7e7;
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-top: 0.875rem;
  padding-top: 0.75rem;
}

.filters__apply {
  background: #1a4d8f;
  border: 1px solid #1a4d8f;
  border-radius: 0.25rem;
  color: #fff;
  cursor: pointer;
  font: inherit;
  padding: 0.3125rem 0.75rem;
}

.filters__apply:hover {
  background: #16427a;
}

.filters__clear {
  color: #1a4d8f;
  font-size: 0.875rem;
}
```

The 14rem cap on `.filters__options` (about 224 pixels) is the answer to a real number: the location list is managed on its own and can reach thousands of rows. Without a cap, the panel would grow until the Apply button was off the bottom of the page.

#### The rating — new

Three small rules give the average more weight than the review count, and grey out the empty state so it reads as absence rather than as a bad score.

New — `static/css/site.css:262`:

```css
.charity-card__rating {
  color: #444;
  display: flex;
  flex-wrap: wrap;
  font-size: 0.875rem;
  gap: 0.25rem;
}

.charity-card__rating--empty,
.rating__count {
  color: #777;
}

.rating__value {
  font-weight: 600;
}
```

What it buys: the panel is usable on a phone and does not push the results off the screen, and the one unbounded list on the page is bounded in the place that draws it.

---

### 7.9 `docs/DECISIONS.md` — the decisions this branch records

**Three decisions are recorded: the rating on the card, the filter groups, and the filter audit's corrections.**

The file is the project's log of decisions that fill gaps or override the customer's design document. This branch adds D-044, D-045 and D-046, plus three open questions.

The first decision says the card shows the average and the review count, both derived when the page is read, with "No reviews yet" for a charity nobody has reviewed — `docs/DECISIONS.md:407`:

```markdown
## D-044: The listing shows each charity's average rating and review count

- Date: 2026-11-13
- Decided by: CEO (Yosef), asked for directly
- Status: Active
- Design doc ref: §5.2.15, §5.3, §6.2.3
- Decision: Every card in the charity listing shows the charity's average rating and how many reviews it has. §5.3 has the listing page show "average rating", so that number is on the card, and the count goes with it because an average alone hides whether it is based on one review or fifty. Both are derived from REVIEW on read — nothing is stored, per §5.3's "derive data" rule — and a charity with no reviews shows "No reviews yet" instead of "0 out of 5", which would read as a rating of zero rather than no rating. The average is shown to one decimal. The repository annotates the page query with `Count`/`Avg` so the listing still costs no extra round trip, and the card carries the pair as `ReviewSummary(count, average)` where `average` is `None` when there are no reviews.
```

The second decision says the listing narrows by the document's seven groups, storing ids rather than names, using a 1–5 star scale, and treating zero as a real answer. Its opening line says "six" and its list is seven; see section 5 — `docs/DECISIONS.md:417`:

```markdown
## D-045: The charity listing filters by six groups, with the shape the doc gives them

- Date: 2026-11-13
- Decided by: CEO (Yosef), asked for directly; built by the filter branch
- Status: Superseded by D-046 on 2026-11-13, for the parameter-name correction and the min_rating range rule
- Design doc ref: §6.2.4 (Filter — FR 2), §8.5 (UC-03)
- Decision: `charities.services.list_charities` takes an optional `filters` mapping and narrows the listing by **six** of §6.2.4's seven groups: `domain`, `location`, `haskama_rabbis`, `min_rating`, `min_reviews`, `min_approving_haskamas`, `max_disapproving_haskamas` — that is all seven, with `haskama_rabbis` present in shape but unpopulated (see the sub-decision below). Values repeat inside a group (OR) and groups combine (AND), exactly as §6.2.4 says; setting any filter returns page 1. The groups mean, precisely:
```

The rest of D-045 is eight bullets, and they are the specification the code implements, so they are quoted in full — `docs/DECISIONS.md:424`:

```markdown
  - `domain`, `location`, `haskama_rabbi`: repeatable **ids** (`?domain=2&domain=5`), not names. A raw value that names no row is ignored rather than rejected, the same way the listing already treats a junk `page`. Ids because names are not keys: D-032 makes LOCATION unique on (name, region, country), so a name alone can point at several locations.
  - `min_rating`: a minimum **average star rating, 1–5 inclusive**, the scale `REVIEW.rating` holds and the one D-044 prints on the card ("4.5 out of 5"). There is no "no minimum" value: clearing the group is what clears it. A value off the scale is clamped into it and the sidebar says so (D-046). A charity with no reviews has no average, so it does not match a `min_rating` filter.
  - `min_reviews`: minimum `ReviewSummary.count`, the number D-044 already shows on the card.
  - `min_approving_haskamas` / `max_disapproving_haskamas`: minimum and maximum counts of `HASKAMA` rows with verdict `approve` / `disapprove`.
  - `0` is a real value for `min_reviews`, `min_approving_haskamas` and `max_disapproving_haskamas` ("no reviews", "no disapprovals"). An absent `max_disapproving_haskamas` is no cap, because absence cannot mean zero without ruling out every charity that has one.
- Sub-decision — `haskama_rabbis` returns nothing today: `HASKAMA` is queried in its real shape (`verdict`, `rabbi_user_id`), but the **option list** it needs is `accounts.services.search_rabbis`, which §6.2.4 names and which does not exist yet. Until it does, the group's options are empty and its parameter matches nothing; the query path is written and covered by a test with direct `HASKAMA` rows, so wiring the search in changes no other code. Asked for this way: "include whatever tables it needs in real form, but there happens to be no data, so you will have to give that result."
- Sub-decision — no `is_visible` filtering while D-042 stands: as of 2026-11-13 the listing shows charities that are not yet admin-approved (D-042), and the CEO's instruction is that every filter applies the same way, so rating, review and haskama counts are read from all charities' rows, published or not. Repositories filter on `is_visible` only through their existing `published_only` argument, so the day the approval queue flips it, the filters narrow with the listing and nothing else changes.
- Sub-decision — a location's label is its full identity: because a name is not unique, both the card chip and the filter checkbox label show name, region and country ("Lakewood, New Jersey, USA"), never the name alone.
```

The third decision records the audit's corrections: the singular rabbi name, the clamped-and-announced rating, the counts as ids, the zero that still shows, and the scrolling option list — `docs/DECISIONS.md:437`:

```markdown
## D-046: Filter audit corrections: the rabbi parameter is singular, an out-of-range rating filters nothing, and a chosen zero still shows

- Date: 2026-11-13
- Decided by: CEO (Yosef) and Platform Lead, on the filter-branch audit
- Status: Active
- Design doc ref: §6.2.4 (Filter — FR 2)
- Decision: Four corrections to D-045, three of which change what is built:
  - The Haskamos group's URL parameter is `haskama_rabbi` — singular, exactly as §6.2.4 writes it — not `haskama_rabbis` as D-045 recorded. The group's internal name stays `haskama_rabbis` (one rabbi filters by their id, several filter by several); only the URL surface is the doc's spelling. D-045 is superseded for its parameter-name and rating-range text, and stays active for everything else.
  - A `min_rating` outside 1–5 is **clamped into the scale, once, where the URL is read**, and the correction is shown instead of being silent: the sidebar's input displays the value actually applied and a note beside it says "Kept between 1 and 5; using 5." D-045's original clamp was invisible, which is what made `?min_rating=99` surprising; the problem was the silence, not the saturating.
  - The Haskamos group's values are **ids**, not the usernames §6.2.4's parameter line mentions. Ids survive a rabbi renaming their public name, match the other repeatable groups, and are what `accounts.services.search_rabbis` will feed the sidebar; the doc's "username" was a design note, not a contract. Decided here because D-045 asserted ids without saying the doc names usernames.
  - A chosen `0` in `max_disapproving_haskamas` (or any numeric group) renders as `0`, not as a blank box: the sidebar now carries an explicit `is_set` per group rather than inferring "set" from a truthy value.
  - This entry first said an out-of-range rating would be *ignored* rather than clamped, and that was built and reviewed. The CEO then chose clamping: "clamp it, but make it clear." Clamping therefore stands, and the audit finding is answered by making the correction visible. `clamp_rating` in `filters.py` is the one place it happens, so the query, the sidebar's input and the page links cannot disagree, and `sidebar_groups` receives the raw numbers `requested_numbers` read so it can compare and say what changed.
  - The repeatable groups' option lists scroll inside the panel (`.filters__options`, capped at 14rem) instead of growing without bound, so a real, thousands-row location list cannot push the Apply button off the page. The group table also collapsed into one `Group` entry per filter, keyed by URL parameter, so the code no longer keeps three lists that must agree.
```

Three questions that need a decision are recorded as undecided — `docs/DECISIONS.md:455`:

```markdown
- **2026-11-13: Where is "one review per member per charity" enforced?** §8.6 and UC-05 say a member has one review per charity, but REVIEW has no unique (charity, author) constraint and `save_review` does not exist yet. Options: enforce it only in the upsert service, or add a unique constraint too (a schema change, so decide before the review form lands). See `docs/NOTES.md` N1.
- **2026-11-13: Default statuses for APPROVAL_REQUEST and TICKET?** The doc (§5.2.5, §5.2.19) gives no default; the models default `ApprovalRequest.status` to `pending` and `Ticket.status` to `not_responded`. Those defaults are the only choices nobody has confirmed.
- **2026-11-13: Can users pick a rabbi in the listing filter yet?** §6.2.4 makes `haskama_rabbi` repeatable by rabbi and names `accounts.services.search_rabbis`, which does not exist. The filter is wired end to end but its option list is empty, so it matches nothing. Resolved as D-045 (sub-decision) on 2026-11-13; it becomes usable when `search_rabbis` lands.
```

The third of those is the one a reviewer will care about: the rabbi filter is present, matches nothing, and the pull request says so in three places rather than pretending otherwise.

Each of D-044, D-045 and D-046 also carries its reason and the code locations it touches. Those lines are not quoted here; the reasons are in section 4 and the locations are the file sections below, except for D-045's, which section 5 corrects.

What it buys: the choices this branch makes — ids instead of names, a 1–5 scale, zero as a real answer, a clamped and announced rating — are written down with their reasons, so a later change that reverses one has to argue with the record.

---

### 7.10 `docs/NOTES.md` — new: observations that are not decisions

**This new file gives observations a home that is not the decision log, and records the database audit plus eight findings from this branch's work.**

The file holds things someone checked, noticed or measured, where no decision has been made yet. It states its own filing rules at the top so it does not turn into a junk drawer.

Its four filing rules, quoted: a decision goes to the decision log, a question to that log's open-questions list, work to the task list, and a bare observation here — `docs/NOTES.md:3`:

```markdown
Where things go, so this file does not turn into a junk drawer:

- **A decision** goes in `docs/DECISIONS.md` as a `D-NNN` entry, with its date and who decided.
- **A question that needs a decision** goes in the Open questions list at the end of `docs/DECISIONS.md`.
- **Work to do** goes in `comtai` (`comtai add`), not here.
- **An observation** — something checked, noticed or measured, with no decision in it — goes here,
  newest first, with the date and how it was checked.
```

The audit's verdict, quoted: the tables match the design document, and every difference is already covered by a recorded decision — `docs/NOTES.md:18`:

```markdown
**Verdict: the schema matches the doc. No contradiction is undocumented.** All 19 tables exist.
Every column the doc lists exists with the same nullability and delete rule. All 8 indexes from
§5.2.20 exist in Postgres (`pg_indexes`). Every difference from the doc is a recording decision
already in `docs/DECISIONS.md`:
```

A nine-row table then lists each difference and the decision that covers it. The note also records that the chatbot, recommendations and dashboards apps own no tables, which is what the design document says.

The audit's findings, N1 to N4, are summarised rather than quoted, because each is a paragraph with one claim. They are, in order — `docs/NOTES.md:41` onward:

1. **N1. "One review per member per charity" is not enforced by the database.** No unique constraint on (charity, author); the rule would rest on a service that does not exist yet. Adding the constraint after reviews exist needs a cleanup migration, so it is cheaper to decide first. Raised as an open question and filed as work.
2. **N2. Two status columns have defaults the doc does not give.** Approval requests default to pending, tickets to not responded.
3. **N3. An old seed run tried to store a rating of 6.** The server log shows a rejected insert; the constraint did its job. The note says it is history, and that it proves the range check is load-bearing against developer data rather than only against requests.
4. **N4. The listing now reads review rows on every page view.** Since D-044 the page computes counts and averages; it costs no extra database question and uses an existing index, but it means the listing cannot render if review rows are unavailable.

The four filter findings, quoted where they are most specific — `docs/NOTES.md:64` onward:

```markdown
**N5. The filter sidebar resets a page correctly, but only because the form omits `page`.** The doc says "setting a filter resets page to 1", and it works: the sidebar form has no `page` input, so a fresh Apply always lands on page 1. A URL that *does* carry `?page=3&domain=2` keeps page 3, which is the faithful reading of UC-03 ("everything is stored in URL parameters"). Both behaviours are tested in `tests/unit/test_views.py`.

**N6. Two separate "no results" states exist and should not be confused.** A filtered listing with no matches shows "No charities match those filters."; an empty database shows "No charities found.". They are the same template line conditionally worded. §6.2.4 asks only for the first; the second predates the filter.

**N7. `min_rating` on an unreviewed charity behaves exactly like the card reads it.** A charity with no reviews has no average (D-044 shows "No reviews yet", and `ReviewSummary.average` is `None`), so `min_rating` simply never matches it. The alternative — treating "no reviews" as a rating of 0 — was considered and rejected in D-045.

**N8. The seeded database has no rabbi rows to tick.** The Haskamos group's options are empty until `accounts.services.search_rabbis` exists, so it is wired but returns nothing (D-045). To see the group work in a browser, a developer must add `HASKAMA` rows by hand, which is why the unit tests create them directly.
```

The most valuable of those for a reviewer is N5, because it explains a behaviour that looks like a bug and is not: a web address that already says page three keeps page three, while a fresh Apply goes to page one, and both are intended.

What it buys: the observations made while doing this work — including the honest ones about what the page now depends on and what cannot be tried in a browser yet — are written down where the next person will look, instead of living in this pull request's comment thread.

---

### 7.11 `.gitignore` — one line

**Throwaway screenshots stay out of git.**

The file lists what git should not track. The branch adds the directory it used for temporary screenshots while checking the page.

Before — `.gitignore:31`:

```gitignore
# Generated local secret for dev.sh; never committed
.env.local-key
```

After — `.gitignore:31`:

```gitignore
# Generated local secret for dev.sh; never committed
.env.local-key
+.tmp-shots/
```

What it buys: nothing in the product. It keeps a developer's scratch screenshots out of the repository, which is all it claims to do.

---

### 7.12 `tests/unit/test_filter_service.py` — the address reader and the panel, without a database

**This new file pins the rules that need no rows: what an address means, what a panel group contains, and where the clamp happens.**

It tests the service and filter layers using a stand-in database helper that records what it was asked for. That is why it can run in milliseconds and why it can test a page with no database at all.

The stand-in, quoted because every test in the file depends on it — `tests/unit/test_filter_service.py:22`:

```python
class FakeRepository:
    """Records the filters it was handed and returns a fixed set."""

    def __init__(self) -> None:
        self.seen: list[CharityFilters] = []

    def page(self, offset, limit, filters) -> tuple[CharityCard, ...]:
        self.seen.append(filters)
        return ()

    def count(self, filters) -> int:
        self.seen.append(filters)
        return 0
```

The address tests, quoted as a group, because together they define what a link may say — `tests/unit/test_filter_service.py:37`:

```python
class FiltersFromQueryTest(SimpleTestCase):
    """§6.2.4's parameter names are the app's public URL surface."""

    def test_no_parameters_means_no_filters(self) -> None:
        filters = from_query(_Query({}))

        self.assertEqual(filters, CharityFilters())
        self.assertTrue(filters.is_empty)

    def test_repeatable_parameters_collect_every_value(self) -> None:
        filters = from_query(_Query({"domain": ["2", "5"], "location": ["7"]}))

        self.assertEqual(filters.domains, (2, 5))
        self.assertEqual(filters.locations, (7,))

    def test_repeated_ids_are_kept_once(self) -> None:
        filters = from_query(_Query({"domain": ["2", "2", "5"]}))

        self.assertEqual(filters.domains, (2, 5))

    def test_numbers_are_read(self) -> None:
        filters = from_query(
            _Query(
                {
                    "min_rating": ["4"],
                    "min_reviews": ["2"],
                    "min_approving_haskamas": ["1"],
                    "max_disapproving_haskamas": ["0"],
                }
            )
        )

        self.assertEqual(filters.min_rating, 4)
        self.assertEqual(filters.min_reviews, 2)
        self.assertEqual(filters.min_approving_haskamas, 1)
        self.assertEqual(filters.max_disapproving_haskamas, 0)

    def test_zero_is_a_real_number(self) -> None:
        """0 means "no reviews" or "no disapprovals", not "unset" (D-045)."""
        filters = from_query(_Query({"min_reviews": ["0"], "max_disapproving_haskamas": ["0"]}))

        self.assertEqual(filters.min_reviews, 0)
        self.assertEqual(filters.max_disapproving_haskamas, 0)
        self.assertFalse(filters.is_empty)

    def test_junk_values_are_dropped_not_rejected(self) -> None:
        filters = from_query(
            _Query(
                {
                    "domain": ["abc", "0", "-3", ""],
                    "min_rating": ["lots"],
                    "min_reviews": [""],
                }
            )
        )

        self.assertEqual(filters.domains, ())
        self.assertIsNone(filters.min_rating)
        self.assertIsNone(filters.min_reviews)
        self.assertTrue(filters.is_empty)

    def test_unknown_parameters_are_ignored(self) -> None:
        filters = from_query(_Query({"sort": ["name"], "search": ["keren"]}))

        self.assertEqual(filters, CharityFilters())

    def test_active_count_counts_groups_and_values(self) -> None:
        filters = from_query(_Query({"domain": ["1"], "min_rating": ["4"]}))

        self.assertEqual(filters.active_count(), 2)
```

The round-trip test is the one that protects shared links, because it writes a set of answers to an address and reads them back — `tests/unit/test_filter_service.py:109`:

```python
class FiltersQueryStringTest(SimpleTestCase):
    """A page link must repeat the filters it was made under."""

    def test_empty_filters_make_an_empty_string(self) -> None:
        self.assertEqual(query_string(CharityFilters()), "")

    def test_repeatable_and_numeric_groups_round_trip(self) -> None:
        filters = CharityFilters(domains=(1, 2), min_rating=4, min_reviews=0)

        self.assertEqual(query_string(filters), "domain=1&domain=2&min_rating=4&min_reviews=0")
        self.assertEqual(from_query(_Query(_parse(query_string(filters)))), filters)

    def test_pairs_keep_a_zero(self) -> None:
        self.assertIn(("min_reviews", 0), query_pairs(CharityFilters(min_reviews=0)))
```

The panel tests, quoted for the decisions they pin — the seven-group order, the empty rabbi note, the bound on the rating box, and the three-part place label — `tests/unit/test_filter_service.py:125`:

```python
class SidebarGroupsTest(SimpleTestCase):
    def test_all_seven_groups_appear_in_the_doc_order(self) -> None:
        groups = sidebar_groups(CharityFilters(), {})

        self.assertEqual(
            [group.parameter for group in groups],
            [
                "domain",
                "location",
                "haskama_rabbi",
                "min_rating",
                "min_reviews",
                "min_approving_haskamas",
                "max_disapproving_haskamas",
            ],
        )

    def test_repeatable_groups_are_checkboxes_with_their_options(self) -> None:
        class Option:
            id = 3
            name = "Free loans"

        groups = sidebar_groups(CharityFilters(), {"domains": (Option(),)})

        domain = groups[0]
        self.assertEqual(domain.kind, "checkboxes")
        self.assertEqual([(o.id, o.label) for o in domain.options], [(3, "Free loans")])

    def test_selected_options_come_from_the_filters(self) -> None:
        class Option:
            id = 3
            name = "Free loans"

        groups = sidebar_groups(CharityFilters(domains=(3,)), {"domains": (Option(),)})

        self.assertEqual(groups[0].selected, (3,))

    def test_a_group_with_no_options_says_so(self) -> None:
        """D-045: the rabbi group is real but accounts cannot list rabbis yet."""
        groups = sidebar_groups(CharityFilters(), {})

        rabbis = next(group for group in groups if group.parameter == "haskama_rabbi")
        self.assertEqual(rabbis.options, ())
        self.assertTrue(rabbis.empty_note)

    def test_numbers_are_single_inputs_bounded_by_the_star_scale(self) -> None:
        groups = sidebar_groups(CharityFilters(min_rating=3), {})
        rating = next(group for group in groups if group.parameter == "min_rating")

        self.assertEqual(rating.kind, "number")
        self.assertEqual(rating.value, 3)
        self.assertEqual((rating.min, rating.max), (MIN_STAR_RATING, MAX_STAR_RATING))

    def test_a_location_option_is_labelled_by_its_full_identity(self) -> None:
        class Option:
            id = 1
            name = "Lakewood"
            region = "New Jersey"
            country = "USA"

            @property
            def label(self) -> str:
                return f"{self.name}, {self.region}, {self.country}"

        groups = sidebar_groups(CharityFilters(), {"locations": (Option(),)})

        location = next(group for group in groups if group.parameter == "location")
        self.assertEqual(location.options[0].label, "Lakewood, New Jersey, USA")

    def test_an_empty_maximum_has_no_cap(self) -> None:
        groups = sidebar_groups(CharityFilters(), {})
        most = next(g for g in groups if g.parameter == "max_disapproving_haskamas")

        self.assertIsNone(most.value)
        self.assertTrue(most.none_note)
```

The parameter-spelling tests, quoted because they are the ones that would fail if someone "tidied up" the singular name — `tests/unit/test_filter_service.py:250`:

```python
class DocParameterNamesTest(SimpleTestCase):
    """The URL surface is §6.2.4's, verbatim (D-046)."""

    def test_the_parameters_are_the_docs_own_spelling(self) -> None:
        from apps.charities.filters import GROUPS

        self.assertEqual(
            [group.parameter for group in GROUPS],
            [
                "domain",
                "location",
                "haskama_rabbi",
                "min_rating",
                "min_reviews",
                "min_approving_haskamas",
                "max_disapproving_haskamas",
            ],
        )

    def test_the_rabbi_parameter_is_singular_like_the_doc(self) -> None:
        filters = from_query(_Query({"haskama_rabbi": ["7"]}))

        self.assertEqual(filters.haskama_rabbis, (7,))
        self.assertEqual(query_string(filters), "haskama_rabbi=7")

    def test_the_plural_spelling_is_not_accepted(self) -> None:
        """D-045 used `haskama_rabbis`; D-046 replaced it, not aliased it."""
        filters = from_query(_Query({"haskama_rabbis": ["7"]}))

        self.assertEqual(filters.haskama_rabbis, ())
```

The last two classes pin the D-046 behaviours, quoted together — `tests/unit/test_filter_service.py:282`:

```python
class OutOfRangeRatingTest(SimpleTestCase):
    """A rating off the 1-5 scale is clamped, and the correction is visible (D-046)."""

    def test_a_rating_above_the_scale_is_clamped_and_flagged(self) -> None:
        groups = sidebar_groups(CharityFilters(min_rating=5), {}, requested={"min_rating": 99})
        rating = next(g for g in groups if g.parameter == "min_rating")

        self.assertEqual(rating.value, 5)
        self.assertTrue(rating.is_set)
        self.assertIn("Kept between 1 and 5", rating.adjusted_note)

    def test_an_in_range_rating_has_no_correction_note(self) -> None:
        groups = sidebar_groups(CharityFilters(min_rating=4), {}, requested={"min_rating": 4})

        rating = next(g for g in groups if g.parameter == "min_rating")

        self.assertEqual(rating.adjusted_note, "")


class ZeroIsSetTest(SimpleTestCase):
    """A chosen 0 is a filter, so the sidebar must not render it as blank (D-046)."""

    def test_zero_reads_as_set(self) -> None:
        groups = sidebar_groups(CharityFilters(max_disapproving_haskamas=0), {})
        most = next(g for g in groups if g.parameter == "max_disapproving_haskamas")

        self.assertTrue(most.is_set)
        self.assertEqual(most.value, 0)

    def test_absent_does_not_read_as_set(self) -> None:
        groups = sidebar_groups(CharityFilters(), {})
        most = next(g for g in groups if g.parameter == "max_disapproving_haskamas")

        self.assertFalse(most.is_set)
        self.assertIsNone(most.value)

    def test_a_ticked_group_reads_as_set(self) -> None:
        class Option:
            id = 2
            name = "Free loans"

        groups = sidebar_groups(CharityFilters(domains=(2,)), {"domains": (Option(),)})

        self.assertTrue(groups[0].is_set)
```

The remaining tests in the file — the blank-number test and the two tests that prove the answers reach the database helper — are listed by name in section 8.

What it buys: the rules with the most edge cases — zero, blanks, junk, repeats, singular versus plural — are pinned without a database, so they run fast and fail with a clear message.

---

### 7.13 `tests/unit/test_filter_repository.py` — the narrowing, against real rows

**This new file checks that the seven groups keep the right charities when the data is real, including the counts the cards print.**

It needs the database because what it tests is how seven answers become one question: "either" inside a group, "and" between groups, and a count that does not double when a charity has two causes.

The domain tests, quoted — `tests/unit/test_filter_repository.py:17`:

```python
class DomainFilterTest(TestCase):
    def setUp(self) -> None:
        self.a = Charity.objects.create(name="Alpha")
        self.b = Charity.objects.create(name="Beta")
        self.general = Domain.objects.create(name="General")
        self.food = Domain.objects.create(name="Food Security")
        self.a.domains.add(self.general, self.food)
        self.b.domains.add(self.general)

    def test_a_domain_selects_charities_in_it(self) -> None:
        cards = self._page(CharityFilters(domains=(self.food.id,)))

        self.assertEqual([card.name for card in cards], ["Alpha"])

    def test_domains_are_or(self) -> None:
        """Two domains together match a charity in either one (§6.2.4)."""
        cards = self._page(CharityFilters(domains=(self.food.id, self.b.domains.first().id)))

        self.assertEqual({card.name for card in cards}, {"Alpha", "Beta"})

    def test_two_domains_on_one_charity_count_once(self) -> None:
        cards = self._page(CharityFilters(domains=(self.general.id, self.food.id)))

        self.assertEqual([card.name for card in cards], ["Alpha", "Beta"])
        self.assertEqual(
            DjangoCharityRepository().count(
                CharityFilters(domains=(self.general.id, self.food.id))
            ),
            2,
        )

    def _page(self, filters):
        return DjangoCharityRepository().page(0, 10, filters)
```

That third test is the one that would fail without the rule that asks for distinct charities: Alpha has both causes, so a naive database question would list it twice and count it twice.

The place and rabbi tests, quoted because the rabbi group is the wired-but-empty one, and because it makes a choice worth seeing: any haskama by that rabbi counts, approval or objection — `tests/unit/test_filter_repository.py:52`:

```python
class LocationFilterTest(TestCase):
    def test_a_location_selects_and_is_distinct(self) -> None:
        charity = Charity.objects.create(name="Alpha")
        first = Location.objects.create(name="Lakewood", region="NJ", country="USA")
        second = Location.objects.create(name="Monsey", region="NY", country="USA")
        charity.locations.add(first, second)

        cards = DjangoCharityRepository().page(0, 10, CharityFilters(locations=(first.id,)))

        self.assertEqual([card.name for card in cards], ["Alpha"])

    def test_locations_are_or(self) -> None:
        charity = Charity.objects.create(name="Alpha")
        first = Location.objects.create(name="Lakewood", region="NJ", country="USA")
        second = Location.objects.create(name="Monsey", region="NY", country="USA")
        charity.locations.add(first, second)

        cards = DjangoCharityRepository().page(0, 10, CharityFilters(locations=(second.id,)))

        self.assertEqual([card.name for card in cards], ["Alpha"])


class HaskamaRabbiFilterTest(TestCase):
    def test_a_rabbi_selects_charities_they_endorsed(self) -> None:
        charity = Charity.objects.create(name="Alpha")
        other = Charity.objects.create(name="Beta")
        rabbi = UserFactory()
        other_rabbi = UserFactory()
        Haskama.objects.create(rabbi_user=rabbi, charity=charity, verdict=Haskama.Verdict.APPROVE)
        Haskama.objects.create(
            rabbi_user=other_rabbi, charity=other, verdict=Haskama.Verdict.APPROVE
        )

        cards = DjangoCharityRepository().page(0, 10, CharityFilters(haskama_rabbis=(rabbi.id,)))

        self.assertEqual([card.name for card in cards], ["Alpha"])

    def test_rabbis_are_or(self) -> None:
        charity = Charity.objects.create(name="Alpha")
        other = Charity.objects.create(name="Beta")
        first = UserFactory()
        second = UserFactory()
        Haskama.objects.create(rabbi_user=first, charity=charity, verdict=Haskama.Verdict.APPROVE)
        Haskama.objects.create(rabbi_user=second, charity=other, verdict=Haskama.Verdict.APPROVE)

        cards = DjangoCharityRepository().page(
            0, 10, CharityFilters(haskama_rabbis=(first.id, second.id))
        )

        self.assertEqual({card.name for card in cards}, {"Alpha", "Beta"})

    def test_a_disapproving_haskama_still_counts_as_endorsement(self) -> None:
        """The group matches any haskama, approve or disapprove (D-045)."""
        charity = Charity.objects.create(name="Alpha")
        rabbi = UserFactory()
        Haskama.objects.create(
            rabbi_user=rabbi, charity=charity, verdict=Haskama.Verdict.DISAPPROVE
        )

        cards = DjangoCharityRepository().page(0, 10, CharityFilters(haskama_rabbis=(rabbi.id,)))

        self.assertEqual([card.name for card in cards], ["Alpha"])
```

The rating tests, quoted, because they tie the card's number to the filter's comparison — `tests/unit/test_filter_repository.py:116`:

```python
class MinRatingFilterTest(TestCase):
    def setUp(self) -> None:
        self.rated = Charity.objects.create(name="Rated")
        self.unrated = Charity.objects.create(name="Unrated")
        author = UserFactory()
        for rating in (5, 4):
            Review.objects.create(charity=self.rated, author=author, rating=rating)

    def test_filters_by_average_star_rating(self) -> None:
        cards = self._page(min_rating=4)

        self.assertEqual([card.name for card in cards], ["Rated"])

    def test_a_charity_with_no_reviews_has_no_average_and_does_not_match(self) -> None:
        cards = self._page(min_rating=1)

        self.assertEqual([card.name for card in cards], ["Rated"])

    def test_lower_bound_is_inclusive(self) -> None:
        """The average is 4.5, so 4 keeps the charity and 5 does not."""
        self.assertEqual([c.name for c in self._page(min_rating=4)], ["Rated"])
        self.assertEqual([c.name for c in self._page(min_rating=5)], [])

    def test_cards_show_the_same_average_the_filter_uses(self) -> None:
        card = self._page(min_rating=4)[0]

        self.assertEqual(card.reviews.average, 4.5)
        self.assertEqual(card.reviews.count, 2)

    def _page(self, min_rating):
        return DjangoCharityRepository().page(0, 10, CharityFilters(min_rating=min_rating))
```

The count tests, quoted — `tests/unit/test_filter_repository.py:149`:

```python
class MinReviewsFilterTest(TestCase):
    def test_counts_reviews(self) -> None:
        busy = Charity.objects.create(name="Busy")
        Charity.objects.create(name="Quiet")
        author = UserFactory()
        Review.objects.create(charity=busy, author=author, rating=5)
        Review.objects.create(charity=busy, author=author, rating=3)

        cards = DjangoCharityRepository().page(0, 10, CharityFilters(min_reviews=2))

        self.assertEqual([card.name for card in cards], ["Busy"])

    def test_zero_matches_even_a_charity_with_no_reviews(self) -> None:
        """D-045: 0 is a real lower bound, not "unset"."""
        Charity.objects.create(name="Quiet")

        cards = DjangoCharityRepository().page(0, 10, CharityFilters(min_reviews=0))

        self.assertEqual([card.name for card in cards], ["Quiet"])


class HaskamaCountFilterTest(TestCase):
    def test_min_approving_haskamas_counts_approve_verdicts(self) -> None:
        charity = Charity.objects.create(name="Approved")
        other = Charity.objects.create(name="Other")
        first = UserFactory()
        second = UserFactory()
        Haskama.objects.create(rabbi_user=first, charity=charity, verdict=Haskama.Verdict.APPROVE)
        Haskama.objects.create(rabbi_user=second, charity=charity, verdict=Haskama.Verdict.APPROVE)
        Haskama.objects.create(rabbi_user=first, charity=other, verdict=Haskama.Verdict.APPROVE)

        cards = DjangoCharityRepository().page(0, 10, CharityFilters(min_approving_haskamas=2))

        self.assertEqual([card.name for card in cards], ["Approved"])

    def test_max_disapproving_haskamas_counts_disapprove_verdicts(self) -> None:
        charity = Charity.objects.create(name="Approved")
        other = Charity.objects.create(name="Disputed")
        first = UserFactory()
        second = UserFactory()
        Haskama.objects.create(rabbi_user=first, charity=other, verdict=Haskama.Verdict.DISAPPROVE)
        Haskama.objects.create(rabbi_user=second, charity=other, verdict=Haskama.Verdict.DISAPPROVE)
        Haskama.objects.create(rabbi_user=first, charity=charity, verdict=Haskama.Verdict.APPROVE)

        cards = DjangoCharityRepository().page(0, 10, CharityFilters(max_disapproving_haskamas=1))

        self.assertEqual([card.name for card in cards], ["Approved"])

    def test_zero_disapproving_haskamas_means_none_at_all(self) -> None:
        Charity.objects.create(name="Clean")
        disputed = Charity.objects.create(name="Disputed")
        rabbi = UserFactory()
        Haskama.objects.create(
            rabbi_user=rabbi, charity=disputed, verdict=Haskama.Verdict.DISAPPROVE
        )

        cards = DjangoCharityRepository().page(0, 10, CharityFilters(max_disapproving_haskamas=0))

        self.assertEqual([card.name for card in cards], ["Clean"])
```

The combination tests, quoted — `tests/unit/test_filter_repository.py:210`:

```python
class CombinedFiltersTest(TestCase):
    def test_groups_are_and(self) -> None:
        """A domain AND a rating must both hold (§6.2.4)."""
        food = Domain.objects.create(name="Food Security")
        in_food = Charity.objects.create(name="In food")
        also_in_food = Charity.objects.create(name="In food, poorly rated")
        in_food.domains.add(food)
        also_in_food.domains.add(food)
        author = UserFactory()
        Review.objects.create(charity=in_food, author=author, rating=5)
        Review.objects.create(charity=also_in_food, author=author, rating=2)

        cards = DjangoCharityRepository().page(
            0, 10, CharityFilters(domains=(food.id,), min_rating=4)
        )

        self.assertEqual([card.name for card in cards], ["In food"])

    def test_the_counts_are_recomputed_together(self) -> None:
        food = Domain.objects.create(name="Food Security")
        charity = Charity.objects.create(name="Alpha")
        other = Charity.objects.create(name="Beta")
        charity.domains.add(food)
        author = UserFactory()
        for rating in (5, 5):
            Review.objects.create(charity=charity, author=author, rating=rating)
        Review.objects.create(charity=other, author=author, rating=5)

        cards = DjangoCharityRepository().page(
            0, 10, CharityFilters(domains=(food.id,), min_rating=5, min_reviews=2)
        )

        self.assertEqual([card.name for card in cards], ["Alpha"])


class CountRespectsFiltersTest(TestCase):
    def test_count_matches_the_filtered_set(self) -> None:
        food = Domain.objects.create(name="Food Security")
        charity = Charity.objects.create(name="Alpha")
        other = Charity.objects.create(name="Beta")
        charity.domains.add(food)
        other.domains.add(food)

        repository = DjangoCharityRepository()
        filters = CharityFilters(domains=(food.id,))
        self.assertEqual(repository.count(filters), 2)
        self.assertEqual(repository.count(CharityFilters(domains=(food.id, 999999))), 2)
```

The last assertion is worth a sentence: an id that names no row is harmless. It can match nothing, so the result is the same as if it had been dropped, and the code does not need to check the id exists first.

The option-list tests, quoted — `tests/unit/test_filter_repository.py:259`:

```python
class FilterOptionsRepositoryTest(TestCase):
    def test_domains_and_locations_come_from_the_shared_lists(self) -> None:
        from apps.charities.repositories import DjangoFilterOptionsRepository

        domain = Domain.objects.create(name="Education")
        Location.objects.create(name="Lakewood", region="NJ", country="USA")

        options = DjangoFilterOptionsRepository()

        self.assertEqual([(o.id, o.name) for o in options.domains()], [(domain.id, "Education")])
        self.assertEqual([o.label for o in options.locations()], ["Lakewood, NJ, USA"])

    def test_rabbis_are_empty_until_accounts_can_list_them(self) -> None:
        from apps.charities.repositories import DjangoFilterOptionsRepository

        self.assertEqual(DjangoFilterOptionsRepository().rabbis(), ())
```

The clamp and scroll tests, quoted — `tests/unit/test_filter_repository.py:277`:

```python
class RatingClampTest(TestCase):
    """D-046: min_rating is clamped into the 1-5 scale, and the clamp is visible.

    The repository compares what it is given; the clamp happens where the URL is
    read, so these tests exercise `from_query` and the sidebar's correction note.
    """

    def setUp(self) -> None:
        self.rated = Charity.objects.create(name="Rated")
        self.unrated = Charity.objects.create(name="Unrated")
        author = UserFactory()
        Review.objects.create(charity=self.rated, author=author, rating=5)

    def test_from_query_clamps_above_the_scale_to_five(self) -> None:
        filters = from_query(QueryDict("min_rating=99"))

        self.assertEqual(filters.min_rating, 5)
        cards = DjangoCharityRepository().page(0, 10, filters)
        self.assertEqual([c.name for c in cards], ["Rated"])

    def test_from_query_clamps_below_the_scale_to_one(self) -> None:
        filters = from_query(QueryDict("min_rating=0"))

        self.assertEqual(filters.min_rating, 1)
        # min_rating=1 still excludes the unreviewed charity: it has no average.
        cards = DjangoCharityRepository().page(0, 10, filters)
        self.assertEqual([c.name for c in cards], ["Rated"])

    def test_inside_the_scale_is_untouched(self) -> None:
        self.assertEqual(from_query(QueryDict("min_rating=4")).min_rating, 4)


class ScrollableOptionListTest(TestCase):
    """D-046: the repeatable groups' options scroll instead of unrolling."""

    def test_options_are_wrapped_in_a_scrollable_panel(self) -> None:
        from django.test import Client

        body = Client().get("/charity/").content.decode()

        self.assertIn('class="filters__options"', body)
        self.assertIn("tabindex", body)
```

That last test checks the text of the page rather than its behaviour. It is the cheapest way to pin "the option list is bounded"; the actual bound lives in the stylesheet, which no test reads.

What it buys: the transformation from seven answers to one database question is tested where it is hardest — real rows, real labels, real counts — including the two ways a count can go wrong (a duplicated charity and a filter that counts the wrong verdict).

---

### 7.14 `tests/unit/test_repositories.py` — the old tests, reshaped, plus the rating

**The existing repository tests now pass the empty answer set, and three new tests pin the rating mapping and its database cost.**

The file tests the database helper's mapping from rows to cards. It changed because the helper's two methods now require answers, and because a card now carries a review summary.

#### Every existing call — before and after

Before, the helper was called with just a window. After, every call passes the empty answer set, which means "no narrowing" and keeps the old expectations meaningful.

Before — `tests/unit/test_repositories.py:14`:

```python
class DjangoCharityRepositoryTest(TestCase):
    def setUp(self) -> None:
        self.repository = DjangoCharityRepository()

    def test_returns_cards_in_name_order(self) -> None:
        for name in ["Zohar Fund", "Adas Chessed", "Mercaz Tzedaka"]:
            Charity.objects.create(name=name)

        cards = self.repository.page(offset=0, limit=10)
```

After — `tests/unit/test_repositories.py:16`:

```python
class DjangoCharityRepositoryTest(TestCase):
    def setUp(self) -> None:
        self.repository = DjangoCharityRepository()
        self.no_filters = CharityFilters()

    def test_returns_cards_in_name_order(self) -> None:
        for name in ["Zohar Fund", "Adas Chessed", "Mercaz Tzedaka"]:
            Charity.objects.create(name=name)

        cards = self.repository.page(filters=self.no_filters, offset=0, limit=10)
```

The same change repeats in seven more tests: `test_maps_domains_and_locations`, `test_window_skips_preceding_rows`, `test_count_matches_rows`, `test_card_does_not_leak_model_behaviour`, `test_loads_relations_without_extra_queries`, and both `PublishedOnlyTest` tests. Only one assertion changed meaning: the place label test now expects the full three-part string.

Before — `tests/unit/test_repositories.py:45`:

```python
self.assertEqual([loc.name for loc in card.locations], ["Lakewood"])
```

After — `tests/unit/test_repositories.py:48`:

```python
self.assertEqual([loc.label for loc in card.locations], ["Lakewood, NJ, USA"])
```

#### The rating mapping — new

Two tests pin the conversion from review rows to the card's summary, including the empty case that must not read as a zero. A third pins the cost: adding reviews must not add one database question per charity.

New — `tests/unit/test_repositories.py:83`:

```python
def test_maps_review_average_and_count(self) -> None:
    """§5.3: the average rating is derived from the reviews, not stored."""
    author = UserFactory()
    charity = Charity.objects.create(name="Keren L'Dugma")
    for rating in (2, 4, 5):
        Review.objects.create(charity=charity, author=author, rating=rating)

    card = self.repository.page(filters=self.no_filters, offset=0, limit=1)[0]

    self.assertEqual(card.reviews.count, 3)
    self.assertAlmostEqual(card.reviews.average, 11 / 3)


def test_charity_without_reviews_has_no_average(self) -> None:
    Charity.objects.create(name="Keren L'Dugma")

    card = self.repository.page(filters=self.no_filters, offset=0, limit=1)[0]

    self.assertEqual(card.reviews, ReviewSummary(count=0, average=None))


def test_reviews_do_not_add_queries_per_charity(self) -> None:
    author = UserFactory()
    for index in range(1, 4):
        charity = Charity.objects.create(name=f"Charity {index:02d}")
        Review.objects.create(charity=charity, author=author, rating=5)

    with self.assertNumQueries(3):  # page and the two prefetches
        self.repository.page(filters=self.no_filters, offset=0, limit=10)
```

The `assertNumQueries(3)` is the assertion that keeps the front door fast: one database question for the page (which now includes the review arithmetic) and two for the labels. If someone later adds a review lookup inside the card-building loop, this test fails.

What it buys: the helper's existing promises are still tested, the new rating has both a normal case and an empty case, and the number of database questions is pinned so the feature cannot quietly become slower.

---

### 7.15 `tests/unit/test_services.py` — the stand-in types catch up to the card

**The service tests' fake card and fake helper now carry a review summary and accept answers, so the paging tests still describe the real records.**

This file tests the listing's page and size rules using a stand-in helper. It needed two changes: the card factory gained the new field, and the stand-in's methods accepted the answers they now receive.

Before — `tests/unit/test_services.py:19`:

```python
def card(name: str) -> CharityCard:
    return CharityCard(
        id=1,
        name=name,
        tagline="",
        image="",
        domains=(DomainTag(name="Free loans"),),
        locations=(LocationTag(name="Lakewood"),),
    )
```

After — `tests/unit/test_services.py:19`:

```python
def card(name: str) -> CharityCard:
    return CharityCard(
        id=1,
        name=name,
        tagline="",
        image="",
        domains=(DomainTag(name="Free loans"),),
        locations=(LocationTag(name="Lakewood", region="NJ", country="USA"),),
        reviews=ReviewSummary(count=0, average=None),
    )
```

Before — `tests/unit/test_services.py:36`:

```python
def page(self, offset: int, limit: int) -> tuple[CharityCard, ...]:
    return self._cards[offset : offset + limit]


def count(self) -> int:
    return len(self._cards)
```

After — `tests/unit/test_services.py:36`:

```python
def page(
    self, offset: int, limit: int, filters: CharityFilters | None = None
) -> tuple[CharityCard, ...]:
    return self._cards[offset : offset + limit]


def count(self, filters: CharityFilters | None = None) -> int:
    return len(self._cards)
```

The default `None` is what keeps the existing tests readable: they are about paging, not filtering, and they now say so by not mentioning answers at all.

What it buys: nothing in the product. It keeps the paging tests honest about the shape of a card, so a future field on the card cannot be added without this file noticing.

---

### 7.16 `tests/unit/test_template_contract.py` — what the page is allowed to read

**Two rating tests are added to the card contract, and a new class pins the panel's contract with the template.**

Django templates fail silently: a template that asks for a field a record does not have renders nothing and raises no error. This file exists to turn those silences into failures. The branch extends it to the new rating and to the panel.

#### The card contract — new tests and an extended one

The card test's sensor list gains `reviews`, and its docstring says so. Two rendering tests are new: one for a normal rating and one for the empty state.

New — `tests/unit/test_template_contract.py:62`:

```python
def test_review_summary_renders(self) -> None:
    author = UserFactory()
    charity = Charity.objects.create(name="Keren L'Dugma")
    for rating in (4, 5):
        Review.objects.create(charity=charity, author=author, rating=rating)

    body = self._render_single_charity()

    self.assertIn("4.5 out of 5", body)
    self.assertIn("2 reviews", body)


def test_charity_without_reviews_says_so(self) -> None:
    """The empty state stands in for the rating, rather than showing 0 out of 5."""
    Charity.objects.create(name="Keren L'Dugma")

    body = self._render_single_charity()

    self.assertIn("No reviews yet", body)
    self.assertNotIn("out of 5", body)
```

Before, the attribute list covered five fields; after, it covers six, and the place assertion reads the full label.

Before — `tests/unit/test_template_contract.py:77`:

```python
for attribute in ("name", "tagline", "image", "domains", "locations"):
    self.assertTrue(hasattr(card, attribute), attribute)

self.assertEqual(list(card.domains)[0].name, "Free loans")
self.assertEqual(list(card.locations)[0].name, "Lakewood")
self.assertFalse(hasattr(card.domains, "all"))
```

After — `tests/unit/test_template_contract.py:101`:

```python
for attribute in ("name", "tagline", "image", "domains", "locations", "reviews"):
    self.assertTrue(hasattr(card, attribute), attribute)

# The template iterates these directly, so they must be iterable and
# must not be ORM managers left over from the old contract.
self.assertEqual(list(card.domains)[0].name, "Free loans")
self.assertEqual(list(card.locations)[0].label, "Lakewood, NJ, USA")
self.assertFalse(hasattr(card.domains, "all"))
self.assertEqual(card.reviews.count, 2)
self.assertEqual(card.reviews.average, 4.5)
```

#### `FilterSidebarContractTest` — new

Before, nothing checked the panel at all, because there was no panel. The new class asks the rendered page five questions: does every group have its heading, do the checkbox groups name their inputs after their web-address parameter, does each number group render one bounded input, does the form submit in the web address, and did any template comment leak into the page.

New — `tests/unit/test_template_contract.py:120`:

```python
class FilterSidebarContractTest(TestCase):
    """The sidebar template reads only fields `FilterForm` guarantees (D-045).

    Django templates fail silently, so a group that loses its `legend` or
    `kind` would render an empty panel with no error. These pin the contract.
    """

    def setUp(self) -> None:
        self.url = reverse("charities:listing")

    def test_every_group_renders_a_legend(self) -> None:
        body = self.client.get(self.url).content.decode()

        for legend in [
            "Domains",
            "Locations",
            "Haskamos",
            "Rating",
            "Reviews",
            "Approving haskamos",
            "Disapproving haskamos",
        ]:
            self.assertIn(legend, body)

    def test_checkbox_groups_render_inputs_named_by_their_parameter(self) -> None:
        Domain.objects.create(name="Free loans")
        Location.objects.create(name="Lakewood", region="NJ", country="USA")

        body = self.client.get(self.url).content.decode()

        self.assertIn('type="checkbox"', body)
        self.assertIn('name="domain"', body)
        self.assertIn('name="location"', body)

    def test_number_groups_render_one_bounded_input_each(self) -> None:
        body = self.client.get(self.url).content.decode()

        self.assertIn('name="min_rating"', body)
        self.assertIn('min="1"', body)
        self.assertIn('max="5"', body)
        self.assertIn('name="max_disapproving_haskamas"', body)

    def test_the_form_is_a_get(self) -> None:
        """Filters live in the URL, so the form must not post (UC-03)."""
        body = self.client.get(self.url).content.decode()

        self.assertIn('<form class="filters" method="get"', body)

    def test_no_template_comment_leaks_into_the_page(self) -> None:
        body = self.client.get(self.url).content.decode()

        self.assertNotIn("{#", body)
        self.assertNotIn("{%", body)
```

The last test is a nice example of a cheap assertion with a real failure behind it: a mistyped comment marker would print the comment's text to every visitor, and this test would catch it.

What it buys: the panel cannot lose a heading, a parameter name, a bound, or its way of submitting without a test failing — and those are exactly the failures a template makes quietly.

---

### 7.17 `tests/unit/test_views.py` — the page, as a visitor uses it

**The black-box tests gain two classes: one that ticks boxes and checks the results, and one that checks the clamped rating is explained on the page.**

This file drives the listing through Django's test client, which is as close to a browser as the suite gets without one. It is the place where "a visitor ticks a box and sees fewer charities" is proved end to end.

#### The chip-divider test — before and after

Before, the test searched the whole page for the divider and the place name. That stopped being meaningful once the panel also prints "Lakewood, NJ, USA", because the panel appears before the results: the test could pass on the panel's text rather than the card's.

Before — `tests/unit/test_views.py:119`:

```python
self.assertIn("chip-divider", body)
self.assertLess(body.index("Free loans"), body.index("chip-divider"))
self.assertLess(body.index("chip-divider"), body.index("Lakewood"))
```

After — `tests/unit/test_views.py:122`:

```python
# Locations are labelled with their full identity (D-045). The sidebar
# offers the same strings, so look inside the card only.
card = body[body.index("charity-card") :]
card = card[: card.index("</a>")]
self.assertIn("chip-divider", card)
chip_divider = card.index('class="chip-divider"')
self.assertLess(card.index("Free loans"), chip_divider)
self.assertLess(chip_divider, card.index("Lakewood, NJ, USA"))
```

That is the only pre-existing test in this file whose meaning changed; every other old test in the file is untouched.

#### `ListingFilterPageTest` — new

Before, there was no filter to test. The new class sets up two charities in two causes and then behaves like a visitor: it reads the panel, ticks a box, ticks two, combines a tick with a number, and checks the web addresses and links it gets back.

New — `tests/unit/test_views.py:186`:

```python
class ListingFilterPageTest(TestCase):
    """Black-box: a visitor picks filters in the sidebar and the results narrow (§6.2.4)."""

    def setUp(self) -> None:
        self.url = reverse("charities:listing")
        self.food = Domain.objects.create(name="Food Security")
        self.education = Domain.objects.create(name="Education")
        self.pantry = Charity.objects.create(name="Pantry")
        self.school = Charity.objects.create(name="School")
        self.pantry.domains.add(self.food)
        self.school.domains.add(self.education)

    def test_the_sidebar_offers_every_domain_and_location(self) -> None:
        Location.objects.create(name="Lakewood", region="New Jersey", country="USA")

        response = self.client.get(self.url)

        self.assertContains(response, 'name="domain"')
        self.assertContains(response, "Food Security")
        self.assertContains(response, "Education")
        # A location is offered by its full identity, never its name alone (D-045).
        self.assertContains(response, "Lakewood, New Jersey, USA")

    def test_a_chosen_domain_narrows_the_results(self) -> None:
        response = self.client.get(self.url, {"domain": [self.food.id]})

        self.assertContains(response, "Pantry")
        self.assertNotContains(response, "School")

    def test_two_domains_are_or(self) -> None:
        response = self.client.get(self.url, {"domain": [self.food.id, self.education.id]})

        self.assertContains(response, "Pantry")
        self.assertContains(response, "School")

    def test_a_chosen_box_stays_ticked(self) -> None:
        response = self.client.get(self.url, {"domain": [self.food.id]})
        box = re.search(
            rf'name="domain"\s*value="{self.food.id}"\s*checked', response.content.decode()
        )

        self.assertIsNotNone(box, "the chosen domain should render ticked")

    def test_filters_and_numbers_are_and(self) -> None:
        author = User.objects.create_user(username="reviewer", password="x")
        Review.objects.create(charity=self.pantry, author=author, rating=5)
        Review.objects.create(charity=self.school, author=author, rating=1)

        response = self.client.get(
            self.url, {"domain": [self.food.id, self.education.id], "min_rating": 4}
        )

        self.assertContains(response, "Pantry")
        self.assertNotContains(response, "School")

    def test_no_match_says_so(self) -> None:
        response = self.client.get(self.url, {"min_rating": 5})

        self.assertContains(response, "No charities match those filters.")
        self.assertNotContains(response, "No charities found.")

    def test_an_empty_listing_still_says_no_charities_found(self) -> None:
        Charity.objects.all().delete()

        response = self.client.get(self.url)

        self.assertContains(response, "No charities found.")

    def test_the_filter_form_has_no_page_field_so_apply_starts_at_page_one(self) -> None:
        """§6.2.4: setting a filter returns page 1. The sidebar form sends no
        `page`, so a fresh Apply always lands on page 1; a URL with an explicit
        page keeps it, because UC-03 stores the whole view state in the URL."""
        for index in range(1, 26):
            Charity.objects.create(name=f"Charity {index:02d}")

        response = self.client.get(self.url, {"page": 3, "page_size": 5})

        form = response.content.decode()
        form = form[form.index('<form class="filters"') : form.index("</form>")]
        self.assertNotIn('name="page"', form)

    def test_a_shared_url_keeps_its_page_and_filters(self) -> None:
        for index in range(1, 26):
            charity = Charity.objects.create(name=f"Charity {index:02d}")
            charity.domains.add(self.food)

        response = self.client.get(self.url, {"page": 2, "page_size": 5, "domain": self.food.id})

        self.assertEqual(response.context["page"].number, 2)

    def test_page_links_keep_the_filters(self) -> None:
        for index in range(1, 26):
            charity = Charity.objects.create(name=f"Charity {index:02d}")
            charity.domains.add(self.food)

        response = self.client.get(self.url, {"domain": [self.food.id], "page_size": 5})

        self.assertContains(response, f"page=2&amp;page_size=5&amp;domain={self.food.id}")

    def test_page_size_form_keeps_the_filters(self) -> None:
        response = self.client.get(self.url, {"domain": [self.food.id]})

        self.assertContains(response, f'<input type="hidden" name="domain" value="{self.food.id}">')

    def test_clear_filters_link_appears_only_when_filtering(self) -> None:
        self.assertNotContains(self.client.get(self.url), "Clear filters")
        self.assertContains(self.client.get(self.url, {"domain": [self.food.id]}), "Clear filters")

    def test_a_junk_filter_value_is_ignored(self) -> None:
        response = self.client.get(self.url, {"domain": "nonsense"})

        self.assertContains(response, "Pantry")
        self.assertContains(response, "School")

    def test_the_sidebar_is_on_the_page_for_every_visitor(self) -> None:
        """Filtering needs no account (§6.2.4 Permissions)."""
        response = self.client.get(self.url)

        self.assertContains(response, 'class="listing__sidebar"')
        self.assertContains(response, "Apply filters")
```

The page-link assertion is the one to read closely: it expects `page=2&page_size=5&domain=N`, in that order, because that is the string the service builds, written the way a web address has to be written in a page. It is a test of the exact shape of a shared link, down to the `&amp;` the page has to write where the address itself has a plain `&`.

#### `RatingClampOnThePageTest` — new

Before, a rating outside the scale had no page behaviour to test. The new class checks the whole visible result of the clamp: the list is the one for five stars, the note is printed, the box shows five, and an in-range value prints no note.

New — `tests/unit/test_views.py:308`:

```python
class RatingClampOnThePageTest(TestCase):
    """D-046: an off-scale min_rating is clamped, and the page says so."""

    def setUp(self) -> None:
        self.url = reverse("charities:listing")
        self.charity = Charity.objects.create(name="Keren L'Dugma")
        author = User.objects.create_user(username="reviewer2", password="x")
        Review.objects.create(charity=self.charity, author=author, rating=5)

    def test_an_over_scale_rating_is_clamped_and_explained(self) -> None:
        response = self.client.get(self.url, {"min_rating": 99})
        body = response.content.decode()

        self.assertEqual(response.context["page"].total, 1)
        self.assertContains(response, "Kept between 1 and 5; using 5.")
        # the sidebar shows the value actually applied, not the one asked for
        self.assertRegex(body, r'name="min_rating"[\s\S]{0,200}?value="5"')

    def test_an_under_scale_rating_is_clamped_and_explained(self) -> None:
        response = self.client.get(self.url, {"min_rating": 0})

        self.assertContains(response, "Kept between 1 and 5; using 1.")

    def test_an_in_range_rating_has_no_note(self) -> None:
        response = self.client.get(self.url, {"min_rating": 4})

        self.assertNotContains(response, "Kept between")
```

The `assertRegex` is doing real work: it proves the box's `value="5"` appears near `name="min_rating"`, rather than anywhere on the page. That is as close as testing the page's text gets to "the box shows five".

What it buys: the two behaviours a visitor can actually see — a narrowed list and an explained correction — are tested through the whole stack, from address to database to the page's text, the same way a visitor experiences them.

---

## 8. The tests

The test names are the change's own summary of itself. Read as sentences, they say: what an address means, what a panel contains, what the database keeps, what the page shows, and what it says when it cannot do either.

### What an address means — `tests/unit/test_filter_service.py`

- `test_no_parameters_means_no_filters`
- `test_repeatable_parameters_collect_every_value`
- `test_repeated_ids_are_kept_once`
- `test_numbers_are_read`
- `test_zero_is_a_real_number`
- `test_junk_values_are_dropped_not_rejected`
- `test_unknown_parameters_are_ignored`
- `test_active_count_counts_groups_and_values` — the name says "groups and values"; it counts groups only, two groups in the example.
- `test_a_blank_number_input_is_no_filter`
- `test_the_parameters_are_the_docs_own_spelling`
- `test_the_rabbi_parameter_is_singular_like_the_doc`
- `test_the_plural_spelling_is_not_accepted`

### What a panel contains — `tests/unit/test_filter_service.py`

- `test_empty_filters_make_an_empty_string`
- `test_repeatable_and_numeric_groups_round_trip`
- `test_pairs_keep_a_zero`
- `test_all_seven_groups_appear_in_the_doc_order`
- `test_repeatable_groups_are_checkboxes_with_their_options`
- `test_selected_options_come_from_the_filters`
- `test_a_group_with_no_options_says_so`
- `test_numbers_are_single_inputs_bounded_by_the_star_scale`
- `test_a_location_option_is_labelled_by_its_full_identity`
- `test_an_empty_maximum_has_no_cap`
- `test_a_rating_above_the_scale_is_clamped_and_flagged`
- `test_an_in_range_rating_has_no_correction_note`
- `test_zero_reads_as_set`
- `test_absent_does_not_read_as_set`
- `test_a_ticked_group_reads_as_set`
- `test_the_filters_reach_the_repository`
- `test_no_filters_pass_an_empty_filter_object`

### What the database keeps — `tests/unit/test_filter_repository.py`

- `test_a_domain_selects_charities_in_it`
- `test_domains_are_or`
- `test_two_domains_on_one_charity_count_once`
- `test_a_location_selects_and_is_distinct`
- `test_locations_are_or`
- `test_a_rabbi_selects_charities_they_endorsed`
- `test_rabbis_are_or`
- `test_a_disapproving_haskama_still_counts_as_endorsement`
- `test_filters_by_average_star_rating`
- `test_a_charity_with_no_reviews_has_no_average_and_does_not_match`
- `test_lower_bound_is_inclusive`
- `test_cards_show_the_same_average_the_filter_uses`
- `test_counts_reviews`
- `test_zero_matches_even_a_charity_with_no_reviews`
- `test_min_approving_haskamas_counts_approve_verdicts`
- `test_max_disapproving_haskamas_counts_disapprove_verdicts`
- `test_zero_disapproving_haskamas_means_none_at_all`
- `test_groups_are_and`
- `test_the_counts_are_recomputed_together`
- `test_count_matches_the_filtered_set`
- `test_domains_and_locations_come_from_the_shared_lists`
- `test_rabbis_are_empty_until_accounts_can_list_them`
- `test_from_query_clamps_above_the_scale_to_five`
- `test_from_query_clamps_below_the_scale_to_one`
- `test_inside_the_scale_is_untouched`
- `test_options_are_wrapped_in_a_scrollable_panel`

### What the card and the page show — `test_repositories.py`, `test_template_contract.py`, `test_views.py`

Card mapping, updated:

- `test_maps_domains_and_locations` — now expects `Lakewood, NJ, USA`
- `test_returns_cards_in_name_order`
- `test_window_skips_preceding_rows`
- `test_count_matches_rows`
- `test_card_does_not_leak_model_behaviour`
- `test_loads_relations_without_extra_queries`
- `test_maps_review_average_and_count`
- `test_charity_without_reviews_has_no_average`
- `test_reviews_do_not_add_queries_per_charity`
- `test_default_shows_every_charity`
- `test_published_only_hides_unpublished_charities`

Card and panel rendering:

- `test_review_summary_renders`
- `test_charity_without_reviews_says_so`
- `test_card_type_has_the_attributes_the_template_uses`
- `test_every_group_renders_a_legend`
- `test_checkbox_groups_render_inputs_named_by_their_parameter`
- `test_number_groups_render_one_bounded_input_each`
- `test_the_form_is_a_get`
- `test_no_template_comment_leaks_into_the_page`

The visitor's page:

- `test_the_sidebar_offers_every_domain_and_location`
- `test_a_chosen_domain_narrows_the_results`
- `test_two_domains_are_or`
- `test_a_chosen_box_stays_ticked`
- `test_filters_and_numbers_are_and`
- `test_no_match_says_so`
- `test_an_empty_listing_still_says_no_charities_found`
- `test_the_filter_form_has_no_page_field_so_apply_starts_at_page_one`
- `test_a_shared_url_keeps_its_page_and_filters`
- `test_page_links_keep_the_filters`
- `test_page_size_form_keeps_the_filters`
- `test_clear_filters_link_appears_only_when_filtering`
- `test_a_junk_filter_value_is_ignored`
- `test_the_sidebar_is_on_the_page_for_every_visitor`
- `test_an_over_scale_rating_is_clamped_and_explained`
- `test_an_under_scale_rating_is_clamped_and_explained`
- `test_an_in_range_rating_has_no_note`
- `test_divider_sits_between_domain_and_location_chips` — updated to look inside the card only

Nothing in `test_services.py` changed name or assertion. Only the card factory and the fake helper grew the new field and parameter, because every test there still exercises paging and page sizing, and none of them mentions filters.

### Deleted tests

There are none. Every test that existed before this branch still exists, with one assertion changed in `test_divider_sits_between_domain_and_location_chips` (it now scopes itself to the card) and the calls reshaped in `test_repositories.py` and `test_services.py`. Nothing was removed to make a change pass.

---

## 9. Departures from the design document

*This section is not part of the standard walkthrough. It was added on request.*

The design document is the customer's description of what the product should be. It is a Word file in `docs/`, and the project's rules say it is never edited. When the code needs to do something differently, the difference is written up as a numbered entry in `docs/DECISIONS.md` instead. That is the mechanism this section checks.

The relevant section is **§6.2.4 Filter — SRS FR 2**. Its specification, in the customer's own terms, is:

- **Path:** the visitor picks filters, submits, and the listing shows only matching charities, starting at page 1. There are seven groups, listed as Domains, Locations, Haskamos, `min_rating`, `min_reviews`, `min_approving_haskamas`, `max_disapproving_haskamas`. Ticking several choices in one group means "either of these"; two groups together mean both must hold.
- **Address:** `domain` (repeatable), `location` (repeatable), `haskama_rabbi` (repeatable, **username**), `min_rating`, `min_reviews`, `min_approving_haskamas`, `max_disapproving_haskamas`, `page`, `page_size`. Setting a filter resets page to 1.
- **Permissions:** "This can be set by anoyone, even a guest" (the typo is the document's).
- **Tables read and written:** writes none; reads `CHARITY`, `CHARITY_DOMAIN`, `DOMAIN`, `CHARITY_LOCATION`, `LOCATION`, `REVIEW`, `HASKAMA`, `USER`, `NEW_CHARITY_REQUEST`, `APPROVAL_REQUEST`.
- **Service functions:** `list_charities(filters, sort, page, page_size, search)`, returning the items and how many there are, where the filter is a plain dictionary of keys to values; and, in the accounts app, a function that finds rabbis whose names match a string.
- **View and template:** the same as the charity listing; "the filters are similar to Amazon's".
- **When nothing matches:** a message says nothing matching was found.
- **Tests:** tests of the listing function on its own, and tests through the page with a user ticking several filters in each group.

Two requirements elsewhere in the document bear on this branch. One line says the reviews table exists so the charity page can show reviews and the listing page can show an average rating. The find-a-charity use case's constraints add: full page loads so Back works, everything stored in the web address, checks only for published charities, the database computes the numbers in the same request (the document calls this `annotate`), and inputs are pulled back into range.

Here is every place this branch differs from that, with what authorises the difference and what it costs.

### 9.1 The rabbi group filters by id, not username

The document says `haskama_rabbi` — singular, and explicitly a **username**. The code sends a whole number: the id of the rabbi's stored account. The group's web-address name is the document's singular spelling; its stored name is plural, and its values are ids.

What the code does — `apps/charities/filters.py:38`:

```text
Group("haskama_rabbi", "haskama_rabbis", repeatable=True),
```

**What authorises it:** D-046. Ids survive a rabbi renaming their public name, they match the other two repeatable groups, and they are what `accounts.services.search_rabbis` will hand the panel.

**What it costs if it is wrong:** an address written with a rabbi's username selects nothing, because the group only accepts whole numbers. The tests also pin that D-045's earlier plural spelling is no longer accepted at all, so any link shared from that intermediate state is dead. If the customer insists on usernames, the code change is small, but every request would then have to look up the rabbi by name.

### 9.2 The service function is smaller, and shaped differently

The document specifies one function with five inputs and a second function on another app. The code has four inputs, one of which the document does not mention, and no second function.

What the code does — `apps/charities/services.py:112`:

```python
def list_charities(
    repository: CharityRepository,
    page: int | None = 1,
    page_size: int | None = None,
    filters: CharityFilters | None = None,
) -> Page:
    """Return one page of the charities `filters` keep, alphabetically by name."""
```

The differences, in order:

- **`sort` and `search` are absent.** They have their own sections and their own features — §6.2.5 and §6.2.6 — and the project builds one end-to-end slice at a time.
- **`filters` is a record, not a plain dictionary.** The document calls the filter a dictionary. The code uses a record with named fields, so a misspelt field is an error rather than a silently ignored key.
- **`repository` is an extra input.** The document's function reads the database itself. The code is handed the part that does, which is what lets the filter rules be tested with no database at all.
- **The return is a page bundle, not just the items and the total count.** The bundle carries the same two facts plus the links between pages, so the page does no arithmetic.
- **`accounts.services.search_rabbis` does not exist.** The document names it as the source of the rabbi choices; the code's rabbi list is empty and says so on the panel (D-045).

**What authorises it:** the feature boundaries for sort and search; D-045 for the filter shape; D-006 and the app-boundary rules for the injected database helper. The alphabetical default the document asks for is what the code does.

**What it costs if it is wrong:** adding sort or search later changes what every caller has to hand it. There is exactly one caller today, and the tests pass a stand-in, so the change is contained.

### 9.3 The filter reads seven tables, not ten

The document lists ten tables read, including `USER` and the two approval tables. The code reads charities, the two tables that record which charity has which domain and which place, the domains, the places, the reviews and the haskamas. It never reads `USER`, `NEW_CHARITY_REQUEST` or `APPROVAL_REQUEST`.

`USER` is absent because a rabbi is filtered by the id stored on the haskama; no name lookup happens. The two approval tables are absent because the listing does not consult approvals at all — the visibility switch on the charity is the gate (D-038).

**What authorises it:** D-038 for the approvals, and D-045's empty rabbi list for `USER`.

**What it costs if it is wrong:** when `search_rabbis` lands, the rabbi choices must arrive through the accounts app's service rather than a direct read, because apps may not read each other's tables (D-006). That is a change inside one function, which the database helper's comment names.

### 9.4 The listing still ignores the published switch, and now filters on hidden charities' numbers

UC-03's implementation constraints say the listing "checks only for published charities". The view passes an explicit `False` instead, so unpublished charities are listed.

What the code does — `apps/charities/views.py:38`:

```text
repository=DjangoCharityRepository(published_only=False),
```

That departure predates this branch (D-042). What this branch adds is a second use of that exception: the card's rating and the filters' comparisons are computed for every charity the listing shows, and while D-042 stands that includes charities the public is not supposed to see, so their review and haskama counts now decide which cards match.

**What authorises it:** D-042 for the listing, and D-045's sub-decision for the counts ("every filter applies the same way").

**What it costs if it is wrong:** the same risk in production that D-042 already carries — if the site ships while `published_only` is `False`, hidden charities are publicly browsable — with a slightly wider effect, because a hidden charity's review and haskama counts now decide whether other charities match a filter. The way out is still one setting, `published_only=True`.

### 9.5 "Setting a filter resets page to 1" is true only when the panel is used

The document's sentence is unconditional. The code implements it by leaving `page` out of the panel's form: a fresh Apply therefore lands on page one. But an address that arrives already carrying both a page and a filter keeps its page, because a missing page is the only thing that means "page one".

**What authorises it:** no decision; it is recorded as observation N5 in `docs/NOTES.md`, with both behaviours tested.

**What it costs if it is wrong:** a shared or hand-edited address can show page three of a filtered list, which a strict reading of the sentence would not allow. The alternative — always discarding the page when any filter is present — makes every shared filtered link start at the top.

### 9.6 Choices the document leaves open

The document fixes the seven groups, their address names, and that "either" applies inside a group and "both" between groups. It does not state the following, so each is a fill-in rather than a contradiction, and each is recorded in D-044, D-045 or D-046:

- **Ids, not names, for domains and locations.** The document says "repeatable" without saying what a value is. D-032 makes a place unique on name, region and country together, so a name alone is ambiguous.
- **A 1–5 star scale for `min_rating`.** The document fixes a review's score at 1 to 5; the filter's scale is unstated. The code uses the same scale the card prints.
- **Zero is a real answer** for the three count groups, so "no reviews" and "no disapprovals" can be asked for. An absent maximum means no cap.
- **An out-of-range rating is clamped and announced.** UC-03 does ask for clamped parameters; the announcement is the code's addition (D-046), so a visitor is not silently given a different filter.
- **Two empty states.** The document asks for the "matches nothing" message; the code keeps the pre-existing empty-database message beside it and words the two differently.
- **Option lists come from the shared lists,** so a domain or location with no charities is still offered. The document does not say where the choices come from.
- **The card shows the review count** as well as the average, and shows "No reviews yet" and one decimal place. UC-05 says the average and count are recomputed; the display wording and rounding are unstated.

### 9.7 Sort and search are absent

The document gives sort its own section (FR 3: alphabetical, trending, most popular, highest reviews, most haskamos, recently added, recently updated, each with a direction) and search its own (FR 4, with an advanced toggle). Neither is in this branch. The listing still defaults to alphabetical, which §6.2.3 asks for.

**What authorises it:** the feature boundary; each is a separate feature slice of its own.

**What it costs if it is wrong:** nothing now. The listing page still has no sort control and no search bar, so a visitor who wants either finds nothing where the design document's page inventory promises them.

### 9.8 The document disagrees with itself on `per_page` versus `page_size`

§6.2.3 says the amount per page is called `per_page=` in the address. §6.2.4, one section later, lists the same parameters and calls it `page_size`. The code uses `page_size` in the address, and this branch's page links now depend on that spelling to carry filters forward.

This is not a departure from §6.2.4 — it follows it — but it is a departure from §6.2.3. It is recorded here so no one "fixes" one spelling and breaks shared links or the filter's page resets.

### 9.9 The tests are per group in the repository, not per group in a browser

The document asks for tests through the page itself (what it calls black box) with "users picking multiple filters, for each group". The code has tests against the database helper for every group, where the real narrowing happens, and tests through the page for a domain, for two domains, for a domain combined with a rating, for the empty state, for the page reset, for page links keeping filters, and for the clamped rating. The Haskamos group has no path through the page because its option list is empty until `search_rabbis` exists (N8), so its end-to-end behaviour is covered by hand-made haskama rows in tests that bypass the page.

**What authorises it:** nothing; it is a gap against the document's test requirement, not a contradiction.

**What it costs if it is wrong:** a defect in how the panel draws a rabbi choice would not be caught until `search_rabbis` exists. The repository side of that group is covered today.

### 9.10 Inherited differences this branch relies on but does not create

- **The listing lives at `/charity/`, not `/listing/`.** The filter panel's form sends the visitor back to whatever address the listing has, so it inherits this. Authorised by D-009 and D-028, both older than this branch. The cost is one line in `config/urls.py` if the customer insists on `/listing/`.
- **The page-size ceiling of 100 is not in the document.** The document lets the visitor set the amount per page and puts no upper bound on it. This branch's page links now repeat the capped size, so the ceiling travels with a shared filtered link. Authorised by nothing explicit; it is a defensive default that predates the filter.

### 9.11 What matches, for completeness

Not every line of the specification was departed from. These parts match, and it is worth knowing which, so a reviewer's attention goes where the differences are:

- **The seven groups, in the document's order**, with the document's address names, including the singular `haskama_rabbi`.
- **OR inside a group, AND between groups**, exactly as written.
- **Open to everyone, including a guest.** No login is required, and a test says so.
- **Writes nothing.** The page only reads.
- **Full page loads, with the whole view in the address**, so Back, bookmarking and sharing work (UC-03).
- **The filters sit in a panel on the side of the listing page**, in the Amazon style the document describes, with tick boxes for the repeatable choices and one number box for each numeric group.
- **Alphabetical default order** for the unfiltered list.
- **The average rating is derived on read, not stored** (§5.3's "derive data" rule), and the database computes it in the same request (what the document calls `annotate`).
- **The inputs are pulled back into range** (UC-03): the rating into 1–5, the page into the range of pages that exist, the page size into 1–100.
- **A filtered listing with no matches prints a message** saying nothing matches.

---

*End of walkthrough.*
