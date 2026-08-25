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
| **setup** | `data/idmap*.json`, `harvest/idmap*`, `docs/LANES.md` | **active** — all 327 entries of `data/publications.json` resolved; `data/idmap-review.json` is now empty. |
| **citations** | `harvest/citations/` | **active** — `harvest_citations.py` (two passes: `--pass openalex`, `--pass s2`) has harvested citing-work metadata for every `data/idmap.json` entry with an id: 151 keys in the first sweep, plus 26 keys whose ids only landed with the later idmap-review resolutions (task `citations-s2-continue`, 2026-08-24) — 177 files, 26,192 merged citing works, all S2-enrichable keys enriched. |
| **artifacts** | `harvest/artifacts/` | **active** — `found.json`/`review.json` built from Crossref+DataCite+OpenAlex (151 DOI'd entries) and a PDF text scan (309 local PDFs); ACM DL badge scraping via browser automation stayed blocked (see log), but a user-supplied `acm_badges.json` (badge markup for all 92 `10.1145` DOIs) was ingested — `found.json` now has 23 entries, 20 with a real ACM badge. All 6 `review.json` rows settled (2 promoted to `found.json`, 4 to `settled_not_own.json`); `review.json` is empty. See `harvest/artifacts/README.md`. |
| **repos** | `harvest/repos/` | **active** — step 1 (in-paper discovery) done: all 353 PDFs scanned, 142 code-host URLs verified into `harvest/repos/mentions.json`, and `harvest/repos/search-plan.json` prepared for the 268 papers with no live repo link. Step 2 (task `repos-search step 2`, 2026-08-24) complete: `search_github.py` scored candidates via the GitHub REST API for all 268 -- 217 strong, 27 weak-only, 24 none -- into `harvest/repos/candidates.json`. Auto-accepts nothing; see lane log. |
| **authors** | `harvest/authors/` | **active** — `authors_build.py` parses every `author0` into individual authors, dedupes exactly, enriches from Crossref/OpenAlex, matches `data/people.xml`, and writes `harvest/authors/authors.json` (369 distinct authors) plus `harvest/authors/review.json` (221 flagged rows: 4 name-variant near-misses + 217 from the enrich pass). `enrich_openalex.py` resolves each of the 369 against their own OpenAlex author entity (ORCID or shared-work match, never name alone) into `harvest/authors/enriched.json`; 287/369 resolved (task `authors-enrich verify`, 2026-08-24 — OpenAlex's search quota reset, rerun recovered 24 of the 79 previously-blocked people; 77 genuinely unresolved, 5 ambiguous, 0 still search-blocked; see lane log). |
| **site-citations** | `docs/citation-design.md`, `data/citations/SCHEMA.md`, `data/citations/gscholar.json`, `data/citations/reception.json`, the 8 pilot `data/citations/<bibtexKey>.json` files, `data/citations/index.json` (bootstrap; merge script owns non-pilot rows), `prototype/`, and — for the citation view only — `publications.html`, `assets/js/citations.js`, the citation-view additions in `assets/js/publications.js` + `assets/css/style.css` | **active** — the per-paper citation section, designed, prototyped, human-APPROVED, and now **integrated into `publications.html`** (task `site-integration`, 2026-08-24): one small `index.json` fetch at page load turns on a "Citations (N)" toggle for the 150 papers with data files; per-paper data lazy-loads on first expand. Three sort modes (Impact / Recency / Popularity) with a headers on/off toggle — all three render uniform collapsible groups, collapsed by default with counts (categories / years / count buckets); expanded Summary and Citations panels sit in a lightly-outlined shaded box; Recency and Popularity incorporate own-group citations chip-marked, Impact keeps them in their separate section. `prototype/` kept as reference. `data/citations/SCHEMA.md` remains the contract; non-pilot `<bibtexKey>.json` files belong to the classify-corpus merge. |
| **fulltext** | `harvest/fulltext/` | **active** — `harvest_fulltext.py` fetches full text of citing works for 8 pilot papers via free routes (OpenAlex OA location, arXiv, Unpaywall, PMC). Cached text/sidecars are gitignored; `harvest/fulltext/manifest.json` (committed) has per-paper yield stats. Does not touch `harvest/citations/`. Task `abstracts-all` (2026-08-24, complete): `harvest_abstracts_all.py` extended the abstract harvest from the 8 pilots to every non-pilot citing work, batch-fetched via OpenAlex's OR filter (100 ids/request) rather than one-by-one -- 167 papers, 21,545 citing works, 14,014 gained a real abstract (65%). Deliberately left the 3 sampled high-cited pilots' abstract files untouched (they're inert for reclassification -- pilots are permanently excluded from `curate/classify_citations.py`'s population). Fed the taxonomy lane's rejudge sweep (see its log). |
| **taxonomy** | `harvest/taxonomy/`, `docs/taxonomy-draft.md`, `curate/`, `data/citations/<bibtexKey>.json` for non-pilot papers, `data/citations/index.json` (owns it after the first merge run, preserving the pilot rows) | **active** — pilot human-reviewed (approved with one amendment, applied 2026-08-24 as codebook v0.2): two-dimension citation taxonomy (FUNCTION × CENTRALITY, plus flags/evidence-tier/confidence per row) drafted from a stratified deep read and applied to all 4,629 citing-work records of the 8 pilot papers (2,751 judged; 1,878 title-only left `unclassified`). v0.2 replaced residual `mentions` with `detailed-citation`/`passing-citation` and re-split all 701 affected rows (349/352). Deliverables: `docs/taxonomy-draft.md` (codebook, worked examples, per-pilot distributions, S2 `isInfluential`/`intents` comparison) + `harvest/taxonomy/pilot-classifications.json`. Built `curate/classify_citations.py` (task `classify-corpus`, Anthropic Batch API) and `curate/merge_taxonomy.py` (emits data/citations/SCHEMA.md's shape for non-pilot papers only, never touching the pilot files or gscholar.json). Dry-run cost estimate reported (~$69/10,021 requests), approved by the human; actual submit came in at 11,082 requests / 28 batches (see lane log) — all collected, 22 rule-level rejections fixed by a parser/repair fix and recovered, 11,082/11,082 classified. `merge_taxonomy.py --write` folded all 142 non-pilot papers into `data/citations/<bibtexKey>.json` + `index.json` (144 papers total, pilot rows and files untouched). Task `classify-corpus` complete. Task `cited_by verify`: harvest-layer backfill was site-citations/nextgen-a2's work (see their log); `merge_taxonomy.py` updated to set `cited_by` (max over dedup siblings, always present per SCHEMA.md) and rerun `--write` — all 142 non-pilot files now carry it, pilot files/gscholar.json verified untouched. Task `commit-papers redefine` (2026-08-24): added `is_saman()` (byte-identical to `prototype/build_pilot_data.py`'s copy) and replaced `own_group`/`n_own` with `commit`/`n_commit` per the human's schema refinement (COMMIT papers = Saman-authored citing works, not author-overlap-with-the-cited-paper); verified against both pilot files' `counts.commit` before rerunning `--write`. Task `abstracts-all + rejudge sweep` (2026-08-24, complete): after the abstracts-all pass (fulltext lane), cleared 603 existing staging records that were `function: unknown` or `confidence: low` and had just gained a real abstract, so they'd regenerate with better evidence; previously-title-only rows needed no clearing (`load_candidates()` picks up an evidence-tier upgrade automatically). Dry-run came to 7,766 requests / ~$56 (over the $20 auto-approve line) — human approved. Hit a duplicate-`custom_id` Batch API rejection mid-submission (3 literal duplicate citing records in `harvest/citations/`, same DOI twice with whitespace-differing titles); fixed by deduping `load_candidates()` on `(key, slug)`, collected the 1,600 already-sent requests first so they wouldn't be re-billed, then resubmitted the remaining 6,166 clean. Also fixed two more model-output quirks (bareword `"confidence": low`, an occasionally-omitted `flags` field) via the same parser/`repair()` pattern as classify-corpus. Final: 18,242 total staging records, folded into 165 non-pilot `data/citations/` files (up from 142 -- 23 papers with zero prior judgeable content, several from `idmap-review-rest`'s OpenAlex-only resolutions, now have their first citation page) totaling 18,554 works, 13,024 judged (70.2%, up from the classify-corpus baseline). `index.json` now has 173 papers. |

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
- **idmap-review-rest** (task `idmap-review-rest`, 2026-08-24): finalized the
  29 remaining rows. For each, `harvest/idmap_review_finalize.py`
  independently re-checked the top candidate's OpenAlex-by-DOI record
  (venue+year+authors, corroborating the earlier Crossref-based note) and,
  new this pass, searched OpenAlex directly for the publication's *own*
  title -- workshop/CIDR/NeurIPS papers often have an OpenAlex work record
  with no DOI at all, which the original build never checked since it only
  resolved via DOI. 13 rows had a genuine own record (exact title, full
  author-list match, hand-verified by fetching each work by id): 12 with no
  DOI (`kind: "openalex_only"`) and one, `tiramisu-auto`, with a real arXiv
  DOI (`kind: "doi"`) that OpenAlex's title search surfaced but the DOI-based
  build had no way to find. The 3 rows that share a `claimed_doi` with an
  already-accepted sibling key (`hall:dtj:1998`, `puppin:ijpp:2005`,
  `thies:recombposter:2006`) were written as `kind: "same_work_as"` pointing
  at that sibling. The remaining 13 got no corroborating record from either
  check and were written `kind: "no_doi"` with the existing note preserved.
  `data/idmap.json` now covers all 327 `data/publications.json` entries (164
  doi / 147 no_doi / 13 openalex_only / 3 same_work_as); `data/idmap-review.json`
  is empty.

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
- **Continuation sweep** (task `citations-s2-continue`, 2026-08-24): the
  idmap-review passes had resolved ids for 26 more keys *after* the first
  harvest (12 `fuzzy_reviewed`/`doi`, 13 `openalex_only`, `tiramisu-auto`),
  so those keys had no citations file at all — the queue task's original
  "partial S2 coverage" framing was already stale, since every existing
  file was fully enriched. Ran both passes; both completed with zero
  failures (S2 429s retried through). 26 new files, 3,038 merged citing
  records (largest: `wilson:sigplan:1994` 803, `hall:computer:1996` 644,
  `stephenson:pldi:2000` 309); 12 of the 26 had S2 ids and are enriched
  with contexts/intents/isInfluential. Corpus now 177 files / 26,192
  merged citing works. These records postdate classify-corpus's submitted
  request list — per the queue they belong to the later straggler sweep.
- **cited_by backfill** (task `cited-by-backfill`, 2026-08-24): the original
  harvest's `select=` never requested citation counts, so the queue's
  "mostly already stored" assumption did not hold — this was a real fetch.
  `harvest/citations/backfill_cited_by.py` resolves every citing record's
  own citation count: OpenAlex `cited_by_count` batched 50 ids/request via
  `filter=openalex_id:` (12,791 ids) and `filter=doi:` (2,987 DOI-only
  rows), then S2 `citationCount` via POST /paper/batch (4,007 S2-only
  rows). 316 requests, 0 failures; `cited_by` set on 26,015/26,192 records
  (99%), null on 177 (no resolvable id). Idempotent; --refresh re-fetches.
  `harvest_citations.py` now requests `cited_by_count`/`citationCount`
  natively (merge prefers the OpenAlex figure), so future harvests carry
  `cited_by` without the backfill. Feeds the citation view's popularity
  sort per the 2026-08-24 sort-mode ruling.

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
- 2026-08-24 (later same day): ingested a user-supplied
  `~/Downloads/acm_badges.json` (badge markup + links for all 92 `10.1145`
  DOIs, obtained outside this session after the browser route stayed
  blocked). Parsed real badge-type strings into `badges[]`
  (`badge_source: "acm_dl"`) on 20 papers, added 11 brand-new `found.json`
  entries the PDF/DataCite scan had missed entirely, and merged raw
  supplementary links into a new `acm_dl_links[]` field (filled
  `artifact_doi`/`artifact_url` where empty, excluding six links already
  known to be citations to a shared dependency, not the paper's own
  artifact). `found.json` now has 23 entries. Details in
  `harvest/artifacts/README.md`.

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
- **Step 2** (task `repos-search step 2`, 2026-08-24): `search_github.py`
  searches GitHub for each of the 268 `search-plan.json` papers. Two
  sources per paper: direct `GET /repos/{owner}/{repo}` existence checks
  (core API, 5000/hr) over `(owner, repo)` pairs built by crossing
  `known_owners_same_authors` + `username_candidates` + `lab_org_candidates`
  with `repo_name_candidates` (capped at 30 pairs/paper), plus one
  `GET /search/repositories` call per paper (search API, 30/min) on the
  project/software name to catch repos under an unguessed owner/name. Every
  repo found either way is scored: repo name / description match,
  owner match (including a fuzzy first-initial+surname check —
  `bthies` for "Bill Thies" — since the pre-generated username list
  doesn't enumerate every handle shape), created-date proximity to
  publication year, and a README-contains-title/author-surname check
  (one extra core-API call per candidate). Confidence: high (score≥5),
  medium (≥3), low (else). **Auto-accepts nothing** — writes the top 3
  scored candidates per paper with full evidence to
  `harvest/repos/candidates.json`; a human decides what to promote.
  Result: 217 papers with a high/medium top candidate, 27 with only a
  low-confidence one, 24 with none found (spot-checked as plausible —
  theses/position papers with no released code). API responses cached
  under `harvest/repos/_ghcache/` (gitignored, ~29 MB, 5,230 core +
  78 search requests for the full run).

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
- **authors-enrich verify** (task `authors-enrich verify`, 2026-08-24):
  confirmed completeness first — all 369 `authors.json` people have an
  `enriched.json` row (0 missing, 0 extra) and `review.json`'s 221 rows
  (4 original name-variant flags + 217 from the enrich pass) exactly match
  the counts documented above. The one real gap was the 79
  `openalex_search_unavailable` stragglers; OpenAlex's search quota had
  since reset (confirmed working during the same day's `idmap-review-rest`
  task), so reran `enrich_openalex.py --write` in full. 287/369 resolved now
  (143 orcid / 144 shared-work, +24 recovered from the stragglers); 77
  genuinely unresolved, 5 ambiguous, 0 still search-blocked; 270 with
  affiliation, 42 with homepage. `affiliation_conflict` unchanged at 111
  (unrelated to the quota issue, still unverified). Full rerun rather than
  a targeted subset since the script has no partial-rerun mode and the
  other 290 people were fast cache hits (792 cached / 196 net requests
  total).

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

### taxonomy

- **Pilot pass** (task `taxonomy-pilot`, 2026-08-24). Read-only inputs:
  `harvest/citations/<key>.json` (S2 contexts/intents/isInfluential),
  `harvest/fulltext/abstracts/<key>.json`, and the gitignored local
  full-text cache under `harvest/fulltext/<key>/`. No other lane's files
  written.
- Method: built a per-pilot evidence index (each citing record tagged
  with its best evidence tier: fulltext > abstract+contexts > contexts >
  abstract > title_only); deep-read a stratified 111-row sample (seeded
  `random.Random(42)`, quotas per pilot over influential/non-influential/
  abstract-only strata) plus keyword-windowed reads of 15 cached full
  texts; drafted the codebook; then classified all 2,751 judgeable
  records in 67 rendered evidence batches, each row carrying evidence
  tier, context anchoring (named/numref/none), confidence, flags, and a
  short justification note. Title-only records (1,878) were left
  `unclassified`, never guessed.
- Taxonomy (codebook v0.2): FUNCTION (extends > uses-tool > adopts-idea
  > uses-benchmark > baseline > positions > surveys > supports-claim >
  exemplifies > detailed-citation > passing-citation; priority order
  resolves multi-function rows, lower values recorded in `secondary[]`)
  × CENTRALITY (core/engaged/peripheral) + flags (`own-group`,
  `self-version`, `lineage`, `polluted-contexts`, `critical`).
- Notable data hazards found and handled: 10% of judged rows have S2
  contexts that never anchor to the cited work (`polluted-contexts`,
  confidence downgraded); many same-work duplicate records
  (arXiv/DOI/venue clones) labeled consistently but not collapsed —
  dedup policy is an open review question; 3 records are the pilot
  papers citing themselves (`self-version`).
- Step (d) headline: S2 `isInfluential` is strongly anti-correlated with
  peripherality (4% base rate) but misses ~60% of substrate-level
  dependence (P(infl|core)=39%; 124 core rows flagged not-influential,
  incl. papers with the pilot system in their title); S2 `intents`
  `methodology` is ~3× diluted by list mentions. Details and named cases
  in `docs/taxonomy-draft.md` §6.
- **v0.2 amendment** (human review, applied 2026-08-24): the residual
  `mentions` value was replaced by two bottom-of-priority residuals —
  `detailed-citation` (≥2 in-text cite sites to our paper, OR ≥1
  sentence targeting our paper specifically; negative/comparative
  counts) and `passing-citation` (our cite appears only in multi-paper
  list sentences). All 701 `mentions` rows re-split (349 detailed /
  352 passing: 109 mechanical via the multiple-cites rule, 573 by
  sentence-level judgment in 10 rendered batches, 19 context-free rows
  by manual ruling or duplicate-sibling inheritance); all 292 `unknown`
  rows re-checked for the cheaper call — none resolvable (180 have no
  contexts, 112 have only non-anchoring/polluted contexts). All 38
  `lineage`-flagged residual rows landed `detailed-citation`.
  Draft is otherwise approved; corpus-wide classification is queued.
- **classify-corpus submit** (2026-08-24): human approved the ~$69 /
  10,021-request dry-run estimate; ran `--submit` for real. Between the
  dry-run and the submit call, `citations-s2-continue` landed 26 new
  non-pilot `harvest/citations/<key>.json` files (its OpenAlex pass), and
  `load_candidates()` re-scans that directory fresh rather than pinning a
  snapshot -- so the real submission came in at **11,082 requests / 28
  batches**, ~11% over the approved count (flagged to the human; harmless
  in substance, just a timing race with a concurrent lane, no duplicate
  work). Batch ids and per-item lookup in
  `harvest/taxonomy/records/_batches.json`. All 28 batches ended
  `succeeded` on first check -- `--collect` wrote 11,060/11,082 records,
  leaving 22 in `needs-review.jsonl`: 20 were the model writing a FLAG name
  (`own-group`/`self-version`/`lineage`) into `function`/`secondary`
  instead of `flags` (its own note always described the flag condition
  correctly, just filed in the wrong field), and 2 were the model
  self-correcting mid-response ("Wait, I need to reconsider...") and
  writing a second JSON object that first-brace-to-last-brace parsing
  turned into invalid JSON spanning both objects. Fixed both in
  `classify_citations.py` (`parse_record()` now tries the JSON object
  latest-opened-first; a new `repair()` moves a misplaced flag-as-function
  value into `flags` and falls back `function` to `unknown`) and reran
  `--recover`: 22/22 promoted, 0 left in review.
  Final distribution (11,082 records, 142 non-pilot papers): FUNCTION
  passing-citation 3117 / exemplifies 2705 / detailed-citation 1481 /
  supports-claim 870 / uses-tool 763 / positions 739 / unknown 569 /
  baseline 287 / adopts-idea 189 / uses-benchmark 161 / surveys 108 /
  extends 93. CENTRALITY peripheral 8049 / engaged 1708 / core 763 /
  unknown 562. Ran `curate/merge_taxonomy.py --write`: 142 non-pilot
  `data/citations/<bibtexKey>.json` files written, `index.json` now has
  144 papers (pilot rows/files verified untouched). Task complete.

### site-citations

- **Design pass** (2026-08-24). Read-only inputs: `publications.html` +
  `assets/` (conventions), `data/publications.json`,
  `harvest/taxonomy/pilot-classifications.json`, `harvest/citations/`;
  reader-facing prose voice calibrated against `knowledge/writing/` in
  `samanamarasinghe/my-agentic-knowledge-base`.
- Deliverables: `docs/citation-design.md` (design + walkthrough + open
  questions), `data/citations/SCHEMA.md` (schema v1: per-paper
  `<bibtexKey>.json`, `index.json` for the publications page, human-only
  `gscholar.json`; displayed count = `max(verified, gscholar)` computed in
  JS), and the prototype (`prototype/citations.html|js|css`,
  `prototype/build_pilot_data.py` as the schema's reference
  implementation).
- Key decisions recorded for review: top-level detailed/passing split maps
  `exemplifies` to passing; own-group citations stay inside the verified
  count (Scholar-comparable) but render apart from external impact;
  `unknown`/`unclassified` render as "not yet analyzed", never folded into
  either side; judgment notes do not ship to the site.
- Dedup per the human ruling (fold by normalized title, keep
  highest-evidence sibling, drop `self-version` groups):
  halide:pldi:2013 1,706 records → 1,483 works (586/416/438
  detailed/passing/unjudged external, 43 own-group); netblocks-pldi24
  5 → 4 (2/2/0).
- Prototype verified rendering in Chrome against a local static server:
  toggle counts, on-demand load, split bar, centrality filter (core counts
  reconcile), lazy group expansion, lineage/core chips, zero-count legend
  suppression. Stopped there per task instruction, then resumed on the
  approved sort-mode ruling (below) — human review before
  anything reaches the live pages.
- **Sort modes + `cited_by`** (2026-08-24, on the human's sort-mode
  ruling): SCHEMA.md gained a required nullable `cited_by` per citation
  entry (the citing work's own citation count; max over dedup siblings,
  OpenAlex figure preferred). The view gained the three approved sort
  modes — Impact (default; codebook priority, collapsible category groups),
  Recency (year descending, year headers), Popularity (`cited_by`
  descending, count-bucket headers 1,000+/100–999/10–99/1–9/not yet
  cited/count unknown, "N cites" chip per row) — plus a headers on/off
  toggle; every non-default combination renders one flat sorted list.
  Pilot data rebuilt with `cited_by` (1,470/1,483 resolved for Halide;
  top: TensorFlow 19,935, TVM 2,131); all modes and the toggle verified
  in Chrome, including a popBucket header bug caught and fixed. Merge-side
  propagation for the 142 non-pilot files is with the taxonomy lane per
  the agreed split.
- **Site integration** (task `site-integration`, human-approved,
  2026-08-24): generated the remaining 6 pilot data files
  (`build_pilot_data.py`; index now 150 papers), graduated
  `prototype/citations.js` to `assets/js/citations.js` (only the data
  path and header differ), appended the namespaced `cite-` styles to
  `assets/css/style.css`, and wired `publications.js`: one always-resolving
  `index.json` fetch at boot (10.4 KB — the only added initial-load data;
  page renders exactly as before if it fails) and a per-paper
  `CITATIONS.attachToggle()` in `renderItem()`. Same-turn refinements from
  the human, applied to prototype and site alike: expanded Summary/
  Citations panels render in a lightly-outlined `#fafafa` box echoing
  `.pub-item`; all three sort modes use the same collapsed-groups-with-
  counts presentation when headers are on (categories / years / count
  buckets), flat list when off; Recency and Popularity incorporate
  own-group rows into the main list with an "our group" chip while Impact
  keeps the separate section. Verified in Chrome on the live
  `publications.html`: toggle placement next to Summary, boxed panels,
  drill-downs, and Recency year-group counts matching the data histogram
  exactly (1,002 external + 43 own-group judged for Halide).
- **COMMIT papers** (human refinement, 2026-08-24): the separated bucket
  is now defined by Saman Amarasinghe's authorship of the citing work, not
  the classifier's broader any-author-overlap `own-group` flag (kept as
  metadata only), and is labeled "COMMIT papers" ("COMMIT" chip in
  Recency/Popularity). New per-entry `commit` field + `counts.commit`
  emitted at build time; the name rule (Saman/S./Saman P. Amarasinghe,
  excluding other Amarasinghes) is in SCHEMA.md and must be identical in
  every emitter. All 8 pilot files rebuilt (Halide 40, StreamIt 39, Raw 15
  COMMIT papers — e.g. Raw's 16 Taylor/Miller/Agarwal-only works moved to
  external, and 3 Saman-authored works the flag had missed moved in).
  Verified in Chrome on the live page. Non-pilot files await the
  merge-script rerun (taxonomy lane).
- **List-level Citations sort** (2026-08-24): the publications page's
  Group & sort control gained a "Citations" option sorting the paper list
  by the displayed count (`max(verified, gscholar)` from `index.json`),
  descending. As the primary key it groups under the per-paper popularity
  sort's count buckets (via `CITATIONS.countBucket`, now a shared export)
  with a final "No citation data" group; with primary None it is a flat
  ranked list. Papers without data key as -1 and sort last everywhere.
  Year grouping stays the default. Verified in Chrome (buckets, in-bucket
  rank 947>711>705>648>632>631>628, no-data tail, flat mode).
- **Displayed-count hardening** (bug report: list sort showing zero for
  every paper — not reproducible at HEAD over HTTP; every probe returned
  the real figures, so the likely cause was a stale-cache pairing of new
  HTML with an older cached publications.js). Fixed the class of bug
  regardless: `CITATIONS.displayCount(row)` = max(verified, gscholar ?? 0)
  is now the single source of truth used by the toggle label, the expanded
  headline, and the list-level sort; `loadIndex()` fetches with
  `cache: 'no-store'`; and publications.html versions the two script URLs
  (`?v=2`) so the HTML/JS pair can never be mixed vintages. Re-verified:
  Halide ranks first at 1,483, and a gscholar of 2,417 wins the max.
- **Boxed panels, take two** (2026-08-24): the human re-requested the
  boxed expanded panels — the earlier box was live but style.css carried
  no cache-busting version, so browsers could hold the pre-box stylesheet.
  publications.html now links style.css?v=2, and the panel shade is tuned
  to the request: same 1px #ddd border and radius as .pub-item, background
  rgba(226,226,226,0.35) — the page gray at low opacity, ~96% white.
  Applies to Summary and Citations alike (both are .pub-summary.open).
- **Reception-summary pilot** (2026-08-24): hand-wrote a reception
  summary for each of the 8 pilot papers — what cites it, notable
  descendants and users, and its distinctive pattern (StreamIt's
  benchmark-suite afterlife, Raw's numbers-that-travel, Halide's
  idea-becomes-vocabulary mass) — voice-matched to knowledge/writing/ in
  the personal KB: academic, understated, no superlatives, timeless
  phrasing. Curated in `data/citations/reception.json` (claimed; human
  prose only), folded into the pilot JSONs as the schema's new optional
  `reception` field by `build_pilot_data.py`, and rendered as the first
  element of the expanded Citations panel (style.css?v=3 /
  citations.js?v=3). Stopped after the 8 per task instruction — human
  critique before any scaling to the corpus.
- **Show citations expand-all** (2026-08-24): a button beside Show
  summaries opens/closes every paper's Citations panel; later-rendered
  items follow the state (CITATIONS.setDefaultOpen), per-paper files
  still lazy-load through a 4-wide progressive fetch queue, and the
  summaries expand-all was scoped with :not(.cite-view)/:not(.cite-toggle)
  — it had been silently rewriting the citation panels' classes and
  toggle labels. Verified: 173 panels open and render, summaries toggle
  leaves them untouched, filter re-render keeps them open, hide collapses
  all. citations.js?v=4, publications.js?v=3.
- **Page-level citation tools** (2026-08-24 request): global
  Impact/Recency/Popularity + All/Core/Engaged/Peripheral controls
  driving every open panel; a FUNCTION-category facet listbox and a
  citing-work search filtering panel rows; two paper-threshold sliders
  (citation count, and impact = Σ weight×count from the new per-paper
  `functions` counts in index.json — weights in SCHEMA.md); an aggregate
  overview box with a cross-paper-citers finder (DOI/title matched,
  untitled records skipped); Years converted from the button grid to a
  facet listbox. Clear filters resets the tools. Verified in Chrome end
  to end (global sync into panels, category/search row filtering,
  slider thresholds 723-impact→2 papers, cross-citers over 43 papers →
  2,491 works). Non-pilot index rows lack `functions` until the
  taxonomy lane's merge rerun — impact shows pilots-only meanwhile.
  style.css?v=4, citations.js?v=5, publications.js?v=4.
- **Reception/summaries decoupling + tool counts** (2026-08-24): the
  human reported Show citations "also shows summaries" — the actual
  Summary sections stay closed (verified by probe); what showed was the
  reception prose at the top of each pilot panel. Reception is now a
  collapsed "Reception ▸" section that follows the Show summaries state
  (CITATIONS.setReceptionVisible), so citations-without-summaries is
  clean; the head still toggles it per panel. Also added facet-style
  paper counts to the page-level tools: each citation category shows how
  many shown papers have ≥1 citation in it, and the centrality buttons
  show papers with ≥1 core/engaged/peripheral citation — backed by a new
  per-paper `centrality` count object in index.json (pilots emitted;
  non-pilot rows await the taxonomy lane's merge rerun).
  style.css?v=5, citations.js?v=6, publications.js?v=5.
- **Impact tiers** (2026-08-24): the impact slider's raw number meant
  nothing to users — it now snaps to five descriptive tiers (all papers /
  top half / top quarter / top 10% / top 3% by impact), thresholds taken
  from the corpus impact distribution. Verified: 327 → 89 → 43 → 17 → 5
  papers across the tiers.
- **Overview simplified** (2026-08-24): the aggregate line now reads
  just "N of M shown papers have T total citations" — combined impact
  and the detailed/passing totals dropped per the human's wording.
  publications.js?v=6.
- **Categories box height** (2026-08-24): the citation-categories list
  now uses the same scrolling shell as the other facet boxes (~5 rows
  visible), halving its height (299px → 149px) so all three
  citation-tools blocks sit at equal height (176px measured).
  publications.js?v=7.
- **Cross-citers button removed** (2026-08-24): the human liked the
  concept but ruled a reverse index of cross-paper citers must be done
  properly, not as an on-the-fly scan — button dropped from the
  overview; CITATIONS.ensureData/crossCiters stay in citations.js as
  the seed of a future proper implementation. publications.js?v=8.
- **TEMP pilot-only toggle** (2026-08-24): a "Pilot papers only [TEMP]"
  button (dashed-orange marked) in the filter row narrows the list to
  the 8 pilot bibtexKeys for review convenience. Deliberately one
  self-contained, clearly-fenced block in publications.js (inserts its
  own button, wraps filteredItems in place) — delete the block and the
  feature is fully gone. publications.js?v=9.
- **Reception merged into Summary + expand/collapse groups**
  (2026-08-24 ruling): the separate Reception section is gone. The
  publications page renders summary + reception as ONE Summary block —
  reception texts rewritten to flow seamlessly from each summary's last
  sentence (e.g. TOPLAS's "'step towards'… first step" → "The step was
  taken up."; the IJPP text's framing corrected to the journal-of-the-
  language-paper it actually is). Storage stays two fields in two files
  (summary in data/publications.json, untouched; reception in
  data/citations/reception.json, fetched no-store by the page) so
  regeneration can never overwrite hand-written prose; SCHEMA updated.
  Also per the human's idea, the panels' Headers on/off toggle became
  **Expand all / Collapse all** — groups and their headers persist in
  both states across all three sort modes (verified: 13 impact groups /
  1,483 rows expand, 16 recency year groups inherit the state, collapse
  keeps headers). style.css?v=6, citations.js?v=8, publications.js?v=10.
  Stopped after the 8 pilots for seam critique before the other 144.
- **Panel trimmed** (2026-08-24): the COMMIT-papers note under the
  split bar and the codebook provenance footer are removed per the
  human ("keep it simple") — the COMMIT papers group itself, with its
  gloss, still carries the separation. style.css?v=7, citations.js?v=9.
- **Group headers simplified** (2026-08-24): "Builds on it 35 — gloss…"
  became "Builds on it (35)" with the gloss as a tooltip, per the human.
  style.css?v=8, citations.js?v=10.
- **Headline KISS** (2026-08-24): "1,483 citations — 1,483 verified and
  analyzed below" claimed too much (429 rows are unanalyzed) and said
  too much; the headline is now just "1,483 citations".
  style.css?v=9, citations.js?v=11.
- **Category counts = citation totals** (2026-08-24): the categories
  listbox now shows how many citations in each category the shown papers
  have (summed from index functions), not how many papers have at least
  one — e.g. "Uses the system (1,026)" corpus-wide. Centrality buttons
  keep paper counts. publications.js?v=11.
- **Dual counts + tooltips** (2026-08-24, overnight requests): category
  rows read "Builds on it (44, cited by 142)" — papers with such
  citations, then the citation total; every citation control page-level
  and in-panel carries a descriptive tooltip (sort semantics, centrality
  definitions from the codebook, sliders, search, expand/collapse); the
  visible impact explanation under the sliders moved into the impact
  slider's tooltip. style.css?v=10, citations.js?v=12,
  publications.js?v=12.
- **Receptions corpus-wide** (2026-08-24 overnight, human-authorized
  "apply this to all the papers"): reception texts generated for all 149
  non-pilot papers with ≥3 judged external citations (16 thinner papers
  deliberately skipped) — 13 parallel writer agents over per-paper
  briefs (summary, function/centrality profiles, notable citing works),
  then 13 independent verifier agents enforcing grounding, timelessness,
  no-hype, seam, honesty, and shape; 33 texts got minimal corrective
  edits (typical catches: overstated engagement vs an
  exemplifies-dominated profile, group-internal works presented as
  external reception, invented document types, leaked writer-facing
  instructions), 1 missing text written by hand, mechanical checks clean
  (0 banned phrases, full coverage). reception.json now holds 157
  entries; the site renders them immediately. Non-pilot per-paper JSON
  convenience copies refresh on the taxonomy lane's next merge run.
- **TACO joins the pilot button** (2026-08-25, queue task pilot-button):
  Kjolstad:2017:TTG added to the TEMP pilot filter — 9 papers now.
  publications.js?v=13.

## Cross-lane requests

- **site-citations → taxonomy** (2026-08-24): your claim extension to all of
  `data/citations/` (still uncommitted in this worktree when this note was
  written) overlaps the site-citations claims above, which the coordinator's
  design task assigned by name (`data/citations/SCHEMA.md` plus the pilot
  data files and `gscholar.json`). Proposed split, matching the queue:
  taxonomy/classify-corpus owns `data/citations/<bibtexKey>.json` for
  **non-pilot** papers and must emit the shape in `data/citations/SCHEMA.md`;
  site-citations owns SCHEMA.md, `gscholar.json` (human-edited only — no
  script writes it), the pilot data files, and `prototype/`. `index.json`:
  site-citations bootstrapped it; your merge script takes it over on first
  run and must preserve the pilot rows. Please narrow your row's claim
  accordingly — and note this worktree is shared, so please stage your
  commits by explicit path, not `git add -A` (my in-flight files sit next to
  yours under `data/citations/`).
  - **taxonomy, resolved**: agreed, row narrowed above to exactly this split.
    `curate/merge_taxonomy.py` reads `data/citations/SCHEMA.md` and
    `gscholar.json`, writes only non-pilot `<bibtexKey>.json` files, refuses
    to touch a pilot key, and updates `index.json` in place (loads the
    existing file, sets only its own keys, leaves the pilot rows alone).
    Committing by explicit path, not `git add -A`, per your note.
