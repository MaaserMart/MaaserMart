# PR 13 — "Sort": the charity listing learns seven orders

A plain-English walkthrough of pull request #13 on MaaserMart.

- Branch: `sort` into `full_charity_listing`
- Twelve commits, 27 files, +2021 lines, −101 lines
- Written to be reviewed from. The code is quoted in full below.

---

## Read this part even if you read nothing else

MaaserMart is a website where people look up charities and decide where to give. The busiest page is the listing: one page that shows every charity, twenty at a time, with a filter sidebar down the left that narrows the list.

The filter sidebar already worked. The **order** did not. The listing could only ever show charities by name, A to Z.

The design document asks for more. Its section on the listing's sort control (§6.2.5) asks for seven orders, and for two directions on each: a dropdown to pick the order, and two buttons to pick which way it runs. Before this branch, the page had neither the dropdown nor the buttons, and the one order it had was fixed in the code.

So the branch builds the seven orders and the control. Then, commit after commit, it discovers the orders cannot be trusted yet, and spends most of its length making them trustworthy. Five things were wrong, and every one had the same shape: **something on the page said one thing while the database did another.**

- **Filtered rows were being counted more than once.** The listing's filters were fetched by fusing tables together. A charity that sat in two matching food categories, and had two reviews, came back as two rows — so the card said "4 reviews" and showed a rating that belongs to no charity. The fix stops fusing tables for filters and asks a simpler question: "does at least one matching row exist?"
- **The order and the filter deleted each other.** Pick a filter, then pick an order, and the filter was gone. Clear the filters and the order was gone. The fix makes every form and every link on the page repeat both.
- **Every page load paid for work it never showed.** Even a plain first page with no filters and no order ran the review count and the averaging, only to learn how many charities matched. The fix adds a number only when a card shows it, a filter compares it, or the order reads it.
- **The trending order counted this week's visits twice.** The design document's sentence can be read that way, and the first commit read it that way: an event today scored 3 + 2 = 5. A single busy day beat a month of steady work. The fix gives the two time windows no overlap: an event is worth 3, or 2, never both.
- **The fake development data repeated names.** Two hundred charities were built from sixty-four possible names, so six of them were called "Lev Chaim". Paging a rating-ordered list showed "Lev Chaim" at the bottom of one page and the top of the next, which reads exactly like a paging bug. The fix has 208 possible names and draws 200 without repeats.

Two more problems surfaced because the orders exposed them. The "most recently updated" order reads a recorded change, and the admin's own edit screen never recorded one — so an admin renaming a charity left the order stale. Now every save of a charity goes through one door that records it. And the cards showed none of the numbers the activity orders sort by, so a visitor could not check the order at all. Now every card shows its event count, its approving-haskama count (a haskama is a rabbi's endorsement) and its last-change date.

**The fix in one sentence:** the listing can reorder itself seven ways, and the price of that was making every number, every link, every form and every fake row on the page agree with every other one.

What that buys, stated as consequences in the world:

- A visitor can filter to food charities, order by rating, and share the address; the recipient gets the same list in the same order.
- A reviewer can see, on each card, the numbers that placed it where it is.
- A plain page load no longer pays for a review count nobody reads.
- An admin's edit now moves that charity up the "most recently updated" list.

Everything below is the same idea in more detail.

---

## How to read this file

**Who it is for.** Two readers, both served at full size. The first is someone who needs to understand what changed without reading code. The second is the engineer who will approve or reject this pull request. Neither is an afterthought.

**Three rules.**

1. **Read the glossary first.** Every term in this document is defined there before it is used.
2. **Every code box is optional.** The sentence directly above each box says the same thing in plain English. Skip every box and you lose nothing. That rule is what lets this document quote as much real code as it does.
3. **Each file section opens with a bold one-line summary.** Reading only those lines gives you the whole change.

This document explains; it does not grade. It has no findings, no nitpicks and no verdict. It gives you what you need to form your own.

---

## The glossary

Twelve words, defined by what they do and why anyone cares.

| Word | What it means |
|---|---|
| **listing** | The page at `/charity/` that lists every charity, twenty per page. The thing this whole PR changes. |
| **card** | The small block the listing draws for one charity: name, tagline, rating, categories, locations. |
| **mechanism** | One of the seven orders in the dropdown: `alphabetical`, `trending`, `popular`, `rating`, `haskamos`, `newest`, `updated`. |
| **direction** | Which way an order runs. For names: A to Z or Z to A. For counts: low to high or high to low. |
| **sort** | A chosen mechanism **together with** a chosen direction. The pair the address carries. |
| **event** | A row in the database recording that something happened to a charity: a view, a link click, a rejection, or a save. |
| **haskama** | A rabbi's endorsement of, or objection to, a charity. Each one carries a verdict: approve or disapprove. |
| **annotated column** | A number the database calculates and attaches to each row while it fetches it — for example, each charity's event count. It is not stored; it is computed on the way out. |
| **join** | Asking the database to fuse two tables row by row. When one charity matches three rows in the other table, a join makes that charity appear three times. This is where the duplication bug came from. |
| **row multiplication** | The name for that duplication. One charity, several matching rows on the other side, several copies of the charity. |
| **service** | The only door one part of the system may use to call another (project rule D-006). To count events, the listing asks the events app; it never reads the events table itself. |
| **tie-break** | The rule that decides the order when two charities have equal values. |

And the code names you will meet in the boxes, mapped to plain words once:

| In the code | Plain words |
|---|---|
| `bool` | A yes/no switch |
| `int` | A whole number |
| `str` | A piece of text |
| `tuple` | A fixed-length list |
| `dataclass(frozen=True)` | A named bundle of values that cannot be changed once made |
| `Protocol` | A written promise about what a piece of code can do, with no promise about how |
| `CharitySort` | A chosen sort: one mechanism plus one direction |
| `Mechanism` | One entry in the dropdown |
| `Subquery` | A separate small question the database answers once per row |
| `QuerySet` | The list of rows the page is about to show, built as a recipe rather than fetched yet |
| `GET form` | A form whose answers land in the page address, so the address can be shared |

---

## The story

### What the system does all day

1. A visitor opens the charity listing. The page asks the database for one page of charities, twenty at a time, and draws a card for each.
2. The visitor narrows the list with the filter sidebar: by category, by location, by minimum rating, by minimum review count, by approving or disapproving haskamas. This part worked before the branch.
3. The visitor chooses an order from a dropdown, and a direction from two buttons.
4. Every one of those choices is written into the page address, so a shared link describes the same view. Anything that changes one choice repeats the others.
5. The database answers with one query. It computes the numbers every card shows, keeps only the charities the filters keep, sorts them, and returns the twenty that belong on this page.

### The bug, told as a story

Follow a charity called **"Lev Chaim"**.

The development seed builds fake charities so a developer has something to look at. Before this branch it built a name by picking one prefix from eight ("Keren", "Chasdei", "Yad", "Ezras", "Bais", "Tomchei", "Achiezer", "Lev") and one word from eight ("Chesed", "Shalom", "Emunah", "Tzedakah", "Rachamim", "Simcha", "Torah", "Chaim"). Eight times eight is sixty-four possible names, drawn independently, for **200** charities.

The result was six charities named "Lev Chaim", and five named "Tomchei Torah".

Now sort the listing by rating. Several of those names have no reviews, so they all tie. The tie-break puts them in name order. Paging then walks down a list where "Lev Chaim" appears at the bottom of page 3, and again at the top of page 4. A developer seeing that reports a paging bug. It was the data. Which means a chunk of this branch's audit time went on a bug that was not in the paging code at all.

### The cost, stated plainly

If the rest of this branch were not made:

- A visitor filters to food charities, then picks "most haskamos", and the food filter silently disappears. The page now shows every charity, and nothing says so.
- A visitor shares a link to "rating, high to low, page 2". The recipient opens it and sees page 1, alphabetical, because the page links carried only the page number.
- A charity with reviews of 5 and 3 shows "2 reviews, 4.0 average" — or, with two food filters on, "4 reviews, 4.0 average", a number that belongs to no charity.
- One busy weekend makes a charity the most "trending" in the city, ahead of charities that were visited steadily all month.
- An admin renames a charity through the admin site. The "most recently updated" order never notices.
- Every page load pays for a review count and an average that the page may not even print.

### The fix, in one sentence

The listing reorders itself seven ways, and every number, link, form and fake row on the page was made to agree with every other one.

---

## Contradictions

Where the pull request's description, its commits, and its code disagree, this section says which to trust. There is no PR description on #13 — the body is empty — so the commit messages and `docs/DECISIONS.md` carry the intent.

**1. The trending score counted twice, then once.** The first commit on the branch built the design document's sentence literally: the week sits inside the month, so a charity with one event today scores `3 + 2 = 5`. Eight commits later, D-050 replaced the two overlapping windows with two that do not overlap: one event is worth 3 or 2, never both. The head of the branch has the non-overlapping version. Both are quoted in the events section, and the first is quoted here so a reviewer knows what was deliberately removed.

The first commit's version, quoted from `apps/events/services.py` as it stood at commit `b6d80c7`:

```python
# §6.4.3 Trending: events in the past week count three, events in the past month
# count two. The week is inside the month, so a row from this week counts in both.
TRENDING_WEEK_WEIGHT = 3
TRENDING_MONTH_WEIGHT = 2
```

and, from the same commit, its own docstring on the score:

```python
    """§6.4.3's trending score for one charity, as an integer expression.

    The score is `3 × events in the past week + 2 × events in the past month`,
    measured from `now` (UTC by default, D-010). The week is part of the month,
    so a charity with one event today scores 5 and one event 20 days ago scores 2.
```

**Trust the code at the head of the branch.** The final comment reads:

```python
# §6.4.3 Trending: events in the past week count three, events in the past month
# count two. The two windows do not overlap, or a row from this week would be
# counted twice (D-050): the month bucket holds days 8–30 only.
```

