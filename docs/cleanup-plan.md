# Cleanup phase-2 plan (proposed 2026-08-26, awaiting his go)

Executes the WRONG and UNTIDY findings of `docs/cleanup-audit.md`.
Governing rules from `tasks/CLEANUP.md`: both harnesses green after every
batch; one concern per commit; format changes move writer + reader +
oracle + docs together; deletions in their own listed commit; refactors
are behavior-preserving or they stop.

## Safety model — nothing can break the live site

- All work happens in `~/workspace/nextgen` on branch **`cleanup`**.
  The live repo (`/Users/saman/commit-website`) is not touched until the
  final batch.
- Baseline first: record the branch point SHA; capture a **golden
  snapshot** of observable behavior (impact-sort top 20, featured 10,
  overview line, one paper's .bib output, one open panel's rows) to
  byte-compare after every batch — the harnesses check correctness
  against the oracle, the snapshot catches "correct but different".
- Gate = `tests/ui/facet_test.py` (908 cases) + `random_settings_test.py`
  (100) against a local server, after every batch. A red gate stops the
  batch; its commit is reverted before continuing.
- Upload is a single final sync to `commit-website` with the rollback
  SHA in the merge message, then Pages build watch + the full live
  checklist (CUTOVER step 5, incl. Umami on 4/4 pages).

## Batch 0 — prep (no changes)

Branch `cleanup`; run both harnesses for a green baseline; write the
golden snapshot to `/tmp` (not committed); note current live SHAs.

## Batch A — the two behavior-adjacent fixes (audit "wrong" #1–2)

- **A1. Loud boot-fetch failures** (`publications.js`): split the
  over-broad `.catch` on the index `Promise.all` so each of the six boot
  fetches (citations index, repos index, reception, impact-authors,
  author-links, citers) fails independently; on failure, `console.error`
  with the path AND render one visible line in `#cite-overview`
  ("some citation data failed to load: <file>") — the pattern the
  per-panel loads already use. Success path byte-identical.
  *Extra test*: failure injection — rename `data/repos/index.json`
  locally, verify the notice appears and citations still work, restore.
- **A2. BibTeX landmine**: delete the dead `makeBibLink` append and its
  `<span>` fallback (`publications.js:705, :1087`); `createBibLink`
  (oldbibtex-aware) remains the single builder. Golden-snapshot the
  .bib of one `oldbibtex` record and one normal record before/after.

## Batch B — data-format fixes (writer+reader+oracle+docs together)

- **B1. Repos index sheds dead fields**: `build_repo_data.py` stops
  emitting `tiers` and `impact`; regenerate `data/repos/index.json`;
  no JS reads them (verified); oracle reads only `.repos` (verified);
  update `data/repos/SCHEMA.md` in the same commit. ~3KB/paper-set
  saved on first paint, one less stale concept.
- **B2. Reception single-store**: `merge_taxonomy.py` and
  `build_pilot_data.py` stop embedding `reception` in shards;
  one regeneration pass strips the field from existing non-pilot shards.
  **Pilot shards are protected outputs — they keep the field untouched
  until their next legitimate rebuild** (readers never read it, so the
  inconsistency is invisible; SCHEMA.md documents the transition).
  `reception.json` remains the single read path and review artifact.
- **B3. Filename mapping stops being folklore**: one `fileKeyOf(key)`
  helper in `citations.js` used by its three fetch sites; the five
  Python one-liners get a pointer comment; the `':' → '_'` rule is
  documented in both SCHEMA.md files.

## Batch C — code consolidation (behavior-preserving)

- **C1. Dead-code sweep** (one commit per file):
  `publications.js` — `splitAuthors`, duplicate `splitKeywords`, first
  `venueOf`, `makeSorter` + `state.sortKey`/`sortDesc`, `state.scroll`,
  the unreachable key-only probe in `compositeImpactOf`, three
  commented-out `localizeURL` variants, stale paste-marker comments.
  `citations.js` — dead exports `impactScore`+`WEIGHTS` (the superseded
  engagement score), `ensureData`, `crossCiters`, `setDataBase`
  (latently broken), `CENTRALITIES`, `repoDataCache`; `dataCache`
  **stays** (kept as the documented hook for panel-refetch avoidance).
  `tests/ui/oracle.py` — its dead `impact_score` twin, same commit
  series.
