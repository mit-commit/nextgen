# Refresh procedure — every few months

This is the checklist for bringing the site's data back up to date after
new papers land, new citing works accumulate, and a new Google Scholar
scrape is available. Each step names its script and who runs it — **worker**
means any Claude session picks it up from the task queue; **human** means it
genuinely needs a person (a login, a judgment call, or a GUI check).

Run the steps in order within each phase; phases can interleave across
sessions as long as a later phase's inputs are ready.

## 0. New papers (human, occasional)

Add the new entry to `data/publications.json` by hand (it is read-only for
every script — nothing else touches it). Everything below picks up a new
`bibtexKey` automatically the first time its outputs are regenerated; there
is no separate "register a new paper" step.

## 1. Identifiers (worker)

    python3 harvest/idmap_build.py --write

Resolves DOI → OpenAlex → Semantic Scholar for every `data/publications.json`
entry not already in `data/idmap.json`. Anything that can't be resolved
automatically lands in `data/idmap-review.json`; a worker session (or the
human, for anything account-gated) resolves those by hand the way
`idmap_review_finalize.py` did — check OpenAlex/Crossref directly, mark
`same_work_as` for reprint/poster duplicates, `no_doi` with a note otherwise.

## 2. Citations harvest (worker)

    python3 harvest/citations/harvest_citations.py --pass openalex
    python3 harvest/citations/harvest_citations.py --pass s2
    python3 harvest/citations/backfill_cited_by.py --write

Both passes are additive and idempotent — a `bibtexKey` whose file already
exists is only touched by the `s2` pass filling in matched fields, so
re-running after a refresh only does new work. `backfill_cited_by.py`
fills in the new citing works' own `cited_by` counts (skips anything that
already has one).

## 3. Evidence for classification (worker)

    python3 harvest/fulltext/harvest_abstracts_all.py

Fetches an OpenAlex abstract for every non-pilot citing work that doesn't
have cached evidence yet (skips anything already in
`harvest/fulltext/abstracts/<key>.json`, any status). The 8 taxonomy pilots
are out of scope here — their evidence is a fixed sample, not meant to grow.

## 4. Classification (worker, cost-gated)

    python3 curate/classify_citations.py --submit --dry-run

Report the cost estimate. Under $20, submit directly
(`--submit`); above that, stop for human approval (standing rule as of the
2026-08-25 full-force rollout). Then:

    python3 curate/classify_citations.py --status     # poll until all batches "ended"
    python3 curate/classify_citations.py --collect
    python3 curate/classify_citations.py --recover     # re-validate needs-review.jsonl, no API call

`load_candidates()` only ever proposes citing works that (a) aren't already
staged in `harvest/taxonomy/records/<key>/` and (b) have evidence better
than title-only, so a refresh run naturally submits just the new/upgraded
rows. If the codebook itself changes (`docs/taxonomy-draft.md`), a targeted
rejudge sweep clears the affected staging records first — see the taxonomy
lane's log in `docs/LANES.md` for the pattern used after the v0.2 amendment
and after the abstracts-all pass.

## 5. Repos (worker, cost-gated where noted)

    python3 harvest/repos/extract_candidates.py   # only if new PDFs landed
    python3 harvest/repos/verify.py
    python3 harvest/repos/repair.py
    python3 harvest/repos/build_outputs.py
    GITHUB_TOKEN=... python3 harvest/repos/search_github.py
    python3 curate/verify_repos.py --submit --dry-run   # then --submit if <$20, else stop for approval
    python3 curate/verify_repos.py --status / --collect / --recover

Steps 1–4 (in-paper discovery) only need rerunning when new PDFs are added
to `papers/`. `search_github.py` and `verify_repos.py` are resumable —
already-processed `bibtexKey`s are skipped — so a refresh run is cheap.

## 6. Merge into the site's data (worker)

    python3 curate/merge_taxonomy.py --write

Folds every non-pilot paper with new/changed `harvest/taxonomy/records/`
into `data/citations/<bibtexKey>.json` and refreshes `data/citations/
index.json` (including every other paper's `gscholar` figure, even ones
with no new records this run — see step 7). Never touches the 8 pilot
`data/citations/<bibtexKey>.json` files or `gscholar.json`/`reception.json`
themselves; those are `prototype/build_pilot_data.py`'s and the human's
respectively.

