# LANES.md — the parallel-session protocol

Several Claude sessions work this repo at the same time. They do not see each
other's context, so the only thing keeping them from overwriting each other is
this file. Read it before you touch anything.

## The protocol

1. **Claim your paths before you write them.** A lane owns a set of file paths.
   The claim is recorded in the table below, and it lands **in the same commit as
   that lane's first change** — not a commit earlier, not a commit later. A claim
   that is not pushed does not exist.
2. **Never write a path another lane claims.** Not "just this once", not a
   one-line fix, not a typo. If a change you need lives inside someone else's
   claim, stop and raise it — open an issue, or leave a note under
   [Cross-lane requests](#cross-lane-requests) and let that lane make the change.
3. **Refresh before you start any work:**

       git fetch && git log --oneline origin/main -10

   Do this at the start of every session and again before every push. The lane
   table you are reading may already be stale.
4. **A rejected push is a collision, not a retry.** If you get a non-fast-forward
   rejection, or you committed against a SHA that is no longer the tip of
   `origin/main`, another lane landed work under you. Do not `--force`. Do not
   loop on `pull --rebase` until it goes through. Stop, read what landed
   (`git log --oneline HEAD..origin/main`), confirm it does not touch your
   claimed paths, and only then rebase and push.

Unclaimed paths at the repo root (`index.html`, `README.md`, `assets/`, the
existing `data/*.xml`, `papers/`) belong to nobody. Raise before writing them.

## Lanes and claims

| Lane | Claimed paths | Status |
|---|---|---|
| **setup** | `data/idmap*.json`, `harvest/idmap*`, `docs/LANES.md` | **active** — ID map built for all 327 entries of `data/publications.json`; `data/idmap.json` and `data/idmap-review.json` landed. |
| **citations** | `harvest/citations/` | **active** — `harvest_citations.py` (two passes: `--pass openalex`, `--pass s2`) has harvested citing-work metadata for all 151 `data/idmap.json` entries with an id into `harvest/citations/<bibtexKey>.json`; 23,154 merged citing works. |
| **artifacts** | `harvest/artifacts/` | **active** — `found.json`/`review.json` built from Crossref+DataCite+OpenAlex (151 DOI'd entries) and a PDF text scan (309 local PDFs); ACM DL badge scraping (route 3) is blocked (403). See `harvest/artifacts/README.md`. |
| **repos** | `harvest/repos/` | **active** — step 1 (in-paper discovery) done: all 353 PDFs scanned, 142 code-host URLs verified into `harvest/repos/mentions.json`, and `harvest/repos/search-plan.json` prepared for the 268 papers with no live repo link. No GitHub searching run yet. |
| **authors** | `harvest/authors/` | **active** — `authors_build.py` parses every `author0` into individual authors, dedupes exactly, enriches from Crossref/OpenAlex, matches `data/people.xml`, and writes `harvest/authors/authors.json` (369 distinct authors) plus `harvest/authors/review.json` (4 flagged near-misses). |
| **fulltext** | `harvest/fulltext/` | **active** — `harvest_fulltext.py` fetches full text of citing works for 8 pilot papers via free routes (OpenAlex OA location, arXiv, Unpaywall, PMC). Cached text/sidecars are gitignored; `harvest/fulltext/manifest.json` (committed) has per-paper yield stats. Does not touch `harvest/citations/`. |

`docs/LANES.md` is itself a shared file. Every lane appends to its own row and
to its own log section — nothing else. Two lanes editing their own separate rows
in the same table rebase cleanly; two lanes rewriting the table do not.

`data/publications.json` is the input to every lane and is **read-only for all of
them**. Nothing in a harvest lane edits it.

Every lane reads `data/idmap.json` and should treat it as its join key: it maps
`bibtexKey` to DOI, OpenAlex work id, and Semantic Scholar paperId. Do not
re-resolve identifiers in your own lane — if a key you need is missing or wrong,
raise it to the setup lane.

## Lane logs

### setup

- Cloned from `mit-commit/commit-website`; origin repointed at `mit-commit/nextgen`.
- Wrote this file.
- `harvest/idmap_build.py` resolves DOI → OpenAlex → Semantic Scholar for all 327
  publications and writes `data/idmap.json` plus `data/idmap-review.json`.
  Dry-run by default; `--write` to write, `--report` to summarize what exists.

### citations

- `harvest/citations/harvest_citations.py` runs as two independent passes so
  the fast OpenAlex side never blocks on the slower, more rate-limited S2
  side:
  - `--pass openalex`: for every entry with an OpenAlex id, pages
    `works?filter=cites:<id>` and writes `harvest/citations/<bibtexKey>.json`
    fresh — `{counts: {openalex, s2: 0}, citing: [...]}`. Skips a key whose
    file already exists.
  - `--pass s2`: for every entry with an S2 id, pages
    `/paper/<id>/citations` (fields include `isInfluential`, `intents`,
    `contexts`) and merges into the *existing* file by DOI, filling in `s2`
    plus those three fields on matched records and appending s2-only
    records otherwise. Completion is tracked per key in
    `harvest/citations/.s2_state.json`, separately from the file's
    existence, so a merge that fails partway (429s exhausting retries) is
    retried whole next run rather than marked done on partial data.
  - Both keyless at 1 req/s with 429 backoff by default; read
    `OPENALEX_API_KEY` / `S2_API_KEY` from the environment on every request.
    HTTP responses are cached under `harvest/citations/cache/` (gitignored).
  - All 151 entries with an id are harvested: 14,851 OpenAlex citing works,
    18,156 S2 citing works, 23,154 after merging on DOI. 2 papers (both
    2025/2026) have zero citations so far.

### artifacts

- `harvest/artifacts/metadata_scan.py` queries Crossref/OpenAlex/DataCite per
  DOI in `data/idmap.json`; `harvest/artifacts/scan_pdfs.py` scans local
  `papers/**.pdf` text for artifact/Zenodo/FigShare mentions; `merge.py`
  combines both into `found.json`/`review.json`. Raw unfiltered signal kept
  in `harvest/artifacts/raw/` for provenance.
- ACM DL landing-page scraping (route 3, badge markup for the 87 `10.1145`
  DOIs) returned 403 on the first request and was not retried further, per
  the "stop on any 403/challenge" instruction — badge names are unavailable
  this pass. Details and the precision rules used to keep the PDF/DataCite
  scan from drowning in citation-noise false positives are in
  `harvest/artifacts/README.md`.
- Result: 10 confirmed artifacts, 6 flagged for review, 0 badges recovered.

### repos

- Step 1 only, no GitHub searching. `harvest/repos/` holds a four-stage pipeline
  (`extract_candidates.py` → `verify.py` → `repair.py` → `build_outputs.py`);
  see `harvest/repos/README.md`.
- `mentions.json` keys all 327 `bibtexKey`s; 59 have a live in-paper repo URL,
  1 has only a dead one, 267 have none. Every URL was checked with a GET and
  carries its status, the line it was printed on, and `final_url` when the
  request was redirected (that is how repo renames surface).
- PDF layout artifacts (URLs wrapped across lines, footnote markers glued on,
  `%7B%22` escapes) are repaired where they resolve and otherwise recorded in
  `mentions-pruned-variants.json` rather than reported as dead links.
- `search-plan.json` carries keyword candidates only — author surnames,
  username guesses, lab orgs observed elsewhere in the corpus, project and
  software names, plausible repo spellings. Nothing in it has been searched.

### authors

- `harvest/authors/authors_build.py`: parses `author0` on every publication
  ("Last, First and Last, First" or a bare "First Last") into one appearance
  per author, in paper order. Dedupes on the exact normalized name only —
  nothing is merged automatically. Distinct names that share a folded surname
  + first initial are compared and, when they look like the same person
  written two ways (an initial vs. a full given name, or an accent/case
  difference), flagged to `harvest/authors/review.json` — never auto-merged.
  For every `data/idmap.json` entry with a DOI, fetches the Crossref work and
  the OpenAlex work's `authorships`, matches their author lists back onto our
  parsed names by folded surname + initial, and attaches ORCID and the most
  recent affiliation. Matches names against `data/people.xml` to flag COMMIT
  members: exact (folded) match, or a surname+initial match that is
  unambiguous on both sides and given-name-compatible — deliberately *not* a
  bare surname+initial match, since e.g. "Jang Kim" and "Jason Kim" (two
  distinct RAW-project authors, 1997–2004) both coarse-match a current,
  unrelated member ("Juni C. Kim"); when our own author list has more than
  one distinct person at that coarse key, the COMMIT match is skipped for all
  of them. Writes `harvest/authors/authors.json`:
  `{person_id, name, variants[], papers[], orcid, latest_affiliation,
  commit_member}`. Dry-run by default; `--write` to write, `--report` to
  summarize what exists. HTTP responses are cached under
  `harvest/authors/cache/` (gitignored).

### fulltext

- Pilot set (8 papers): the 3 highest-cited entries in `harvest/citations/`
  by `counts.openalex` (`thies:cc:2002`, `taylor:micro:2002`,
  `halide:pldi:2013`), plus 5 named low-cited papers resolved to
  `bibtexKey`s in `data/publications.json` (`netblocks-pldi24`,
  `levison:istas:2002`, `amarasinghe:ijpp:2005`, `thies:toplas:2007`,
  `petkov:ipdps:2002`).
- `harvest/fulltext/harvest_fulltext.py` reads each pilot's citing list from
  `harvest/citations/<bibtexKey>.json` — every citing work for the 5
  low-cited papers, a `random.Random(42)` sample of 300 for each high-cited
  one. For each, tries free-text routes in order (OpenAlex work's
  `best_oa_location.pdf_url`, then an arXiv location on that work — via
  `pdf_url`, an `arxiv.org/abs/` landing page, or the `10.48550/arxiv.*` DOI
  itself, since OpenAlex often lists the arXiv source without a `pdf_url` —
  then `api.unpaywall.org`, then Europe PMC's render endpoint keyed off
  `ids.pmcid`), stopping at the first route whose extracted text (via
  pypdf) reaches 2,000 chars. A citing work with neither a DOI nor an
  OpenAlex id can't be looked up at all (`no_id`).
- Writes `harvest/fulltext/<bibtexKey>/<doi-slug>.txt` + a `.json` sidecar
  (`{doi, route, chars, status}`) per citing work; skipped/resumed on rerun
  by sidecar presence. `harvest/fulltext/` (except `manifest.json`) is
  gitignored — cached publisher text must not be pushed.
- Yield is low (paywalls/bot-walls dominate `fetch_fail`, e.g. ScienceDirect
  and ACM DL 403 on scripted requests even for Unpaywall-flagged-OA links;
  no evasion attempted). Full results in `harvest/fulltext/manifest.json`.
- Did not touch `harvest/citations/` (owned by another lane).

## Cross-lane requests

_(none open)_