- **C2. One scoring module**: new `assets/js/scoring.js` holding
  `awardYearOf`, `venueBonus`, `impactScoreOf` (publications page) and
  `featuredScoreOf` (home page); `publications.js` and `pubs.js` call
  it; both HTML pages load it (versioned URL). The oracle keeps its own
  deliberate mirror — a header comment in both files names the pairing
  so future formula rulings are a 2-site edit (scoring.js + oracle.py)
  instead of 5.
- **C3. Mechanical duplicate collapse, low-risk subset only**:
  category↔repo-group map ×4 → exported once from `citations.js`;
  thesis-type rule ×3 → one helper in scoring.js; `awardYearOf` JS
  duplicate removed by C2. **Explicitly out of scope** (audit LEAVE):
  the three grouping engines, the five fetch idioms, attachToggle
  unification — high-churn, low-payoff rewiring of a live page.

## Batch D — documentation truth

- **D1. refresh.md**: fix `build_login_worklist` → `2`; add the missing
  "site data build" section (build_repo_data → judge_embodiment note →
  build_citers → build_impact_authors + author-overrides note →
  join_links/apply_link_overrides → gen_tier2_priority); name each of
  the 16 undocumented-but-durable scripts in the step where it runs, or
  send it to the attic in Batch E.
- **D2. New `docs/DATA-FLOW.md`** — the end-to-end map: sources
  (publications.json, gscholar.json, rulings/overrides) → harvest →
  curate → `data/` → page fetches; for every `data/` file: who writes
  it, who reads it, what regenerates it. The audit's "single most
  valuable doc".
- **D3. LANES split**: `docs/LANES.md` keeps protocol + active claims +
  the current round; the rest moves verbatim to
  `docs/LANES-archive.md`. Coordinated with the other sessions via a
  LANES note before the move (it is a shared file).

## Batch E — debris (deletions last, own commits, fully listed)

- **E1. Tracked intermediates of closed rounds** (~6MB): deephunt
  scratch set, thesis-mining scratch set, login worklists v1–v3, empty
  review queues, stale run reports, `links-residue.md`. One
  deletions-only commit, every path listed in the message.
- **E2. One-off scripts**: superseded v1s deleted
  (`harvest_abstracts.py`, `build_login_worklist.py`,
  `measure_ecosystems.py`, `utils/addoldbibtex.py`); closed-round task
  scripts move to `harvest/attic/` (kept runnable for archaeology);
  the `apply_*` ruling-encoding scripts **stay where they are**
  (protected as records of human rulings).
- **E3. prototype/**: `build_pilot_data.py` promoted to `curate/`
  (refresh.md + SCHEMA.md + LANES claim updated same commit); the
  superseded `citations.js/.css/.html` and the impact mock deleted with
  their three doc pointers updated in the same commit.
- **E4. Hygiene**: `.gitignore` gains `harvest/impactview/qualify_state.json`;
  `__pycache__`/`.DS_Store` cleaned from the tree.
- **NOT in scope**: `papers/` legacy `.ps`/`.ppt`/`.mov` (~590MB) —
  serves historical public URLs per `.htaccess`; awaiting his explicit
  ruling, and deletion wins no repo size anyway.

## Batch F — full test pass (before any upload)

1. Both harnesses green on the `cleanup` branch (they ran after every
   batch; this is the final consecutive green run).
2. Golden-snapshot diff vs Batch 0: impact top-20, featured 10, overview
   line, sample .bib, sample panel — byte-identical or the difference is
   explained and approved.
3. Sync the branch into `/Users/saman/commit-website` **working tree
   only** (no commit yet); serve it locally; run BOTH harnesses again
   against that copy; 370-file lazy-data HEAD sweep; all four pages
   console-clean; failure-injection retest; Umami tag count 4/4.
4. Manual click-through list: expand summary/citations/repos on 3
   papers, category + centrality drill-down, Clear filters, author
   links, Featured panels on home, one PDF link, Export .bib.

## Batch G — the one upload

Single commit in `commit-website` (message lists the batch series and
the **rollback SHA**), push, watch the Pages build via API, then the
live checklist: new content live, panels expand with real data, no
404s, four pages + Umami, featured list correct. Report results plainly.
LANES gets the closing entry.

## Estimated shape

7 batches, ~12–15 commits, 6 full gate runs (~20 min each). Everything
reversible per-commit; the live site changes exactly once, at G.
