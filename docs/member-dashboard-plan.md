# Member dashboard, history, recommendations and reviews

This plan follows the design document sections 6.2.7–6.2.11 and the project decisions in `DECISIONS.md`. The member dashboard is `/dashboard/` as requested. Every account is a member under D-YOSEF-accounts-login; the account can also have other roles.

## Implementation plan

1. Reuse the existing `EVENT` and `REVIEW` tables and their constraints. No migration is needed. Continue recording views and outgoing clicks on charity pages; attribute signed-in activity to that user.
2. Expose activity through the events service. Show only the signed-in member's visible view and link-click events, newest first, with the charity and timestamp. Hide one or clear all with CSRF-protected POSTs that set the existing hidden flag; never accept another user's activity ID.
3. Build `/dashboard/` with history and recommendations side by side on wide screens, stacked on small screens. Show empty states and the existing maaser balance. Avoid caching the private page.
4. Compute recommendations from the member's events through events and charities service interfaces. Count all view/click events in the denominator, including hidden ones, while hidden events contribute no charity weight. Apply the three design tiers in order, deduplicate, alphabetize within tiers, exclude non-published and previously rejected charities, and persist a reject event when a member removes an offered recommendation. Thresholds are provisional and configurable: minimum history 3, x 0.2, y 0.1 and z 0.2. No result limit is imposed until the unspecified number is agreed.
5. Allow authenticated members to submit or edit one review per charity from its public page. Require an integer rating 1–5, allow optional text, and use the existing unique constraint. Keep existing public review display and derived averages.
6. Integrate existing-user login and logout so the member pages are reachable; preserve the existing lockout, rate limiting and safe-redirect code. Signup remains a separate unfinished feature on main.
7. Verify privacy and ownership, POST/CSRF handling, input validation, recommendation tiers and hidden-event math, empty states, integration with existing pages, lint, migrations and the full PostgreSQL test suite.

## Dependencies and follow-up

The listing deliberately shows unpublished charities until the approval workflow can publish them (D-042), but recommendations use published charities only as the design requires. Until charities are published, recommendations can be empty even when the listing contains charities. The recommendation thresholds and a result limit need product tuning. The current project has no signup flow on main; an existing account is needed to log in.
