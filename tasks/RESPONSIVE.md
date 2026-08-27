# Responsive pass — worker spec (Fable)

His instruction, 2026-08-27, from an iOS screenshot and a very narrow desktop
window. Make the publications page work at small widths **without
compromising the large-window view**. That constraint is the whole point: if
a change alters the desktop layout, it is out of scope.

Everything here lives behind `max-width` media queries, or is a font-size
adjustment applied deliberately at each tier. Do not touch the desktop grid,
the facet logic, or any data path.

## The bug to fix first (all widths)

In the screenshot the **"Cited and Used by" panel overlaps the impact
category text** — "cited by 1195 papers and 620 re…" and "179 repo…" are
covered by the panel drawn on top of them. That is not narrow-window
crowding; it is an overlap in the impact-tools row that should be fixed at
every width. Find it before doing anything cosmetic.

## Progressive disclosure of labels

His example: `Builds on it (46, cited by 153 papers and 199 repos)` carries
detail that stops being worth its width. Degrade it in tiers rather than
letting it wrap or clip:

| Width | Impact category label |
|---|---|
| ≥ 1100px | `Builds on it (46, cited by 153 papers and 199 repos)` — unchanged |
| 700–1099px | `Builds on it (46)` |
| < 700px | `Builds on it` — count right-aligned as a small badge if it fits |

Apply the same principle to the other facet lists: the parenthetical count
survives longer than the prose, and the prose goes first.

Implementation note that matters: render the parts as separate spans
(`.facet-label`, `.facet-count`, `.facet-detail`) and hide by class in CSS.
**Do not rebuild the label string in JS per breakpoint** — that puts layout
knowledge in the data layer and will drift. The full text stays available to
screen readers and as a `title` tooltip at every width.

## Font sizes

Smaller inside the selection boxes, as he asked:

- facet list rows: 13px at desktop, 12px below 700px
- facet column headers and counts: 12px / 11px
- impact category rows: same treatment as facet rows
- the publication list itself: leave alone. It is the content, and it is
  already right.

**One hard exception: any `<input>` or `<select>` must stay at 16px or
larger.** iOS Safari auto-zooms the whole page when a smaller field takes
focus, which is far more disruptive than the space the larger text costs.
That applies to the title search box and the two "Filter names…" fields.

## Layout at small widths

1. **Results first.** Below 700px the whole first screen is controls and no
   paper is visible without scrolling. Collapse Filters into a single button
   showing the active-filter count; open the page on the publication list.
2. **Stack the facets.** Four side-by-side columns at ~90px each is what
   produces "2." and "Approximate …". Below 700px: one full-width accordion
   per facet, closed by default.
3. **Years as wrapping chips** rather than a scrolling checkbox column —
   they are four characters each and there are 35 of them.
4. **Touch targets ≥ 44px.** Make the entire row tappable, not just the
   checkbox.
5. **Header image `max-width: 100%`** — the logo is clipped on the right.
6. **Sticky result count** at the top of the list, so filtering gives
   feedback without scrolling back up.

## Gate

- Both UI harnesses stay green at desktop width — that is the proof the large
  view is uncompromised.
- Add a narrow-viewport pass to `tests/ui/random_settings_test.py`: run a
  sample of the settings at 390×844 (iPhone) and 768×1024, asserting no
  horizontal scroll on `body`, no element overlapping another, and every
  facet reachable.
- Screenshot both widths before and after for his review.

Report in `docs/LANES.md`, and say plainly whether the desktop view is
byte-identical in rendering or whether anything moved.
