# Responsive pass — worker spec (Fable), v2

His instruction, 2026-08-27, from an iOS screenshot and a very narrow desktop
window: make the publications page work at small widths **without
compromising the large-window view**. He then asked that this be informed by
current practice rather than invented, so v2 is rewritten against the guides
listed at the bottom. Three things changed from v1 and are called out inline.

## The bug to fix first (all widths)

In his screenshot the **"Cited and Used by" panel overlaps the impact
category text** — "cited by 1195 papers and 620 re…" and "179 repo…" are
covered by the panel drawn on top of them. That is not narrow-window
crowding; it is an overlap in the impact-tools row, and it should be fixed at
every width before any cosmetic work.

## CHANGE 1 — container queries, not viewport breakpoints, for the facets

v1 specified viewport media queries throughout. That is the wrong tool for
this page. The facet columns are narrow *even on a wide desktop* — that is
exactly how "Approximate …" and "2." got clipped in a maximised window. A
viewport query cannot see that; a container query can, because the component
asks how much room **it** has rather than how wide the window is.

Current practice splits the two cleanly: media queries for page-level
structure (does the filter panel sit beside the results or collapse into a
drawer), container queries for component-level decisions (how a facet row
renders in the space it was given). They are complementary, not competing.

So:

- `container-type: inline-size` on each facet column and on the impact
  categories box, each with a `container-name` so nested queries cannot
  collide.
- The label tiers below become `@container` queries against that column's
  width, not `@media` queries against the viewport.
- Pick the tier widths by **where the content actually breaks** — resize
  until the label clips, use that number — not by device-shaped constants
  like 768px.

## Progressive disclosure of labels

His example: `Builds on it (46, cited by 153 papers and 199 repos)` carries
detail that stops earning its width. Degrade in tiers:

| Container width | Label |
|---|---|
| roomy | `Builds on it (46, cited by 153 papers and 199 repos)` |
| medium | `Builds on it (46)` |
| tight | `Builds on it` with the count right-aligned as a badge |

**The prose goes first; the count survives longest.** That ordering is
deliberate and the guides are firm on it: per-option counts are what stop a
user stacking filters into a zero-result dead end. Dropping the count to save
space trades a real usability property for a cosmetic one.

Implementation: render the parts as separate spans (`.facet-label`,
`.facet-count`, `.facet-detail`) and hide by class in CSS. **Do not rebuild
the label string in JS per breakpoint** — that puts layout knowledge in the
data layer and will drift. Full text stays available as a `title` and to
assistive tech at every width.

## Fluid type instead of fixed steps

He asked for smaller text, especially inside the selection boxes. Use
`clamp()` rather than two hard-coded sizes:

- facet rows and impact rows: `clamp(0.75rem, 0.7rem + 0.3vw, 0.875rem)`
- facet headers and counts: one step below that
- the publication list: leave alone — it is the content, and it is right

Two constraints on the clamp scale:

- The middle term must include a `rem` component, and the maximum must not
  exceed about 2.5× the minimum, or the text fails WCAG 1.4.4 under zoom.
- **Any `<input>` or `<select>` stays at 16px or larger.** iOS Safari
  auto-zooms the page when a smaller field takes focus, which is far more
  disruptive than the space saved. Applies to the title search box and both
  "Filter names…" fields.

## CHANGE 2 — a filter drawer with deferred apply, on small screens

v1 said "collapse Filters into a button". The guides are more specific about
what happens next, and it matters here: on touch, **instant-apply feels laggy
and misfires**, because the target is large and imprecise and the user queues
taps faster than the page can respond. This page recomputes a lot per change,
so it would feel worse than most.

Below the page-level breakpoint:

- A single, always-visible **Filters** button showing the active-filter
  count; it opens a drawer over the results.
- Inside the drawer, one collapsible section per facet, closed by default,
  ordered with the facets he actually uses first — Years, Topics, Type — and
  the long tail below. Do not expose everything at once.
- A pinned bottom button reading **"Show 42 results"**, updating live as
  selections change, so the cost of a selection is visible before committing.
  Selections apply on tap, not per checkbox.
- Active filters shown as removable chips above the results, so a user can
  see why the list is short without reopening the drawer.
- Size the drawer with `svh`, not `vh` or `dvh`: `100vh` overflows behind
  iOS browser chrome, and `dvh` can reflow mid-scroll.

On desktop nothing changes: the filter panel stays inline and instant-apply
stays.

## CHANGE 3 — intrinsic layout, so most breakpoints disappear

The facet row should be
`grid-template-columns: repeat(auto-fill, minmax(220px, 1fr))`. That collapses
four columns to two to one on its own, with no media query at all, and it
fixes the ~90px squeeze at any window size rather than only below a chosen
threshold. Reserve explicit breakpoints for the drawer decision, which
genuinely cannot be expressed intrinsically.

## The rest

- **Touch targets ≥ 44px**: the entire facet row tappable, not just the box.
- **Header image**: `max-width: 100%` — the logo is clipped on the right.
  Add `srcset` with a `sizes` attribute; without `sizes` the browser assumes
  full-width and fetches the desktop file for a phone.
- **Sticky result count** above the list, in an `aria-live="polite"` region,
  so filtering announces "125 results" to screen readers and gives everyone
  feedback without scrolling back up.
- Confirm the viewport meta tag is present and correct before anything else —
  most responsive bugs start there.

## Gate

- Both UI harnesses green at desktop width. That is the proof the large view
  is uncompromised, and it is not optional.
- Add a narrow-viewport pass to `tests/ui/random_settings_test.py`: a sample
  of settings at 390×844 and 768×1024, asserting no horizontal scroll on
  `body`, no overlapping elements, every facet reachable, and the deferred
  apply button reflecting the same count the list then shows.
- Screenshots at both widths, before and after, for his review.

Report in `docs/LANES.md`, and state plainly whether the desktop rendering is
unchanged or whether anything moved.

## Sources read

- scrimba.com/articles/responsive-web-design-a-complete-guide-2026-2 — the
  four-tool split (media queries for structure, container queries for
  components, clamp for type, intrinsic grid), plus the svh/dvh and WCAG
  clamp constraints.
- cssawwwards.com/blog/css-media-queries-guide-2026 — media vs container
  query division of labour; only add breakpoints where content breaks.
- dev.to/nickbenksim/the-ultimate-guide-to-css-container-queries-in-2026 —
  named containers, breakpoints from the component not the device.
- baymard.com/learn/ecommerce-filter-ui — explicit apply button on mobile.
- witscode.com/blogs/shopify-collection-filtering — why instant-apply misfires
  on touch; the live result count on the apply button.
- btng.studio + pencilandpaper.io — per-option counts prevent zero-result
  dead ends; expandable sections over exposing everything.
