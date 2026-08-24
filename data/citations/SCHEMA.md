# data/citations/ — per-paper citation data for the site

This directory feeds the publications page's citation view. The design that
consumes it is `docs/citation-design.md`; the reference implementation that
emits it for the 8 pilot papers is `prototype/build_pilot_data.py`. The
corpus-wide merge script (classify-corpus task) must emit exactly this shape
for every other paper.

Schema version: **1**. Any breaking change bumps `schema` in every file and
this heading.

## Files

| file | written by | read by |
|---|---|---|
| `<bibtexKey>.json` | merge script (pilot papers: `prototype/build_pilot_data.py`) | citation view, on expand only |
| `index.json` | merge script (every run, all papers) | publications page, once at load |
| `gscholar.json` | **the human, by hand** — never a script | merge script (folds counts into the other two) |
| `SCHEMA.md` | design lane | you |

Filenames use the `bibtexKey` verbatim (it is already filesystem-safe:
letters, digits, `:`, `-`, `.`, `_`).

## `<bibtexKey>.json` — one paper's citations

```json
{
  "schema": 1,
  "key": "halide:pldi:2013",
  "generated": "2026-08-24",
  "codebook": "0.2",
  "counts": {
    "records_raw": 1706,
    "works": 1483,
    "own_group": 43,
    "judged": 1045,
    "gscholar": null
  },
  "citations": [ ... ]
}
```

- `records_raw` — harvested citing records before dedup (provenance only).
- `works` — the **verified citation count**: deduped citing works, with
  `self-version` records (the paper indexed as citing itself) excluded.
  This is the number compared against Google Scholar.
- `own_group` — how many of `works` carry the `own-group` flag (author
  overlap with the paper). The view reports them separately from external
  impact; they stay inside `works` so the total is comparable to Scholar's.
- `judged` — works with a real FUNCTION judgment (not `unknown`/`unclassified`).
- `gscholar` — the human-supplied Google Scholar count for this paper, or
  `null` if none has been supplied. Copied verbatim from `gscholar.json` by
  the merge script. **Convenience copy only, and it may lag**: the merge
  script rewrites a paper's file only when that paper is reprocessed, while
  `index.json` refreshes every paper's figure on every run — so `index.json`
  is authoritative for display, and the view reads the Scholar figure from
  its index row, falling back to this field only if the row lacks one.

**Everything else is derived client-side.** Function/centrality/flag
summaries are counted from `citations[]` in the browser; do not add summary
blocks here.

### `citations[]` entries

One entry per deduped citing work, sorted by FUNCTION priority order, then
year descending, then title. Omit a field rather than writing `null`/empty.

| field | required | meaning |
|---|---|---|
| `title` | yes | citing work's title (`"Untitled"` if the record has none) |
| `function` | yes | codebook v0.2 FUNCTION value, or `unknown` / `unclassified` |
| `split` | yes | `"detailed"`, `"passing"`, or `null` (mapping below) |
| `year` | no | publication year |
| `venue` | no | venue string as harvested |
| `authors` | no | display string: first three authors, then `" et al."` |
| `url` | no | one link: `https://doi.org/<doi>`, else the OpenAlex work URL, else the Semantic Scholar page |
| `centrality` | judged only | `core` / `engaged` / `peripheral` / `unknown` |
| `confidence` | judged only | `high` / `medium` / `low` |
| `secondary` | no | lower-priority FUNCTION values that also apply |
| `flags` | no | union over folded siblings: `own-group`, `lineage`, `polluted-contexts`, `critical` |
| `evidence` | yes | evidence tier of the kept sibling: `fulltext` / `abstract+contexts` / `contexts` / `abstract` / `title_only` |

Judgment notes (the audit trail) deliberately do **not** ship to the site;
they stay in `harvest/taxonomy/`.

### The detailed/passing split

`split` is precomputed so the page never hard-codes taxonomy knowledge:

- `"detailed"` — `extends`, `uses-tool`, `adopts-idea`, `uses-benchmark`,
  `baseline`, `positions`, `surveys`, `supports-claim`, `detailed-citation`.
  Every one of these engages the paper specifically.
- `"passing"` — `exemplifies`, `passing-citation`. List membership: the cite
  is one item among several works cited together.
- `null` — `unknown` (evidence insufficient) and `unclassified` (title-only,
  never judged). The view reports these as "not yet judged", never folds
  them into either side.

### Dedup rule (human ruling, 2026-08-24)

Fold same-work records by normalized title (lowercase, strip non-alphanumerics;
records with no title never fold), keep the **highest-evidence** sibling
(tier order above; ties broken by judged-over-unjudged, then has-DOI, then
slug). Union the siblings' flags; fill missing bibliographic fields from any
sibling. If any sibling is `self-version`, drop the whole group.

## `index.json` — what the publications page loads

```json
{
  "schema": 1,
  "generated": "2026-08-24",
  "papers": {
    "halide:pldi:2013":  { "verified": 1483, "gscholar": null },
    "netblocks-pldi24":  { "verified": 4,    "gscholar": null }
  }
}
```

One small file, fetched once by the publications page. A paper appears here
iff `<bibtexKey>.json` exists; presence is what turns on the paper's
"Citations" toggle. **Displayed count = `max(verified, gscholar ?? 0)`** —
computed in JS, not stored, so neither number is ever overwritten by the
other and both can be shown side by side in the expanded view.

## `gscholar.json` — human-supplied Scholar counts

```json
{
  "halide:pldi:2013": { "count": 2417, "date": "2026-08-24" }
}
```

Keys are `bibtexKey`s; papers without a scrape are simply absent. The human
pastes numbers from a Google Scholar profile scrape every few months, then
reruns the merge script, which copies them into `index.json` and each
paper's `counts.gscholar`. Scripts must never write this file. (The count
shown above is an example shape, not a real scrape.)

## Refresh workflow (every few months)

1. Harvest new citing works: `harvest/citations/harvest_citations.py`
   (both passes) — existing lane, incremental.
2. Classify the new records: classify-corpus pipeline (only unclassified
   records are submitted).
3. Update `gscholar.json` by hand from a fresh Scholar scrape.
4. Run the merge script. It rewrites `<bibtexKey>.json` for papers with new
   records and always rewrites `index.json` (including gscholar refreshes).
5. Commit `data/citations/`. Nothing on the site itself changes.

Adding a brand-new paper = adding it to `data/publications.json` and
`data/idmap.json` as today; it gets a citation view automatically the first
time steps 1–4 give it an `index.json` row.