## 7. Google Scholar counts (human, account-gated — the one truly manual step)

Paste fresh counts from a Google Scholar profile scrape into
`data/citations/gscholar.json` by hand (keyed by `bibtexKey`, `{count,
date}`). Never edit it with a script. Re-run `curate/merge_taxonomy.py
--write` afterward — it picks up the new figures for every paper in
`index.json`, not just ones with new citing works, per its gscholar-refresh
pass.

## 8. Reception + summaries (human review required before publishing)

Reception text (`data/citations/reception.json`, folded into per-paper
files by the same merge step) and paper summaries are both **generated
text reviewed by the human before it ships** — never auto-published. The
generation pipeline (evidence pack → Batch API → `docs/summary-style.md`'s
voice) runs in waves of ~25 papers, ordered by citation count descending;
the human spot-checks each wave before the next one runs. See
`docs/summary-style.md` for the approved voice and `docs/LANES.md`'s
site-citations log for the current wave state.

## 9. Verify and ship

- Confirm `data/citations/index.json`'s paper count matches the number of
  per-paper `<bibtexKey>.json` files on disk (everything under
  `data/citations/` except `SCHEMA.md`, `gscholar.json`, `reception.json`,
  and `index.json` itself).
- Spot-check a couple of newly-classified or newly-repo-verified papers in
  the live page (`publications.html`) — Citations panel, Repositories
  panel where wired, sort modes, centrality buttons.
- Commit and push each phase's output separately (matches every prior
  refresh's pattern in `docs/LANES.md`) rather than one giant commit --
  makes a bad batch easy to isolate and revert.

## What never runs automatically

- `data/publications.json` — hand-edited only.
- `data/citations/gscholar.json` — hand-edited only, human account access.
- The 8 pilot `data/citations/<bibtexKey>.json` files and
  `harvest/taxonomy/pilot-classifications.json` — the taxonomy pilot is a
  fixed, hand-reviewed reference sample, not meant to grow or be
  reclassified by later automation.
- Anything behind a login (ACM DL, IEEE Xplore, publisher full text,
  LinkedIn) — a worker prepares a worklist (see
  `harvest/fulltext/build_login_worklist.py` and
  `harvest/authors/build_session_sheet.py` for the pattern: gather
  candidates, construct search URLs, fetch nothing) and a human works
  through it in a browser sitting.

## Pre-cutover gate: the UI combinatorial test harness

Before any cutover (deploying `publications.html` to the public site, or
after any structural change to `assets/js/publications.js` /
`assets/js/citations.js`), run the combinatorial harness and require a
green report:

    python3 -m http.server 8123 &        # from the repo root
    python3 tests/ui/facet_test.py               # combinatorial -- writes tests/ui/combinatorial-report.md
    python3 tests/ui/random_settings_test.py     # random-settings -- writes tests/ui/report.md

The two scripts write to different files on purpose (`random_settings_test.py`'s
output path, `tests/ui/report.md`, is his own instruction in `tests/ui/SPEC.md` --
don't let a `facet_test.py` rerun clobber it).

`facet_test.py` checks every single-facet value, sampled pairwise and
3–4-way facet combinations, the sort modes and Show toggles, against an
independent oracle computed straight from the data files (~900 cases).
`random_settings_test.py` (per his `tests/ui/SPEC.md` instruction)
discovers every control in `#pubs-filters` at runtime, exercises ~100
random settings (single/multi/extreme) plus per-paper Summary/
Repositories/Citations expansions (lazy-load timing, no duplicate fetch
on reopen, console/network cleanliness), and requires its report's first
line to read `RUN COMPLETE — <n> tests, <p> passed, <f> failed, seed <s>`.
Both oracles reload their data snapshot fresh before every test case --
this repo is actively edited by concurrent lanes while the harness runs,
so a stale oracle snapshot can otherwise misreport a concurrent commit as
a site bug. Structural failures from either STOP the cutover (round-11
task 2 precedent: `facet_test.py` caught `clearAll()` orphaning
facet-state closures — a class of bug invisible to casual clicking).
