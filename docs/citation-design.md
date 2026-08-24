# The per-paper citation section — design

**Status: APPROVED and integrated** (human sign-off 2026-08-24, including
the three sort modes and header toggle). The view is live in
`publications.html` via `assets/js/citations.js` + the citation block in
`assets/css/style.css`; the prototype (`prototype/`, §8) is kept as a
reference implementation. The data contract lives in
`data/citations/SCHEMA.md`; the classify-corpus merge script emits it for
the whole corpus.

## 1. What this is

Raw citation counts treat a compiler built on Halide and a one-line list
mention as the same event. The publications page should not. This section
gives every paper an expandable citation view that says, with evidence
behind every row, *who* cites the paper and *what the citation does* —
builds on it, runs it, borrows its idea, measures against it, or waves at
it from a related-work list.

Requirements it honors, from the task:

- One integrated site; the publications page must not get slower.
- Per-paper citation data loads only when that paper's citation view opens.
- Displayed citation count = max(our verified count, the Google Scholar
  count from a human-supplied scrape).
- The section expands exactly like the existing per-paper summary.
- Top level: detailed vs passing. Drill-down: FUNCTION and CENTRALITY, with
  flags; COMMIT papers (citing works Saman Amarasinghe co-authored)
  reported apart from external impact.
- A routine "add new papers + citations" refresh every few months stays easy
  (§7).

## 2. What the reader sees

On the publications page, a paper with citation data grows one more action
in its meta line, next to Bib and Summary:

> Bib &nbsp; Slides &nbsp; **Citations (1,483) ▸** &nbsp; Summary ▸

The number is the displayed count: the larger of our verified count and
Google Scholar's. Clicking expands a panel inside the paper's box, the same
mechanic as the summary toggle. The panel shows, top to bottom:

1. **Headline.** "1,483 citations — 1,483 verified and analyzed below;
   Google Scholar reports 2,417." Both numbers appear when both exist; the
   reader never has to wonder which count they are looking at.
2. **The split bar.** One horizontal bar over the external citations, three
   segments: **detailed engagement** (the citing work engages this paper
   specifically), **passing mention** (this paper appears inside a
   multi-paper citation list), and **not yet analyzed** (no usable
   evidence). For Halide: 598 detailed, 416 passing, 429 not yet analyzed.
   A one-line note follows: "Counts above are external. 40 more citations
   are COMMIT papers (Saman Amarasinghe among the authors); they are
   listed separately at the bottom."
3. **A centrality filter.** "How central is this paper to the citing work?"
   — All / Core / Engaged / Peripheral buttons, with counts. *Core* means
   the citing work would be fundamentally different without this paper.
   Halide external: 78 core, 198 engaged, 738 peripheral.
4. **Sort modes** (approved ruling, 2026-08-24): **Impact** (default;
   codebook priority order), **Recency** (year, newest first), and
   **Popularity** (the citing work's own citation count — `cited_by` in the
   schema — highest first, with a "N cites" chip per row). With **headers
   on** (the default), all three modes render the same way: collapsible
   groups, collapsed by default, the count in each header — category
   groups under Impact, years under Recency, count buckets (1,000+ /
   100–999 / 10–99 / 1–9 / not yet cited / count unknown) under
   Popularity, all lazily rendered in one shared style. **Headers off**
   gives one flat sorted list. Impact keeps COMMIT papers in
   their separate section (the external-impact story); Recency and
   Popularity incorporate them into the main list, each row marked with a
   "COMMIT" chip.
5. **Function groups.** Under Impact with headers: collapsible groups in
   codebook priority order, each
   with a plain-language label, a count, and a one-clause gloss:
   - Builds on it (`extends`) — 35
   - Uses the system (`uses-tool`) — 77
   - Adopts the idea (`adopts-idea`) — 89
   - Uses its benchmarks, Measures against it, Positions against it,
     Surveys it, Cites a result as evidence, Names it as an example,
     Mentions it specifically, Cites it in a list — and, under All,
     "Not yet analyzed" and "COMMIT papers".
   Opening a group lists its citing works: linked title, authors, venue,
   year, a `core` chip where earned, and a "via a successor system" chip on
   lineage citations (papers that cite Halide as TVM's ancestor). Rows are
   built lazily, so opening the panel never renders 1,400 rows at once.
6. **Provenance footer.** "Classified with codebook v0.2 (2026-08-24);
   duplicates folded, self-citations by the paper itself excluded."

No chart library, no dependencies: the bar is three divs, the groups are
the site's existing toggle pattern.

### Sorting the paper list itself by citations

The page's **Group & sort** control gained a **Citations** option (2026-08-24
ruling). As the level-1 key it groups the paper list under the same
count-bucket headers the per-paper popularity sort uses (1,000+ / 100–999 /
10–99 / 1–9 / not yet cited), ranked descending inside each bucket, with a
final **No citation data** group for papers without a `data/citations` row.
With level 1 set to None and Citations at a lower level, the list is one
flat ranked run — no headers. The sorted figure is the displayed count,
`max(verified, gscholar)` from `index.json`. Year grouping stays the
default; Reset restores it.

