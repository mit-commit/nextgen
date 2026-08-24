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
| **artifacts** | `harvest/artifacts/` | **active** — `found.json`/`review.json` built from Crossref+DataCite+OpenAlex (151 DOI'd entries) and a PDF text scan (309 local PDFs); ACM DL badge scraping (route 3) retried with a real headful browser and manual human solving, still fully blocked by Cloudflare — badges remain empty. All 6 `review.json` rows settled (2 promoted to `found.json`, 4 to `settled_not_own.json`); `review.json` is now empty. See `harvest/artifacts/README.md`. |
| **repos** | `harvest/repos/` | **active** — step 1 (in-paper discovery) done: all 353 PDFs scanned, 142 code-host URLs verified into `harvest/repos/mentions.json`, and `harvest/repos/search-plan.json` prepared for the 268 papers with no live repo link. No GitHub searching run yet. |
| **authors** | `harvest/authors/` | **active** — `authors_build.py` parses every `author0` into individual authors, dedupes exactly, enriches from Crossref/OpenAlex, matches `data/people.xml`, and writes `harvest/authors/authors.json` (369 distinct authors) plus `harvest/authors/review.json` (4 flagged near-misses). `enrich_openalex.py` resolves each of the 369 against their own OpenAlex author entity (ORCID or shared-work match, never name alone) into `harvest/authors/enriched.json`; 263/369 resolved so far — 79 pending a rerun once OpenAlex's search endpoint is unblocked (see lane log). |
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
- **idmap-review pass** (task `idmap-review`): resolved the 41
  `data/idmap-review.json` rows by hand. `harvest/idmap_review_fetch.py`
  pulls each candidate DOI's real Crossref record (authors, container, year)
  for side-by-side comparison against the `publications.json` entry;
  `harvest/idmap_review_apply.py` bakes in the ACCEPT/NOTE verdicts and
  applies them (`--write` to commit, dry run otherwise).
  - 12 accepted into `data/idmap.json` with `match: fuzzy_reviewed`: the
    programmatic title-prefix check missed them for mundane reasons (an
    ACM "Perspectives:" prefix, a Crossref title typo, initials vs. full
    names, or -- for `hall:computer:1996`, `lee:micro:2002`,
    `thies:bmc:2007` -- a same-claimed-DOI collision with a reprint/poster
    sibling that `idmap_build.py`'s `dedupe()` correctly refused to pick a
    winner for). Venue+year+authors all independently verified against the
    live Crossref record before accepting, not just against the review
    file's cached summary.
  - 29 left in `data/idmap-review.json`, each with a one-line `note`
    explaining why: most have no real matching candidate (workshop/CIDR/
    NeurIPS papers commonly have no DOI at all, or Crossref's bibliographic
    search only turned up unrelated same-acronym noise). Three
    (`hall:dtj:1998`, `puppin:ijpp:2005`, `thies:recombposter:2006`) are
    reprints/posters/extended versions that share a claimed DOI with one of
    the 12 now-accepted keys -- the DOI's real Crossref record matches the
    *other* key, not these, so they're flagged as probable
    `same_work_as` candidates for a human to fold rather than auto-decided
    here.
  - `data/idmap.json` now has 298 entries (151 exact / 12 fuzzy_reviewed /
    135 no_doi); `data/idmap-review.json` has 29.

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
- 2026-08-24: retried route 3 with real browser access (Playwright, headful
  Chromium, persistent profile). Every attempt — a specific paper DOI, the
  plain dl.acm.org homepage, and two rounds of a human manually trying to
  solve the challenge in the visible window — hit an unclearing Cloudflare
  "Just a moment..." interstitial. Confirmed not a rate/headless-detection
  issue (the user's own normal Chrome loaded IEEE Xplore fine at the same
  time). Stopped per instructions; badges remain unavailable. Separately,
  settled all 6 `review.json` rows by opening each `artifact_url` (Zenodo
  landing page) and comparing title/authors to the paper's own: 2 were the
  paper's own artifact (promoted into `found.json`), 4 were bibliography
  citations to a shared dependency (Shapely or FInAT) and moved to
  `harvest/artifacts/settled_not_own.json`. `review.json` is now empty.
  Details in `harvest/artifacts/README.md`.

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
- **Part 2** (`enrich_openalex.py`): resolves each of the 369
  `harvest/authors/authors.json` people against their own OpenAlex author
  entity — ORCID first (a direct `authors/orcid:<orcid>` lookup, not the
  filter-search form — see below), else a shared-work match: every one of
  the person's papers with an OpenAlex work id (from `data/idmap.json`) has
  its authorship list fetched and checked for the *single* authorship whose
  folded surname + first initial matches the person; people with no
  idmap-anchored paper fall back to an OpenAlex title search. Two or more
  papers pointing at different OpenAlex author ids, or an authorship list
  with two+ matches at the same coarse key, is ambiguous and never
  auto-resolved. For a resolved author: `works_count`,
  `summary_stats.h_index`, and current/last-known affiliation (scored by
  years-persisted across the author's affiliation history, not OpenAlex's
  own "last known" pick, which is known to mis-rank e.g. "Moscow Institute
  of Thermal Technology" above the real MIT on common/ambiguous names) come
  from the author entity; any homepage comes from the *public* ORCID
  record's researcher-urls. Writes `harvest/authors/enriched.json`
  (`{person_id, name, openalex_id, resolution_method, resolution_evidence,
  orcid, affiliation, works_count, h_index, homepage}`, one stub row per
  person including unresolved ones) and appends ambiguous/unresolved/
  affiliation-conflict rows to `harvest/authors/review.json` (tagged
  `openalex_ambiguous` / `openalex_unresolved` /
  `openalex_search_unavailable` / `openalex_affiliation_conflict`) —
  nothing is guessed. Dry-run by default; `--write` to write, `--report` to
  summarize what exists, `--retries N` to cap HTTP backoff attempts.
  - Discovered mid-run that OpenAlex meters *filtered/search* endpoints
    (`authors?filter=...`, `works?search=...`) on a separate, much smaller
    daily USD-credit budget than plain by-ID GETs (`authors/{id}`,
    `works/{id}`) — and that budget was already exhausted (`retry-after`
    ~10h) by the day's citations/artifacts search-endpoint usage before
    this script ran. Fixed the ORCID step to use the direct-ID form
    (`authors/orcid:<orcid>`), which is unaffected and works even now.
    The title-search fallback has no by-ID equivalent and stayed blocked;
    rather than let a person fail there read as a genuine no-match, those
    are now tagged `openalex_search_unavailable` (distinct from
    `openalex_unresolved`) so a rerun after the quota resets retargets
    exactly them, not everyone.
  - First `--write` pass (this exhausted-quota window): 263/369 resolved
    (143 via ORCID, 120 via shared-work); 259 with affiliation, 40 with
    homepage; 5 ambiguous, 22 genuinely unresolved, 79
    `openalex_search_unavailable` pending a rerun once OpenAlex's search
    quota resets; 111 flagged `openalex_affiliation_conflict` (kept in
    `enriched.json` but unverified — mostly a real known-affiliation-at-
    publication-time vs. current-affiliation divergence, not a resolution
    error).

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
- **Abstracts pass** (task `fulltext-abstracts`): for every citing work in
  the same population `harvest_fulltext.py` attempts (all citing works for
  the 5 low-cited pilots, the fixed 300-sample for the 3 high-cited ones)
  that has no cached full text (`status != "ok"`, or never attempted),
  `harvest/fulltext/harvest_abstracts.py` fetches the OpenAlex work record
  and inverts `abstract_inverted_index` into plain text. Written to
  `harvest/fulltext/abstracts/<bibtexKey>.json`, one dict per pilot paper
  keyed by the same slug `harvest_fulltext.py` uses, so it joins by key
  against `harvest/fulltext/<key>/`. Unlike the cached full text, this is
  metadata (title + abstract), so it's committed -- `.gitignore` gained a
  `!harvest/fulltext/abstracts/**` exception to the fulltext lane's
  blanket subdirectory ignore.
  - 982 citing works needed an abstract across the 8 pilots; 528 landed one
    (OpenAlex has no abstract for the rest, or the citing work has neither
    a DOI nor an OpenAlex id to look up at all).
  - Idempotent/resumable like the full-text pass: an already-written slug
    in the output file is skipped on rerun.

## Cross-lane requests

_(none open)_
