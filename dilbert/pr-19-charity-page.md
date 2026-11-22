# PR 19 — "Charity page": one charity in full, and a site that stops promising dead ends

- **PR:** [#19](https://github.com/MaaserMart/MaaserMart/pull/19) — `audit/03-charity-page-and-errors` into `audit/02-schema-and-writes`
- **Size:** 21 files, 1080 added lines, 57 removed
- **Position in the stack:** third of five.
- **Commits:** `a325490` — the charity page, with the visits and clicks it promises (D-057, D-058); `36f1a21` — stop advertising destinations that 404, add friendly error pages (B1, S4, M8, A3); `0b1f532` — a failed visit write no longer fails the page (§6.2.7), found in review.
- **Written for:** the reviewer working without the diff, and anyone who wants to know what these two changes are for.

---

## 1. Read this part even if you read nothing else

A site makes promises with its links. Every link is a sentence: *"there is something here"*. A
visitor who clicks a link and lands on a dead page has been told something untrue, and the cost is
not the dead page — it is that they stop believing the other links.

This PR is mostly about keeping promises, in two ways.

**First, the biggest promise the site had been making and not keeping: the charity itself.** The
listing shows twenty-five charity cards per page — a name, a picture, a rating. Clicking one did
nothing. Every card was a link to `#`, a placeholder. There was no page anywhere on the site that
showed a single charity in full: its description, its locations, its three outbound links, the rabbis
who endorsed it, and the reviews members had written.

This PR builds that page, at `/charity/<id>/`. It also does something less visible and more
interesting: **it records what people do there.** Every visit writes a line in the events table
saying "somebody viewed this charity", and every click on a charity's outbound link writes "somebody
clicked the donate link of this charity" *before* sending them to the charity's own website. Those
lines are what the listing's "most popular" and "trending" orderings count. Until now those orderings
read only the seeded sample data, so "most popular" was a promise the site could not keep either.

**Second, the site's other false sentences.** The navigation bar had eight hand-written links, and
seven of them led to pages that do not exist yet — dead ends for anyone who tried. The nav now builds
each link from the site's own route table and simply leaves out any page that has not shipped. A short
honest nav, instead of eight destinations and seven dead ends.

And when someone does land on an address that does not exist — or a page they may not see, or a page
that breaks — they now get a real page that says so in words and offers a way back, instead of the
browser's bare error. There is also a "skip to content" link at the very top, so a keyboard user does
not have to tab through eight navigation links to reach the content.

**The whole change is one idea: make the site's claims true.** Cards lead to charities, links lead to
pages, errors say what happened, and popularity is counted from real visits rather than only from
seeded rows.

Everything below is the same idea in more detail.

---

## 2. How to read this file

Three rules.

1. **Read the glossary first** (section 3). Every term in this document is defined there before it is
   used.
2. **Every grey code box is optional.** The sentence directly above each box says the same thing in
   English. Skip all the boxes and the story is complete.
3. **Each file section opens with a bold one-line summary.** Those lines alone are the change in a
   dozen sentences.

This document explains; it does not grade. Section 6 lists where the code departs from the customer's
written design, so you can decide what to do about it.

---

## 3. The glossary

| word | what it means here |
|---|---|
| **charity** | One organisation on the site: a name, a tagline, a description, an image, some domains and locations, links, endorsements and reviews. |
| **the listing** | The page of charity cards. It links to the charity page added here. |
| **the charity page** | The new page showing one charity in full. |
| **link** (outbound) | One of a charity's three website links: donate, about, or contact. Each is a stored web address. |
| **endorsement / haskama** | A rabbi's public statement about a charity: approves or does not approve, with a note and an importance rating out of ten. The site's own word for it is *haskama*. |
| **review** | A member's rating (1–5) and comment about a charity. |
| **event** | A recorded line saying something happened to a charity: a view, a click, a rejection, an edit. The listing's popularity orderings count these. |
| **route / URL pattern** | The site's own list of which addresses exist. A route is the *name* of a page (`charities:detail`), from which the site can work out the *address* (`/charity/7/`). |
| **context processor** | A small function the site runs on every page to add values to what the template can see. Here, it supplies the nav's links to every page. |
| **404 / 403 / 500** | The three standard "this went wrong" answers: the address does not exist (404), you may not see it (403), the site itself failed (500). |
| **redirect** | An answer that says "the thing you asked for is over there" and sends the visitor on without them noticing, except that the address in their bar changes. |

The plain words map onto the code like this:

| the code says | this document says |
|---|---|
| `CharityPage`, `CharityLink`, `ReviewEntry`, `HaskamaEntry` | the charity page's data, one piece at a time |
| `repository.detail`, `get_charity_page` | "read one charity in full" |
| `link_redirect`, `get_link_url` | "count the click, then send them on" |
| `record_event(..., "view")` | "write down that this was visited" |
| `hidden_by_user` | an event the member hid from their own history |
| `NAV_DESTINATIONS`, `reverse`, `NoReverseMatch` | the nav's list, and the site's refusal to build an address for a page that does not exist |
| `context_processors.nav` | the function that puts the nav on every page |

---

## 4. The story

### 4.1 The page that was promised

Imagine the site as a shop with a window display. The window is the listing: twenty-five cards, each
with a name, a picture, a rating and a couple of tags. It is a good window. But the shop behind it was
empty — clicking any card took you nowhere, because every card's link was literally `#`, the
placeholder that means "no destination".

The design document is clear about what should be behind that window (§6.2.7, quoted in full below).
It describes a page showing the charity's image, name, locations, domains, tagline and description;
a links section with three links — about, contact, donate; a haskama section; a review section; and a
line saying when the page was last updated. And it says what the page must *write*, not only show:
every visit is recorded, and every click on one of a charity's links is recorded, attributed to the
signed-in visitor when there is one.

The code needed all of that, and the shape of the page is the smallest part of it. The interesting
part is that the page has to **read one charity from many tables and write down what happens**,
without either half being able to see the other half's tables directly.

### 4.2 Why "recording the visit" is not bookkeeping

The listing has two orderings that are not alphabetical: "most popular" and "trending". Both count
**events** — the table where the site writes down that something happened to a charity.

Until this PR, nothing in the running site wrote a view or a click. The only events in the database
were the ones the sample-data command created. So "most popular" sorted the seeded sample, and
"trending" measured which sample rows were stamped with recent dates. Both were honest code reading a
dishonest database: the orderings were real, but the traffic they measured was invented.

Two lines of this PR fix that, and they are the two least visible lines in it:

- the charity page records a `view` event every time it is opened;
- the outbound-link route records a `link_click` event every time somebody clicks a charity's donate,
  about or contact link — and then sends them to the charity's own site.

From then on the popularity orderings read real visits. That is also why the listing page does **not**
record views: showing twenty-five cards is not twenty-five visits (D-057 says this in as many words).

### 4.3 Counting a click without breaking the link

To count a click you have to be in the path of the click. If a charity's donate button points straight
at the charity's website, the site never learns that the click happened.

So the outbound links point at a small internal address instead:
`/charity/7/link/12/`. That address does three things and nothing else: find link 12, check that its
target is a real `http` or `https` web address, write the click, and redirect the browser to the real
target. The visitor sees the charity's site; the database sees the click.

The check matters. A stored link is a piece of text somebody typed, and a text field can hold
`javascript:alert(1)` — a value that, put in a link by hand-written template code, runs a script
instead of going to a website. Only `http` and `https` are followed anything else answers "not found".

### 4.4 Where a hidden event stands

The events table has a column called `hidden_by_user`: a member can hide an event from their own
history (the design doc's §5.2.21 defines the column). Nobody had yet decided what hiding *means* for
the popularity counts.

D-057 decides it: **an event the member hid counts for nothing.** Hiding is a statement that this
should not be remembered, so a hidden view must not keep pushing a charity up the "most popular" list.
Two queries changed to honour that — the event count behind "most popular" and the weighted score
behind "trending" — and the test that proves it is delightfully blunt (`HiddenEventTest`): one charity
gets a visible view and one gets a hidden view, and the visible one must rank higher.

### 4.5 The other half: a site that stops lying

The second commit is not about the charity page at all. It is about the nav bar, which had eight links
written by hand as plain text (`<a href="/tools/">Maaser tools</a>`), of which seven led to pages that
do not exist yet. A visitor who clicked "Maaser tools" got a dead end.

The fix is a small change with a large idea in it: **the nav is built from the site's own route
table.** Each nav entry names a *route* (`charities:listing`), and the site is asked to turn that into
an address. If the route does not exist yet, the question fails and that one link is left out. The
result is a bar that is short today and grows by itself, one link at a time, as pages are built — and
that cannot advertise an address nobody can serve.

Alongside it:

- a **404 page, a 403 page and a 500 page** that look like the site and say what happened in words,
  with a way back to the listing. Before, an unknown address produced the browser's bare error text;
- a **skip link** at the very top of every page, so a keyboard user can jump past the nav instead of
  tabbing through it;
- a labelled `<main>` region and a labelled nav, which is what tells a screen reader "the navigation
  starts here" and "the content starts here".

### 4.6 What was switched on, in one sentence

The listing's cards now lead to a page for the charity, that page shows everything the design names
and records visits and clicks as it goes, the popularity orderings count real traffic and ignore
hidden events, the rabbi filter finally has its list of rabbis, and the site's navigation only
advertises pages that exist.

---

## 5. Contradictions — places where code and documents disagree

Four of these are worth your attention. They are stated, not judged; the first was a real defect and is
now fixed, and its section says so.

### 5.1 A failed event write must not fail the page — it used to, and now it cannot

**Status: found in review, then fixed on this branch (`0b1f532`).** This section is kept because the
reason it was wrong is more instructive than the fix.

§6.2.7's "Service functions" line reads, in the customer's document:

> `events.services.record_event(charity_id, action, link_id, user_id)` -> **Failed writes do not fail
> the page**

As first written, the view did not guard the call:

```python
    if charity is None:
        raise Http404("No charity with that id")
    record_event(charity_id, "view", user_id=_actor_id(request))
    return render(request, "charities/detail.html", {"charity": charity})
```

And `record_event` deliberately turns a rejected write into a raised `ValueError` (PR #18 changed it
from a raw database error to a named one). So a failed write took the page down with it: a member whose
account was deleted mid-session would send a `user_id` that no longer exists, and the page answered 500
instead of showing the charity. The charity itself is confirmed to exist one line earlier, so the
common case was safe — this was the *uncommon* case the document asks to be made safe, which is exactly
the kind of case a review is for.

Both views now count through one helper that logs the refusal and carries on:

```python
def _count_visit(charity_id: int, action: str, **context) -> None:
    """Write one visit/click EVENT, and never let that write fail the page.

    §6.2.7 asks for exactly this: `record_event` is bookkeeping, so "Failed writes
    do not fail the page". `record_event` raises a `ValueError` when a reference
    does not exist (audit B6), and a visitor whose account was deleted mid-session
    is enough to trigger that — the charity is still there to show, and losing the
    count is cheaper than a 500.
    """
    try:
        record_event(charity_id, action, **context)
    except ValueError:
        logger.warning(
            "visit not counted: charity_id=%s action=%s context=%s",
            charity_id,
            action,
            context,
            exc_info=True,
        )
```

Two tests pin the promise from both ends: `test_a_refused_visit_write_still_shows_the_charity` (the
page renders with a 200 and the charity's name) and
`test_a_refused_click_write_still_sends_the_visitor_on` (the click still redirects to the charity's own
site). Both make the write fail on purpose with `monkeypatch`, which is the only honest way to test a
path that depends on the database refusing something.

### 5.2 The design's URL is bare; the code's has a prefix

§6.2.7 gives the URL as `/charity_id/` — literally a number after the slash, no word in front. That
would collide with every other top-level path (`/tools/`, `/dashboard/`, `/accounts/`…) and is
ambiguous to read.

The code uses `/charity/<id>/`. That is what `CLAUDE.md` already said, and it follows D-009's rule that
each app's pages live under the app's own prefix. Recorded as D-057. See 6.D1.

### 5.3 The design says the page returns a `dict`; the code returns a frozen object

§6.2.7's service line:

> `charities.services.get_charity_page(charity_id)` → **dict** with name, tagline, description, image,
> links, locations, domains, reviews, haskamas, avg_rating, review_count, last_updated

The code returns a `CharityPage`, a frozen data object with those fields and a few more (`links` as
its own typed entries, `haskamas` and `reviews` as typed entries, `is_visible`, and an `activity`
summary). A `dict` would let any typo in a template read `charity.review_count` on a page that has
`count` and silently render nothing; an object fails loudly instead.

This is the same shape of disagreement as the search module (D-054) and is not recorded as its own
decision. It is a deliberate, small departure in type only — the *names* it delivers are the ones the
design asks for.

### 5.4 The design says the page reads the two request tables. The code does not.

§6.2.7's "Models touched / Reads" list includes `new_charity_request` and `approval_request`. The page
does not read either. Nothing in §6.2.7's own description of the page says what it would show from
them, and the approval queue that owns those tables is not built yet. So the code reads what the page
displays and nothing more. Listed as a departure (6.D5) so it is a decision rather than an omission.

---

## 6. Departures from the design document

Each entry: what the document says, what the code does, why, and how hard it is to undo. Where a
decision exists, its id is given. These are for your judgement, not a defence of the code.

### 6.D1 The charity page's address

- **Document says:** `/charity_id/` (§6.2.7).
- **Code does:** `/charity/<id>/`.
- **Why:** a bare number at the top level collides with every other app's prefix and breaks D-009's
  rule (each app's pages live under the app's prefix). `CLAUDE.md` already stated the prefixed form.
- **Judged:** D-057 (Active). Adopt the prefix; the document's version is ambiguous, not wrong in
  spirit.
- **Reversible in:** one line of `apps/charities/urls.py` plus anywhere that builds the address. The
  code never hard-codes the path — every link is built from the route name — so the cost is one line.

### 6.D2 Outbound links go through a counter, not straight to the charity

- **Document says:** "On clicking a link, it goes to that link and calls `record_event`, with a
  `link_id`" (§6.2.7). Read literally, the anchor points at the charity's website and the site
  records the click as it happens.
- **Code does:** the anchor points at `/charity/<id>/link/<link_id>/`, which records the event and
  then redirects to the real target. Only `http`/`https` targets are followed.
- **Why:** a browser leaving for another site cannot be made to write to our database on the way out.
  A redirect is the only reliable way to count the click — and the only way to refuse a target that is
  not a web address (audit B5's neighbour; `validate_image` and this share the same reasoning).
- **Judged:** D-057. Unavoidable if the count is to be real.
- **Reversible in:** making each anchor point at `link.url` and deleting the route. Doing that loses
  the click count, which is the point of the design's sentence.

### 6.D3 The nav is shorter than the document's nav

- **Document says:** "There is a tab on top of the page, always visible. It contains links to login,
  signup, help, report charity, request charity, dashboard, maaser-tools, and charity listing"
  (§7.2).
- **Code does:** the nav lists exactly those destinations **whose pages exist**, in that order, and
  omits the rest. Today that is fewer than eight. There is also no chatbot icon, which §7.2 mentions;
  the chatbot has no module yet.
- **Why:** seven of the eight were dead links, which is worse than a short bar. The list is declared
  once, by route name, and each entry appears the day its page lands — so nothing has to be remembered
  when a later PR adds a page.
- **Judged:** D-057's neighbour and audit finding B1. The bar is the customer's list, in the
  customer's order; it is just not lying about what exists yet.
- **Reversible in:** nothing to undo — the entries are already all declared. Pages fill the bar in as
  they ship.

### 6.D4 Hidden events count for nothing

- **Document says:** `hidden_by_user` exists on EVENT (§5.2.21) but no section says what hiding means
  for the popularity counts, which the document derives from EVENT rows.
- **Code does:** the event count behind "most popular", the trending score, and the activity line on
  the charity page all ignore hidden events. `last_changed` is unaffected, because `charity_updated`
  events are never hidden.
- **Why:** hiding an event is a member saying it should not be remembered; letting it keep raising a
  charity's rank would make the member's choice decorative.
- **Judged:** D-057, explicit.
- **Reversible in:** one filter argument in two query methods, if you decide hiding is only about the
  member's own history.

### 6.D5 The page reads fewer tables than the document lists

- **Document says:** the page reads `new_charity_request` and `approval_request` (§6.2.7).
- **Code does:** reads charity, links, reviews, haskamas, domains, locations and events. Not the two
  request tables.
- **Why:** nothing on the page displays anything from them, and the approval queue that owns them is
  not built. Reading them now would be a cross-app import for data no template shows.
- **Judged:** not recorded as its own decision — a gap in the document rather than a disagreement.
  Worth a line in `DECISIONS.md` if the approval flow later wants a "pending edit" banner here.
- **Reversible in:** adding a service call from approvals; no schema, no migration.

### 6.D6 The wording is "charity", where the document asks for "tzedaka"

- **Document says:** §7.4, "Wording and Tone Requirements": *"Charity → Tzedaka"*, with the note that
  more such pairings will likely come up ("Orthodox Jewish terminology per SRS 3.2.1").
- **Code does:** every user-facing string says "charity" or "charities" — nav, page headings, error
  pages, the listing ("Back to all charities").
- **Why:** nothing in the code has adopted §7.4 yet; the wording rule has never been applied, so this
  PR matches the rest of the site rather than being inconsistent with it.
- **Judged:** this is the one departure with a *customer-facing* cost, and it is site-wide rather than
  local to this PR. Applying §7.4 is a small change that is expensive only in review attention, and it
  should be one deliberate pass over all copy — not a corner of a charity-page PR.
- **Reversible in:** find-and-replace over template strings, plus the tests that assert on visible text.
  Cheap technically; costly socially if done twice.

### Not departures, though they may look like it

- **Recording a `view` on every page load.** The document says "On loading, it calls `record_event` to
  record that it was visited" — no dedupe, no bot detection. The code does exactly that. (See 8.5 for
  the consequence: a refresh is a visit.)
- **Reviews and haskamas appearing on the page.** The document asks for both sections, in that order,
  with the counts. The code shows approvals/disapprovals count, the endorsing rabbi's name, verdict,
  importance, note and date; and the reviewer's name, rating, text and date.
- **The "last updated" line.** The document asks for it; the code shows it as "Last changed" from the
  latest `charity_updated` event. Same value, different words.
- **A 404 for an unknown charity.** The document does not name an error path for a missing id; the code
  raises a real 404 that renders the new friendly page. That is the document's §6.5 spirit, not a
  departure.

---

## 7. Reading order

Read in this order; each row is a file and the reason it is in this PR.

| # | file | why it changed | size |
|---|---|---|---|
| 1 | `apps/charities/contracts.py` | declares what the page is made of | +56 |
| 2 | `apps/charities/repositories.py` | reads one charity in full; safe link lookup; rabbi list | +134, −9 |
| 3 | `apps/charities/services.py` | two function names the views call | +17 |
| 4 | `apps/charities/urls.py` | two new addresses | +3 |
| 5 | `apps/charities/views.py` | the page, and the counted redirect | +43, −2 |
| 6 | `apps/charities/templates/charities/detail.html` | the page itself | +128 |
| 7 | `apps/charities/templates/charities/listing.html` | the card finally points somewhere | +1, −2 |
| 8 | `apps/events/services.py` | hidden events stop counting | +13, −4 |
| 9 | `apps/accounts/services.py` | rabbi identity, member names, rabbi list | +80, −1 |
| 10 | `apps/charities/filters.py` | the "not available yet" note is gone | +2, −6 |
| 11 | `apps/support/context_processors.py` | the nav, built from routes | +71 |
| 12 | `templates/base.html` | nav, skip link, main region | +30, −25 |
| 13 | `templates/403.html`, `404.html`, `500.html` | the friendly error pages | +34 |
| 14 | `config/settings/base.py` | register the nav processor | +2 |
| 15 | `static/css/site.css` | styles for the page, the errors, the skip link | +168 |
| 16 | `docs/DECISIONS.md` | D-057, D-058 | +25, −2 |
| 17 | `tests/unit/test_charity_page.py` | the page's tests (read in section 9) | +157 |
| 18 | `tests/integration/test_base_template.py` | the nav's tests (section 9) | +62, −8 |
| 19 | `tests/unit/test_repositories.py` | hidden events do not count (section 9) | +28 |

---

## 8. The files, one at a time

Each section opens with a bold line that is the whole point of the file.

### 8.1 `apps/charities/contracts.py` — the page's shape, declared before it is read (+56)

A **contract** is the list of values a page is allowed to see. Declaring it before writing the query
means the template and the query cannot drift: the template can only ask for names that exist.

Four new frozen data objects, one per thing the page shows — an outbound link, a review, an
endorsement, and the page itself:

```python
@dataclass(frozen=True)
class CharityPage:
    """Everything §6.2.7's charity page shows, read in one place.

    ``image`` is the stored value (a path or an allowed URL), never a rendered
    `src`; the template turns it into one through `image_src` (D-056).
    """

    id: int
    name: str
    tagline: str | None
    ...
    reviews: tuple[ReviewEntry, ...]
    review_summary: ReviewSummary
    haskamas: tuple[HaskamaEntry, ...]
    approving_haskamas: int
    disapproving_haskamas: int
    activity: ActivitySummary
    is_visible: bool
```

Two details in the docstring are worth a reader's attention. First, `image` holds **the stored
value** — a repository path or an approved web address — never a browser-ready `src`; the template
converts it through the same filter the cards use, so an image cannot be rendered here that a card
would refuse (PR #18's rule, honoured on the new page without re-deciding it). Second, the review
summary is the listing's own `ReviewSummary` object, not a fresh pair of numbers, so the page and the
card are arithmetically incapable of disagreeing.

### 8.2 `apps/charities/repositories.py` — reading one charity in full, and a safe link target (+134, −9)

Three additions and one deletion. The deletion is a win: the filter's rabbi list stops being a
placeholder that always returns nothing.

**Reading the page.** One query, with the same annotations the listing uses, then the child rows
fetched from it. The two `accounts` calls are the app-boundary rule in action: the repository needs
members' names and rabbis' public identities, and it asks accounts' service for them rather than
reading accounts' tables (D-006).

```python
def detail(self, charity_id: int) -> CharityPage | None:
    """Everything §6.2.7's charity page shows for one charity, or None.

    The counts (reviews, haskamas, events) are the same annotations the
    listing uses, so the page and the card cannot disagree. Author and
    rabbi names come from accounts' services, never from its tables (D-006).
    """
    rows = self._annotated(reviews=True, approving=True, disapproving=True)
    row = self._with_activity_values(rows, DEFAULT_SORT).filter(pk=charity_id).first()
    if row is None:
        return None
    reviews = tuple(row.reviews.order_by("-created", "-id"))
    haskamas = tuple(row.haskamas.order_by("-updated", "-id"))
    members = accounts.usernames(
        [review.author_id for review in reviews] + [haskama.rabbi_user_id for haskama in haskamas]
    )
    rabbis = accounts.rabbi_identities(haskama.rabbi_user_id for haskama in haskamas)
```

The second half builds the object. Note the two fallbacks, both about accounts that no longer exist:

```python
reviews = (
    tuple(
        ReviewEntry(
            # A deleted account leaves the review; it is shown as anonymous.
            author=members.get(review.author_id, "A member"),
            rating=review.rating,
            body=review.body,
            created=review.created,
        )
        for review in reviews
    ),
)
```

and, for a rabbi who never filled in a profile, "A rabbi". Neither is a crash and neither is a blank
line: a review with no name is still a review. The consequence to notice is that the page fetches
names in **two** queries rather than one join, which is the price of the app boundary — charities may
not join to accounts' user table.

**The safe link target.** Before counting a click, the address is checked:

```python
def link_url(self, charity_id: int, link_id: int) -> str | None:
    """The target of one of a charity's links, only if it is an http(s) URL.

    A link row written outside the form path could hold any scheme, so the
    redirect view asks for a safe target rather than trusting `URLField`.
    """
    url = (
        Link.objects.filter(charity_id=charity_id, pk=link_id).values_list("url", flat=True).first()
    )
    if url is None or urlsplit(url).scheme.lower() not in ("http", "https"):
        return None
    return url
```

`Link.url` is a `URLField`, which validates on the form path only. A row written by a fixture, a
management command or a future API is unvalidated text, and text becomes a link that a browser
executes if its scheme is `javascript:`. So the read edge asks for a *safe* target, exactly as the
image read edge in PR #18 asks for a *trusted* image. The saved test for this is the blunt one
(`test_a_link_with_an_unsafe_scheme_is_not_followed`: `javascript:alert(1)` → 404, and no event
written).

**The rabbi list.** The filter group that used to say "not available yet" now has options:

```python
    def rabbis(self) -> tuple[RabbiOption, ...]:
        """The rabbis the Haskamos group offers (§6.2.4, D-045).

        A rabbi's public identity lives in accounts (§6.1), so this asks its
        service rather than reading RABBI_PROFILE. The ids are user ids, which
        is what HASKAMA stores and the filter compares (audit Q3).
        """
        return tuple(
            RabbiOption(id=rabbi.user_id, display_name=rabbi.display_name, title=rabbi.title)
            for rabbi in accounts.search_rabbis()
        )
```

The parenthesis about ids is the whole bug that audit Q3 found: a rabbi has two ids (one in the user
table, one in the rabbi-profile table) and the filter compares *user* ids, because that is what an
endorsement row stores. Getting this wrong would produce a filter that matches nothing and looks fine.

### 8.3 `apps/charities/services.py` — two names for the views (+17)

The views never reach for a repository class directly for these two jobs; they call a service
function, which is the app's own front door.

```python
def get_charity_page(repository: CharityRepository, charity_id: int) -> CharityPage | None:
    """One charity in full, or None when no row has that id."""
    return repository.detail(charity_id)


def get_link_url(repository: CharityRepository, charity_id: int, link_id: int) -> str | None:
    """The safe target of one of a charity's links, or None."""
    return repository.link_url(charity_id, link_id)
```

The name `get_charity_page` is the design's own name for it (§6.2.7), kept deliberately so the code and
the document can be read side by side. The repository is passed in rather than constructed here, which
is why the tests can substitute a fake one.

### 8.4 `apps/charities/urls.py` — two new addresses (+3)

```python
# §6.2.7: the charity page is /charity/<id>/, settled as D-057.
(path("<int:charity_id>/", views.detail, name="detail"),)
(path("<int:charity_id>/link/<int:link_id>/", views.link_redirect, name="link"),)
```

The second one exists only to count clicks (6.D2). Neither address is written by hand anywhere else in
the codebase — every template builds them from these names, which is what made the URL change in PR
#21 (later in this stack) a small change.

### 8.5 `apps/charities/views.py` — the page and the counter (+43, −2)

**The page.** Read, or 404; then record the visit; then render.

```python
def detail(request: HttpRequest, charity_id: int) -> HttpResponse:
    """§6.2.7's charity page: everything known about one charity.

    The visit is recorded as a `view` EVENT (§5.2.21's visit count, §6.2.7's
    "writes events"), which is what makes the listing's popular and trending
    orders read real traffic instead of only seeded rows (audit M4).
    """
    charity = get_charity_page(
        # published_only stays False until the approval queue publishes
        # charities, for the same reason as the listing (D-042).
        DjangoCharityRepository(published_only=False),
        charity_id,
    )
    if charity is None:
        raise Http404("No charity with that id")
    _count_visit(charity_id, "view", user_id=_actor_id(request))
    return render(request, "charities/detail.html", {"charity": charity})
```

Three things a reviewer should note, in order of how much they matter:

1. The visit is recorded **after** the charity is confirmed to exist, so a made-up id does not fill the
   events table. (The redirect route does the same, and has a test for it:
   `test_a_stray_redirect_request_records_no_event`.)
2. `published_only=False` is the same compromise the listing already carries (D-042): until the
   approval queue publishes charities, hiding an unpublished one would make half the seeded data
   unreachable. The comment says so rather than leaving a future reader to guess.
3. The write goes through `_count_visit`, which cannot fail the page (5.1 — this started as an
   unguarded call and was fixed on this branch).

**Who gets the credit.** A visitor has no user id, and the design allows events with no user (§5.2.21
makes `user_id` nullable):

```python
def _actor_id(request: HttpRequest) -> int | None:
    """The signed-in user's id, or None for a visitor (§5.2.17 allows both)."""
    return request.user.id if request.user.is_authenticated else None
```

**The counter.** Find the link, refuse it if it is not a web address, write the click, send the visitor
on:

```python
def link_redirect(request: HttpRequest, charity_id: int, link_id: int) -> HttpResponse:
    """Count a click on a charity's outbound link, then send the visitor there.

    §5.2.21 derives "link clicks" from EVENT, and §6.2.7 says the charity page
    writes events; without this, a click on a donate link is invisible (audit M4).
    """
    url = get_link_url(DjangoCharityRepository(published_only=False), charity_id, link_id)
    if url is None:
        raise Http404("No such link")
    _count_visit(charity_id, "link_click", link_id=link_id, user_id=_actor_id(request))
    return HttpResponseRedirect(url)
```

The order is deliberate: the click is written **before** the redirect is returned, so a browser that
closes the tab mid-redirect still leaves the row. A refused write is logged and the redirect happens
anyway (5.1) — losing a count is cheaper than losing the visitor.

One consequence nobody should be surprised by later: **bots and refreshes count.** A reload is a
visit; a crawler is a visit. The design asks for exactly this ("On loading, it calls `record_event` to
record that it was visited") and picks no dedupe window. If the popularity numbers ever look inflated,
this is where the inflation enters, and the fix (a session-scoped dedupe or a bot filter) is a decision
nobody has made yet.

### 8.6 `apps/charities/templates/charities/detail.html` — the page itself (+128)

Four sections in the order the design names them, plus a header and a footer. The whole template is
readable as English; three details carry the thinking.

**The image is the stored value, turned into a `src` by the same filter the cards use:**

```html
      {% with image=charity.image|image_src %}
        {% if image %}
          <img class="charity-page__image" src="{{ image }}" alt="" width="160" height="160">
        {% else %}
          <span class="charity-page__image charity-page__image--empty" aria-hidden="true"></span>
        {% endif %}
      {% endwith %}
```

`alt=""` is correct here and is not an oversight: the image is beside the charity's name, so a screen
reader that read the image too would say the name twice. The empty-state span is `aria-hidden` for the
same reason — a decorative placeholder is not information.

**Each outbound link points at the counter, not at the charity:**

```html
                <a class="charity-page__link" href="{% url 'charities:link' charity.id link.id %}" rel="noopener">
                  {{ link.label }}: {{ link.url }}
                </a>
```

`rel="noopener"` stops the destination page from reaching back into this one through the browser. The
label comes from the repository (`Donate`, `About`, `Contact` — §5.2.14's three kinds, in the words the
design uses), and the address is shown next to it, so a visitor can see where they are going before
they click.

**Each endorsement states its verdict in words, not only in styling:**

```html
                <span class="haskama__verdict{% if not haskama.approving %} haskama__verdict--no{% endif %}">
                  {% if haskama.approving %}Approves{% else %}Does not approve{% endif %}
                </span>
                {% if haskama.importance %}
                  <span class="haskama__importance">Importance {{ haskama.importance }}/10</span>
                {% endif %}
```

The class changes the colour; the text says the same thing. A colour-blind reader, a screen-reader
user and a printed page all get the verdict.

The footer repeats the design's "when the page was last updated" as **"Last changed"**, and adds the
event count and the count of approving endorsements — the same activity summary the card shows
(D-044), so the two cannot disagree.

### 8.7 `apps/charities/templates/charities/listing.html` — the card finally goes somewhere (+1, −2)

This is the two-line change the whole PR is really about, seen from the visitor's side:

```html
-              {# TODO(comtai): point at the charity page once that bullet exists. #}
-              <a class="charity-card" href="#">
+              <a class="charity-card" href="{% url 'charities:detail' charity.id %}">
```

The `TODO` marker is gone with it — the work it described is done, which is what a source marker is
for. The test that pins it is a plain string search:
`assert f'href="/charity/{populated_charity.id}/"' in body` (`test_the_listing_card_links_to_the_charity_page`).

### 8.8 `apps/events/services.py` — a hidden event stops counting (+13, −4)

Two query methods, two added conditions, and — more importantly — a docstring that says what hiding
means:

```python
    are all activity. An event the member hid from their own history does not
    count (D-057): hiding it is a statement that it should not be remembered,
    not a separate flag the totals may ignore. A charity with no events has no
    row to aggregate, so the expression coalesces to 0 rather than NULL: "no
    events" is zero activity,
```

and in the queries themselves:

```python
-Event.objects.filter(charity=charity_ref)
+Event.objects.filter(charity=charity_ref, hidden_by_user=False)
```

```python
-        Subquery(
-            Event.objects.filter(charity=charity_ref, created__gte=month_ago)
+        Subquery(
+            Event.objects.filter(charity=charity_ref, created__gte=month_ago, hidden_by_user=False)
```

There is a quiet correctness point in the second one: the comment above it explains that the week and
month windows do not overlap, so an event from this week is not counted twice (D-050). Adding a
condition to a weighting expression is exactly the kind of edit that can double-count; this one cannot,
because it narrows rows without touching the weights.

### 8.9 `apps/accounts/services.py` — three small ways to ask about people (+80, −1)

Accounts had an empty front door: a docstring promising a public interface, and nothing behind it. The
charity page needed three things from it, and the filter needed a fourth.

```python
def search_rabbis(term: str = "") -> tuple[RabbiIdentity, ...]:
    """Every rabbi's public identity, optionally narrowed by a typed term (§6.2.4).
    ...
    """
    profiles = RabbiProfile.objects.select_related("user").order_by("display_name", "user_id")
    if term.strip():
        needle = term.strip()
        profiles = profiles.filter(
            Q(display_name__icontains=needle) | Q(user__username__icontains=needle)
        )
```

```python
def rabbi_identities(user_ids) -> dict[int, RabbiIdentity]:
    """The identities of the given rabbis, keyed by user id.

    A user with no RABBI_PROFILE (a haskama whose author never completed the
    profile) is left out of the result; the caller decides what to show then
    rather than getting a made-up name.
    """
```

```python
def usernames(user_ids) -> dict[int, str]:
    """The account names of the given users, keyed by id, for showing authorship."""
```

Three judgement calls are visible in those docstrings, and each is the same instinct — *do not invent
data*:

- a rabbi with no profile is **left out** of the identity map rather than given a made-up name, so the
  caller decides what to show;
- `search_rabbis` returns **every** rabbi when the term is empty, because that is what the filter's
  checkbox list needs, and it takes a `term` it does not yet use from a template so a search box could
  be added later without a second function;
- the ids are **user** ids everywhere, said out loud in `RabbiIdentity`'s docstring, because that is
  what an endorsement stores (audit Q3).

`usernames` returns a dictionary rather than a list so the caller does not have to match rows to
reviews by position — the classic way to attach the wrong name to the wrong review.

### 8.10 `apps/charities/filters.py` — one placeholder note deleted (+2, −6)

The sidebar used to say, under the rabbi group, "Rabbi search is not available yet." That sentence was
true, and it was a placeholder for exactly this PR:

```python
-EMPTY_NOTES: dict[str, str] = {
-    # D-045: the group is real but its options come from accounts, which has no
-    # rabbi search yet. Saying so beats an empty box that looks broken.
-    "haskama_rabbi": "Rabbi search is not available yet.",
-}
+# No group has special text today: the rabbi list now comes from
+# accounts.services.search_rabbis (D-058), so an empty group is just empty.
+EMPTY_NOTES: dict[str, str] = {}
```

The mechanism is kept (the dictionary and the code that reads it) rather than deleted, and the comment
says why it is now empty. A reader who later finds an empty group with no explanation has this comment
to tell them the silence is intentional.

### 8.11 `apps/support/context_processors.py` — the nav, built from the route table (+71)

The new file the second commit is really about. The list is declared once, by route name:

```python
NAV_DESTINATIONS: tuple[tuple[str, str], ...] = (
    ("charities:listing", "Charities"),
    ("charities:add", "Request a charity"),
    ("support:report", "Report a charity"),
    ("tools:index", "Maaser tools"),
    ("dashboards:dashboard", "Dashboard"),
    ("support:help", "Help"),
)
```

and turned into addresses at render time, one at a time, skipping any that do not exist:

```python
def _url_of(name: str) -> str | None:
    """The path of a URL pattern, or None while that page does not exist."""
    try:
        return reverse(name)
    except NoReverseMatch:
        return None


def nav(request) -> dict:
    """The nav's destinations for this request.

    A page that has not shipped yet contributes no link at all, rather than a
    link to a 404. The bar is then short, which is honest: the alternative was
    eight destinations and seven dead ends.
    """
    destinations = [
        NavDestination(label=label, url=url)
        for name, label in NAV_DESTINATIONS
        if (url := _url_of(name)) is not None
    ]
```

Two reasons this lives in `support`, stated in the module docstring: the nav belongs to no single app,
and §6.1 lets support depend on nothing — while `reverse()` needs no dependency at all. It is also the
one app every page already has, since the nav is on every page.

The same function supplies the session-dependent links, which is why the template no longer decides
whether "Log in" or "Log out" is available:

```python
    return {
        "nav": {
            "destinations": destinations,
            "login_url": _url_of(LOGIN_URL_NAME),
            "signup_url": _url_of(SIGNUP_URL_NAME),
            "logout_url": _url_of(LOGOUT_URL_NAME),
        }
    }
```

**Be aware of one consequence:** the accounts pages do not exist yet in this PR, so today the bar
genuinely shows one link ("Charities") and no "Log in". As PRs land, entries appear. If you want the
login page to exist before the bar is useful, that is a question about PR order, not about this code.

### 8.12 `templates/base.html` — nav, skip link, main region (+30, −25)

Hand-written addresses out; loops over the resolved destinations in:

```html
-  <nav class="nav">
+  <nav class="nav" aria-label="Main">
     <ul class="nav__list">
-      <li><a href="/charity/">Charities</a></li>
-      <li><a href="/charity/add/">Request a charity</a></li>
-      ...
+      {% for destination in nav.destinations %}
+        <li><a href="{{ destination.url }}">{{ destination.label }}</a></li>
+      {% endfor %}
```

and the two accessibility additions at the top of the body and around the content:

```html
+  <a class="skip-link" href="#main">Skip to content</a>
...
-  <main>
+  <main id="main" tabindex="-1">
```

`tabindex="-1"` is what makes the skip link actually work: without it, focus moves to the region but
the browser does not let the keyboard continue from there.

**One change in this file is not mentioned by either decision entry, and you should know about it.**
The old body tag carried the CSRF token in an attribute for the page's interactive library:

```html
-<body hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'>
+<body>
```

That token existed so future HTMX requests could post without a hidden form field. No `hx-` attribute
exists anywhere in the templates today (`git grep hx-` over `templates/` and `apps/` returns nothing),
so removing it changes no behaviour now. But when the first HTMX form lands, it will need a CSRF
source — either a hidden input (which the nav's log-out form already uses) or a meta tag. Dropping the
attribute without a note is the kind of quiet removal that costs an hour later. It is also, arguably,
the fix audit finding SEC2 asked for (a token sitting in an attribute readable by any script on the
page); either way, it deserves a sentence in the PR body or a decision entry.

Also visible: the file now ends without a trailing newline. Harmless, trivially fixed, mentioned
because a reviewer diffing this file will see it and wonder.

### 8.13 `templates/403.html`, `404.html`, `500.html` — the error pages (+34)

Three short templates that extend the site's own base, so an error looks like the site:

```html
{% extends "base.html" %}

{% block title %}Page not found &middot; MaaserMart{% endblock %}

{% block content %}
  <div class="error-page">
    <h1>Page not found</h1>
    <p>The address you used does not match any page. It may have been moved, or the link may be out of date.</p>
    <p><a href="{% url 'charities:listing' %}">Back to the charity listing</a></p>
  </div>
{% endblock %}
```

The 500 page carries the important constraint in a comment:

```html
  {# D-035: nothing here may depend on context that can fail; this is only text. #}
```

That is the rule for an error page and it is easy to break: a 500 page that reads a value from the
request, or calls a service, or uses the nav processor against a broken database, produces a second
error on top of the first. This one is text and one hard-built address. (It still extends `base.html`,
which runs the nav processor — worth a thought if a 500 is ever caused by the database itself.)

Django serves all three automatically from these filenames; nothing needed registering, which is why
no settings change appears for them.

### 8.14 `config/settings/base.py` — one line to switch the nav on (+2)

```python
+                # The nav's links: only what a URL pattern actually resolves (B1).
+                "apps.support.context_processors.nav",
```

A context processor runs on every rendered template, so this line makes the nav available everywhere
at once. It is also the line that would have to be removed if the nav ever became more expensive than
a handful of `reverse()` calls.

### 8.15 `static/css/site.css` — styles for three new things (+168)

Nothing surprising: a page container, the header with the image beside the intro text, chip lists for
domains and locations, the link list, the endorsement and review lists, the error page block, and the
skip link (which is off-screen until it is focused):

```css
+.charity-page {
+  margin: 0 auto;
+  max-width: 56rem;
+  padding: 2.5rem 1.5rem 4rem;
+}
```

`max-width: 56rem` with `margin: 0 auto` is the same reading-width device the listing uses, so the two
pages line up. The skip link's job is done by the CSS: visible only when tabbed to, which is why the
template can put it first in the document without it appearing to everyone.

### 8.16 `docs/DECISIONS.md` — D-057 and D-058 (+25, −2)

Two entries, in the file's standard shape (date, decider, status, design-doc reference, decision, why,
where in code).

**D-057** is the interesting one, because it is three decisions in one entry, and they are the three
things that could not be settled by writing code carefully:

> the page is `/charity/<id>/` … it also has a counted outbound-link route … the page records a `view`
> EVENT for every visit, attributed to the signed-in user or `NULL` for a visitor … an EVENT the member
> hid from their own history counts for nothing.

**D-058** closes an open question that had been sitting in the file since 2026-11-13 ("Can users pick a
rabbi in the listing filter yet?") by making the thing it was waiting for exist. The open-question line
is edited to point at D-058 rather than deleted, so the trail stays.

### 8.17 The audit document, untouched

`docs/AUDIT-2026-11-17.md` is not in this PR's diff. The findings it names (M3, M4, M6, M9, DOC3, A1,
B1, S4, A3, Q3) are addressed in code and recorded in D-057/D-058, and the document's own dispositions
are updated in PR #20. Worth knowing so you do not go looking for them here.

---

## 9. The tests

Read the names as sentences. Together they are this PR's summary.

**The page shows what the document says it shows** (`tests/unit/test_charity_page.py`). One fixture
builds a charity with everything a charity can have — tagline, description, image, a domain, a
location, two outbound links, a review with an author, an endorsement from a rabbi with a profile — and
then one test asks for the page and checks each thing appears:

```python
def test_the_page_shows_everything_the_doc_names(client, populated_charity):
    response = client.get(reverse("charities:detail", args=[populated_charity.id]))

    body = response.content.decode()
    for text in [
        "Keren L'Dugma",
        "Interest-free loans.",
        "A gemach lending at no interest",
        "Free loans",
        "Lakewood, NJ, USA",  # a location's full identity (D-045)
        "https://keren.example.org/donate",
```

This is a "walk the list from the design document" test, and it is the right shape here: the document
names nine things, so the test names nine strings. A page that renders beautifully and drops the
description fails it.

**The events the design promises** — four tests, one per promise:

- `test_a_visit_is_recorded_as_a_view_event` — a visit writes a `view` with no user attached;
- `test_a_signed_in_visit_is_attributed` — the same, with the member's id;
- `test_clicking_a_link_counts_it_and_sends_the_visitor_on` — the click writes a `link_click` and the
  visitor is sent to the real address (`assert response["Location"] == link.url`);
- `test_a_link_with_an_unsafe_scheme_is_not_followed` — `javascript:alert(1)` gives a 404 **and writes
  no event**, the pair of assertions that makes the safety real rather than cosmetic.

Plus two refusals: `test_an_unknown_charity_is_a_real_404` and `test_a_stray_redirect_request_records_no_event`
(guessing at a link id fills nothing in the events table).

**And two tests for the version of the promise that only appears when things go wrong**
(`test_a_refused_visit_write_still_shows_the_charity`,
`test_a_refused_click_write_still_sends_the_visitor_on`). Both make the write fail deliberately, then
assert the visitor still gets what they came for — the page with the charity's name in it, or the
redirect to the charity's own site. They exist because §6.2.7 says *"Failed writes do not fail the
page"*, and a rule like that is only real if something breaks on purpose and the page survives.

**The card points at the page** — `test_the_listing_card_links_to_the_charity_page`, a string search for
`href="/charity/<id>/"` in the listing's HTML. The two-line template change has a test, which is more
than most two-line changes get.

**The rabbi group works** (`RabbiOptionsTest`, three tests):

- `test_the_filter_offers_every_rabbi_with_a_profile` — and asserts `option.id == rabbi.id` with the
  comment *"the *user* id, not the profile's (Q3)"*, which pins the id bug shut;
- `test_a_rabbi_without_a_profile_is_not_offered` — no invented names;
- `test_the_filters_s_feature_a_rabbi_who_can_endorse` — the end-to-end proof: filter by the rabbi,
  get the charity that rabbi endorsed. This one matters most, because it is the test that would have
  failed for months while the group sat empty.

**The nav promises nothing that 404s** (`tests/integration/test_base_template.py`). The best test in
the PR, because it is written to keep being true:

```python
def test_every_nav_link_answers(client):
    """The nav promises nothing that 404s (audit B1): each nav href must resolve."""
    html = client.get("/charity/").content.decode()
    nav = html[html.index('class="nav"') :]
    nav = nav[: nav.index("</nav>")]
    hrefs = re.findall(r'href="(/[^"]+)"', nav)

    assert hrefs  # the nav is not empty
    for path in hrefs:
        response = client.get(path)
        assert response.status_code in (200, 302), path
```

It scrapes the rendered nav and visits every link, so a nav entry added for a page that does not exist
fails the suite — without anyone having to remember this rule. The counterpart asserts the honest
silence:

```python
    # A route with no pattern yet is not advertised at all (B1).
    assert 'href="/tools/"' not in html
    assert 'href="/accounts/login/"' not in html
```

**Accessibility, tested as three facts** rather than asserted in prose:
`test_the_skip_link_is_the_first_thing_for_a_keyboard_user` (the skip link appears before the nav in
source order *and* `id="main"` exists), `test_the_main_nav_has_a_landmark_label`
(`aria-label="Main"`), and `test_a_404_serves_the_friendly_template` (an unknown address renders the
words "Page not found").

**Hidden events count for nothing** (`HiddenEventTest`, two tests in `tests/unit/test_repositories.py`):
one asserts the activity count is 1 when two views exist and one is hidden; the other puts a visible
view and a hidden view on two charities and asserts the trending order puts the visible one first:

```python
        self.assertEqual([card.name for card in cards], ["Shown", "Hidden"])
```

A neat property of that assertion: it does not just check that the hidden event was ignored, it checks
the *order* the visitor would see, which is the only thing that actually matters for "trending".

**Nothing was weakened.** No test was deleted, no assertion loosened. The nav tests changed because the
nav changed (eight hand-written links became a resolved list), and `test_nav_is_pinned_to_the_top` and
`test_nav_is_a_full_width_bar_above_the_content` still assert the same visual commitments as before.

---

## 10. The audit

The Dilbert test run against the finished document, and the two-layer check.

**Where he would have fallen off, and what was fixed:**

- **"404", "403", "500"** are numbers he would not know. They are a glossary row now, in the order a
  person meets them ("the address does not exist / you may not see it / the site failed"), and section
  4.5 says what changed for a visitor without using the numbers at all. — fixed.
- **"route" / "URL pattern"** were used in 4.5 before being defined. They are a glossary row, and 4.5
  leads with the plain sentence (*the nav is built from the site's own route table*), then names the
  mechanism. — fixed.
- **"event"** is the word most likely to be misread as "a party". Defined in the glossary as "a recorded
  line saying something happened to a charity", and section 4.2 spends a whole subsection on why those
  lines are the popularity counts. — checked at four places.
- **"280/302/`Location` header"** — the redirect is explained in section 4.3 as *"sends the visitor on
  without them noticing"*, and the test's `assert response["Location"] == link.url` is described in
  words in section 9 before it is shown. — checked.
- **"the customer's document says X"** appears in sections 5 and 6 with the exact quoted line above each
  disagreement, so he can see what the disagreement *is about* without holding the docx open. — checked
  at all six departure entries and all four contradictions.
- **One long sentence** in 4.2 about what the orderings counted was split in two. — fixed.

**Every code box has an English sentence directly above it.** Walked: the model contract, the
repository's `detail`, the review fallback, `link_url`, `rabbis`, the two service functions, the two
URLs, the detail view, `_actor_id`, the redirect view, the four template excerpts, the two listing
lines, the two hidden-event conditions, `search_rabbis`, `rabbi_identities`, `usernames`, the
`EMPTY_NOTES` deletion, `NAV_DESTINATIONS`, `_url_of`/`nav`, the nav's return value, the base-template
before/after, the CSRF attribute removal, the 404 template, the 500 comment, the settings line, one CSS
rule, the D-057 quote, and six quoted tests. All covered.

**The two-layer check.**

- *Delete every code box.* The document still contains: the promise-keeping opening; the glossary; the
  story of a window display with an empty shop behind it, of popularity that measured invented traffic,
  of a nav of seven dead ends; four contradictions with the document quoted; six departures with
  judgements and reversal costs; a reading order; a plain-English account of all seventeen files; and
  the tests read as sentences. It stands.
- *Read only the code boxes.* The whole change is visible: the page's shape, the single query that fills
  it, the safe-target check, the rabbi list, both routes, both views, the page's four sections, the
  card's new href, the two added event filters, the three accounts services, the nav processor, the
  base template's nav and skip link, the three error pages, the setting, and the tests. A reviewer could
  approve from the boxes alone. It stands.

**Where he still cannot follow, and why that is acceptable:** the `_annotated`/`_with_activity_values`
line in `detail`. "The same annotations the listing uses" is as plain as that gets without a diagram of
the query; the consequence (*the page and the card cannot disagree*) is stated in the sentence above the
box, and that is what he needs. The engineer gets the exact call.

**Bottom line:** the document can be reviewed from, and it explains itself. It does not grade. The
judgement calls it hands back to you are: the CSRF attribute that disappeared from `<body>` without a
decision entry (8.12), the wording rule in §7.4 that nothing on the site has adopted (6.D6), and whether
a short nav is acceptable today (6.D3). The one contradiction that was a genuine defect — the unguarded
`record_event` (5.1) — is fixed on this branch.
