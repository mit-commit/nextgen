# Ecosystems VERIFY step -- confirmed tier-2/3 outside-user candidates

Human directive (2026-08-25): tier-2 goes deep for ALL own repos, ranked
by stars x citations for VERIFY *depth* (not selection). Population:
harvest/impactview/ecosystem-measure.json's 71 own repos (52 initially,
+19 from the deep-hunt/halide-import expansion, re-measured by
nextgen-a2 in `4627f08d`).

## Pipeline

1. **Enumerate** (`enumerate_candidates.py`, free/mechanical): real
   candidate identities behind nextgen-a2's dependents-graph + README/
   description-mention counts, PLUS this session's addition -- forks
   pushed >30 days after their own creation, checked against the real
   GitHub compare API for an actual `ahead_by` count (not just a proxy).
   763 candidates across 71 repos, 0 trimmed by the 300-per-repo cap
   (no ecosystem got that large even with fork-divergence added).
2. **Verify** (`verify_ecosystem_candidates.py`, one live model call per
   candidate): classifies into the SDV integration vocabulary
   (`docs/impact-view-design.md`) -- `fork` / `derivative_work` ->
   **Builds on it**, `api_user` / `inherited` -> **Uses the system**,
   `uses_benchmark` -> **Uses its benchmarks** -- or `reject`. Reject
   explicitly covers the biggest false-positive class in the `mentions`
   source (flagged by nextgen-a2 after eyeballing raw candidates):
   curated "awesome-*" list repos, blog posts, and course materials that
   namedrop a project without using its code.

## Result

**266 of 763 candidates confirmed (35%)** as real tier-2 integrations,
across 26 of the 71 own repos (the other 45 -- mostly small thesis repos
-- had zero qualifying candidates from any of the three signals):

| SDV term | unified group | count |
|---|---|---:|
| fork | Builds on it | 160 |
| api_user | Uses the system | 80 |
| derivative_work | Builds on it | 18 |
| inherited | Uses the system | 7 |
| uses_benchmark | Uses its benchmarks | 1 |

Expanded across every paper each own repo maps to (via `data/repos/
papers/*.json`'s own rows, not tier2-priority.md's truncated 3-paper
preview column -- e.g. taco actually maps to 21 papers, streamit to 30),
this is **1,241 (paper, candidate) rows across 103 papers**, written to
`harvest/ecosystems/verified.json` keyed by bibtexKey, same convention as
`harvest/repos/descendants.json` / `own-inventory.json` /
`halide-import.json`. Row shape is pre-mapped to `data/repos/SCHEMA.md`:
`{group, sdv, name, url, stars, desc, own_repo, source, evidence}`.

Confirmed candidates by own repo (top 10 of 26):

| own repo | confirmed |
|---|---:|
| halide/Halide | 88 |
| jansel/opentuner | 41 |
| DynamoRIO/dynamorio | 35 |
| tensor-compiler/taco | 17 |
| dmtcp/dmtcp | 16 |
| ithemal/Ithemal | 11 |
| Tiramisu-Compiler/tiramisu | 8 |
| exaloop/codon | 7 |
| ithemal/bhive | 7 |
| weld-project/weld | 6 |

## Notes

- **Cost**: live Sonnet calls, ~763 total across two runs (one bug-caused
  partial re-run of the 500 already-rejected candidates from the first
  52-repo pass, see below) -- well under the standing $20 auto-submit
  line.
- **Bug found and fixed mid-run**: the first version only recorded a
  `_done_key` for *confirmed* candidates (embedded in `verified.json`'s
  rows), so re-running the script to pick up the 19 newly-measured repos
  re-verified all 500 previously-*rejected* candidates too (no record of
  "already checked, rejected" existed anywhere). Fixed by adding
  `harvest/ecosystems/verify_seen.json`, a flat done-key set updated
  regardless of `--write` (the model call, and its cost, happens whether
  or not the result gets persisted -- a dry run must not be re-billable
  either). Caught this by noticing the second run was reprocessing
  candidates already logged as rejected in the first run's transcript,
  killed it, patched, reran -- no bad data was written, just some
  duplicate spend on candidates already known to be rejects.
- **2 of 763 candidates are still unresolved** (unparseable model
  output on both runs) -- rerunning the script will retry just those
  two; low enough to not block delivery.
- Two independent MEASURE passes happened in parallel this round (this
  session's, dropped after nextgen-a2's landed first as `ba11eb56`) --
  see the cross-session log in `docs/LANES.md` for how that was
  reconciled. `harvest/ecosystems/measure_candidates.py` /
  `candidates-report.md` / `measure_candidates_scratch.json` in this
  directory are that dropped pass's leftovers, kept only as scratch
  (not the canonical measure artifact -- `harvest/impactview/
  ecosystem-measure.json` is).