**2. The dropdown was applied in two different ways.** Commit `8a3e254` added an inline instruction to the dropdown itself, so the browser submitted the form the moment the choice changed:

```html
  <select
    class="sort__select"
    id="{{ sort_form.parameter }}"
    name="{{ sort_form.parameter }}"
    onchange="this.form.submit()"
  >
```

Five commits later, `68ea90a`, deleted that line and moved the behaviour into `static/js/sort.js`, which also covers the Enter key. The head of the branch has the script, and a test now asserts the inline handler is gone (`tests/unit/test_template_contract.py:222`). **Trust the head.** The script is quoted in full in its own section below.

**3. This branch cut itself before the sidebar existed.** The branch `sort` was cut from the listing branch before the filter work landed there, so it briefly lost the sidebar entirely. Commit `04e353ba` is a merge that puts both features back together:

> "sort was cut from full_charity_listing before the filter PR landed, so the branch had lost the sidebar. The merge keeps both: one Page carries the filters and the order, and every form and page link replays both, so neither control drops the other's state."

That is why a pull request titled "Sort" touches four filter templates (`filters.html`, `filter_state.html`, `state.html`, and the filter half of `listing.html`). Those lines are the two features learning to share a page, not a change of filter behaviour.

**4. One verb in a decision entry is looser than the code.** D-051 says the page "now always aggregates" the approving-haskama count. The code does not aggregate across the table; it asks a separate counting question per charity. The substance — the number is always present on a page that shows cards — holds. The code is quoted below so a reviewer can see exactly which it is.

---

## Departures from the design doc

The design document is the customer's document. This section lists every place where the code at the head of the branch does something the document does not say, or says differently. Each is settled by a decision in `docs/DECISIONS.md`, except the last two, which are older decisions this branch inherits.

**1. §6.2.5 says the sort reads `new_charity_request`, `edit_request` and `approval_request`. The code reads none of those three tables.**

The document's "Models touched" line for Sort reads: *"Reads charity, reviews, haskamos, new_charity_request, edit_request, approval_request, and events."*

The code reads charity, reviews, haskamos and events. For "most recently added" it reads the charity's own creation date; for "most recently updated" it reads the charity's own recorded changes. It never reads the three request tables. The reason is the project's dependency rule, §6.1 and D-006: approvals depend on charities, not the reverse, so charities may not read approvals' tables. Settled by **D-048**, which records both choices explicitly.

**2. §6.4.3's trending sentence double-counts the week; the code does not.**

The document says: *"The score is assigned by multiplying events in the past week by 3 and events in the past month by 2."* The week is inside the month, so the literal sum counts a week-old event twice. The code makes the two windows non-overlapping: the last 7 days count 3, and days 8–30 count 2. Settled by **D-050**, which also records that D-048 first built the literal reading.

**3. §6.2.5's tie-break is alphabetical; the code adds the row number as a second tie-break.**

The document's failure path reads: *"Tie -> Alphabetical tiebreaker."* The code sorts by name, then by the charity's row number. The row number is what makes the order *total*: without it, two charities with the same name could swap places between two page loads, so a page boundary could repeat or skip one. Settled by **D-048**. The added rule does not contradict the document; it completes it.

**4. §6.2.5 names the parameters but not their values; the code chooses the values.**

The document says *"Parameters: sort= and direction="* and nothing more. The code uses `?sort=<mechanism>&direction=<asc|desc>`, with seven mechanism names and two direction values. It also settles three things the document leaves open:

