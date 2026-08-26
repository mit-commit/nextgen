# Cleanup audit — phase 1 (2026-08-26, audit only, nothing changed)

Per `tasks/CLEANUP.md`. Everything below is measured or verified in code;
line references are against the working tree at commit `883ec492`.
Triage vocabulary: **WRONG** (misleads or will break something),
**UNTIDY** (costs attention, not correctness), **LEAVE** (imperfect on
purpose or not worth the risk).

---

## 1. Data structures

### What the page actually costs

First paint, publications.html, as served (gzipped over GitHub Pages):

| fetch | raw | gzipped |
|---|---:|---:|
| publications.html + style.css + 4 JS files | 171KB | ~55KB |
| data/publications.json | 680KB | 159KB |
| data/citations/index.json | 59KB | 6.7KB |
| data/repos/index.json | 106KB | 12.8KB |
| data/citations/reception.json | 125KB | 40.7KB |
| **first paint total** | **1.14MB** | **~275KB, 10 requests** |

Post-boot (async, doesn't block paint): impact-authors.json 953KB/81KB gz,
citers.json 122KB, author-links.json 20KB.

Lazy per-paper shards: data/citations 206 files, 10.2MB total, median
17KB, max 632KB (halide). data/repos/papers 163 files, 1.7MB, median
1.4KB. Fetched only on panel expand through a 4-wide queue.

**Verdict on "should the data files be consolidated": no — the shard
architecture is right and measurably paying for itself.** 12MB of
evidence never touches first paint; the indexes that gate the toggles
cost 19.5KB gzipped combined. Consolidating shards into one file would
put megabytes on first paint to save nothing; consolidating the indexes
into publications.json would couple his hand-edited source file to
machine-regenerated data. The problems below are field-level, not
architectural.

### Field-level findings

- **WRONG — dead fields shipped on every load**: `data/repos/index.json`
  carries `tiers` (2.9KB) and `impact` (0.2KB) per paper; nothing reads
  either since the impact-formula change. The builder should stop
  emitting them. (`rids` 20.7KB and `grids` 22.3KB are earned — they
  power the distinct-repo overview and per-category counts.)
- **WRONG — double-stored reception**: every citation shard embeds a
  `reception` copy AND `reception.json` (125KB, fetched at boot) holds
  the same text. The page reads only `reception.json`; the shard copies
  are writer convenience nobody consumes. One copy should go (keep
  `reception.json`: it is the page's read path and the human-review
  artifact).
- **UNTIDY — the 953KB outlier**: `data/impact-authors.json` is shaped
  for its writer (`people[] → papers[]`); the page immediately inverts
  it to a by-paper map. Emitting the inverted map (or both) would delete
  ~20 lines of boot code and parse work. Post-boot, so low urgency.
- **UNTIDY — filename mapping is folklore**: keys keep colons
  (`halide:pldi:2013`) but files are colon-free (`halide_pldi_2013.json`)
  since the Pages incident; the `key.replace(':','_')` rule now lives in
  6 call sites across JS/Python with no shared helper. One more reader
  will get it wrong someday.
- **UNTIDY — two venue strings**: every record has a display `venue` and
  the raw `booktitle`/`journal`; the impact venue-bonus reads `venue`
  while renderers read both through three duplicated `venueOf` copies.
  Not wrong today, but the coupling is invisible.
- **LEAVE**: `gscholar` convenience copies in shards (index is
  authoritative, documented in SCHEMA.md); derived-but-committed site
  data (`data/repos/**`, citers, author-links, impact-authors) — the
  site must serve them, and regenerability is documented; `counts`
  blocks in shards (cheap, self-describing).

---

## 2. Code

### Shape of the two monoliths

`assets/js/publications.js` (2,194 lines): ~450 lines are pure, cleanly
separable helpers (name/date/keyword normalization, BibTeX build, type
labels); everything after L343 is welded to five module singletons
(`state`, `els`, `DATA`, `CITE_INDEX`, `REPO_INDEX`) with `applyFilters`
as the hub. The indentation actively lies about scope: ~230 lines of
column-0 functions (export-bib, sort UI, the XHR loader) are actually
nested inside `boot()`. Splitting the tangle would move mess, not remove
it; extracting the pure ~450 lines is safe and worthwhile if we ever
split at all.

`assets/js/citations.js` (847 lines): ~250 pure lines (codebook, render
helpers, bucket ladders); the tangle is six module singletons plus
`gPanel`. `renderView` (236 lines) is the largest single unit.
`attachToggle`/`attachRepoToggle` are a ~50-line near-duplicate pair
that could be one parameterized function.

### Duplication (worst first)

- **WRONG (landmine, verified)**: `renderItem` appends TWO BibTeX
  elements (`publications.js:1087` + `:1090`). Today the first renders
  as an empty `<span>` because `pubs.js` never exports
  `makeBibDownloadLink` — one visible link, by accident. If anyone
  exports it, every paper grows a second BibTeX link with *different*
  content (`pubs.js`'s builder lacks the `oldbibtex` passthrough).
  Delete the `makeBibLink` append and the fallback.
- **WRONG (five-site formula)**: the impact/featured scoring exists in
  five places — `publications.js` (impact), `pubs.js` (featured),
  `tests/ui/oracle.py` (mirror, deliberate), plus `awardYearOf`
  line-for-line duplicated in JS twice. The oracle copy is by design;
  the JS `awardYearOf`/displayCount inlines are not. Every formula
  ruling is currently a 5-file edit — today's venue-bonus change proved
  it.
- **UNTIDY**: category↔repo-group map ×4 (`BADGE_FG`/`FG`/`FUNC_GROUP`/
  `REPO_FUNC`); thesis-type rule ×3 (two maps + a regex); fetch idiom ×5
  styles across files (incl. `common.js:getJSON` with zero callers);
  field accessors ×3 (incl. `venueOf` three times in one file, one dead);
  grouping engine ×3; split-bar rendered once as a function and once
  inline; sort-button builder ×3; `splitKeywords` byte-identical twice
  in one file (one dead).

### Dead code (verified no callers)

- `publications.js`: `splitAuthors`, IIFE `splitKeywords`, first
  `venueOf`, `makeSorter` + `state.sortKey`/`state.sortDesc` (init-only,
  never assigned — all five sort branches unreachable), `state.scroll`,
  the O(n) "key-only probe" in `compositeImpactOf` (no caller passes
  key-only), 3 commented-out `localizeURL` variants.
- `citations.js` exports, 7 of 21 dead: `refreshToggleBadges`,
  `countBucket` (export), `impactScore` + `WEIGHTS` (the old
  engagement-weighted score — now fully superseded), `ensureData`,
  `crossCiters` (+ `dataCache` retained solely to feed it), `setDataBase`
  (latently broken: `REPO_BASE` wouldn't follow). `CENTRALITIES`,
  `repoDataCache` written-never-read.
- `oracle.py:impact_score` — the same dead score in Python; remove both
  together or neither.
- `pubs_index.js` retry loop unreachable (script order guarantees PUBS).

### Silent error handling — the audit's most consequential code finding

Eight swallowed-failure sites, ranked in the agent report; the pattern:
`publications.js`'s six boot fetches degrade to "feature silently
absent" (a failed repos index changes the *impact ranking* with no
indication; a failed reception fetch silently drops his prose from every
summary). `citations.js`'s per-panel loads do it right — visible
"Could not load…" text in the panel. **WRONG**, cheap to fix: give each
boot fetch the citations.js treatment (a one-line console.error at
minimum; a visible notice ideally). The over-broad `.catch` at `:375`
that nulls `CITE_INDEX` when *any* of three fetches fails is the single
worst line.

- **LEAVE**: the `umami.track` try/catch guards (analytics must never
  break the page); the boot XHR error path (already loud).

---

## 3. Documentation

- **WRONG — refresh.md drift**: §3 and "never runs automatically" name
  `build_login_worklist.py`; the current builder is
  `build_login_worklist2.py` (per HARVEST-AND-UPDATE.md). And the entire
  site-build layer (`build_repo_data`, `build_citers`,
  `build_impact_authors`, `join_links`/`apply_link_overrides`,
  `judge_embodiment`, the ecosystems lane) appears only in
  `tasks/HARVEST-AND-UPDATE.md`, not in refresh.md's per-script manual.
  16 re-runnable scripts are named in neither doc (list in §4 agent
  notes) — "the ambiguity is the actual defect."
- **UNTIDY — LANES.md**: 1,414 lines / 154KB, ~90% closed history.
  Proposed split: `docs/LANES.md` keeps the protocol + current claims +
  last ~2 rounds; everything older moves verbatim to
  `docs/LANES-archive.md`.
- **Missing (the single most valuable doc to add)**: an end-to-end data
  flow map — which files are source (publications.json, gscholar.json,
  overrides, rulings), which are harvest intermediates, which are
  derived site data, and what regenerates what. Nothing like it exists;
  a newcomer cannot currently answer "if I edit X, what must re-run".
- Known stale, confirmed: `harvest/authors/links-residue.md`.
- The two committed test reports (`tests/ui/report.md`,
  `combinatorial-report.md`) rot on every source edit; either stop
  committing them or stamp them with the commit they describe.

---

## 4. Debris

(Agent-verified: what each was for, proof of disuse, recoverability.)

- **Closed-round intermediates, tracked, ~6MB — UNTIDY, safe deletes**:
  deephunt scratch (3.6MB `deephunt_repolist.json` + 5 siblings),
  thesis-mining scratch (963KB + 3 files), login worklists v1–v3 (all
  sittings closed, ~700KB), empty review queues (0-byte JSONLs, `[]`
  files), run-report markdowns referenced only from LANES history.
  All recoverable from git.
- **One-off scripts, 21 of 65 — UNTIDY**: each encodes a closed round
  task (deephunt suite, sitting-ruling appliers, idmap review appliers,
  superseded v1s: `harvest_abstracts.py`, `build_login_worklist.py`,
  `measure_ecosystems.py`). Recommend a `harvest/attic/` move rather
  than deletion for the ruling-encoding ones (`apply_*` scripts arguably
  fall under "records a human ruling" — LEAVE those in place).
  `utils/addoldbibtex.py`: zero references, 11 months stale — delete.
- **prototype/ — UNTIDY with one exception**: `build_pilot_data.py` is
  PRODUCTION (protected, sole writer of pilot shards) misfiled under
  prototype/ — promote to `curate/`. `citations.js` there is a 14-line-
  diff duplicate of the shipped file, re-touched the same day — a live
  maintenance hazard; the mock and demo html are superseded. Delete
  after updating the 3 doc pointers.
- **papers/ — LEAVE pending his ruling**: 0 missing-file references,
  0 duplicate PDFs by hash. But ~590MB of legacy `.ps`/`.ppt`/`.mov`
  nothing in publications.json links — and `papers/.htaccess` proves the
  directory serves *historical public URLs* from the 1990s–2000s.
  Deleting would break decades-old external links and win no repo size
  (blobs stay in the 725MB pack without a history rewrite). Flag, do
  not delete.
- **Caches on disk, gitignored, ~930MB**: correct design, just large
  (fulltext 479MB, gh caches 292MB+118MB). One stray: 4.5MB
  `owner-repos.json` cache sits among committed outputs;
  `qualify_state.json` is untracked and unignored — add to .gitignore.

---

## Recommendation summary (the triage he asked for)

**Genuinely wrong — fix in phase 2, highest value first:**
1. Silent boot-fetch failures (8 sites; the `:375` over-broad catch
   first).
2. The BibTeX landmine (dead append + divergent builders).
3. Dead `tiers`/`impact` fields in the repos index; reception
   double-store.
4. refresh.md drift + the missing data-flow map (blocks the next
   "harvest and update" run months from now).
5. The 5-site scoring formula: extract one `impact-formula.js` shared by
   page and featured (oracle stays independent by design).

**Merely untidy — batch cheaply, one concern per commit:**
dead code sweep (both JS files + oracle's dead twin), duplicate-helper
consolidation, ~6MB closed-round intermediates, one-off scripts to
attic, prototype/ retirement (+ promote build_pilot_data.py), LANES
split, .gitignore strays.

**Leave alone:**
papers/ legacy archive (his ruling required — public URLs), gitignored
caches, links.json override indirection (protected), pilot outputs,
oracle.py's deliberate mirroring, gscholar shard copies, the shard
architecture itself — it is the right shape.
