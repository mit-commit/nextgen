# data/repos/ — per-paper repository data for the impact view

Feeds the publications page's Repositories panel (design:
`docs/impact-view-design.md`, Option B as approved). Built by
`harvest/impactview/build_repo_data.py` from the repos, artifacts,
ecosystems, and descendants harvests; regenerate with `--write` after any
of those change. Distinct from `data/repos/<ecosystem>.json` (the
ecosystems lane's tier-2 pools, keyed by ecosystem): everything here is
keyed by paper.

Schema version: **1**.

## `papers/<bibtexKey>.json` — one paper's repositories

```json
{ "schema": 1, "key": "ansel:pact:2014", "generated": "2026-08-25",
  "repos": [
    { "name": "Archival artifact", "group": "own", "role": "artifact",
      "artifact": true, "url": "https://doi.org/10.5281/zenodo...",
      "badges": ["Artifacts Available"], "evidence": "badged artifact record" },
    { "name": "jansel/opentuner", "url": "https://github.com/jansel/opentuner",
      "group": "own", "role": "implementation", "confidence": "high",
      "desc": "An extensible framework for program autotuning",
      "stars": 438, "active": 2025, "evidence": "…" }
  ] }
```

Row fields: `group` uses the **unified relationship taxonomy** shared with
citations — `own` (Artifact & own repository), `builds-on` (Builds on it:
derivative works, forks), `uses` (Uses the system: API users, inherited),
`benchmarks` (Uses its benchmarks), `adopts` (Adopts the idea:
idea-descendant repos). `sdv` (optional) carries the SDV integration term
for the row chip. `artifact: true` marks badged archival artifacts (always
listed first). `paper`/`paperOnly` mark tier-3 rows whose citing work has
no located repo. `stars`/`active`/`desc`/`archived` come from the GitHub
API (cached in `harvest/impactview/ghmeta.json`); rows render gracefully
without them. `gone: true` marks a 404ing repo. `evidence` renders as the
row tooltip.

**Excluded on purpose**: `verified.json`'s `third_party` rows — repos the
paper itself mentions or depends on. That is the reverse direction of
impact and never renders here.

## `index.json`

One row per paper with data — `{ "repos": n, "rids": [ids], "grids":
{group: [ids]}, "cc": 1? }` — `rids` are corpus-stable repo ids for
distinct-count unions; `grids` partitions them by shared-taxonomy group
for the category facet counts; `cc` marks a paper whose publications.json
Code link is covered by a row (the page hides its Code button). It is
fetched once by the publications page to decide which papers get a
"Repositories (N)" toggle. Papers absent simply show no toggle
("gracefully absent" per F2). As the tier-2 ecosystems and tier-3
descendants harvests land, the builder folds them in and counts grow with
no front-end change.
