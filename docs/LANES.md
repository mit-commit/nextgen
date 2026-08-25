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
| **repos** | `harvest/repos/` | **active** — step 1 (in-paper discovery) done: all 353 PDFs scanned, 142 code-host URLs verified into `harvest/repos/mentions.json`, and `harvest/repos/search-plan.json` prepared for the 268 papers with no live repo link. Step 2 (task `repos-search step 2`, 2026-08-24) complete: `search_github.py` scored candidates via the GitHub REST API for all 268 -- 217 strong, 27 weak-only, 24 none -- into `harvest/repos/candidates.json`. Auto-accepts nothing; see lane log. Task `repo-verify` (2026-08-25, complete): `curate/verify_repos.py`, a Batch API model pass over all 303 papers with any repo evidence (24 of 327 have none) -- pilots submitted and pushed first per instruction, spot-checked, then the remaining 295 (~$1.14 total). 183/303 papers got >=1 verified repo (132 implementation, 115 third_party, 16 benchmark, 10 artifact roles; 148 own_group / 125 not); 25 papers have a low-confidence row parked in `harvest/repos/review.json` for human spot-check; 120 genuinely have none (spot-checked several -- old theses/papers, or search candidates that were real projects but unrelated, e.g. "Umbra" collided with a game exploration tool and a CMS). Canonical-over-fork worked as designed (tensor-compiler/taco over manya-bansal/taco; correctly split cases like an author's personal DynamoRIO fork containing thesis work vs. the canonical upstream). See lane log. Task `verified-quirks` (2026-08-25, complete): fixed the repo-rename duplicate rows the impact-view lane flagged (`curate/dedupe_verified_repos.py`, 3 papers, resolves each URL's owner/repo through the GitHub API -- which auto-follows a rename -- and groups by the stable numeric repo id rather than URL text; string-level canonicalization can't catch a rename). Also removed a dead, actually-buggy helper (`_github_repo_from_url`, never called: `.rstrip('.git')` strips a character set not a suffix, silently mangling "graphit" to "graph" -- caught while writing the real dedup logic). The other flagged quirk (own_group=true rows with role=third_party) is NOT a bug: verified `harvest/impactview/build_repo_data.py` already excludes role=='third_party' from the "own" tier regardless of own_group, by design, and every one of the 7 such rows is a genuine case (the same research group's other tool used as a dependency) -- no change made. Task `descendants-all` (2026-08-25, partial -- see below): tier-3 idea-descendant extraction, corpus-wide -- `curate/build_idea_descendants.py` (mechanical + light search) + `curate/verify_descendants.py` (model check on search hits). 1,795 qualifying rows (extends/adopts-idea at core/engaged, uses-tool at core, per the sketch-frontend-lesson widening); Both waves now run and verified (human approved the widened wave's cost after `nextgen-a2` explained it) -- **47 genuine descendant repos located across 24 papers total** (30/17 from the strong wave, +17 more from the widened uses-tool/core wave's 83 search hits, 66 of which were correctly rejected as false positives -- an 80% FP rate on this bucket, even higher than the strong wave's 59%). See lane log. Task `own-repo-deep-hunt` (round 7, claimed 2026-08-25): `nextgen-a2`'s phase A (org/account enumeration, 102 candidates) plus this session's phase B (personal-account hunt for the 191 repo-less papers, esp. theses) both landed; joint model-verification judged 178 candidates together, **13 confirmed** into `harvest/repos/own-inventory.json` -- thesis gap still mostly open (1/72). A concurrent hunt in this same round (verified-identity author map via exact contributor-name matches + GitHub search, not guessed handles) added **26 net-new own_group-confirmed papers** on top of that (deduped against the 178 already-tried pairs first) -- corpus-wide own_group coverage 126 -> 157 papers, repo-less 201 -> 170 (theses/TRs 73 -> 60 still repo-less). `harvest/repos/own-inventory.json` now 54 keys / 38 confirmed total; `data/repos/` and `tier2-priority.md` are stale against the later 26 and still need a rebuild. See lane log for both hunts' numbers. Task `own-repo ranking` (round 7 task 2, 2026-08-25, complete): rebuilt `data/repos/` (`build_repo_data.py --write`, 162 papers/245 rows, up from 139/211) and `harvest/impactview/tier2-priority.md` (`gen_tier2_priority.py`, now 71 ranked own repos, up from 52) against the now-current `own-inventory.json`. Found and fixed a real bug along the way: the later deep-hunt batch's 26 net-new rows store `url` as a bare `"owner/repo"` string (no `github.com/` substring), unlike every earlier row (verified.json + phase-A/B own-inventory rows), which all carry a full URL -- `build_repo_data.py`'s `fullname_of()` required that substring, so those rows silently got no GitHub star/description/last-push enrichment, and `gen_tier2_priority.py`'s own-repo filter (`'github.com' not in url`) silently dropped them from the ranking entirely (19 real own repos missing, no error). Fixed `fullname_of()` to accept a schemeless `"owner/repo"` string while still correctly rejecting a full non-GitHub URL (verified.json has 4 gitlab/bitbucket rows that must NOT be misparsed as an owner/repo pair), and switched the ranking filter to key off the already-normalized `name` field (exactly one `/`, no spaces) instead of re-testing the raw `url`. STOPPING here per the queue's gate: `harvest/impactview/tier2-priority.md` is the ranking sheet for the coordinator's tier-2 outside-user-hunt pick (dynamorio needs explicit human approval, per the standing rule) -- did not pick a hunt list myself. Noticed a live concurrent session actively writing under `harvest/ecosystems/` (uncommitted `candidates.json`/`enumerate_candidates.py`/`measure_candidates.py` etc., files changing minute-to-minute) while working this task -- left that path untouched. **Follow-up** (2026-08-25, later): picked up the ecosystems lane's flag on `174c18fd` (`curate/verify_deephunt.py`'s bare-`owner/repo` bug fixed at the source, `own-inventory.json`/`deephunt_review.json` urls corrected to real `https://github.com/...` links) -- reran `build_repo_data.py --write`; exactly the 26 flagged `data/repos/papers/<key>.json` files changed (url field only, bare string -> real link), `data/repos/index.json` and `tier2-priority.md` both byte-identical to before (ranking already keyed off the normalized name, unaffected). Task `own-inventory fold + repos rebuild` (round 8 task 1, claimed 2026-08-25): starting -- see lane log. |
| **authors** | `harvest/authors/` | **active** — `authors_build.py` parses every `author0` into individual authors, dedupes exactly, enriches from Crossref/OpenAlex, matches `data/people.xml`, and writes `harvest/authors/authors.json` (369 distinct authors) plus `harvest/authors/review.json` (221 flagged rows: 4 name-variant near-misses + 217 from the enrich pass). `enrich_openalex.py` resolves each of the 369 against their own OpenAlex author entity (ORCID or shared-work match, never name alone) into `harvest/authors/enriched.json`; 287/369 resolved (task `authors-enrich verify`, 2026-08-24 — OpenAlex's search quota reset, rerun recovered 24 of the 79 previously-blocked people; 77 genuinely unresolved, 5 ambiguous, 0 still search-blocked; see lane log). Task `authors-worklist` (2026-08-25, complete): `build_session_sheet.py` writes `harvest/authors/session-sheet.md` -- Part 1 lists the 77 unresolved + 5 ambiguous people (papers, reason, OpenAlex candidate ids for the ambiguous ones, Scholar/LinkedIn search links); Part 2 is a LinkedIn-presence checklist for all 369, alphabetical, each with a constructed (never visited) LinkedIn search URL and known affiliation/homepage/OpenAlex link as disambiguation context where resolved. Fetches nothing. |
| **site-citations** | `docs/citation-design.md`, `docs/impact-view-design.md`, `docs/summary-style.md`, `harvest/summaries/`, `data/citations/SCHEMA.md`, `data/citations/gscholar.json`, `data/citations/reception.json`, the 8 pilot `data/citations/<bibtexKey>.json` files, `data/citations/index.json` (bootstrap; merge script owns non-pilot rows), `prototype/`, `harvest/impactview/`, `data/repos/SCHEMA.md` + `data/repos/index.json` + `data/repos/papers/` (the ecosystems lane keeps `data/repos/<ecosystem>.json`), and — for the citation view only — `publications.html`, `assets/js/citations.js`, the citation-view additions in `assets/js/publications.js` + `assets/css/style.css` | **active** — the per-paper citation section, designed, prototyped, human-APPROVED, and now **integrated into `publications.html`** (task `site-integration`, 2026-08-24): one small `index.json` fetch at page load turns on a "Citations (N)" toggle for the 150 papers with data files; per-paper data lazy-loads on first expand. Three sort modes (Impact / Recency / Popularity) with a headers on/off toggle — all three render uniform collapsible groups, collapsed by default with counts (categories / years / count buckets); expanded Summary and Citations panels sit in a lightly-outlined shaded box; Recency and Popularity incorporate own-group citations chip-marked, Impact keeps them in their separate section. `prototype/` kept as reference. `data/citations/SCHEMA.md` remains the contract; non-pilot `<bibtexKey>.json` files belong to the classify-corpus merge. |
| **fulltext** | `harvest/fulltext/` | **active** — `harvest_fulltext.py` fetches full text of citing works for 8 pilot papers via free routes (OpenAlex OA location, arXiv, Unpaywall, PMC). Cached text/sidecars are gitignored; `harvest/fulltext/manifest.json` (committed) has per-paper yield stats. Does not touch `harvest/citations/`. Task `abstracts-all` (2026-08-24, complete): `harvest_abstracts_all.py` extended the abstract harvest from the 8 pilots to every non-pilot citing work, batch-fetched via OpenAlex's OR filter (100 ids/request) rather than one-by-one -- 167 papers, 21,545 citing works, 14,014 gained a real abstract (65%). Deliberately left the 3 sampled high-cited pilots' abstract files untouched (they're inert for reclassification -- pilots are permanently excluded from `curate/classify_citations.py`'s population). Fed the taxonomy lane's rejudge sweep (see its log). Task `login-worklist` (2026-08-25, complete): `build_login_worklist.py` finds citing-work judgments on the "detailed" side of the taxonomy at low confidence from contexts-only evidence, whose DOI belongs to a paywalled publisher (IEEE/ACM/Springer/Elsevier) -- reads pilot-classifications.json and every harvest/taxonomy/records/<key>/*.json, joins back to harvest/citations/ for the citing work's own metadata, fetches nothing. 26 rows (9 ACM, 8 IEEE, 6 Springer, 3 Elsevier) written to harvest/fulltext/login-worklist.json + a publisher-grouped checklist in login-worklist.md for the human's browser sitting. Task `fulltext-ingest` (2026-08-25, complete): the human worked the worklist and dropped 23 PDFs in `~/workspace/nextgen-fulltext`; `ingest_manual_pdfs.py` extracted all 23 (pypdf, surrogate-safe write, 2000-char floor -- 0 failures, 0 below floor), covering 54 (key, slug) pairs since several citing works cite more than one corpus paper. Found and fixed a real bug in `curate/classify_citations.py`'s fulltext evidence packing along the way (was head-truncating to 4000 chars, missing citations in the related-work section of any real-length paper -- now `windowed_fulltext()` searches in tiers for the cited paper's actual mentions). Re-judged all 54: 18 pilot rows via `rejudge_pilots_with_fulltext.py` (live calls, patches `pilot-classifications.json` directly -- pilots are otherwise frozen, but a genuine evidence upgrade earns a rejudge), 36 non-pilot via the normal batch pipeline. **36/53 rows with a prior judgment changed function or centrality (68%)** -- see lane logs for both. Task `login-worklist2` (2026-08-25, complete): expanded population (confidence low/medium contexts-only detailed-side, OR unknown, OR title-only-with-a-DOI; IEEE/ACM/Springer, Elsevier skipped this pass) deduped by DOI across the whole corpus -- `build_login_worklist2.py`, 3,641 rows (1,432 ACM / 1,243 IEEE / 966 Springer) with ready-to-fetch URLs, written to `harvest/fulltext/login-worklist2.json`. IEEE arnumbers resolved via Crossref's bulk filter API (40 DOIs/call, zero publisher requests) -- `resource.primary.URL`'s `/document/<arnumber>/` or the vor `link` entry's `?arnumber=`; 21 IEEE DOIs dropped for lack of either. |
| **taxonomy** | `harvest/taxonomy/`, `docs/taxonomy-draft.md`, `curate/`, `data/citations/<bibtexKey>.json` for non-pilot papers, `data/citations/index.json` (owns it after the first merge run, preserving the pilot rows) | **active** — pilot human-reviewed (approved with one amendment, applied 2026-08-24 as codebook v0.2): two-dimension citation taxonomy (FUNCTION × CENTRALITY, plus flags/evidence-tier/confidence per row) drafted from a stratified deep read and applied to all 4,629 citing-work records of the 8 pilot papers (2,751 judged; 1,878 title-only left `unclassified`). v0.2 replaced residual `mentions` with `detailed-citation`/`passing-citation` and re-split all 701 affected rows (349/352). Deliverables: `docs/taxonomy-draft.md` (codebook, worked examples, per-pilot distributions, S2 `isInfluential`/`intents` comparison) + `harvest/taxonomy/pilot-classifications.json`. Built `curate/classify_citations.py` (task `classify-corpus`, Anthropic Batch API) and `curate/merge_taxonomy.py` (emits data/citations/SCHEMA.md's shape for non-pilot papers only, never touching the pilot files or gscholar.json). Dry-run cost estimate reported (~$69/10,021 requests), approved by the human; actual submit came in at 11,082 requests / 28 batches (see lane log) — all collected, 22 rule-level rejections fixed by a parser/repair fix and recovered, 11,082/11,082 classified. `merge_taxonomy.py --write` folded all 142 non-pilot papers into `data/citations/<bibtexKey>.json` + `index.json` (144 papers total, pilot rows and files untouched). Task `classify-corpus` complete. Task `cited_by verify`: harvest-layer backfill was site-citations/nextgen-a2's work (see their log); `merge_taxonomy.py` updated to set `cited_by` (max over dedup siblings, always present per SCHEMA.md) and rerun `--write` — all 142 non-pilot files now carry it, pilot files/gscholar.json verified untouched. Task `commit-papers redefine` (2026-08-24): added `is_saman()` (byte-identical to `prototype/build_pilot_data.py`'s copy) and replaced `own_group`/`n_own` with `commit`/`n_commit` per the human's schema refinement (COMMIT papers = Saman-authored citing works, not author-overlap-with-the-cited-paper); verified against both pilot files' `counts.commit` before rerunning `--write`. Task `abstracts-all + rejudge sweep` (2026-08-24, complete): after the abstracts-all pass (fulltext lane), cleared 603 existing staging records that were `function: unknown` or `confidence: low` and had just gained a real abstract, so they'd regenerate with better evidence; previously-title-only rows needed no clearing (`load_candidates()` picks up an evidence-tier upgrade automatically). Dry-run came to 7,766 requests / ~$56 (over the $20 auto-approve line) — human approved. Hit a duplicate-`custom_id` Batch API rejection mid-submission (3 literal duplicate citing records in `harvest/citations/`, same DOI twice with whitespace-differing titles); fixed by deduping `load_candidates()` on `(key, slug)`, collected the 1,600 already-sent requests first so they wouldn't be re-billed, then resubmitted the remaining 6,166 clean. Also fixed two more model-output quirks (bareword `"confidence": low`, an occasionally-omitted `flags` field) via the same parser/`repair()` pattern as classify-corpus. Final: 18,242 total staging records, folded into 165 non-pilot `data/citations/` files (up from 142 -- 23 papers with zero prior judgeable content, several from `idmap-review-rest`'s OpenAlex-only resolutions, now have their first citation page) totaling 18,554 works, 13,024 judged (70.2%, up from the classify-corpus baseline). `index.json` now has 173 papers. |
| **docs** | `docs/refresh.md` | **active** — task `refresh-docs` (2026-08-25, complete): the every-few-months refresh procedure, one phase per pipeline stage (idmap → citations harvest → abstracts → classification → repos → merge → gscholar → reception/summaries), each naming its script, worker-vs-human, and cost-gating rule; a closing list of what never runs automatically (publications.json, gscholar.json, the pilot files, anything behind a login). |
| **ecosystems** | `harvest/ecosystems/` | **active** — task `halide-import` (round 7 task 6, 2026-08-25, complete): confirmed `data/repos/papers/halide:pldi:2013.json` had zero rows attributed to `samanamarasinghe/Halide-world` before this (its 8 tier-3 rows all came from this corpus's own generic descendants pass). `build_halide_import.py` fetches that repo's `data/site/halide-index.json` (schema v1, corpus-wide index of 16 Halide anchors) via the GitHub contents API and maps ONLY the `pldi2013-halide`-anchor slice onto `data/repos/SCHEMA.md`'s row shape -- mapping, not re-judging (every verdict/star/evidence value is Halide-world's own). Tier-3: 162 rows / 130 citing papers that published their own artifact repo (a bare "mentions another repo" does not qualify, matching this corpus's own idea-descendants rule) -- modest, panel-reasonable, safe to fold into `data/repos/` directly. Tier-2: 567 real code-level rows (verdict consumer/generator/uses_source → `uses`, halide_copy_or_fork → `builds-on`); deliberately excluded 2,828 `third_party_bundle` rows (Halide arrived only inside a vendored dependency) and 67 `prose_only` rows, both counted in the report, not hidden. **567 is a large single-paper ecosystem, on the order of the outside-user hunts round 7's strategy flagged for human approval (dynamorio)** -- staged in `harvest/ecosystems/halide-import.json` + `halide-import-report.md` rather than written into `data/repos/` (site-citations' claimed path), pending a human look at whether/how to render all 567 at once vs. a capped view. Task `ecosystems measure-step` (round 7 task 5, carried since round 4, checked while this lane was open): `harvest/ecosystems/candidates-report.md` was never absent-but-local, it never existed anywhere in this repo's history, and there is no separate "3 pilot tiers" pipeline distinct from what `data/repos/` + this halide-import already are -- the round-4 plan's `harvest/ecosystems/<repo>/` MEASURE step was superseded in practice by the actual build order this corpus took (verify_repos.py's tier-1 -> build_idea_descendants.py's tier-3 -> today's own-repo-deep-hunt/tier2-priority.md ranking -> this halide-import), which is a real ecosystem-size estimate per own-group repo, just not shaped like the round-4 spec expected. Treating task 5 as superseded rather than duplicating effort chasing a file path that was never going to be filled. **Retraction, same session**: a concurrent session started writing exactly that file (`harvest/ecosystems/candidates-report.md`, plus `candidates.json`/`enumerate_candidates.py`/`measure_candidates.py`/`verify_ecosystem_candidates.py`/`verified.json`, seen uncommitted in this shared worktree) minutes after the above was logged -- so it was not in fact abandoned, just not yet landed when this lane checked. Left every one of those files untouched (not mine, still in flight) and did not re-close task 5 a second way; whoever lands it should log there, not overwrite this entry. **Also, real bug found and fixed**: `curate/verify_deephunt.py`'s `build_request()` displayed a candidate's bare `owner/repo` string to the model as if it were "the URL" (preferred `c['repo']` over `c['url']` when both existed) -- the model dutifully echoed that bare string back as its own `url` field, so all 66 rows (53 own-inventory.json + 13 deephunt_review.json) from this session's batch stored a `url` with no `github.com`/`https://` at all. `harvest/impactview/build_repo_data.py` and `gen_tier2_priority.py` (site-citations, c4fc4da4) worked around the *filtering* symptom (dropped own-repo rows from the ranking) but their fix keys off the normalized name, not the url string -- so `data/repos/papers/<key>.json`'s `url` field for these 26 papers is STILL the bare, unlinkable string as of that commit. Fixed at the source: `own-inventory.json` and `deephunt_review.json`'s urls rewritten to real `https://github.com/...` links, and `build_request()` now always shows the real URL (falls back to constructing one from `repo` only if `url` is truly absent). **site-citations: `data/repos/papers/` for the 26 papers this session's deep-hunt touched needs a `build_repo_data.py` rerun to pick up the corrected urls** -- the ranking counts are already right, only the link field is stale. |

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
- **Step 2b, model verification** (task `repo-verify`, 2026-08-25):
  `curate/verify_repos.py` runs a Batch API pass (model claude-sonnet-4-6)
  over every paper's combined repo evidence -- in-paper mentions from
  `mentions.json` (with the surrounding sentence, since a printed URL is
  sometimes the paper's own repo and sometimes a bibliography citation to
  someone else's tool) plus `candidates.json`'s heuristic search hits (with
  stars/description/created_at for judging real vs. name-collision and
  canonical vs. fork). System prompt instructs: reject a candidate outright
  when the only support is name similarity; classify role
  (implementation/artifact/benchmark/third_party) and own_group
  independently; keep only the canonical repo when two candidates are
  clearly the same project (an org repo over a contributor's fork, etc.).
  Pilots (9 keys) submitted, collected, and spot-checked first per task
  instruction -- all 8 pilots with evidence came back correct, including
  two (`levison:istas:2002`, `thies:toplas:2007`) that correctly returned
  zero repos after the model recognized their only candidates (a Tektronix
  emulator, a Kubeflow tool, a Spotify chart app) as unrelated name
  collisions, not a false negative. Pushed, then submitted the remaining
  295 papers (~$1.14 total, both batches together -- well under the $20
  line). Zero rule-level rejections across all 303 requests.
  Result: 183/303 papers have >=1 verified repo (`harvest/repos/
  verified.json`) -- 132 implementation / 115 third_party / 16 benchmark /
  10 artifact roles, 148 own_group true; 25 papers have a low-confidence
  row in `harvest/repos/review.json` for a human spot-check; 120 have
  none, spot-checked as genuine (old theses, or search hits that are real
  projects but unrelated -- "Umbra" collided with a game exploration tool
  and a CMS). Canonical-over-fork worked on inspection: correctly picked
  `tensor-compiler/taco` over `manya-bansal/taco`, and correctly split a
  case where an author's personal DynamoRIO fork legitimately contained
  the thesis's own modifications (kept as a second, `implementation`
  entry) from the canonical upstream (kept as `third_party`) rather than
  treating them as duplicates.
- **verified-quirks** (2026-08-25): see the row summary above --
  `curate/dedupe_verified_repos.py` fixed 3 papers' repo-rename duplicates
  by resolving through the GitHub API (id-stable) rather than URL text;
  the own_group+third_party "quirk" was confirmed not a bug by reading
  `harvest/impactview/build_repo_data.py` before touching anything.
- **descendants-all** (2026-08-25): no prior idea-descendant extraction
  existed for the 9 pilots or anyone else (checked -- the task's "extend
  ... from the 9 pilots" phrasing was aspirational sequencing, not a
  statement of prior work) so this built the whole thing. Population:
  citing-work rows classified `extends`/`adopts-idea` at centrality
  core/engaged, or `uses-tool` at core (the widened rule from the
  sketch-frontend lesson) -- 1,795 rows across 123 papers, both pilot
  (`pilot-classifications.json`) and non-pilot
  (`harvest/taxonomy/records/`) sources.
  - **Mechanical scan** (free, always runs): search each qualifying
    citing work's own cached evidence (OpenAlex abstract, cached full
    text, S2 contexts) for a `github.com` URL it already contains. Yield
    was near-zero (4/1,795) -- expected, since full text is cached for
    only the 8 pilots + this week's 23 manually-ingested PDFs, and a
    short abstract or S2 snippet rarely names a repo.
  - **Light search wave** (`--search --wave strong`, the 735
    extends/adopts-idea rows, ~26 min at GitHub's 30/min search-API
    limit): one repository-search call per unlocated row on the citing
    work's own title, accepted via word-overlap with the candidate's
    name/description. Found 63 candidates -- but a look at the raw hits
    showed a high false-positive rate driven by short/generic paper
    titles ("Elastic computing", "Resource recycling", "No bit left
    behind") matching totally unrelated repos on shared common words; one
    nonsense-named repo (`jettbrains/-L-`, a W3C standards doc) matched 6
    different unrelated papers.
  - **Verification pass** (`curate/verify_descendants.py`, live model
    calls, same heuristic-then-verify pattern as search_github.py +
    verify_repos.py): checked all 63 candidates against the citing
    paper's actual subject matter. **26/63 confirmed genuine, 37/63
    correctly rejected** as coincidental word overlap -- exactly the
    false positives spotted by eye, plus several more (e.g. a repo titled
    near-identically to "No bit left behind" but reading "No-Bite-Left-
    Behind" with zero stars and no description).
  - Result (strong wave): **30 genuine descendant repos located across
    17 of 123 papers** (4 mechanical + 26 verified-search), written to
    `harvest/repos/descendants.json`. Every unlocated row is honestly
    `located: false` ("paper-only"), never guessed.
  - **Widened wave** (`--search --wave widened`, the remaining 1,060
    `uses-tool`/core rows, ~40 min at GitHub's search-API limit; human
    approved the cost after `nextgen-a2` relayed the estimate): 113
    candidates found via the same light-search heuristic. Verification
    pass (`curate/verify_descendants.py --write`): **17/83 confirmed
    genuine, 66/83 correctly rejected** as coincidental word overlap --
    an 80% false-positive rate, higher than the strong wave's 59%,
    consistent with this bucket's rows being lower-precision by design
    (uses-tool/core rather than extends/adopts-idea). (The build step
    reported 113 "located" after this wave, not 83 -- the other 30 are
    the strong wave's already-verified entries, carried forward as-is
    since `build_idea_descendants.py` is resumable and doesn't redo rows
    that already have evidence.)
  - **Combined final result**: **47 genuine descendant repos located
    across 24 of 123 papers** (30/17 strong wave + 17 more/7 more papers
    from the widened wave), all in `harvest/repos/descendants.json`.
    Both waves are now fully run and committed -- nothing left to do on
    `descendants-all` itself. Pinged `nextgen-a2` to rerun
    `harvest/impactview/build_repo_data.py --write` per their request.
- **own-repo-deep-hunt** (round 7, claimed 2026-08-25): starting now.
  Scope per the queue: enumerate group GitHub orgs, build an author to
  GitHub-account map, enumerate each account's repos in their publication
  window, candidate-match to papers (folding in the 165 medium rows from
  `candidates.json`), write `harvest/repos/deephunt.json`. Will not touch
  `harvest/repos/descendants.json` (owned by the in-flight widened-wave
  run above) or `harvest/repos/verified.json` until the matching-judgment
  Batch step, logged separately below.
- **own-repo-deep-hunt phase B** (2026-08-25, complete): per `nextgen-a2`'s
  split proposal (they built phase A -- 346 non-fork repos across 121
  known own-group owners, mechanically matched into
  `harvest/impactview/own-repo-candidates.json`, 102 candidates), this is
  the harder gap: the 191 papers with no repo in `data/repos/index.json`
  whose code might live under a personal GitHub account we've never seen
  (72 are theses -- the human directive's specific worry).
  `harvest/impactview/hunt_personal_repos.py --fetch` checked 1,018
  distinct guessed usernames (from `search-plan.json`'s per-author handle
  guesses for the 163 papers that have a plan entry, generated fresh from
  `author0` for the 28 that don't) via `GET /users/{u}` -- 545 turned out
  to be real GitHub accounts (a deliberately noisy step; existence alone
  proves nothing, short surnames like "won" or "taylor" collide with
  unrelated strangers constantly). `--match` scored every one of those
  545 accounts' non-fork repos by title-token overlap the same way phase
  A does, yielding 76 candidates across 41 papers into
  `harvest/impactview/personal-repo-candidates.json`.
  `harvest/impactview/verify_own_repos.py --write` then live-model-judged
  BOTH candidate pools together (178 total, well under the $20
  auto-submit line) against the paper's actual title+summary+authors,
  same heuristic-then-verify pattern as `verify_descendants.py`: **13/178
  confirmed** (11/102 phase-A, 2/76 personal-account), **165 rejected** --
  a 93% false-positive rate, confirming the mechanical step alone would
  have been useless without this pass (rejects included real accounts of
  real co-authors whose OTHER, unrelated projects collided on a shared
  word, e.g. Jason Ansel's PyTorch fork surfacing for an Aikido paper).
  Confirmed rows -> `harvest/repos/own-inventory.json` (verified.json-like
  rows, `own_group: true`, plus a `source` field). Result: 12 papers
  gained a confirmed own repo (some papers got >1 row). **The thesis gap
  is mostly still open** -- of the 72 no-repo theses, only 1
  (`willow:phd-thesis:2024` -> `finch-tensor/finch-jl-python`) got
  confirmed; most recent students (2025-2026 theses) either have no
  matching public account under their guessed handles, or their real
  account's repos don't share enough title vocabulary with a thesis title
  to clear the mechanical bar -- expected, since a thesis repo is often
  named after the tool, not the thesis title. Left `own-inventory.json`
  as its own file rather than writing into `verified.json` directly, and
  did not touch any `deephunt_*`/`deep_hunt_repos.py` files (that's
  `nextgen-a2`'s own in-flight lane) -- ping them so they can fold this
  and their phase A into `data/repos/` and build the stars-x-citations
  priority list for the human's tier-2 gating call.
- **own-repo-deep-hunt, picking up the ping** (2026-08-25): this is that
  session (`deep_hunt_repos.py`/`deephunt_*` are mine). My approach ran in
  parallel with phase A/B rather than after them, so before doing anything
  with the model I deduped `deephunt.json` against their two candidate
  pools (`harvest/impactview/own-repo-candidates.json` +
  `personal-repo-candidates.json`, 178 (key, repo) pairs already
  model-judged) and dropped the 5 papers their pass already confirmed
  (`harvest/repos/own-inventory.json`) -- 26 rows removed, 155 papers with
  a genuinely new candidate left (160 -> 155), confirming my pool is
  mostly disjoint from theirs, not a re-run of the same work. The
  difference is the author-identity method: theirs guesses a handle from
  the name and checks existence; mine resolves REAL logins three ways --
  surname-matched against already-verified own_group owners (12), an
  *exact* GitHub profile-name match against contributors to repos we
  already know are own-group (44 -- Andrew Adams, Jonathan Ragan-Kelley,
  Riyadh Baghdadi, Fredrik Kjolstad, Rohan Yadav, etc. all surfaced this
  way with no guessing), and a GitHub user-search-by-name fallback,
  profile-verified (140) -- 196/369 authors mapped, then a FULL listing of
  each mapped account's repos (not just guessed names), scored by
  requiring an actual title/description keyword overlap before date-
  proximity or "their own account" count for anything (an unrelated
  same-year hobby repo isn't evidence). `curate/verify_deephunt.py`
  (verify_repos.py's Batch pattern, reused directly) will write accepted
  rows into `own-inventory.json` too (append, same convention phase B
  established) rather than `verified.json`, so the two hunts land in the
  same staging file without racing each other; folding
  `own-inventory.json` into `verified.json` is a last, explicit step
  after both are done. Dry-run: 155 requests, ~$0.61 -- submitting per
  the standing auto-submit rule. Have not touched `data/repos/` (that's
  site-citations' claimed path, and it already has uncommitted phase-A/B
  changes in this shared worktree) -- leaving the `data/repos/` rebuild
  and the stars-x-citations ranking (queue task 2) for after the fold-in.
- **own-repo-deep-hunt, batch collected** (2026-08-25): all 155 requests
  succeeded, 0 parse failures. **26 net-new own_group-confirmed papers**
  (12 high-confidence, plus a handful at medium parked alongside; 12
  low-confidence rows to `harvest/repos/deephunt_review.json` for a human
  spot-check), appended into `harvest/repos/own-inventory.json` (now 54
  keys / 38 own_group-confirmed total across both hunts). Thesis
  coverage moved from 37/110 to 50/110 -- still real gaps, but real
  movement: `Chaitanya:meng-thesis:2025`, `Kumar:meng-thesis:2025`,
  `Mohr:meng-thesis:2024`, `Ramirez:sb-thesis:2021`,
  `ajay:phd-thesis:2025`, `charithm:sm-thesis:2015`,
  `denniston:sm-thesis:2016`, `ray:phd-thesis:2023`,
  `tej:meng-thesis:2016`, `won:phd-thesis:2026` all got a first repo this
  pass, mostly via the exact-contributor-name-match identity method (see
  above) rather than the org/keyword path. Corpus-wide: 126 -> 157 papers
  with >=1 own_group repo (verified.json + own-inventory.json combined),
  201 -> 170 still repo-less (73 -> 60 of the 110 theses/TRs).
  `harvest/impactview/tier2-priority.md` (c69745e6) was built from the
  pre-this-batch 13-row `own-inventory.json` -- it and `data/repos/` are
  now stale against these 26 new rows; rebuilding both is
  `harvest/impactview/build_repo_data.py` + `gen_tier2_priority.py`
  (site-citations' scripts, in their claimed path) rather than something
  this lane should run. Task `own-repo-deep-hunt` is otherwise complete
  from this lane's side -- remaining repo-less papers (esp. the 60
  theses) either have no public GitHub account discoverable by any
  method tried so far, or a real account whose repos don't share enough
  title vocabulary with a generically-named thesis to clear the
  keyword-overlap bar; closing that tail further would need a different
  signal (README fetch, PDF-body author-homepage links) than more of the
  same search.

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
- **Manual fulltext ingestion** (task `fulltext-ingest`, 2026-08-25): the
  human worked `harvest/fulltext/login-worklist.md` in a browser sitting
  and dropped 23 PDFs (named by DOI slug) in `~/workspace/nextgen-fulltext`
  (3 Elsevier rows from the worklist had no PDF -- inaccessible or
  skipped). `ingest_manual_pdfs.py` extracts with pypdf, writes with
  `errors='surrogateescape'` (malformed embedded font encodings in local
  PDFs occasionally leave lone surrogate codepoints in the extracted
  string, which a plain UTF-8 write raises `UnicodeEncodeError` on), same
  2000-char floor as `harvest_fulltext.py`. All 23 extracted cleanly (0
  failures, 0 below floor, 20k-137k chars each). Searches every
  `harvest/citations/*.json` for the slug, not just the worklist's
  designated paper, since several of these turned out to cite more than
  one corpus paper (one CGO'26 survey cites 9) -- 54 (key, slug) pairs
  total gained fulltext evidence, written to `harvest/fulltext/<key>/
  <slug>.txt` + sidecar. Fed straight into the taxonomy lane's rejudge
  (see its log): 36/53 rows with a prior judgment changed function or
  centrality (68%), a strong signal that a larger login fetch would pay
  off.

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
- **Fulltext rejudge** (task `fulltext-ingest`, 2026-08-25): the fulltext
  lane's manual PDF ingestion (see its log) gave 54 (key, slug) pairs real
  full text for the first time in this corpus -- 18 pilot, 36 non-pilot.
  Non-pilot went through the normal pipeline (cleared the 35 existing
  staging records + the 1 previously-unclassified slug, `--submit`
  --dry-run confirmed ~$0.32, submitted directly). Pilot rows went through
  a new one-off, `curate/rejudge_pilots_with_fulltext.py`, which reuses
  the exact same codebook/prompt/validation via live calls and patches
  `harvest/taxonomy/pilot-classifications.json` directly -- pilots are
  otherwise frozen, but a genuine evidence upgrade is worth a rejudge.
  While building this, found the fulltext evidence packer was head-
  truncating to 4000 chars (dead code path until now -- non-pilot papers
  never had cached full text before this task, so `evidence: "fulltext"`
  had never actually fired in production); for a real paper the citation
  is usually well past that point (confirmed: two rows scored `unknown`
  because the actual "StreamIt" mention sat at char ~55,000 of a
  69,000-char paper). Fixed with `windowed_fulltext()`: search in tiers
  (project name, then author surnames, then distinctive title words,
  stopping at the first tier with a real hit) and send excerpts around
  the actual mentions instead of the document head. Discarded and
  resubmitted the non-pilot batch once fixed (`msgbatch_
  01C8g9fe6VXT7U1p1kxLsKBy`, marked `"discarded"` in `_batches.json`, never
  collected) rather than merge results judged from truncated evidence.
  Result: 17/18 pilot rows and 19/35 non-pilot rows-with-a-prior-judgment
  changed function or centrality -- **36/53 changed, a 68% flip rate**,
  plus 1 non-pilot row classified for the first time. Confidence jumped to
  high/medium on nearly every changed row. The one pilot row that stayed
  `unknown`/low (`taylor:micro:2002` project name "Raw" is a common
  English word, so the keyword search caught an unrelated mention) is
  correct behavior, not a bug -- the model declined to guess on polluted
  evidence. `curate/merge_taxonomy.py --write` folded the 36 non-pilot
  rows into `data/citations/` (121 entries now show `evidence: "fulltext"`,
  including dedup groups where the fulltext sibling won). The 18 pilot
  rows still need `prototype/build_pilot_data.py` rerun by site-citations
  to reach the site's pilot `data/citations/<bibtexKey>.json` files.

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
- **Impact-view design** (2026-08-25, human design task): wrote
  docs/impact-view-design.md — three options for holding citations AND
  the three repo tiers in the paper entry (A: tabbed Impact panel;
  B: twin toggles sharing one grammar and one page-level surface;
  C: one interleaved panel) with Option B recommended, honoring the
  human's mid-task constraints (twin per-paper selectors are fine; the
  all-papers surface must be seamless; the Summary gains a third
  register accommodating repositories). Referenced Halide-world's
  docs/site.md for repo-presentation rules (stars over signature counts,
  no silent truncation, empty facets don't render) and the SDV
  integration vocabulary. Mocked Option B on StreamIt
  (prototype/impact.html + impact-mock.js): real Citations panel,
  Repositories panel in the citation grammar (tier bar,
  Integration/Stars/Recency sorts, Expand all, PLACEHOLDER-chipped
  tier-2 rows, paper-only descendant rows), and the three-register
  Summary with a specimen repo sentence. Stopped for human review —
  a taste decision.
- **Category label compacted** (2026-08-25): "(44, cited by 142)" →
  "(44, by 142)". publications.js?v=14.
- **Impact-view refinements** (2026-08-25, three rulings while the mock
  was under review): (1) one sort vocabulary across both panels — the
  repos panel's Integration/Stars became Impact/Popularity, each panel
  interpreting the names natively (category depth vs relationship depth;
  cited_by vs stars); (2) the paper's badged archival artifact joins the
  Repositories panel, listed first in an "Artifact & own repository"
  group; (3) the two taxonomies normalized into ONE: the citation
  categories' names are the group-level vocabulary for repos too (Builds
  on it = derivative works/forks, Uses the system = API users/inherited,
  Adopts the idea = idea-descendant repos; bibliographic categories
  simply don't render for repos), SDV integration terms demoted to
  per-row chips, and the page-level category facet can now govern both
  panels. Doc + StreamIt mock updated; still stopped for design review.
- **The sketch-frontend lesson** (2026-08-25): the human pointed at
  asolarlez/sketch-frontend building on StreamIt's IR — verified by code
  search (AUTHORS credits the MIT StreamIt team; sketch.compiler.* embeds
  StreamIt's grammar/IR with renamed packages; streamit.frontend.*
  survives in scripts and old trees). Recorded as a real derivative-work
  row in the StreamIt mock and as a doc appendix on catching renamed
  embedded forks: namespace archaeology, grammar/IR fingerprints,
  provenance files, comment fingerprints, and the paper-side net —
  including a recommendation that the idea-descendants task widen from
  extends/adopts-idea to also include uses-tool at core centrality,
  without which Sketch-class descendants fall through.
- **F1 summaries-at-scale, phase 1** (2026-08-25): wrote
  docs/summary-style.md — the binding style reference: the three-register
  Summary, all voice/truth/seam/shape rulings from the pilot phase
  (superlative and present-anchoring ban lists, no numeric counts in
  prose, grounding and honesty-vs-profile rules, COMMIT-not-external,
  KISS), the repository-sentence rules, the wave process, and the 9 pilot
  exemplars embedded verbatim. Built the wave pipeline
  (harvest/summaries/generate_receptions.py — Batch API, style doc as
  system prompt, revise-don't-rewrite over existing receptions, evidence
  packs now including verified own repos and badged artifacts;
  merge_wave.py refuses pilots and touches reception.json only). 6 waves
  of ≤25 non-pilot papers by citation count. Wave 1 (top 25, est $0.28 —
  auto-submit rule) submitted; reviewer pass next; after wave 1 lands,
  STOP for the human's ~10-paper spot-check per F1.
- **F1 wave 1 merged** (2026-08-25): the top-25 batch came back 25/25
  (cost ~$0.28); mechanical screen clean; reviewer pass read every text
  against docs/summary-style.md — grounding spot-checks all landed
  (SIFt, Zephyr, FiberSCIP, SweeD all in their packs) and 4 hand-fixes
  normalized present-anchored repo closers ("continues its life",
  "is maintained") to the sanctioned "lives on" form. 15 receptions
  updated (10 already satisfied the style doc — mostly papers without
  repo data), 10 unchanged; repository sentences now close the texts for
  the 10 papers with verified repos/artifacts (opentuner, dynamorio,
  taco + badges, both Halide gateways, three StreamIt papers,
  petabricks, dmtcp). STOPPED per F1: the human spot-checks ~10 before
  waves 2-6.
- **F1 waves 2–6 merged** (2026-08-25, human approved wave 1): five
  batches submitted together (123 papers, ~$1.37 est., under the $20
  line), all returned complete (123/123). Mechanical screen (ban lists,
  present-anchoring, numeric counts, leaks): zero hits. Five reviewer
  agents (one per wave) verified every text against its evidence pack;
  16 texts fixed — recurring classes: present-anchored repo closers
  ("is maintained", "is available", "carries forward"), COMMIT-internal
  or same-author works presented as external reception (drake's Gordon
  thesis, Finch's WingSpan, Gladshtein's own follow-ons), one leaked
  writer instruction ("only modest claims are possible"), one numeric
  count in prose, two shape violations (unearned second paragraph), one
  invented "survey" label, and one over-repeated opening (the style
  doc's twice-per-wave rule). All fix texts re-screened and their named
  repos/artifacts verified against the packs before applying.
  merge_wave.py --write per wave: 73 receptions updated, 50 already
  satisfied the style doc; pilots, hand-written summaries, and
  gscholar.json untouched. F1 complete — all 157 receptions now conform
  to docs/summary-style.md.
- **Impact tools unified in name and behavior** (2026-08-25, human
  ruling "citation categories and citation panels now are both
  citation/repository — names should reflect that"): the page-level tool
  boxes are renamed "Impact categories" and "Impact panels" (tooltips
  state the shared scope), and the sharing is now real: the page-level
  Sort drives repository panels too (repo panels register for
  setGlobalPanels resync; their local buttons follow), and the category
  filter maps onto repo groups through the unified taxonomy (builds-on →
  extends, uses → uses-tool, benchmarks → uses-benchmark, adopts →
  adopts-idea; 'own' rows are the paper's own artifact, always visible).
  Centrality and citing-work search stay citation-only per their
  tooltips. FUTURE TASK (human, 2026-08-25): the Paper thresholds
  sliders (Citations ≥, Impact) must eventually score BOTH citations and
  repositories via a hidden composite — blocked on normalization until
  tier-2/3 repo data reveals the repo-count distribution (tier-1 max is
  3 repos/paper, too thin to weight).
- **Pilot refold after fulltext rejudge** (2026-08-25, taxonomy lane
  request): reran prototype/build_pilot_data.py --write for
  halide:pldi:2013, taylor:micro:2002, thies:cc:2002 after the manual
  PDF ingestion rejudged 18 rows (17 changed function/centrality).
  Only those 3 pilot files + index.json changed; other pilots,
  gscholar.json, reception.json untouched.
- **Own-repo inventory + tier-2 priority list** (2026-08-25, human
  directive: find ALL our repos first — theses especially — then rank
  the outside-user hunt by stars × citations). Phase A
  (find_own_repos.py): enumerated the 33 own-group GitHub owners' 346
  non-fork repos, mechanical match → 102 candidates. Phase B (repos
  lane, 74be0f6c): personal-account hunt over 191 repo-less papers +
  model verification of BOTH pools — 13 confirmed / 165 rejected (93%
  FP rate; auto-accepting either pool would have poisoned the data).
  Confirmed rows live in harvest/repos/own-inventory.json; the builder
  now folds them in (role=website rows stay inventory-only — project
  pages are not impact). Site: 139 papers / 211 rows. Deliverable for
  the human's gating call: harvest/impactview/tier2-priority.md — all
  52 own GitHub repos ranked by log-stars + log-citations
  (gen_tier2_priority.py regenerates). KNOWN GAP, needs a human
  decision: only 1 of 72 repo-less theses gained a repo — guessing
  student accounts doesn't work; the next lever is reading each
  thesis's own full text for repo URLs/tool names (fulltext-lane
  machinery), and pre-2008 theses predate GitHub entirely.
- **F2 impact-view rollout** (2026-08-25, human-ordered before F1's
  remaining waves): the approved Option-B impact view is live for ALL
  papers. New data layer (claimed): `harvest/impactview/build_repo_data.py`
  reads `harvest/repos/verified.json` + `harvest/artifacts/found.json`
  (read-only) and emits `data/repos/papers/<bibtexKey>.json` +
  `data/repos/index.json` per the new `data/repos/SCHEMA.md` — own-group
  tier-1 rows plus badged artifacts (listed first), enriched with GitHub
  stars/description/last-push/archived via GITHUB_TOKEN (cached in
  `harvest/impactview/ghmeta.json`); rows deduped by canonical repo name,
  and `third_party` rows excluded even when own-group authored (they are
  the paper's dependencies — the reverse direction of impact). Kept clear
  of the ecosystems lane's future `data/repos/<ecosystem>.json` by using
  a `papers/` subdirectory; when tier-2 ecosystems and tier-3 descendants
  land, the builder folds them into the same files with no front-end
  change. Front-end: `citations.js` grew the Repositories panel (same
  grammar — "N repositories" headline, tier bar only when tiers are
  mixed, Impact/Recency/Popularity with tooltips, Expand/Collapse all,
  unified-taxonomy groups with citation-category names, star/active/
  artifact/SDV chips, evidence as row tooltip, greyed paper-only rows for
  tier 3); `publications.js` wires a lazy "Repositories (N)" toggle
  beside Citations for the 131 papers with data, a "Show repositories"
  expand-all button, and the overview clause "… and 162 repositories".
  Initial-load payload grew only by `data/repos/index.json` (~10 KB);
  per-paper files still lazy-load on expand. TEMP pilot button kept per
  F2. Browser-verified: toggles/sorts/expand-all/graceful absence all
  exercised on localhost. Rebuilt 2026-08-25 after the repos lane's
  verified-quirks dedupe (33ffb5db): 161 rows (one og-cgo20
  artifact/implementation duplicate merged upstream, evidence folded
  into the kept rows); builder-side (name, role) dedupe kept as a
  safety net. Tier 3 folded in 2026-08-25 (repos lane's
  harvest/repos/descendants.json, 9ef15f75): the 30 LOCATED descendant
  repos render as "Adopts the idea" rows (GitHub-enriched, skipped if
  the repo already appears for the paper) — 190 rows / 135 papers, 17
  with mixed tiers (the tier bar now shows), 4 new descendants-only
  papers. Unlocated rows deliberately not rendered: those citing works
  already appear in the Citations panel, and the unsearched widened
  bucket (1,060 rows) would swamp the view — revisit when its
  search+verify wave runs. Also fixed a stale-cache bug this exposed:
  per-paper data fetches (citations and repos) now use cache:'no-store'
  like the indexes; in-memory caches still prevent refetch-per-expand.

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