## 3. Page structure and integration

Three pieces, all following existing conventions (`publications.js` style:
ES5, `createElement`, `track()`):

- **`assets/js/citations.js`** (graduated from `prototype/citations.js`,
  unchanged except the data path and header): `CITATIONS.loadIndex()`,
  `CITATIONS.attachToggle(metaEl, itemEl, key, indexRow)`, and the view
  renderer. Nothing else on the page needs to know how the view works.
- **`publications.js`**: two small changes. At startup, fetch
  `data/citations/index.json` alongside `publications.json` (`Promise.all`;
  if the index fails to load, the page renders exactly as today). In
  `renderItem()`, when `index.papers[bibtexKey]` exists, call
  `CITATIONS.attachToggle(...)` — one call, next to the existing summary
  toggle wiring.
- **`assets/css/style.css`**: append `prototype/citations.css` (all
  selectors namespaced `cite-`; the panel reuses `.pub-summary`'s
  open/closed mechanics).

A **Show citations** button beside the existing Show summaries button
expands the Citations panel on every paper at once (and collapses them all
when toggled off), with papers rendered after the toggle following suit.
Expanding all keeps lazy loading per paper: files fetch through a small
progressive queue (four in flight), so the page never blocks. The two
expand-alls are independent — the citation panels and toggles carry a
`cite-` class the summaries toggle deliberately excludes.

Analytics: the view fires `citations-view` on expand and
`citations-centrality-filter` on filter use, via the same `track()` no-op
wrapper the rest of the site uses.

## 4. Loading strategy

- **At page load**: one extra fetch, `data/citations/index.json` — one row
  per paper with data (`{verified, gscholar}`). At the full 327 papers this
  is ~20 KB. It is the only cost the publications page ever pays; papers
  absent from the index simply show no toggle.
- **On first expand**: fetch `data/citations/<bibtexKey>.json`, render,
  keep. Re-collapsing and re-expanding refetches nothing. The largest pilot
  file (Halide, 1,483 entries) is ~600 KB pretty-printed; it loads only on
  an explicit click, and the merge script can drop indentation (~35%
  smaller) if that ever matters.
- **Displayed count** is computed in JS as `max(verified, gscholar ?? 0)` —
  stored nowhere, so a Scholar refresh or a harvest run can never silently
  overwrite the other number.

## 5. The detailed/passing split (reviewable decision)

The v0.2 codebook defines the two residual FUNCTION values by sentence
shape: `detailed-citation` targets the paper specifically, `passing-citation`
is list membership only. The top-level split generalizes that same test to
all eleven values:

- **Detailed** = `extends`, `uses-tool`, `adopts-idea`, `uses-benchmark`,
  `baseline`, `positions`, `surveys`, `supports-claim`,
  `detailed-citation`. Each requires engagement with this paper in
  particular.
- **Passing** = `exemplifies` + `passing-citation`. `exemplifies` is
  "one member of a list of examples of a category", and the v0.2 amendment
  rules that a gloss shared by a whole list is not specific engagement — so
  it sits on the passing side, one notch above `passing-citation` in the
  drill-down but the same story at a glance.
- `unknown` and `unclassified` are **never** folded into either side; they
  render as "not yet analyzed". Honesty over a bigger bar.

The mapping ships precomputed in each entry's `split` field, so changing
this decision is a merge-script rerun, not a JS change.

## 6. Counts, dedup, COMMIT papers

- **Verified count** = deduped citing works, excluding records of the paper
  citing itself (`self-version`), *including* COMMIT papers —
  so it is comparable to Google Scholar's number. Dedup follows the human
  ruling: fold by normalized title, keep the highest-evidence sibling
  (rule details in `data/citations/SCHEMA.md`).
