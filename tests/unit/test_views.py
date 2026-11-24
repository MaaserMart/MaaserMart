"""Black-box page contracts for the listing (design doc §6.2.x).

Five page features used to live in this one 752-line file (audit T3); they now
live next door:

- `test_views_listing.py` — the page, the page size and the pagination
- `test_views_sort.py` — ordering by name, rating, activity and recency
- `test_views_filter.py` — domains, locations, rabbis and the clear link
- `test_views_clamp.py` — out-of-range numbers are clamped visibly (D-046)
- `test_views_search.py` — the tracer-bullet search (D-050)
"""
