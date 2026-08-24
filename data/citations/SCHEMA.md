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
    "commit": 40,
    "judged": 1045,
    "gscholar": null
  },
  "reception": "The citing literature engages this paper along two ...",
  "citations": [ ... ]
}
```

- `reception` (optional) — a short, hand-written reception summary: what
  kinds of work cite the paper, its notable descendants and users, and any
  distinctive citation pattern. Plain text; paragraphs separated by a
  blank line (`\n\n`). The view renders it at the top of the expanded
  Citations panel. Curated in `data/citations/reception.json` (keyed by
  `bibtexKey`, human-reviewed prose — **never machine-generated into the
  site without review**); every emitter folds that file in, so rebuilding
  a paper's JSON preserves its summary. A paper absent from
  `reception.json` simply has no `reception` field. Pilot-only until the
  human approves the pilot texts.

- `records_raw` — harvested citing records before dedup (provenance only).
- `works` — the **verified citation count**: deduped citing works, with
  `self-version` records (the paper indexed as citing itself) excluded.
  This is the number compared against Google Scholar.
- `commit` — how many of `works` are **COMMIT papers**: citing works with
  Saman Amarasinghe among the authors (the per-entry `commit` field). The
  view reports them separately from external impact; they stay inside
  `works` so the total is comparable to Scholar's. (This replaced the
  earlier `own_group` count, which used the classifier's broader
  any-author-overlap flag.)
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
| `commit` | only when `true` | this citing work is a **COMMIT paper**: Saman Amarasinghe is among its authors, checked over all folded siblings' full author lists. Name rule (identical in every emitter): fold the name to lowercase letters; it is Saman iff it contains `amarasinghe` and either contains `saman` or matches `(^| )s (p )?amarasinghe` — so "Saman", "Saman P.", and "S. Amarasinghe" count while other Amarasinghes (Gayashan, Yasith, …) do not. Drives the COMMIT-papers vs external-impact separation in the view. |
| `flags` | no | union over folded siblings: `own-group` (classifier's broader any-author-overlap flag — kept as classification metadata, no longer drives display), `lineage`, `polluted-contexts`, `critical` |
| `evidence` | yes | evidence tier of the kept sibling: `fulltext` / `abstract+contexts` / `contexts` / `abstract` / `title_only` |
| `cited_by` | yes (nullable) | the citing work's own citation count — OpenAlex `cited_by_count`, falling back to S2 `citationCount` for S2-only records; `null` where neither service resolves it. Maximum over folded siblings. Drives the view's popularity sort; backfilled by `harvest/citations/backfill_cited_by.py` and carried natively by new harvests. |

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
    "halide:pldi:2013":  { "verified": 1483, "gscholar": null,
                           "functions": { "extends": 35, "uses-tool": 77, "...": 0 } },
    "netblocks-pldi24":  { "verified": 4,    "gscholar": null,
                           "functions": { "extends": 1, "exemplifies": 2 } }
  }
}
```

- `functions` — the paper's **external judged** citation counts per FUNCTION
  value (COMMIT papers and unjudged rows excluded; zero-count values
  omitted). Lets the publications page compute the paper's **impact score**
  and the aggregate overview without fetching per-paper files. The impact
  score is `Σ weight(function) × count`, with the weights defined once in
  `citations.js` (`CITATIONS.WEIGHTS`) and mirrored here:

  | function | weight | | function | weight |
  |---|---|---|---|---|
  | extends | 10 | | surveys | 2 |
  | uses-tool | 8 | | supports-claim | 2 |
  | adopts-idea | 8 | | exemplifies | 1 |
  | uses-benchmark | 5 | | detailed-citation | 1 |
  | baseline | 5 | | passing-citation | 0.5 |
  | positions | 3 | | | |

  A row without `functions` has no impact score (`null`); the page's impact
  threshold then hides that paper whenever the threshold is above zero.

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