- **COMMIT-papers separation**: a citing work is a COMMIT paper iff Saman
  Amarasinghe is among its authors (the `commit` field; exact name rule in
  SCHEMA.md — deliberately narrower than the classifier's `own-group`
  any-author-overlap flag, which remains as metadata only). The split bar,
  centrality counts, and Impact's function groups cover external citations
  only; COMMIT papers appear in their own labeled group at the bottom of
  Impact, and chip-marked inside Recency/Popularity. Impact claims never
  lean on the group's own citations.

## 7. Routine refresh

The full workflow is in `data/citations/SCHEMA.md`. The short version: run
the harvest (incremental), run the classifier on new records only, paste
fresh Scholar numbers into `data/citations/gscholar.json` by hand, run the
merge script, commit `data/citations/`. No HTML or JS changes, ever. A new
paper gets its citation view the first time the pipeline gives it an index
row.

## 8. The prototype

    cd ~/workspace/nextgen && python3 -m http.server 8000
    open http://localhost:8000/prototype/citations.html

`prototype/citations.html` renders `halide:pldi:2013` and
`netblocks-pldi24` as pub-items with the citation toggle live against their
real `data/citations/` files (built by `prototype/build_pilot_data.py` from
the pilot classifications). Halide exercises the full design at scale;
NetBlocks shows the young-paper case (4 citations, no bar noise, groups
still read cleanly). Neither has a Scholar count yet, so both display their
verified count; the max logic is in place and takes over the moment
`gscholar.json` gets a row.

## 9. Worked examples — the 8 pilot papers

Numbers below predate the COMMIT-papers redefinition (they used the
broader own-group flag); the shape of each story is unchanged.
detailed / passing / not-yet-analyzed.

| paper | works (own) | split D/P/U | what the view shows |
|---|---|---|---|
| halide:pldi:2013 | 1,483 (43) | 586/416/438 | The healthy-descent profile: 214 external works build on, run, or re-implement the idea; the passing mass is the price of winning ("the origin of compute/schedule separation"). Lineage chips mark the TVM-ancestry cites. |
| thies:cc:2002 | 1,361 (35) | 458/390/478 | The benchmark-suite pattern: "Uses its benchmarks" (85 raw judgments) outweighs every other pilot's — the StreamIt suite outlived the compiler. |
| taylor:micro:2002 | 947 (28) | 165/150/604 | The number-that-travels pattern ("Cites a result as evidence": interconnect ≈36% of Raw's power, cited by a decade of NoC papers) — and the honesty case: 604 not-yet-analyzed, because its older citing literature is evidence-poor. |
| amarasinghe:ijpp:2005 | 81 (1) | 32/25/23 | A mid-size paper reads cleanly: differentiation (`positions`) leads. |
| petkov:ipdps:2002 | 31 (0) | 18/4/9 | Technique citations: the HLS line that credits and supersedes unroll-and-squash. |
| thies:toplas:2007 | 17 (0) | 9/2/6 | Small but almost all detailed: the storage-optimization literature treats AUOV as the formal object to generalize. |
| levison:istas:2002 | 10 (0) | 5/3/2 | The ICTD lineage (RuralCafe, COCO) citing TEK as the predecessor system. |
| netblocks-pldi24 | 4 (0) | 2/2/0 | Young paper: two `extends`-core citations already; no unjudged rows. |

## 10. Open questions for review

1. Is `exemplifies` on the passing side right (§5)? Moving it to detailed
   is a merge-script rerun.
2. ~~Row order inside a function group~~ — superseded by the approved
   three-sort-mode ruling (§2 item 4); rows inside Impact groups stay
   year-descending.
3. The unjudged group is visible by default. It could sit behind the
   footer instead; visible is the honest default and my recommendation.
4. Label wording for the two residuals ("Mentions it specifically" /
   "Cites it in a list") — better names welcome.
5. Title-based dedup (the human ruling) keeps same-system records whose
   titles genuinely differ — e.g. the three TVM entries ("End-to-End
   Optimization Stack" arXiv v1, "End-to-End Compilation Stack" arXiv v2,
   and the OSDI paper) all appear under "Builds on it". They are different
   records with different titles, so the rule cannot fold them; folding
   version-families would need a by-hand or by-id pass. Fine to ship as is?
