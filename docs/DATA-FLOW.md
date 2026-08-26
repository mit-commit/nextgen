# Data flow — end to end

The one-page answer to "if I edit X, what must re-run, and what does the
site actually read?" Arrows point downstream. Full per-script detail:
`docs/refresh.md` (per-script manual) and `tasks/HARVEST-AND-UPDATE.md`
(order of work and gates).

## The three kinds of files

- **SOURCE** — hand-maintained, never written by scripts.
- **HARVEST** — machine-gathered evidence and judgments under `harvest/`;
  regenerable in principle, expensive in practice (API calls, batches,
  human sittings). Committed so reruns are incremental.
- **SITE** — derived files under `data/` that the pages fetch. Every one
  is regenerable from SOURCE + HARVEST by a named script.

## Sources (the ground truth)

| file | contents | guarded by |
|---|---|---|
| `data/publications.json` | the 327 records; summaries are his prose | hand-edit only |
| `data/citations/gscholar.json` | Scholar counts, human-pasted | hand-edit only |
| `data/citations/reception.json` | reception prose, human-reviewed waves | wave pipeline + his review |
| `harvest/authors/link-overrides.json` | his link rulings | `apply_link_overrides.py` is links.json's only writer |
| `harvest/impactview/author-overrides.json` | name-qualification rulings | frozen input |
| `harvest/impactview/embodiment.json` | which repo embodies which paper | model-judged, human-overridable |
| `harvest/impactview/manual-rows.json` | hand-verified repo rows | human adds |
| rulings recorded in `tasks/*.md` | frozen exceptions (Anant, spellings, adadima…) | do not touch |

## Pipeline (SOURCE → HARVEST → SITE)

```
publications.json
  ├─ idmap_build.py ──────────────► data/idmap.json
  ├─ harvest_citations.py (2 passes) + backfill_cited_by.py
  │        ────────────────────────► harvest/citations/<key>.json
  ├─ harvest_abstracts_all.py ─────► harvest/fulltext/abstracts/
  │
  ├─ classify_citations.py (Batch API, <$20 gate)
  │        ────────────────────────► harvest/taxonomy/records/<key>/
  ├─ merge_taxonomy.py --write  ◄── gscholar.json, reception.json
  │        ────────────────────────► data/citations/<key'>.json  (non-pilot)
  │                                  data/citations/index.json
  ├─ (pilots only) curate/build_pilot_data.py --write
  │        ────────────────────────► the 8 pilot shards + pilot index rows
  │
  ├─ repos lane: extract_candidates → verify → repair → build_outputs
  │   + search_github + curate/verify_repos (Batch API)
  │        ────────────────────────► harvest/repos/verified.json
  ├─ descendants / ecosystems / own-inventory / fingerprint lanes
  │        ────────────────────────► harvest/repos/descendants.json
  │                                  harvest/ecosystems/verified.json
  │                                  harvest/repos/own-inventory.json
  ├─ judge_embodiment.py ──────────► harvest/impactview/embodiment.json
  ├─ build_repo_data.py --write ◄── all of the above + artifacts/found.json
  │        ────────────────────────► data/repos/papers/<key'>.json
  │                                  data/repos/index.json
  │
  ├─ build_citers.py --write  ◄──── data/citations/<key'>.json (merged shards)
  │        ────────────────────────► data/citations/citers.json
  ├─ build_impact_authors.py --write ◄─ shards + data/repos + authors.json
  │        ────────────────────────► data/impact-authors.json
  └─ authors lane: authors_build → build_links → sittings/overrides
      apply_link_overrides.py ─────► harvest/authors/links.json
      join_links.py --write ───────► data/author-links.json
```

`<key'>` = the bibtexKey with `:` replaced by `_` in FILENAMES only
(GitHub Pages cannot serve `:` paths); keys inside the JSON keep colons.

## What each page fetches

`publications.html` first paint: `publications.json`,
`data/citations/index.json`, `data/repos/index.json`,
`data/citations/reception.json`. Post-boot (async):
`data/impact-authors.json`, `data/citations/citers.json`,
`data/author-links.json`. On panel expand (lazy, per paper):
`data/citations/<key'>.json`, `data/repos/papers/<key'>.json`.

`index.html` (home): `publications.json` + the two indexes (featured
scoring and panels); lazy per-paper shards on expand.

`projects.html` / `people.html`: `data/projects.xml` / `data/people.xml`
only.

## If you edit X, re-run Y

| changed | re-run | then |
|---|---|---|
| publications.json (new paper) | the full refresh (docs/refresh.md §1–§9) | site data regenerates end to end |
| gscholar.json | `merge_taxonomy.py --write` | index gscholar figures refresh |
| reception.json | nothing (page reads it directly) | — |
| any citation shard content | `build_citers.py --write`, `build_impact_authors.py --write` | derived counts follow |
| harvest/repos/* or ecosystems/* or embodiment.json | `build_repo_data.py --write` | then `build_impact_authors.py --write` |
| link-overrides.json | `apply_link_overrides.py` then `join_links.py --write` | author links refresh |
| the impact/featured formula | `assets/js/` (page) **and** `tests/ui/oracle.py` (mirror) | run both harnesses |

## Deploy

Dev repo `mit-commit/nextgen` is the source of truth for the page +
`data/`. The live repo `mit-commit/commit-website` receives synced copies
and publishes via GitHub Pages from `main`. Gate before any sync: both
harnesses green (`docs/refresh.md`, pre-cutover section). Asset URLs are
versioned (`?v=N`) — bump on every asset change.
