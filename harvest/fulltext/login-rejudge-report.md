# Login-PDF ingestion + rejudge report (2026-08-25)

Source: `~/workspace/nextgen-fulltext` (23 publisher PDFs fetched via the
human's institutional login, working through `login-worklist.md`; 3
Elsevier worklist rows had no PDF -- inaccessible or skipped).

## Extraction

- **23/23 PDFs extracted successfully** (`harvest/fulltext/ingest_manual_pdfs.py`,
  pypdf, `errors='surrogateescape'` write, 2,000-char floor matching
  `harvest_fulltext.py`'s convention).
- 0 failed to extract, 0 fell below the 2,000-char floor. Extracted text
  ranged 20,101–137,334 characters.
- A citing DOI can cite more than one corpus paper (one CGO'26 survey
  cites 9 of ours), so the 23 texts covered **54 (key, slug) pairs**
  across the corpus: 18 pilot, 36 non-pilot.

## Bug found and fixed

`curate/classify_citations.py`'s full-text evidence packer was head-
truncating to 4,000 characters -- dead code until this task, since no
non-pilot paper had ever had cached full text before. For a real paper the
citation is typically in the related-work section, well past that point:
confirmed directly on two rows where the actual "StreamIt" mention sat at
character ~55,000 of a 68,964-character paper, outside the sent window.
Replaced with `windowed_fulltext()`: search in tiers (project name, then
author surnames, then distinctive title words, stopping at the first tier
with a real hit so a generic word never dilutes a real match) and send
excerpts around the actual mentions. The affected non-pilot batch was
discarded without collecting and resubmitted once fixed.

## Re-judged

All 54 rows:
- **18 pilot rows** — `curate/rejudge_pilots_with_fulltext.py`, live calls
  reusing `classify_citations.py`'s exact codebook/prompt/validation,
  patched directly into `harvest/taxonomy/pilot-classifications.json`
  (pilots are otherwise excluded from the normal pipeline, but a genuine
  evidence upgrade earns a rejudge).
- **36 non-pilot rows** — normal Batch API pipeline (~$0.32, well under
  the $20 auto-submit line).

## Changes

| | rows | changed (function or centrality) | flip rate |
|---|---|---|---|
| pilot | 18 | 17 | 94% |
| non-pilot (had a prior judgment) | 35 | 19 | 54% |
| non-pilot (newly classified, was title-only) | 1 | — | — |
| **total (rows with a prior judgment)** | **53** | **36** | **68%** |

Confidence jumped to high/medium on nearly every changed row -- these were
previously low-confidence, contexts-only judgments; real full text let the
model see the actual citing sentence instead of a bare S2 snippet.

The one row that stayed low-confidence (`taylor:micro:2002` via
`10.1145/1278480.1278511`) is correct behavior, not a bug: the project
name "Raw" is a common English word, the keyword search caught an
unrelated mention elsewhere in the paper, and the model correctly declined
to force a function onto evidence it recognized as not actually about our
paper.

## Verdict: is a larger login fetch worth it?

**Yes.** A 68% flip rate on rows that were already judged (not just newly
classified) is a strong signal that thin contexts-only evidence is
systematically under-informative for this corpus, and that a broader pass
through `harvest/fulltext/login-worklist.md` (or an extended version of
it) would meaningfully improve classification quality corpus-wide.

## Merged

`curate/merge_taxonomy.py --write` folded the 36 non-pilot rows into
`data/citations/` (121 entries now show `evidence: "fulltext"`, including
dedup groups where the fulltext-tier sibling won evidence rank). The 18
pilot rows are written to `pilot-classifications.json` but still need
`prototype/build_pilot_data.py` rerun (site-citations lane) to reach the
site's pilot `data/citations/<bibtexKey>.json` files.

Full narrative and file-by-file detail in `docs/LANES.md`'s fulltext and
taxonomy lane logs (2026-08-25, "Manual fulltext ingestion" / "Fulltext
rejudge").