- When `sort` names nothing recognisable, the whole choice falls back to alphabetical A to Z. (The document does say this in its service-function line: *"When nothing recognizable is input ... it defaults to alphabetical a->z."* So this one is the document's.)
- When the direction is missing or junk, the chosen mechanism keeps its own default direction: A to Z for names, high to low for every count and date.
- The default view — alphabetical, A to Z — writes **no** parameters into the address, so a plain page link stays plain.

Settled by **D-048**. These fill gaps, they do not overrule.

**5. §6.2.5 says each order has "a high to low and low to high button"; the code words each button in its own order's terms.**

The document says each order has *"a high to low and low to high button."* The two buttons exist exactly as described. Their labels are worded per mechanism instead: "A to Z" / "Z to A" for names, "Lowest rated" / "Highest rated" for rating, "Oldest first" / "Newest first" for the date orders. This is how D-048's comment in `sorting.py` records it: *"'high to low' is never asked of a date."*

**6. §5.3 lists only the average rating for the list page; the cards now show three more numbers.**

§5.3's derived values, and D-044 before it, put the average rating on the listing card. This branch adds the charity's event count, its approving-haskama count and its last-change date to every card. §5.3 does not list those three. Settled by **D-051**, which states plainly that these are *"additions to the doc's list, not replacements."* The reason is that four of the seven orders sort by exactly those numbers, and a list that reorders without printing why cannot be checked.

**7. Every save of a charity now goes through one function and records a change. The document does not describe a single write path.**

§6.2.15 ("Edit Charity") describes the edit screen but not how a save is recorded. D-052 makes `charities.services.update_charity` the one door for field saves, and routes the Django admin's edit form through it, so that the "most recently updated" order and §5.2.21's derived date have something to read. The decision also records a known gap: a change to a charity's categories or locations through the admin's multi-selects still records nothing, because those rows are written after the save; no product path does that today.

**8. The seed's distinct names are not in the document at all.**

`CHARITY.name` stays non-unique in the schema, as **D-013** decided. The seed change is dev tooling, settled by **D-049**. Nothing about the schema moves.

**9. Two older divergences this branch inherits, unchanged.**

The listing lives at `/charity/`, not the document's `/listing/` (§6.2.3), and the page-size parameter is `page_size`, not the document's `per_page`. Both come from earlier decisions (D-009, D-026 through D-028) and are not this branch's to change. They are named here because every sort link in this PR reproduces them.

---

## Reading order

Read in this order; each file makes the next one make sense.

| Order | File | What it is |
|---|---|---|
| 1 | `apps/charities/sorting.py` | **New.** The seven orders: their URL names, labels, and starting directions. |
| 2 | `apps/events/services.py` | **New.** The three activity numbers, answered by the app that owns the events table. |
| 3 | `apps/charities/repositories.py` | The one query: filters that do not duplicate rows, numbers added only when read, and a sorting instruction per order. |
| 4 | `apps/charities/services.py` | The page and its links; and the one door for saving a charity. |
| 5 | `apps/charities/contracts.py` | The plain values a card carries. |
| 6 | `apps/charities/views.py` | The wiring that puts the choice on the page. |
| 7 | `apps/charities/admin.py` | The admin's edit form, now routed through the one door. |
| 8 | the six templates | The control on the page, the state each form replays, and the numbers on the cards. |
| 9 | `static/js/sort.js` | The small script that applies a changed dropdown, Enter included. |
| 10 | `static/css/site.css` | Styling for the control and the new card row. |
| 11 | `apps/dashboards/management/commands/seed.py` | The fake data, now with enough distinct names. |
| 12 | the tests | The whole change, checked against real rows. |

The shape of the whole change in one sentence: one new vocabulary file, one new read-side file in the events app, one query rebuilt so a charity is always one row, one service that now owns saving a charity, and a page whose every link repeats both the filters and the order.

---

## 1. `apps/charities/sorting.py` — the seven orders, named once (new file)

**New file: the seven orders live here, with their address names, their button labels, and the direction each one starts in.**

This is the one place that knows what the order options are called, the order the dropdown shows them in, and which direction each one starts in. The view, the page links, the database query and the template all read a `CharitySort` from this file, so renaming an order is a change here and nowhere else.

Before this file existed, there were no orders to name. The listing had one fixed order written in the database code — `order_by("name")` in `repositories.py` — and the address carried nothing about order at all.

### The module's own statement of purpose

The file opens by saying what it is for: this is the single source of the document's parameter values, and a typed bundle rather than a loose string, so a typo shows up as a failed test rather than a silently unsorted page.

```python
"""The listing's sort orders, as §6.2.5 defines them (D-048).

This is the one place that knows the doc's `sort` and `direction` parameter
values, the order the dropdown offers, and which direction each mechanism starts
with. The view, the page links and the repository read a `CharitySort` from
here, so adding or renaming a mechanism is a change in this file and nowhere
else.

A mechanism is a value object rather than a bare string: the dropdown, the
direction buttons and the ORDER BY all need a mechanism's parts, and a typo in a
string would otherwise only show up as a silently unsorted listing.
"""
```

`apps/charities/sorting.py:1`

### `Mechanism` — one entry in the dropdown

One order, as a bundle: its address value, its label, whether it starts high or low, and what its two buttons say. Before this, there was no such thing; the order was a bare string passed straight to the database.

```python
@dataclass(frozen=True)
class Mechanism:
    """One choice in §6.2.5's dropdown.

    `descending_by_default` is the direction the mechanism starts in: A→Z for
    names, high→low for every count or date. `low_label` and `high_label` are
    what its two direction buttons say, so each order states the direction in
    its own terms: letters for names, counts for tallies, dates for time.
    """

    value: str
    label: str
    descending_by_default: bool = True
    low_label: str = "Low to high"
    high_label: str = "High to low"

    @property
    def default_direction(self) -> str:
        return DESCENDING if self.descending_by_default else ASCENDING
```

`apps/charities/sorting.py:27`

### The seven orders, in dropdown order

The seven mechanisms are defined once, in the order the dropdown shows them, with names and labels. Names start A to Z; everything else starts high to low. Each button label is written in that order's own terms, so "high to low" is never asked of a date.

```python
# §6.2.5's list, in the order the dropdown shows it. "Most popular" is the doc's
# name for the order by EVENT count; the direction labels say what each order
# means, so "high to low" is never asked of a date (D-048).
ALPHABETICAL = Mechanism(
    "alphabetical",
    "Name",
    descending_by_default=False,
    low_label="A to Z",
    high_label="Z to A",
)
TRENDING = Mechanism("trending", "Trending")
POPULAR = Mechanism("popular", "Most popular")
RATING = Mechanism("rating", "Highest rated", low_label="Lowest rated", high_label="Highest rated")
HASKAMOS = Mechanism("haskamos", "Most haskamos")
NEWEST = Mechanism(
    "newest", "Most recently added", low_label="Oldest first", high_label="Newest first"
)
UPDATED = Mechanism(
    "updated",
    "Most recently updated",
    low_label="Least recently changed",
    high_label="Most recently changed",
)

MECHANISMS: tuple[Mechanism, ...] = (
    ALPHABETICAL,
    TRENDING,
    POPULAR,
    RATING,
    HASKAMOS,
    NEWEST,
    UPDATED,
)

DEFAULT_MECHANISM = ALPHABETICAL
```

`apps/charities/sorting.py:48`

### `CharitySort` — a chosen order

The document calls the service's sort input "a tuple with mechanism and direction". The code makes that a named bundle with both parts required, plus a flag the database can read directly.

```python
@dataclass(frozen=True)
class CharitySort:
    """A chosen mechanism and direction — §6.2.5's tuple of both.

    Both parts are required. A default direction here would contradict the
    mechanism's own default (`CharitySort(RATING)` would mean low to high), so
    the only place that fills a missing direction is `from_query`, which reads
    the mechanism's default. `descending` is a flag rather than the URL's word
    so the repository can read it directly and the template can compare it once.
    """

    mechanism: Mechanism
    descending: bool

    @property
    def is_default(self) -> bool:
        """True for alphabetical A→Z, the order a URL with no sort describes."""
        return self.mechanism == DEFAULT_MECHANISM and not self.descending

    @property
    def direction(self) -> str:
        return DESCENDING if self.descending else ASCENDING


DEFAULT_SORT = CharitySort(mechanism=DEFAULT_MECHANISM, descending=False)
```

`apps/charities/sorting.py:85`

### `from_query` — reading the choice out of the address

This is where the document's rules about missing and unrecognisable input live. No `sort` means alphabetical. A `sort` that names no mechanism makes the whole choice fall back to alphabetical. A missing or junk direction keeps the mechanism and takes its default direction.

```python
def from_query(query) -> CharitySort:
    """Read `sort` and `direction` from a request query, as §6.2.5 states.

    An absent `sort` means alphabetical. A `sort` that names no mechanism makes
    the whole choice fall back to alphabetical A→Z: "when nothing recognizable
    is input ... it defaults to alphabetical a->z". A junk or absent
    `direction` keeps the mechanism and takes its default direction, the same
    treatment the filter groups give an unusable value.
    """
    raw_sort = query.get(SORT_PARAMETER)
    if raw_sort is None:
        mechanism = DEFAULT_MECHANISM
    else:
        mechanism = _mechanism(raw_sort)
        if mechanism is None:
            return DEFAULT_SORT

    raw_direction = query.get(DIRECTION_PARAMETER)
    direction = raw_direction if raw_direction in DIRECTIONS else mechanism.default_direction
    return CharitySort(mechanism=mechanism, descending=direction == DESCENDING)
```

`apps/charities/sorting.py:112`

### `query_pairs` and `query_string` — writing the choice back into a link

The default order writes nothing, so a plain address stays plain. Any other order writes both parts.

```python
def query_pairs(sort: CharitySort) -> tuple[tuple[str, str], ...]:
    """The sort as (parameter, value) pairs, empty for the default.

    Leaving the default out keeps a plain page link plain, and makes every URL
    that describes the same view spell it the same way.
    """
    if sort.is_default:
        return ()
    return (
        (SORT_PARAMETER, sort.mechanism.value),
        (DIRECTION_PARAMETER, sort.direction),
    )


def query_string(sort: CharitySort) -> str:
    """The sort as a query string, for a page link that must keep it."""
    return urlencode(query_pairs(sort))
```

`apps/charities/sorting.py:134`

### `SortForm` and `sort_form` — everything the template needs, already worded

The template gets a ready-made form: the option list, which one is selected, which direction is current, both button labels, and the parameter names and direction words. The template therefore holds no sort vocabulary at all.

```python
@dataclass(frozen=True)
class SortForm:
    """The sort control, ready to render.

    The dropdown carries `selected` and the two direction buttons carry their
    labels and which one is current. The parameter names and the direction
    values come from here too, so the template holds no sort vocabulary at all:
    renaming `sort`, `direction`, `asc` or `desc` is a change in this file only.
    """

    options: tuple[SortOption, ...]
    selected: str
    descending: bool
    low_label: str
    high_label: str
    parameter: str = SORT_PARAMETER
    direction_parameter: str = DIRECTION_PARAMETER
    ascending_value: str = ASCENDING
    descending_value: str = DESCENDING


def sort_form(sort: CharitySort) -> SortForm:
    """Assemble the dropdown and its direction buttons from the chosen sort."""
    return SortForm(
        options=tuple(SortOption(mechanism.value, mechanism.label) for mechanism in MECHANISMS),
        selected=sort.mechanism.value,
        descending=sort.descending,
        low_label=sort.mechanism.low_label,
        high_label=sort.mechanism.high_label,
    )
```

`apps/charities/sorting.py:165`

What this buys: one file settles every order name, every label and every direction rule. Adding an eighth order, or renaming `haskamos` to `endorsements`, is a change to this one file plus nothing else — and a typo is caught by tests instead of showing up as a silently unsorted list.

---

## 2. `apps/events/services.py` — the three activity numbers (new reads)

**New: three questions about the events table, answered once per charity, so the listing never touches the events table itself.**

The events app owns the table that records everything that happens to a charity. Four of the seven orders sort by numbers that live in that table, and the listing is forbidden from reading another app's table (D-006). So this file exports the numbers as small questions the listing can attach to its own rows. Before this branch the file had exactly one function, `record_event`, which writes an event.

### Why subqueries and not a join

The comment that introduces this block explains the whole design in three lines: the listing orders by activity, charities may not query the events table, so the events app hands back a question the caller can attach to its own rows.

```python
# --- Activity reads ----------------------------------------------------------
# The charity listing orders by activity, but charities may not query EVENT
# itself (D-006). These functions return subqueries over this app's table, so the
# caller can annotate its own queryset, order and paginate in one query, without
# knowing EVENT's shape (D-048).
```

`apps/events/services.py:42`

### `event_count` — how many events a charity has

One number per charity: every event counts, whatever its type. A charity with no events gets 0 rather than nothing, because "no events" is zero activity and the database would otherwise sort nothing as if it were the largest value.

```python
def event_count(charity_ref: OuterRef) -> Expression:
    """How many EVENT rows reference one charity (§6.2.5's "most events").

    Every action counts: a view, a link click, a rejection and a charity update
    are all activity. A charity with no events has no row to aggregate, so the
    expression coalesces to 0 rather than NULL: "no events" is zero activity,
    and Postgres would otherwise sort NULL first when ordering high to low.
    """
    return Coalesce(
        Subquery(
            Event.objects.filter(charity=charity_ref)
            .order_by()
            .values("charity")
            .annotate(total=Count("pk"))
            .values("total"),
            output_field=IntegerField(),
        ),
        Value(0),
        output_field=IntegerField(),
    )
```

`apps/events/services.py:49`

### `trending_score` — the document's score, with the two windows kept apart

The score counts the charity's events in two windows and weights them: the last seven days count 3 each, days eight to thirty count 2 each. The two windows do not overlap, so one event is worth 3 or 2, never 5. The 30-day cut-off is the outer boundary, and everything older counts nothing.

```python
def trending_score(charity_ref: OuterRef, *, now: datetime | None = None) -> Expression:
    """§6.4.3's trending score for one charity, as an integer expression.

    The score is `3 × events in the past week + 2 × events 8–30 days ago`,
    measured from `now` (UTC by default, D-010). The buckets do not overlap, so
    an event is worth 3 or 2, never both: the week sits inside the month window,
    and counting it in both was the literal reading the doc's wording allows
    (D-050).
    """
    now = now or timezone.now()
    week_ago = now - TRENDING_WEEK
    month_ago = now - TRENDING_MONTH
    return Coalesce(
        Subquery(
            Event.objects.filter(charity=charity_ref, created__gte=month_ago)
            .order_by()
            .values("charity")
            .annotate(
                week=Count("pk", filter=Q(created__gte=week_ago)),
                older=Count("pk", filter=Q(created__lt=week_ago)),
            )
            .annotate(
                score=ExpressionWrapper(
                    F("week") * TRENDING_WEEK_WEIGHT + F("older") * TRENDING_MONTH_WEIGHT,
                    output_field=IntegerField(),
                )
            )
            .values("score"),
            output_field=IntegerField(),
        ),
        Value(0),
        output_field=IntegerField(),
    )
```

`apps/events/services.py:71`

The weights and windows themselves are two constants, with the non-overlap rule in the comment above them:

```python
# §6.4.3 Trending: events in the past week count three, events in the past month
# count two. The two windows do not overlap, or a row from this week would be
# counted twice (D-050): the month bucket holds days 8–30 only.
TRENDING_WEEK_WEIGHT = 3
TRENDING_MONTH_WEIGHT = 2
TRENDING_WEEK = timedelta(days=7)
TRENDING_MONTH = timedelta(days=30)
```

`apps/events/services.py:26`

### `last_changed` — when the charity last changed

Only "charity updated" events count. A view is not a change to the charity, so a charity that is merely popular does not move up the "most recently updated" list. When a charity has no recorded change at all, this returns nothing, and the caller falls back to the charity's own creation date.

```python
def last_changed(charity_ref: OuterRef) -> Expression:
    """When a change to this charity was last recorded, as a datetime expression.

    Only `charity_updated` events count: a view is not a change to the charity.
    The result is NULL when the charity has none, which lets the caller fall back
    to its own creation time (D-048).
    """
    return Subquery(
        Event.objects.filter(charity=charity_ref, action=Event.Action.CHARITY_UPDATED)
        .order_by()
        .values("charity")
        .annotate(last=Max("created"))
        .values("last"),
        output_field=DateTimeField(),
    )
```

`apps/events/services.py:106`

What this buys: the listing gets four activity orders and keeps the project's app boundary intact. And because each number is a question answered once per row rather than a table fused row by row, the page stays one row per charity and one query.

---

## 3. `apps/charities/repositories.py` — the one query

**The one query: filters that do not duplicate rows, numbers added only when something reads them, and one sorting instruction per order.**

This is the only file that talks to the database for the listing. It turns the sidebar's filter groups and the chosen order into a single query, so the numbers on the cards, the values the filters compare, and the values the orders sort by are all computed the same way and cannot disagree.

Before the branch, this file did three things the branch removes: it fused tables for every repeatable filter, it counted reviews on every listing, and it sorted by name and nothing else.

### `OrderKey` and `ORDER_KEYS` — one sorting instruction per order (new)

One order, as a rule for the database: which computed value it sorts on, what breaks a tie, and whether "nothing" means "none" rather than "low". The table below it maps each of the seven orders to one of these rules.

```python
@dataclass(frozen=True)
class OrderKey:
    """How one sort mechanism becomes an ORDER BY.

    `column` is the annotated value the mechanism orders by. `tiebreak` follows
    the primary order and is never reversed, which is what makes a result set
    with equal values total and pageable. `nulls_last` marks a value where NULL
    means "none" rather than "low" (D-048).
    """

    column: str
    tiebreak: tuple[str, ...] = ("name", "pk")
    nulls_last: bool = False
```

`apps/charities/repositories.py:54`

```python
    # §6.2.5's mechanisms mapped to their ORDER BY. Every card shows the event
    # count and last-change date, so the page query always has those two
    # annotations; only trending adds a third (D-051).
    ORDER_KEYS: dict[Mechanism, OrderKey] = {
        ALPHABETICAL: OrderKey("name", tiebreak=("pk",)),
        TRENDING: OrderKey("trending_score"),
        POPULAR: OrderKey("event_count"),
        RATING: OrderKey("average_rating", nulls_last=True),
        HASKAMOS: OrderKey("approving_haskamas"),
        NEWEST: OrderKey("created"),
        UPDATED: OrderKey("last_changed"),
    }
```

`apps/charities/repositories.py:103`

Note the rating row: `nulls_last=True`. A charity with no reviews has no average, and no average is not a low rating, so those charities stay at the bottom in **both** directions. And the alphabetical row breaks ties by row number only, because its primary value already is the name.

### The deleted counting method

Before the branch, every listing annotated four numbers by fusing tables: a distinct review count, an average rating, and two haskama counts with a distinct modifier each.

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

`apps/charities/repositories.py:64` (before, on the branch's base)

The `distinct=True` was the tell: it was there because the joins could return the same review more than once. That method and its successors are gone.

### `_annotated` — numbers added only when something reads them (replaces `_counted`)

Now a number is added only when a card shows it or a filter compares it. Reviews are added when asked for; the approving count when a card needs it, a haskama order needs it, or a haskama filter compares it; the disapproving count only when the "maximum disapproving" filter compares it.

```python
def _annotated(
    self, *, reviews: bool, approving: bool = False, disapproving: bool = False
) -> QuerySet[Charity]:
    """Rows annotated with the numbers the cards and the filters read.

    The counts are over all of a charity's rows, not just published ones:
    while D-042 lists unpublished charities, the filters treat them the same.
    A value is added only when a card shows it or a filter compares it, so
    the pagination count does not aggregate rows it never reads. A haskama
    count comes from a subquery, so it never multiplies the rows the review
    aggregate sees (D-045, D-048).
    """
    rows = self._rows()
    if reviews:
        rows = rows.annotate(
            review_count=Count("reviews"),
            average_rating=Avg("reviews__rating"),
        )
    if approving:
        rows = rows.annotate(approving_haskamas=self._haskama_count(Haskama.Verdict.APPROVE))
    if disapproving:
        rows = rows.annotate(disapproving_haskamas=self._haskama_count(Haskama.Verdict.DISAPPROVE))
    return rows
```

`apps/charities/repositories.py:126`

### `_haskama_count` — one counting question per verdict (new)

The haskama count is its own question, not a join. Counting rows inside a question about this charity cannot multiply the rows the review average sees, which is exactly the bug that used to make a charity with two matching categories show four reviews.

```python
    @staticmethod
    def _haskama_count(verdict: str) -> Expression:
        """How many of a charity's haskamas carry `verdict`, as a count expression.

        HASKAMA is this app's table, so the subquery is read here rather than
        through another app's services. Coalescing to 0 keeps "no haskamas" a
        countable zero instead of NULL, which no filter or order can compare.
        """
        return Coalesce(
            Subquery(
                Haskama.objects.filter(charity=OuterRef("pk"), verdict=verdict)
                .order_by()
                .values("charity")
                .annotate(total=Count("pk"))
                .values("total"),
                output_field=IntegerField(),
            ),
            Value(0),
            output_field=IntegerField(),
        )
```

`apps/charities/repositories.py:152`

### `_narrowed` — filters that do not duplicate rows (rewritten)

This is where the row-multiplication bug was fixed. Before, each repeatable filter fused another table in:

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

`apps/charities/repositories.py:92` (before)

And this helper existed only to decide when to add the de-duplicating `distinct()`:

```python
    @staticmethod
    def _joins_rows(filters: CharityFilters) -> bool:
        """True when a filter multiplies rows, so DISTINCT is needed to count charities."""
        return bool(filters.domains or filters.locations or filters.haskama_rabbis)
```

`apps/charities/repositories.py:114` (before, deleted)

After, each repeatable filter asks "does at least one matching row exist?" instead of fusing tables in. A charity with three matching categories is still one row, so no de-duplication is needed. The method also decides which numbers to add, based on what the page, the filters and the chosen order will read:

```python
def _narrowed(
    self,
    filters: CharityFilters | None,
    *,
    sort: CharitySort | None = None,
    reviews: bool = False,
) -> QuerySet[Charity]:
    """Apply §6.2.4's groups: OR inside a group, AND between groups.

    A repeatable group is one EXISTS, not a join: a charity with three
    matching domains is still one row, so no DISTINCT is needed and the
    review count cannot be multiplied by a filter. A derived value is
    annotated only when a card, a filter or the chosen order reads it.
    """
    filters = filters or CharityFilters()
    needs_reviews = reviews or filters.min_rating is not None or filters.min_reviews is not None
    # A page passes `reviews=True`, and its cards all show the approving
    # count (D-051); the pagination count reads none of it.
    needs_approving = (
        reviews
        or (sort is not None and sort.mechanism == HASKAMOS)
        or filters.min_approving_haskamas is not None
    )
    rows = self._annotated(
        reviews=needs_reviews,
        approving=needs_approving,
        disapproving=filters.max_disapproving_haskamas is not None,
    )
    if filters.domains:
        rows = rows.filter(
            Exists(CharityDomain.objects.filter(charity=OuterRef("pk"), domain__in=filters.domains))
        )
    if filters.locations:
        rows = rows.filter(
            Exists(
                CharityLocation.objects.filter(
                    charity=OuterRef("pk"), location__in=filters.locations
                )
            )
        )
    if filters.haskama_rabbis:
        rows = rows.filter(
            Exists(
                Haskama.objects.filter(
                    charity=OuterRef("pk"), rabbi_user__in=filters.haskama_rabbis
                )
            )
        )
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
    return rows
```

`apps/charities/repositories.py:189`

### `_with_activity_values` — the numbers every card shows (new)

Every card now shows the event count and the last-change date, so those two are always added. Trending is the only order that needs a score as well. The haskama count is deliberately not added here; the previous method already added it when this page needs it, and counting the same rows twice would be waste.

```python
    @staticmethod
    def _with_activity_values(rows: QuerySet[Charity], sort: CharitySort) -> QuerySet[Charity]:
        """Annotate the EVENT-derived values the cards show and the chosen order reads.

        Every card shows the event count and last-change date (D-051), so those
        two are always added; trending is the only order that needs a third.
        The haskama count is not added here: `_narrowed` already knows it is
        needed for this page (or for a haskama filter or order), and reusing
        that one annotation keeps the query from counting the same rows twice.
        EVENT is another app's table, so these expressions come from its
        services.py; charities never imports the model (D-006).
        """
        rows = rows.annotate(
            event_count=events.event_count(OuterRef("pk")),
            last_changed=Coalesce(events.last_changed(OuterRef("pk")), F("created")),
        )
        if sort.mechanism == TRENDING:
            return rows.annotate(trending_score=events.trending_score(OuterRef("pk")))
        return rows
```

`apps/charities/repositories.py:252`

The `Coalesce(..., F("created"))` is where the fallback lives: a charity with no recorded change is "last changed" when it was created, so the date on the card is never empty.

### `_ordered` — the chosen order becomes the sorting instruction (new)

The chosen mechanism looks up its rule, the direction decides ascending or descending, and the tie-break always follows A to Z and then row number — even when the main order is reversed.

```python
    @classmethod
    def _ordered(cls, rows: QuerySet[Charity], sort: CharitySort) -> QuerySet[Charity]:
        """Order by the chosen mechanism, then by §6.2.5's alphabetical tiebreak.

        The tiebreak is always A→Z, even when the primary order is descending;
        the id makes the order total, so paging cannot repeat or skip a row.
        A rating of `None` is no rating, not a low one, so those rows stay last
        in both directions (D-048).
        """
        key = cls.ORDER_KEYS[sort.mechanism]
        primary = F(key.column)
        # Django wants None, not False, when NULLS LAST is not requested.
        nulls_last = True if key.nulls_last else None
        ordered = (
            primary.desc(nulls_last=nulls_last)
            if sort.descending
            else primary.asc(nulls_last=nulls_last)
        )
        return rows.order_by(ordered, *key.tiebreak)
```

`apps/charities/repositories.py:272`

### `page` — the whole query in five lines

The page method reads as the pipeline it is: narrow and annotate, add activity, order, take the window, build the cards. Before, it was `self._narrowed(filters).prefetch_related(...).order_by("name")[offset : offset + limit]` — one fixed order, no sort parameter.

```python
    def page(
        self,
        offset: int,
        limit: int,
        filters: CharityFilters | None = None,
        sort: CharitySort = DEFAULT_SORT,
    ) -> tuple[CharityCard, ...]:
        rows = self._narrowed(filters, sort=sort, reviews=True)
        rows = self._with_activity_values(rows, sort)
        rows = self._ordered(rows, sort)
        rows = rows.prefetch_related("domains", "locations")[offset : offset + limit]
        return tuple(self._to_card(row) for row in rows)
```

`apps/charities/repositories.py:173`

### `count` — the total, cheap again

The count does not pass the sort and does not ask for reviews, so it neither aggregates nor orders. It is a plain count of matching charities.

```python
    def count(self, filters: CharityFilters | None = None) -> int:
        return self._narrowed(filters).count()
```

`apps/charities/repositories.py:186`

### `_to_card` — the card now carries the activity numbers

The card gains one field: its activity, built from the three numbers the query computed.

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
            activity=ActivitySummary(
                events=row.event_count,
                approving_haskamas=row.approving_haskamas,
                last_changed=row.last_changed,
            ),
        )
```

`apps/charities/repositories.py:292`

What this buys: a charity is always one row; a page is always one query for the cards; the numbers a filter compares and the numbers a card prints are the same numbers; and a plain count costs a plain count.

---

## 4. `apps/charities/services.py` — the page, its links, and the one door for saving

**The page's links now replay the filters and the order, and every save of a charity goes through one function that records it.**

This file is the charities app's front door: the functions other apps may call, and the listing's own rules about pages, filters and links. Two things change here. The page learns about the chosen order and repeats it in every link. And a new function becomes the one way to save a change to a charity.

### `EDITABLE_FIELDS` and `update_charity` — one door for field saves (new)

Before, nothing in the app could save an edit. Publishing and hiding had their own path; a field edit had none. Now there is one function for field edits, and it accepts only four fields, locks the row while it works, writes only the fields that actually differ, and records one change event.

```python
# The charity fields a save may change. `is_visible` stays out: it changes only
# through publish/hide, so a caller cannot flip visibility by passing it here.
EDITABLE_FIELDS = ("name", "tagline", "description", "image")


def update_charity(charity_id, by_user_id=None, **changes):
    """Save field changes to a charity, recording one `charity_updated` EVENT.

    Every save of a charity goes through here or `_set_visible` (D-052), so the
    "most recently updated" order and §5.2.21's derived date cannot go stale.
    Only `EDITABLE_FIELDS` are accepted; anything else is a programming error,
    not a value to ignore. A call that changes nothing writes nothing and
    records no event (D-041's rule for an unchanged state).
    """
    unknown = set(changes) - set(EDITABLE_FIELDS)
    if unknown:
        raise ValueError(f"Not an editable charity field: {', '.join(sorted(unknown))}")
    with transaction.atomic():
        charity = Charity.objects.select_for_update().filter(pk=charity_id).first()
        if charity is None:
            raise Charity.DoesNotExist(f"No charity with id {charity_id}")
        changed = [field for field, value in changes.items() if getattr(charity, field) != value]
        if not changed:
            return
        for field in changed:
            setattr(charity, field, changes[field])
        charity.save(update_fields=changed)
        # Every change to a charity is recorded as a charity_updated EVENT (§6.1, D-039).
        record_event(charity_id, "charity_updated", user_id=by_user_id)
```

`apps/charities/services.py:21`

Three refusals live in that function, and each is deliberate. An unknown field is an error rather than something to ignore, so a typo cannot silently do nothing. Visibility is refused because it has its own audited switch. And a save with no actual difference writes nothing and records nothing, so "saved" does not become "changed".

### `Page` — the result set, and every link that must reproduce it

The page value gains the chosen sort, and its link-building is rebuilt so that one function produces any link while repeating the whole state.

Before, the page held a ready-made filter string and built links by gluing it on:

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

    @property
    def page_count(self) -> int:
        return page_count(self.total, self.page_size)

    @property
    def has_previous(self) -> bool:
        return self.number > 1

    @property
    def has_next(self) -> bool:
        return self.number < self.page_count

    def query(self, number: int) -> str:
        """Query string for another page of this same result set."""
        parts = {"page": number, "page_size": min(self.page_size, MAX_PAGE_SIZE)}
        if self.filters_query:
            return f"{urlencode(parts)}&{self.filters_query}"
        return urlencode(parts)
```

`apps/charities/services.py:55` (before)

After, the page holds the sort and the filter pairs, and one builder stitches a link from a base plus both:

```python
@dataclass(frozen=True)
class Page:
    """One page of results, plus the links needed to move between pages.

    The chosen filters and sort belong to the result set, not to one page: every
    link the page builds repeats both, or moving to page 2 would silently drop a
    filter or reorder the list.
    """

    items: tuple[CharityCard, ...]
    total: int
    number: int
    page_size: int
    sort: CharitySort = DEFAULT_SORT
    # The filters as (parameter, value) pairs, for replaying them as hidden inputs.
    filter_pairs: tuple[tuple[str, object], ...] = ()

    @property
    def page_count(self) -> int:
        return page_count(self.total, self.page_size)

    @property
    def has_previous(self) -> bool:
        return self.number > 1

    @property
    def has_next(self) -> bool:
        return self.number < self.page_count

    @property
    def sort_pairs(self) -> tuple[tuple[str, str], ...]:
        """The sort as hidden-input pairs; empty for the default order."""
        return sort_query_pairs(self.sort)

    def _state_query(self, *, include_filters: bool = True, **parts: int) -> str:
        """A query string of `parts`, followed by the active filters and sort."""
        base = urlencode(parts)
        pairs = self.filter_pairs if include_filters else ()
        state = urlencode(pairs + self.sort_pairs)
        return f"{base}&{state}" if state else base

    def query(self, number: int) -> str:
        """Query string for another page of this same result set."""
        return self._state_query(page=number, page_size=min(self.page_size, MAX_PAGE_SIZE))
```

`apps/charities/services.py:88`

### `clear_filters_query` — clearing the filters keeps the order (new)

The "Clear filters" link needs the page with its size and order kept, and the filters dropped. That is one call to the builder with the filters turned off.

```python
    @property
    def clear_filters_query(self) -> str:
        """The page with its size and order kept, but no filters (§6.2.4)."""
        return self._state_query(include_filters=False, page_size=self.page_size)
```

`apps/charities/services.py:142`

Before, the template built that link by hand as `?page_size={{ page.page_size }}` — which in a filtered, sorted world would have thrown the order away.

### `list_charities` — the order reaches the query

The function takes the chosen sort and hands it to the repository, and puts it on the page so the links can replay it.

```python
def list_charities(
    repository: CharityRepository,
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
    count = page_count(total, page_size)
    number = max(1, min(page or 1, count))
    offset = (number - 1) * page_size

    return Page(
        items=repository.page(offset=offset, limit=page_size, filters=filters, sort=sort),
        total=total,
        number=number,
        page_size=page_size,
        sort=sort,
        filter_pairs=filter_query_pairs(filters),
    )
```

`apps/charities/services.py:160`

What this buys: every link the page can build — the numbered pages, previous, next, clear filters — repeats the whole state through one function, so no link can forget the order and none can forget the filters.

---

## 5. `apps/charities/contracts.py` — the card's new field

**New: the card carries the three activity numbers, as a small frozen bundle.**

This file holds the plain values the listing passes around — deliberately free of any database behaviour, so the page logic and the templates cannot depend on how rows were fetched. One bundle is added.

Before, a card carried its reviews and nothing about activity.

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

`apps/charities/contracts.py:33` (before)

After, a new bundle holds the numbers, with a comment explaining why the date is never empty, and the card gains one field.

```python
@dataclass(frozen=True)
class ActivitySummary:
    """The activity values the card shows, and four sort orders read (D-051).

    `last_changed` falls back to CHARITY.created, so it is always a date: a
    charity no one has edited yet was last changed when it was added.
    """

    events: int
    approving_haskamas: int
    last_changed: datetime


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
    activity: ActivitySummary
```

`apps/charities/contracts.py:46`

What this buys: the template reads one named bundle instead of reaching for four separate values, and a test can check the card's shape without a database.

---

## 6. `apps/charities/views.py` — putting it on the page

**The view reads the order from the address and hands the control's ready-made data to the template.**

This is the one page view for the listing. Before, it read the filters and the page number, and passed the page and the sidebar to the template. It knew nothing about order.

```python
def listing(request: HttpRequest) -> HttpResponse:
    """Render the paginated list of charities, narrowed by the sidebar's filters."""
    options_repository = DjangoFilterOptionsRepository()
    # Keyed by the list each group draws from, not by URL parameter.
    options = {
        "domains": list_domains(options_repository),
        "locations": list_locations(options_repository),
        "rabbis": list_rabbis(options_repository),
    }
    # A ticked id that names no row is not a filter (D-045), so the lists are
    # read before the filters are settled rather than after the page is counted.
    filters = keep_known_ids(from_query(request.GET), options)
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
        options,
        # Passed so the sidebar can say when a value was clamped into range.
        requested=requested_numbers(request.GET),
    )
    return render(request, "charities/listing.html", {"page": page, "form": form})
```

`apps/charities/views.py:31` (before)

After, the view reads the sort first, passes it to the page, and adds the ready-made control to the template's values.

```python
def listing(request: HttpRequest) -> HttpResponse:
    """Render the paginated list of charities, narrowed and ordered as chosen."""
    sort = read_sort(request.GET)
    options_repository = DjangoFilterOptionsRepository()
    # Keyed by the list each group draws from, not by URL parameter.
    options = {
        "domains": list_domains(options_repository),
        "locations": list_locations(options_repository),
        "rabbis": list_rabbis(options_repository),
    }
    # A ticked id that names no row is not a filter (D-045), so the lists are
    # read before the filters are settled rather than after the page is counted.
    filters = keep_known_ids(read_filters(request.GET), options)
    page: Page = list_charities(
        # published_only stays False until the admin approval queue publishes
        # charities; see D-042.
        repository=DjangoCharityRepository(published_only=False),
        filters=filters,
        sort=sort,
        page=_positive_int(request.GET.get("page")),
        page_size=_positive_int(request.GET.get("page_size")),
    )
    form = filter_form(
        filters,
        options,
        # Passed so the sidebar can say when a value was clamped into range.
        requested=requested_numbers(request.GET),
    )
    return render(
        request,
        "charities/listing.html",
        {"page": page, "form": form, "sort_form": sort_form(sort)},
    )
```

`apps/charities/views.py:34`

What this buys: the view stays a wiring diagram. It reads the address, asks the services for a page, and passes three ready values to the template.

---

## 7. `apps/charities/admin.py` — the admin edit records itself

**New: the admin's edit form saves through the one door, so an admin edit now moves the charity up the "most recently updated" list.**

This file registers the charity models with Django's admin. Before, the admin could edit a charity's name, tagline, description and image, and that save went straight to the database without recording anything. The publish and hide actions already went through the app's services.

Before, there was no `save_model` at all: the admin used Django's own save.

After, a save that changes something routes the four editable fields through `update_charity`; creating a new charity still uses Django's own save, because creating is not a change:

```python
def save_model(self, request, obj, form, change):
    """Save edits through the service, so each one records an event (D-052).

    Creating a charity is not a change, so that path uses Django's own save
    and records no event, exactly as the factories and the seed do (D-022).
    """
    if not change:
        super().save_model(request, obj, form, change)
        return
    changes = {
        field: form.cleaned_data[field] for field in form.changed_data if field in EDITABLE_FIELDS
    }
    update_charity(obj.pk, by_user_id=request.user.id, **changes)
```

`apps/charities/admin.py:15`

The key detail is `form.changed_data`: only the fields the admin actually altered are passed on, so an unchanged form records nothing. And a field that is not one of the four editable ones is simply not passed, which is what keeps `is_visible` out of this path.

What this buys: the "most recently updated" order cannot go stale because an admin used the admin site. The known gap — categories and locations edited through the admin's multi-selects still record nothing — is written down in D-052 and does not apply to any product path today.

---

## 8. The templates — the control, the state, and the numbers on the cards

**New sort control and state fragments; the sidebar and listing now replay both the filters and the order; the cards show the activity numbers.**

Six template files are involved. Four are new: the control, two state fragments, and one that joins them. The two existing templates each gain an `{% include %}`, plus, in the listing, the new card row.

### `sort.html` — the control (new)

The control is one plain form: a dropdown, two direction buttons, and hidden inputs that carry the page size and the active filters. It sends no page number, so choosing an order lands on page 1. The comment at the top states all of that, and the comment above the dropdown says why submitting the dropdown alone is the right behaviour.

```html
{% load static %}
{% comment %}
The listing's sort control (§6.2.5, D-048): one dropdown and two direction
buttons, all in a plain GET form, so the order lives in the URL like the rest of
the page state. No `page` field is sent, so changing the order starts at page 1.
The active filters ride along as hidden inputs, so sorting never drops them.
`js/sort.js` applies a changed dropdown and Enter, sending no direction so the
mechanism starts in its default one (D-053).
{% endcomment %}
<form class="sort" method="get" action="{% url 'charities:listing' %}" data-sort-form>
  <input type="hidden" name="page_size" value="{{ page.page_size }}">
  {% include "charities/filter_state.html" %}

  <label class="sort__label" for="{{ sort_form.parameter }}">Sort</label>
  {% comment %}Submitting here sends no direction, so the new mechanism starts in
  its default direction; that also refreshes the two buttons' labels, which
  describe the order they will apply.{% endcomment %}
  <select
    class="sort__select"
    id="{{ sort_form.parameter }}"
    name="{{ sort_form.parameter }}"
  >
    {% for option in sort_form.options %}
      <option value="{{ option.value }}"{% if option.value == sort_form.selected %} selected{% endif %}>{{ option.label }}</option>
    {% endfor %}
  </select>

  <button
    class="sort__direction{% if not sort_form.descending %} sort__direction--current{% endif %}"
    type="submit"
    name="{{ sort_form.direction_parameter }}"
    value="{{ sort_form.ascending_value }}"
    {% if not sort_form.descending %}aria-current="true"{% endif %}
  >{{ sort_form.low_label }}</button>
  <button
    class="sort__direction{% if sort_form.descending %} sort__direction--current{% endif %}"
    type="submit"
    name="{{ sort_form.direction_parameter }}"
    value="{{ sort_form.descending_value }}"
    {% if sort_form.descending %}aria-current="true"{% endif %}
  >{{ sort_form.high_label }}</button>
</form>
<script src="{% static 'js/sort.js' %}" defer></script>
```

`apps/charities/templates/charities/sort.html:1`

### `filter_state.html` — the active filters as hidden inputs (new, extracted)

This fragment was previously written out inline in two places. Now it is one file, so the page-size form, the jump form and the sort form all replay the filters the same way.

```html
{% comment %}
The active filters as hidden inputs. A form that changes the order, page size or
page number includes this so it cannot silently drop the filters (§6.2.4).
{% endcomment %}
{% for name, value in page.filter_pairs %}<input type="hidden" name="{{ name }}" value="{{ value }}">
{% endfor %}
```

`apps/charities/templates/charities/filter_state.html:1`

### `sort_state.html` — the active order as hidden inputs (new)

The mirror image: any form that changes the filters, page size or page number includes this so it cannot silently reorder the list.

```html
{% comment %}
The active sort as hidden inputs. A form that changes the filters, page size or
page number includes this so it cannot silently reorder the list (§6.2.5).
{% endcomment %}
{% for name, value in page.sort_pairs %}<input type="hidden" name="{{ name }}" value="{{ value }}">
{% endfor %}
```

`apps/charities/templates/charities/sort_state.html:1`

### `state.html` — both, together (new)

One line that means "everything that makes this result set". The page-size and jump forms include this, because they change neither the filters nor the order.

```html
{% comment %}
Everything that makes the current result set: the filters and the order. The
page-size and jump forms include this, since they change neither.
{% endcomment %}
{% include "charities/filter_state.html" %}{% include "charities/sort_state.html" %}
```

`apps/charities/templates/charities/state.html:1`

### `filters.html` — the sidebar now carries the order

Two changes. The sidebar form gains the order, so applying a filter does not reorder the list. And the "Clear filters" link is now built by the service, so it keeps the size and the order while dropping the filters.

Before, the sidebar sent the page size and nothing about order, and the clear link was hand-built:

```html
  {% comment %}Keep the page size the reader chose; a filter resets the page to 1
  (§6.2.4), which is what a missing `page` parameter means.{% endcomment %}
  <input type="hidden" name="page_size" value="{{ page.page_size }}">
```

`apps/charities/templates/charities/filters.html:14` (before)

```html
      <a class="filters__clear" href="{% url 'charities:listing' %}?page_size={{ page.page_size }}">Clear filters</a>
```

`apps/charities/templates/charities/filters.html:70` (before)

After, the form includes the order, and the clear link asks the page for the right address:

```html
  {% comment %}Keep the page size and the order the reader chose; a filter resets
  the page to 1 (§6.2.4), which is what a missing `page` parameter means.{% endcomment %}
  <input type="hidden" name="page_size" value="{{ page.page_size }}">
  {% include "charities/sort_state.html" %}
```

`apps/charities/templates/charities/filters.html:14`

```html
      <a class="filters__clear" href="{% url 'charities:listing' %}?{{ page.clear_filters_query }}">Clear filters</a>
```

`apps/charities/templates/charities/filters.html:71`

### `listing.html` — the control in the header, the state in the forms, the numbers on the cards

Three changes. The sort control joins the page-size box in a new controls wrapper. The page-size and jump forms stop writing the filters out inline and include `state.html` instead. And every card gains the activity row.

Before, the page-size form wrote the filters inline and there was no control at all:

```html
        <form class="page-size" method="get">
          {% if page.number > 1 %}
            <input type="hidden" name="page" value="1">
          {% endif %}
          {# Keep the filters when the reader changes the page size. #}
          {% for name, value in page.filter_pairs %}
            <input type="hidden" name="{{ name }}" value="{{ value }}">
          {% endfor %}
```

`apps/charities/templates/charities/listing.html:17` (before)

After, the header holds a wrapper with the control beside the size box:

```html
        <div class="listing__controls">
          {% include "charities/sort.html" %}

          <form class="page-size" method="get">
            {% if page.number > 1 %}
              <input type="hidden" name="page" value="1">
            {% endif %}
            {# Keep the filters and the order when the reader changes the page size. #}
            {% include "charities/state.html" %}
```

`apps/charities/templates/charities/listing.html:17`

The jump form does the same one-line include instead of its own copy of the filter loop:

```html
            <form class="jump" method="get">
              <input type="hidden" name="page_size" value="{{ page.page_size }}">
              {% include "charities/state.html" %}
```

`apps/charities/templates/charities/listing.html:131`

And the activity row, added to every card, prints the three numbers the activity orders sort by:

```html
                  {# D-051: the numbers and dates the activity orders sort by, so an order can be checked. #}
                  <span class="charity-card__activity">
                    <span>{{ charity.activity.events }} event{{ charity.activity.events|pluralize }}</span>
                    <span>{{ charity.activity.approving_haskamas }} haskama{{ charity.activity.approving_haskamas|pluralize }}</span>
                    <span>Last changed {{ charity.activity.last_changed|date:"j M Y" }}</span>
                  </span>
```

`apps/charities/templates/charities/listing.html:93`

What this buys: every form and every link now repeats the same state, and the reader can see the numbers that placed each card.

---

## 9. `static/js/sort.js` — applying a changed dropdown

**New: a small script submits the sort form when the dropdown changes or Enter is pressed, sending no direction, so a new order starts in its own default direction.**

Without this script, picking a new order in the dropdown did nothing until the visitor also clicked a direction button. And pressing Enter in a dropdown activates the first button, which is always the ascending one — the wrong starting direction for six of the seven orders. The script submits the form itself, with no button attached, so no direction is sent and the server uses the chosen order's own default.

```javascript
// The listing's sort control (D-053).
//
// A changed dropdown applies at once, and Enter in it does the same. Both paths
// submit the form with no submitter, so no `direction` value is sent and the
// server uses the chosen mechanism's default direction. Without this script the
// browser's implicit submission would click the first direction button (always
// ascending) and the two-click flow would apply the new order only on the second
// click. The direction buttons keep working on their own with no script at all.

(function () {
  "use strict";

  function sortSelect(node) {
    return (
      node instanceof HTMLSelectElement &&
      node.form !== null &&
      node.form.matches("form[data-sort-form]")
    );
  }

  document.addEventListener("change", function (event) {
    if (sortSelect(event.target)) {
      event.target.form.submit();
    }
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Enter" && sortSelect(event.target)) {
      event.preventDefault();
      event.target.form.submit();
    }
  });
})();
```

`static/js/sort.js:1`

What this buys: choosing an order is one click instead of two, and Enter no longer applies the opposite direction. With the script off, the control still works exactly as the document describes: a choice plus a direction click.

---

## 10. `static/css/site.css` — the control and the card row

**New: styling for the controls wrapper, the sort control, and the activity row on the card.**

Three blocks are added. The header wraps instead of squeezing the heading on a narrow screen; the sort control is a row that wraps; and the activity row is small, grey, and wraps.

The header gets a wrapper that holds the sort control and the page-size box together at the right:

```css
/* Sort and page size sit together at the right of the header; on a narrow
   screen they wrap below the heading instead of squeezing it. */
.listing__controls {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  margin-left: auto;
}
```

`static/css/site.css:224`

The activity row, small enough to sit under the categories and locations:

```css
/* D-051: the values the activity orders sort by, shown on every card. */
.charity-card__activity {
  color: #555;
  display: flex;
  flex-wrap: wrap;
  font-size: 0.8125rem;
  gap: 0.25rem 0.75rem;
  margin-top: 0.25rem;
}
```

`static/css/site.css:314`

And the control itself, including the filled style for whichever direction is current:

```css
/* Sort control (§6.2.5, D-048): a dropdown and two direction buttons */
.sort {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.sort__label {
  color: #555;
  font-size: 0.875rem;
}

.sort__select {
  background: #fff;
  border: 1px solid #ccc;
  border-radius: 0.25rem;
  font: inherit;
  padding: 0.25rem 0.375rem;
}

.sort__direction {
  background: #fff;
  border: 1px solid #ccc;
  border-radius: 0.25rem;
  cursor: pointer;
  font: inherit;
  font-size: 0.8125rem;
  padding: 0.25rem 0.5rem;
}

.sort__direction:hover {
  background: #f2f2f2;
}

.sort__direction--current,
.sort__direction--current:hover {
  background: #1a4f8a;
  border-color: #1a4f8a;
  color: #fff;
}
```

`static/css/site.css:396`

The header itself also gains `flex-wrap: wrap` (line 216), so on a narrow screen the controls drop below the heading instead of squeezing it.

What this buys: the control sits beside the page-size box without breaking the header, and the current direction is visibly filled.

---

## 11. `apps/dashboards/management/commands/seed.py` — enough names

**New: 208 possible names, with 200 drawn without repeats, so the seeded listing never shows the same name twice by accident.**

This is dev tooling: a command that fills an empty local database with fake rows. It refuses to run outside development and on a database that already has rows.

Before, a name was one prefix from eight and one word from eight, drawn independently, so repeats were certain:

```python
NAME_PREFIXES = ["Keren", "Chasdei", "Yad", "Ezras", "Bais", "Tomchei", "Achiezer", "Lev"]
NAME_WORDS = ["Chesed", "Shalom", "Emunah", "Tzedakah", "Rachamim", "Simcha", "Torah", "Chaim"]
```

`apps/dashboards/management/commands/seed.py:59` (before)

```python
        for i in range(APPROVED + PENDING):
            name = f"{self.rng.choice(NAME_PREFIXES)} {self.rng.choice(NAME_WORDS)}"
```

`apps/dashboards/management/commands/seed.py:113` (before)

After, the word list is longer and the pairs are built once, then sampled without replacement:

```python
NAME_WORDS = [
    "Chesed",
    "Shalom",
    "Emunah",
    "Tzedakah",
    "Rachamim",
    "Simcha",
    "Torah",
    "Chaim",
    "Yisrael",
    "Mordechai",
    "Avraham",
    "Yitzchak",
    "Yaakov",
    "Moshe",
    "Aharon",
    "David",
    "Shlomo",
    "Menachem",
    "Naftali",
    "Yehuda",
    "Zev",
    "Aryeh",
    "Baruch",
    "Efraim",
    "Yosef",
    "Binyamin",
]

# One name per prefix/word pair: 8 × 26 = 208 pairs for 200 charities, so the
# seeded listing has no repeated name (D-049). CHARITY.name stays non-unique in
# the schema (D-013); this is only about data that reads like real rows.
NAMES = [f"{prefix} {word}" for prefix in NAME_PREFIXES for word in NAME_WORDS]
```

`apps/dashboards/management/commands/seed.py:60`

```python
        names = self.rng.sample(NAMES, APPROVED + PENDING)
        for i, name in enumerate(names):
```

`apps/dashboards/management/commands/seed.py:145`

The sample is 200 of 208. If someone later raises the charity count above 208, `random.sample` fails loudly rather than quietly repeating a name.

What this buys: a developer paging an ordered list sees 200 different names, so a real paging bug would be visible instead of hidden behind duplicate data.

---

## The tests

The test names are the change's own summary of itself. Read in groups, they say what each part promises.

### What each order does, against real rows (`tests/unit/test_sort_repository.py`, new)

This file runs each order against a real database, because the thing under test is the sorting instruction the query builds. The document asks for one test per order, and each order gets a class.

The alphabetical order defaults to A to Z, reverses, and breaks ties by row number so paging cannot repeat a row:

```python
    def test_equal_names_fall_back_to_the_row_id(self) -> None:
        """A tie needs a total order, or a page boundary can repeat a row."""
        first = make_charity("Same Name")
        second = make_charity("Same Name")

        cards = self.repository.page(0, 20, sort=DEFAULT_SORT)
        same_name = [card.id for card in cards if card.name == "Same Name"]

        self.assertEqual(same_name, [first.id, second.id])
```

`tests/unit/test_sort_repository.py:82`

The rating order puts charities with no reviews last in **both** directions, and its tie-break does not reverse with the direction:

```python
    def test_low_to_high_puts_the_unrated_charity_last_too(self) -> None:
        """No reviews is no rating, not a low rating (D-045, D-048)."""
        self.assertEqual(
            self.sorted_names(RATING, descending=False),
            ["Gamma", "Beta", "Alpha", "Delta"],
        )
```

`tests/unit/test_sort_repository.py:114`

The haskama order counts approvals only, and it does not multiply the review summary it shares a query with:

```python
def test_the_haskama_order_does_not_change_the_review_summary(self) -> None:
    """A sort must not multiply the review aggregate it shares a query with."""
    for charity, rating in ((self.alpha, 5), (self.alpha, 3), (self.beta, 4)):
        Review.objects.create(charity=charity, author=UserFactory(), rating=rating)

    cards = {
        card.name: card for card in self.repository.page(0, 20, sort=CharitySort(HASKAMOS, True))
    }

    self.assertEqual((cards["Alpha"].reviews.count, cards["Alpha"].reviews.average), (2, 4.0))
    self.assertEqual((cards["Beta"].reviews.count, cards["Beta"].reviews.average), (1, 4.0))
```

`tests/unit/test_sort_repository.py:168`

The trending order is tested twice over: once for the weights, and once for the non-overlap that D-050 settled. The second test states the arithmetic that used to be wrong:

```python
    def test_a_week_old_event_is_not_also_counted_in_the_month(self) -> None:
        """One event is worth 3, not 5, at the week boundary."""
        week_only = make_charity("Week Only")
        make_event(week_only, days_ago=6)
        month_only = make_charity("Month Only")
        for _ in range(2):
            make_event(month_only, days_ago=10)

        # Week Only 1 × 3 = 3; Month Only 2 × 2 = 4. The literal double count
        # would put Week Only's single event at 5 and reverse this order.
        self.assertEqual(
            self.sorted_names(TRENDING, descending=True),
            ["Month Only", "Week Only"],
        )
```

`tests/unit/test_sort_repository.py:248`

The newest order reads the charity's own creation date; the updated order reads the latest change record, and a newer view does not win:

```python
    def test_high_to_low_uses_the_last_change(self) -> None:
        # Beta changed 1 day ago, Alpha 3 days ago, Gamma never (created 5 days ago).
        self.assertEqual(
            self.sorted_names(UPDATED, descending=True),
            ["Beta", "Alpha", "Gamma"],
        )
```

`tests/unit/test_sort_repository.py:301`

A filter and an order work together in one query, and a repeatable filter keeps the review count exact:

```python
    def test_a_repeatable_filter_keeps_the_review_count_exact(self) -> None:
        """Two matching domains must not turn two reviews into four (D-045)."""
        first = Domain.objects.create(name="Food")
        second = Domain.objects.create(name="Education")
        charity = make_charity("Alpha")
        charity.domains.add(first, second)
        for rating in (5, 3):
            Review.objects.create(charity=charity, author=UserFactory(), rating=rating)

        filters = CharityFilters(domains=(first.id,))
        cards = self.repository.page(0, 20, filters)

        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0].reviews.count, 2)
        self.assertEqual(cards[0].reviews.average, 4.0)
        self.assertEqual(self.repository.count(filters), 1)
```

`tests/unit/test_sort_repository.py:338`

And the cost claims are tested by counting queries: the count never touches the review table, and a page of activity-sorted cards costs three queries (the page, the categories, the locations).

```python
def test_the_total_does_not_aggregate_reviews(self) -> None:
    """The count only needs the number of matching charities (D-045)."""
    make_charity("Alpha")

    with CaptureQueriesContext(connection) as queries:
        self.assertEqual(self.repository.count(), 1)

    self.assertNotIn("charities_review", queries.captured_queries[0]["sql"])


def test_activity_and_haskama_sorts_do_not_add_a_query_per_charity(self) -> None:
    charity = make_charity("Alpha")
    make_event(charity)

    for mechanism in (POPULAR, TRENDING, UPDATED, HASKAMOS):
        with self.subTest(mechanism=mechanism.value):
            with self.assertNumQueries(3):  # page, domains, locations
                self.repository.page(0, 10, sort=CharitySort(mechanism=mechanism, descending=True))
```

`tests/unit/test_sort_repository.py:386`

One more test guards the mapping itself: every mechanism must have a sorting instruction, so adding an eighth order without one fails here rather than on the page.

### The vocabulary and the address (`tests/unit/test_sorting.py`, new)

These need no database. They pin the read rules: nothing means alphabetical, an unrecognised order falls back, a missing direction keeps the mechanism's default, a junk direction does the same, and the default writes no parameters.

```python
def test_a_sort_that_names_no_mechanism_falls_back_to_alphabetical(self) -> None:
    self.assertEqual(from_query(QueryDict("sort=sideways&direction=desc")), DEFAULT_SORT)


def test_a_junk_direction_keeps_the_mechanisms_default(self) -> None:
    sort = from_query(QueryDict("sort=rating&direction=sideways"))

    self.assertEqual(sort.mechanism, RATING)
    self.assertTrue(sort.descending)
```

`tests/unit/test_sorting.py:40`

They also pin the label rule: each order words its own directions, so "High to low" is never asked of a date.

### The page and its links (`tests/unit/test_services.py`, `tests/unit/test_views.py`)

These prove that every link and form repeats the whole state. The page-link tests read the generated address:

```python
    def test_next_query_keeps_the_filters_and_the_sort(self) -> None:
        """A page link must replay the whole result set (D-045, D-048)."""
        page = Page(
            items=(),
            total=30,
            number=1,
            page_size=10,
            sort=CharitySort(mechanism=RATING, descending=True),
            filter_pairs=(("domain", 3), ("min_rating", 4)),
        )

        self.assertEqual(
            page.next_query,
            "page=2&page_size=10&domain=3&min_rating=4&sort=rating&direction=desc",
        )
```

`tests/unit/test_services.py` (PageQueryTest)

```python
    def test_clearing_filters_keeps_the_page_size_and_sort(self) -> None:
        page = Page(
            items=(),
            total=30,
            number=3,
            page_size=10,
            sort=CharitySort(mechanism=RATING, descending=True),
            filter_pairs=(("domain", 3),),
        )

        self.assertEqual(page.clear_filters_query, "page_size=10&sort=rating&direction=desc")
```

`tests/unit/test_services.py` (PageQueryTest)

The page tests drive the real view: the chosen order reorders the page, a mechanism starts high to low, an unrecognised order falls back, the control sends no page number, and the pagination links, the page-size form and the jump form all keep the order. On the other side, a sort does not drop the filter, applying filters keeps the sort, clearing keeps the sort, and page links keep both:

```python
    def test_clearing_filters_keeps_the_sort(self) -> None:
        response = self.client.get(
            self.url, {"domain": [self.food.id], "sort": "rating", "direction": "desc"}
        )

        link = re.search(r'<a class="filters__clear" href="([^"]+)"', response.content.decode())

        self.assertIsNotNone(link)
        self.assertIn("sort=rating", link.group(1))
        self.assertIn("direction=desc", link.group(1))
        self.assertNotIn("domain=", link.group(1))
```

`tests/unit/test_views.py:453`

```python
def test_the_sort_form_sends_no_page_so_a_new_order_starts_at_page_one(self) -> None:
    """§6.2.5: the reader is shown page 1 of the new order."""
    body = self.client.get(self.url, {"page": 2, "page_size": 2}).content.decode()
    sort_form = body[
        body.index('<form class="sort"') : body.index("</form>", body.index('<form class="sort"'))
    ]

    self.assertNotIn('name="page"', sort_form)
```

`tests/unit/test_views.py:277`

### The control's contract with the template (`tests/unit/test_template_contract.py`)

Django templates fail silently, so a control whose option list stops reaching the page would look fine and do nothing. These tests pin what the partial is allowed to depend on: all seven options reach the dropdown, the labels come from the chosen order, the sort form repeats the filters, the form carries the marker the script looks for and has no inline handler, and the script actually contains both listeners:

```python
    def test_the_dropdown_applies_its_choice_when_it_changes(self) -> None:
        """The labels must never describe the mechanism that is no longer chosen (D-053)."""
        body = self.client.get(self.url).content.decode()
        form = self._sort_form(body)

        self.assertIn("data-sort-form", form)
        # The behaviour lives in the script, not in an inline handler that a
        # Content-Security-Policy would have to allow.
        self.assertNotIn("onchange=", form)
        self.assertIn('<script src="', body)
        self.assertIn("js/sort.js", body)
```

`tests/unit/test_template_contract.py:222`

```python
    def test_enter_in_the_dropdown_takes_the_same_path_as_a_change(self) -> None:
        """Both listeners submit with no submitter, so the default direction wins.

        There is no browser here to press the key, so the check is on the script
        the page loads: losing either listener would bring back the asc-first
        implicit submit.
        """
        script = (settings.BASE_DIR / "static" / "js" / "sort.js").read_text(encoding="utf-8")

        self.assertIn('addEventListener("change"', script)
        self.assertIn('addEventListener("keydown"', script)
        self.assertIn('event.key === "Enter"', script)
        self.assertIn("form.submit()", script)
```

`tests/unit/test_template_contract.py` (SortControlContractTest)

The same file also proves the new card row renders, including zero counts:

```python
    def test_activity_values_render_on_every_card(self) -> None:
        """D-051: every order shows the numbers it sorts by, including zero counts."""
        charity = Charity.objects.create(name="Keren L'Dugma")
        for _ in range(2):
            Event.objects.create(charity=charity, action=Event.Action.VIEW)
        Haskama.objects.create(
            rabbi_user=UserFactory(), charity=charity, verdict=Haskama.Verdict.APPROVE
        )

        body = self._render_single_charity()

        self.assertIn("2 events", body)
        self.assertIn("1 haskama", body)
        self.assertIn("Last changed", body)
```

`tests/unit/test_template_contract.py:102`

### The one door for saving (`tests/unit/test_charity_services.py`, `tests/integration/test_charity_admin.py`)

The service tests prove the four promises of `update_charity`: it saves and records one event, a no-change save records nothing, only the changed fields are written, and visibility is refused:

```python
    def test_update_cannot_change_visibility(self) -> None:
        """Visibility belongs to publish/hide, which are the audited switch (D-038)."""
        charity = CharityFactory()

        with pytest.raises(ValueError, match="is_visible"):
            update_charity(charity.id, is_visible=True)

        charity.refresh_from_db()
        assert charity.is_visible is False
        assert not Event.objects.exists()
```

`tests/unit/test_charity_services.py`

The admin test proves the admin screen now goes through that door, and that an unchanged form records nothing:

```python
def test_editing_a_charity_records_an_event(client, admin_user):
    """D-052: an admin edit is a save too, so it moves "most recently updated"."""
    charity = CharityFactory(name="Old Name")

    response = client.post(f"{CHANGELIST}{charity.id}/change/", {"name": "New Name"})

    assert response.status_code == 302
    charity.refresh_from_db()
    assert charity.name == "New Name"
    event = Event.objects.get(charity=charity, action=Event.Action.CHARITY_UPDATED)
    assert event.user_id == admin_user.id
```

`tests/integration/test_charity_admin.py:28`

### The seed (`tests/integration/test_seed.py`)

One new assertion, reading as the sentence it is: the 200 seeded charities have 200 distinct names.

```python
    assert Charity.objects.count() == 200
    # D-049: pairs are sampled without replacement, so no two names repeat.
    assert Charity.objects.values("name").distinct().count() == 200
```

`tests/integration/test_seed.py:19`

### What changed in the existing tests, and what was deleted

No test was deleted. One existing test double gained a `sort` argument with a default, because the repository's `page` method now takes one (`tests/unit/test_filter_service.py`). The card tests gained the new `activity` field, because a card now has one. The repository tests gained two cases for the activity values, including the fallback to the creation date when a charity has never been edited.

---

That is the whole change: one file that names the seven orders, one file in the events app that answers three activity questions, one query rebuilt so a charity is one row and a page is one query, one service that owns saving a charity, and a page whose every link repeats both the filters and the order.
