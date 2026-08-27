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
| **repos** | `harvest/repos/` | **active** — step 1 (in-paper discovery) done: all 353 PDFs scanned, 142 code-host URLs verified into `harvest/repos/mentions.json`, and `harvest/repos/search-plan.json` prepared for the 268 papers with no live repo link. Step 2 (task `repos-search step 2`, 2026-08-24) complete: `search_github.py` scored candidates via the GitHub REST API for all 268 -- 217 strong, 27 weak-only, 24 none -- into `harvest/repos/candidates.json`. Auto-accepts nothing; see lane log. Task `repo-verify` (2026-08-25, complete): `curate/verify_repos.py`, a Batch API model pass over all 303 papers with any repo evidence (24 of 327 have none) -- pilots submitted and pushed first per instruction, spot-checked, then the remaining 295 (~$1.14 total). 183/303 papers got >=1 verified repo (132 implementation, 115 third_party, 16 benchmark, 10 artifact roles; 148 own_group / 125 not); 25 papers have a low-confidence row parked in `harvest/repos/review.json` for human spot-check; 120 genuinely have none (spot-checked several -- old theses/papers, or search candidates that were real projects but unrelated, e.g. "Umbra" collided with a game exploration tool and a CMS). Canonical-over-fork worked as designed (tensor-compiler/taco over manya-bansal/taco; correctly split cases like an author's personal DynamoRIO fork containing thesis work vs. the canonical upstream). See lane log. Task `verified-quirks` (2026-08-25, complete): fixed the repo-rename duplicate rows the impact-view lane flagged (`curate/dedupe_verified_repos.py`, 3 papers, resolves each URL's owner/repo through the GitHub API -- which auto-follows a rename -- and groups by the stable numeric repo id rather than URL text; string-level canonicalization can't catch a rename). Also removed a dead, actually-buggy helper (`_github_repo_from_url`, never called: `.rstrip('.git')` strips a character set not a suffix, silently mangling "graphit" to "graph" -- caught while writing the real dedup logic). The other flagged quirk (own_group=true rows with role=third_party) is NOT a bug: verified `harvest/impactview/build_repo_data.py` already excludes role=='third_party' from the "own" tier regardless of own_group, by design, and every one of the 7 such rows is a genuine case (the same research group's other tool used as a dependency) -- no change made. Task `descendants-all` (2026-08-25, partial -- see below): tier-3 idea-descendant extraction, corpus-wide -- `curate/build_idea_descendants.py` (mechanical + light search) + `curate/verify_descendants.py` (model check on search hits). 1,795 qualifying rows (extends/adopts-idea at core/engaged, uses-tool at core, per the sketch-frontend-lesson widening); Both waves now run and verified (human approved the widened wave's cost after `nextgen-a2` explained it) -- **47 genuine descendant repos located across 24 papers total** (30/17 from the strong wave, +17 more from the widened uses-tool/core wave's 83 search hits, 66 of which were correctly rejected as false positives -- an 80% FP rate on this bucket, even higher than the strong wave's 59%). See lane log. Task `own-repo-deep-hunt` (round 7, claimed 2026-08-25): `nextgen-a2`'s phase A (org/account enumeration, 102 candidates) plus this session's phase B (personal-account hunt for the 191 repo-less papers, esp. theses) both landed; joint model-verification judged 178 candidates together, **13 confirmed** into `harvest/repos/own-inventory.json` -- thesis gap still mostly open (1/72). A concurrent hunt in this same round (verified-identity author map via exact contributor-name matches + GitHub search, not guessed handles) added **26 net-new own_group-confirmed papers** on top of that (deduped against the 178 already-tried pairs first) -- corpus-wide own_group coverage 126 -> 157 papers, repo-less 201 -> 170 (theses/TRs 73 -> 60 still repo-less). `harvest/repos/own-inventory.json` now 54 keys / 38 confirmed total; `data/repos/` and `tier2-priority.md` are stale against the later 26 and still need a rebuild. See lane log for both hunts' numbers. Task `own-repo ranking` (round 7 task 2, 2026-08-25, complete): rebuilt `data/repos/` (`build_repo_data.py --write`, 162 papers/245 rows, up from 139/211) and `harvest/impactview/tier2-priority.md` (`gen_tier2_priority.py`, now 71 ranked own repos, up from 52) against the now-current `own-inventory.json`. Found and fixed a real bug along the way: the later deep-hunt batch's 26 net-new rows store `url` as a bare `"owner/repo"` string (no `github.com/` substring), unlike every earlier row (verified.json + phase-A/B own-inventory rows), which all carry a full URL -- `build_repo_data.py`'s `fullname_of()` required that substring, so those rows silently got no GitHub star/description/last-push enrichment, and `gen_tier2_priority.py`'s own-repo filter (`'github.com' not in url`) silently dropped them from the ranking entirely (19 real own repos missing, no error). Fixed `fullname_of()` to accept a schemeless `"owner/repo"` string while still correctly rejecting a full non-GitHub URL (verified.json has 4 gitlab/bitbucket rows that must NOT be misparsed as an owner/repo pair), and switched the ranking filter to key off the already-normalized `name` field (exactly one `/`, no spaces) instead of re-testing the raw `url`. STOPPING here per the queue's gate: `harvest/impactview/tier2-priority.md` is the ranking sheet for the coordinator's tier-2 outside-user-hunt pick (dynamorio needs explicit human approval, per the standing rule) -- did not pick a hunt list myself. Noticed a live concurrent session actively writing under `harvest/ecosystems/` (uncommitted `candidates.json`/`enumerate_candidates.py`/`measure_candidates.py` etc., files changing minute-to-minute) while working this task -- left that path untouched. **Follow-up** (2026-08-25, later): picked up the ecosystems lane's flag on `174c18fd` (`curate/verify_deephunt.py`'s bare-`owner/repo` bug fixed at the source, `own-inventory.json`/`deephunt_review.json` urls corrected to real `https://github.com/...` links) -- reran `build_repo_data.py --write`; exactly the 26 flagged `data/repos/papers/<key>.json` files changed (url field only, bare string -> real link), `data/repos/index.json` and `tier2-priority.md` both byte-identical to before (ranking already keyed off the normalized name, unaffected). Task `own-inventory fold + repos rebuild` (round 8 task 1, 2026-08-25, complete -- logged under the **ecosystems** row above, since that's where the concurrent session doing it in parallel had already been posting; same numbers, not re-duplicated here): hit a live file-collision mid-task (a concurrent session wrote its own, slightly cleaner version of `curate/fold_own_inventory.py` to the same path while this session was mid-run) -- used theirs rather than fight over which wins, confirmed via diff it had already run `--write` by the time this session got there, then finished the job (`build_repo_data.py` + `gen_tier2_priority.py` rerun, byte-identical output as expected). One number worth calling out here: corpus-wide own_group coverage in `verified.json` alone (now the single source of truth) is **155 papers / 172 repo-less** (theses 50/110 covered) -- two fewer than round 7's own-inventory-inclusive count of 157, exactly the 2 papers (`arxiv:2005.04091`, `tiramisu`) whose only own-inventory row was `role: website`, correctly left out of the fold and correctly not counted as "having an own repo." Task `deephunt confidence pass` (round 8 task 4, 2026-08-25, complete): `curate/deephunt_confidence_pass.py` re-judged all 12 `deephunt_review.json` papers (13 low-confidence rows) with real fuller evidence -- the candidate repo's actual README + root file listing (fetched live, not re-used from the first pass) plus the paper's own summary -- via an independent Batch call with extended thinking enabled (budget 3,000 tokens; the Messages API's lever for "high reasoning effort" on a batch call, no separate effort field exists). Compared each new verdict's `own_group` against the original: **8 agreed false** (confirmed rejections, e.g. `zhao:cgo:2008`'s `ZJU-SPAIL/pipa` -- README states it's a 2024 Python analytics platform from a different university, pure name coincidence with 2008 CGO authors Zhao/Cutcutache/Wong), removed from the review queue; **0 agreed true** (none of the low-confidence own_group=true candidates held up, including reversing the one originally-true row -- see below); **4 disagreed**, left in `deephunt_review.json` for a human and logged both verdicts in `harvest/repos/deephunt_review_resolved.json` rather than auto-resolving either way -- these are genuinely a definitional question (same-lab-org repo vs. this-specific-paper's-own-artifact), e.g. `ithemal/Ithemal`: Saman Amarasinghe and Michael Carbin co-author both it and the citing position paper, but Ithemal is an independent artifact with its own separate ICML paper, not an implementation of the position paper itself. One genuine reversal, not a disagreement in the tracked sense since it flows the other direction: the ONE row originally marked own_group=**true** (`ray:phd-thesis:2023` -> `finch-tensor/finch-jl-python`, "companion tool from the same research group") got reconsidered to **false** with fuller evidence (the README shows Finch.jl is unrelated to Ray's actual thesis topics -- UniTe/CoLa/SHiM/block-based video compression -- and finch-tensor is a different research group entirely); tracked as a disagreement (true->false) and left for a human rather than silently dropped. Also hit and fixed a real bug: one response had an invalid `\'` JSON escape (a model over-escaping an apostrophe in "Baron's thesis") that `json.loads` rejects outright -- recovered that one row by hand and added a general fix to `curate/verify_repos.py`'s shared `parse_record()` (strips `\'` -> `'` before parsing) so every script that imports it benefits. `deephunt_review.json` now down to 4 keys, all genuine human-judgment calls, not stale low-confidence noise. Round-8 task 5 ("widened descendants search wave") checked, not re-run: the queue's "carried if not claimed" hedge was stale by the time this round posted -- `harvest/repos/descendants.json` already shows the widened wave's search+verify step fully run against all 1,060 uses-tool/core rows (round 7, see `descendants-all` above): 1,795 total rows, 47 `located: true` across 24 papers, matching round 7's own DONE summary line-for-line. No unsearched rows remain in that bucket. Not claiming/redoing this. Task `deephunt closure` (round 9 task 4, 2026-08-26, complete): applied the coordinator's ruling ("own repo" means THIS paper's own artifact, not just same-lab) to all 4 disagreement rows from the confidence pass -- found `curate/deephunt_closure.py` already written and already run (`--write`) by a concurrent session by the time this lane got to it, just not yet committed; verified its logic and output were correct, then committed it. All 4 close to `own_group=false, role=third_party` (3 keep their original verdict, since the reconsidered pass's "true" only ever established same-lab, not this-paper's-artifact; `ray:phd-thesis:2023` flips from its original true to false, since fuller README evidence showed `finch-tensor/finch-jl-python` is a different research group's project entirely, not a companion tool). Both verdicts + the ruling text are preserved in each row's `final` field in `deephunt_review_resolved.json` for provenance; `deephunt_review.json` is now `{}` -- the lane is closed, nothing pending. Nothing merges into `verified.json` (all four are own_group=false, matching `deephunt_confidence_pass.py`'s own "agreed false -> no merge" convention). |
| **authors** | `harvest/authors/` | **active** — `authors_build.py` parses every `author0` into individual authors, dedupes exactly, enriches from Crossref/OpenAlex, matches `data/people.xml`, and writes `harvest/authors/authors.json` (369 distinct authors) plus `harvest/authors/review.json` (221 flagged rows: 4 name-variant near-misses + 217 from the enrich pass). `enrich_openalex.py` resolves each of the 369 against their own OpenAlex author entity (ORCID or shared-work match, never name alone) into `harvest/authors/enriched.json`; 287/369 resolved (task `authors-enrich verify`, 2026-08-24 — OpenAlex's search quota reset, rerun recovered 24 of the 79 previously-blocked people; 77 genuinely unresolved, 5 ambiguous, 0 still search-blocked; see lane log). Task `authors-worklist` (2026-08-25, complete): `build_session_sheet.py` writes `harvest/authors/session-sheet.md` -- Part 1 lists the 77 unresolved + 5 ambiguous people (papers, reason, OpenAlex candidate ids for the ambiguous ones, Scholar/LinkedIn search links); Part 2 is a LinkedIn-presence checklist for all 369, alphabetical, each with a constructed (never visited) LinkedIn search URL and known affiliation/homepage/OpenAlex link as disambiguation context where resolved. Fetches nothing. Task `authors fold + backstop` (round 10 task 1, 2026-08-26, complete): `fold_session_results.py` folded `session-results.json`'s 31 matches + 2 tentative into `enriched.json` as `gs_user`/`affiliation`/`gs_evidence` (33 with a Google Scholar id now). 6 names needed a manual variant map to this corpus's actual `author0` spelling (a parsing/formatting difference, not a fresh judgment: "Bennet Yee" -> authors.json's `"and Bennet Yee"` -- a real `authors_build.py` parse bug, an "and " conjunction leaked into the name, out of scope here; "Daniel Reed"->"Dan Reed"; "Allan Snavely"->"A. Snavely"; "William J. Dally"->"Bill Dally"; "Jonathan Frankle"->"Jonathan Elliott Frankle"; "Mark Richards"->"M. Richards"). Kept the sitting's two same-name-trap resolutions verbatim (Michael I. Gordon explicitly NOT the Oregon State namesake; Dan Campbell the NVIDIA/Georgia Tech one). Backstop for the 9 `not_settled` + Nishil Talati: found a genuine, verifiable fix for Talati rather than a generic search -- our own `author0` spells him "Talathi" (extra h), which is why `enrich_openalex.py`'s shared-work method silently failed the coarse-key comparison despite him co-authoring an OpenAlex-linked paper (`randomwalk-iiswc21`, W3212503094) with Saman Amarasinghe; the real authorship list spells him "Nishil Talati" (verified live), so resolved via that exact same shared-work method with the spelling corrected -- ORCID, 67 works, h-index 14, UIUC affiliation, all real. The other 9 (mostly obscure 1990s HPC-report co-authors or unpublished MEng-thesis authors with no indexed OpenAlex presence) got a genuine `authors?search=` name query each: 0 or 2-5 ambiguous hits for every one, never a clean single match -- **0 resolved, 9 stay unresolved**, logged plainly rather than guessed (the "never on name alone" rule this lane has followed throughout would have rejected a single-hit candidate too, but none even reached that bar). `review.json` unchanged (0 backstop candidates cleared even the single-hit bar to be worth flagging). Task `author-links harvest` (round 10 task 2, 2026-08-26, mechanical sources complete, web-search pass in flight): `build_links.py` -- no LinkedIn/Scholar fetched, per the RULING. Four free sources, all inheriting verification from where the identity was ALREADY established (never name-alone): (a) ORCID (`https://orcid.org/<id>` for anyone `enriched.json` resolved via shared-work/ORCID match); (b) OpenAlex `homepage` (from the person's own public ORCID researcher-urls, 42 people); (c) GitHub -- for the 196 people `deephunt_authormap.json` already resolved a real login for, the profile page + the profile's own `blog`/`email` fields; (e) email extracted from the person's own paper PDFs (data/publications.json's local `url` field, ~309 papers, first 3 pages only), kept only when the local-part matches their surname. Real find: one person's GitHub `blog` field pointed at a LinkedIn URL -- routed to a distinct `linkedin_incidental` tier (not treated as a generic "personal" site, not picked as this harvest's "best" tier) so it feeds the coordinator's LinkedIn sitting directly instead of masquerading as a verified personal link. **271/369 got a link this pass** (27 permanent-academic, 232 professional, 12 email, 0 personal-only), **98 residue** -- `links-residue.md` splits them into "nothing found" vs "unverified incidental LinkedIn URL, check directly" for the sitting. Bounded web-search pass (source d) on the 62 residue people with a known affiliation, complete: **24/62 found** (37 genuinely not found even with an affiliation to search against -- mostly name collisions correctly rejected, e.g. a Stanford GSB economist/Nobel laureate sharing a name with our SUIF-compiler Robert P. Wilson, a University of Kansas urologist sharing a name with our systems-paper Binh D. Vo; 1 skipped, flagged deceased), folded into `links.json` as `web_search` candidates. Real-time note: two of four parallel research forks briefly got confused mid-task (one started narrating as if it were the orchestrator coordinating the other forks, rather than reporting its own findings) -- caught via "trust but verify," re-run directly rather than accepted at face value. **Final: 295/369 people (80%) have a link** (237 professional, 43 permanent-academic, 12 email, 3 personal-only), **74 residue** (`links-residue.md`, all "nothing found" -- the incidental-LinkedIn bucket from the mechanical pass is now empty since that one case also had a professional GitHub candidate). Output ready for task 3 (site render) to combine with the LinkedIn sitting per the RULING's priority order. Task `apply sitting-2 rulings` (round 11 task 5, 2026-08-26, complete): hand-applied the coordinator's 3 close-out judgment calls -- (a) Richard P. Sollee III confirmed (`/in/solleer`); (b) `yee-lok-won` merged into `yee-lok-wong` (papers `ansel:cgo:2011`/`ansel:mitcsail-tr:2010` moved over, won's name kept as a variant), confirmed LinkedIn attached; (c) `y-zibin` renamed to "Yoav Zibin" (name field only, `person_id` kept stable) with `/in/yoav-zibin-6392651` attached -- also resolved the pre-existing `review.json` affiliation-conflict flag for him (Come2Play is the sitting-confirmed CURRENT role, Google reads as a prior employer, not cluster contamination) and synced `linkedin-results.json`'s `awaiting_him`/verdict bookkeeping so these two don't show as pending in task 4's join. **Live collision, same task**: found `apply_sitting2_rulings.py` already written on disk (untracked, ~minutes old) by a concurrent session working the identical task with a materially different design choice (rename `person_id` too, vs. keep it stable) -- applied my own edits by hand first, then deferred to the concurrent script's more conservative `person_id`-stable design once discovered (reverted my one field), and rewrote the script idempotently (verified a rerun now safely no-ops) as the durable record. `git status` immediately before commit showed only this task's own 5 files plus two unrelated modified/untracked files from other in-flight work (`tests/ui/report.md`, `harvest/impactview/qualify_state.json`) -- left both untouched, staged by explicit path only. Task `exascale author names` (round 11 task 6, 2026-08-26, complete): recovered full names + 2008-09 affiliations for this paper's initials-only co-authors straight from the report's own front matter -- `papers/2009/amarasinghe-exascale09.pdf` Appendix D.1 ("Extreme Scale Software Study Group Members", p.135) lists all of them by full name and organization. **Caught a real error in the task's own scope first**: the queue listed 13 names, but 3 (P. Negi, C. Pacheco, F. Sherwood) aren't in this report at all -- `harvest/authors/authors.json` shows they're each attached to a completely different paper (`palkar:vldb:2018`, `perkins:sosp:2009` x2) -- flagged rather than resolved. The other 10 (Carlson, Harrison, Hill, Hiller, Karp, Koelbel, Koester, Levesque, Scarpelli, Snavely) are genuinely this paper's, all resolved with a clean page/section citation, written to `harvest/authors/exascale-names.json` and folded into `authors.json`/`enriched.json` (`apply_exascale_names.py`, original initials-only form kept as a variant). Bounded WebSearch pass for "permanent page outranks LinkedIn" candidates per the RULING found two real ones: Robert Harrison's live Stony Brook faculty page (moved on from Oak Ridge since 2009), and Allan Snavely's UCSD memorial profile -- **he is deceased** (SDSC announced his passing; the free-harvest pass had already flagged and skipped him for exactly this reason) -- linked but explicitly marked never-send-to-a-LinkedIn-sitting. The other 7 (mostly government-lab or consultant, no public institutional bio page found) plus the 3 misattributed names are the residue back to the coordinator for a sitting, per the task's own closing instruction. Task `academic-page hunt for ORCID-only` (round 12 task 7, 2026-08-26, complete): population = 141 people (`links.json` best_tier `professional` with an ORCID-sourced candidate -- close to but not exactly the queue's stated 158, since `links.json` kept evolving under concurrent sessions; used the precise, reproducible definition instead of chasing an exact number). Free mechanical pass first: fetched every person's public ORCID record (employment history + researcher-urls) -- 29 had a usable researcher-url, 46 had employment but no url, 66 had neither (fell back to `enriched.json`'s OpenAlex affiliation / `authors.json`'s paper-derived affiliation as search context). Fanned out 6 parallel research forks (WebSearch/WebFetch, never LinkedIn, never name-alone) to verify or find a live permanent page for each, cross-checked against paper topic/co-authorship. **101/141 found, 40 not_found** -- `harvest/authors/academic-pages.json` + full breakdown in `academic-pages-report.md`. Folded all 101 into `links.json` as `permanent-academic` tier (best_tier upgraded), which is the task's whole point -- removes them from the LinkedIn-sitting pool. `links.json` now: 145 permanent-academic (was 44) / 136 professional / 68 residue. **Real data-quality find**: 11 of the 141 had a WRONG ORCID (or, twice, OpenAlex) resolution already sitting in `enriched.json` -- a genuinely different person's employment history entirely (e.g. `deepak-narayanan`'s OpenAlex affiliation was "Sathyabama Institute", nothing to do with the real NVIDIA/Stanford ML-systems researcher who co-authored `Zaharia:CIDR:2017`). Caught only because the wrong employment/field was inconsistent with the actual paper -- 5 of the 11 still resolved correctly via independent search (flagged in their `academic-pages.json` evidence text), the other 6 (`steven-hall`, `mark-halsey`, `yanbin-liu`, `albert-ma`, `martin-c-martin`, `jason-miller`) stay `not_found` since no correct page surfaced either. Recommend a follow-up to re-run or manually clear these 11 in `enrich_openalex.py`'s output so future passes don't inherit the bad steer -- not fixed here, out of this task's scope. `links-residue.md` is now stale (still lists people who no longer need a sitting) -- flagged, not regenerated here. Task `exascale author names` addendum (round 12's revision to task 6, 2026-08-26): the queue widened the population to add Dan Campbell and Andrew Chien (already full names in `author0`, only missing an affiliation) -- same report, same Appendix D.1 citation, plus a live current permanent page for both (Campbell still at Georgia Tech Research Institute; Chien moved on to a University of Chicago CS professorship since the 2009 report). Appended to `exascale-names.json`, folded via the same `apply_exascale_names.py`. Also applied identity ruling 5(d) separately while here: `albert-ma`'s `links.json` entry carried a wrong GitHub candidate (`adadima` -- a surname-substring collision with Alexandra Dima, who correctly owns that account) from `harvest/repos/deephunt_authormap.json`'s own mapping table; removed the bad row from that table (so a `build_links.py` rerun can't reintroduce it) and the candidate from `links.json`, leaving his ORCID entry as the sole/correct link. **This commit also carries a concurrent session's in-progress work on `links.json`** (round-12 task 8's audit application -- dropping wrong/flagging-uncertain GitHub candidates the academic-page hunt's entries had been sitting alongside) that landed on disk while this session was mid-edit; spot-checked several rows (Agarwal, Lee, Sarkar) against the queue's task 8 spec before including it -- correct and clearly in progress, not authored by this session, not further verified beyond the spot check. Task `apply the GitHub match audit` (round 12 task 8, 2026-08-26, complete -- this is that in-progress work, now finished): applied all three actionable buckets of the coordinator's manual `github-match-audit.json` (198 accounts checked in his browser). (a) 17 wrong matches: dropped the bad `github_profile` candidate plus everything derived from it (`github_blog`/`github_email` -- a site or address scraped from the wrong account is equally invalid), recomputed `best_tier`. Albert Ma's `adadima` was already gone from `links.json` by the time this ran (a concurrent fix, see above) -- nothing to do there. The other 16: 8 now have no link at all (real residue, not a bug -- `Rob Schreiber`, `Henry Hoffman`, `Matthew Brown`, `Matthew Frank`, `Johnathan Babb`, `Dan Campbell`, `William Harrod`, `Eric Wong`), the rest fell back to an ORCID/email candidate they already had. (b) 19 uncertain matches: flagged (not removed -- kept for if a real second signal appears) and excluded from `best_tier` ranking. Did the repo-contributor check the task asked for: of the 19, 7 have an own repo traceable via `harvest/repos/verified.json` (DynamoRIO/dynamorio, bthies/streamit x3, spac-proj/SPAC x2, ithemal/bhive+Ithemal) -- fetched each repo's live contributor list, checked for the handle: **no match in any of them** (two spac-proj/SPAC checks came back inconclusive, the API returned 0 contributors entirely). Settles nothing new; all 19 stay uncertain, exactly the task's default. (c) 39 zero-repo/unverifiable accounts: the audit file only kept a 20-item *sample* of this bucket (its wrong/uncertain buckets are exhaustive and match their summary counts; this one and the 123-strong "looks right" bucket aren't) -- re-derived the real list myself by fetching `public_repos` for all 178 `github_profile` candidates still standing after (a)/(b): 17 zero-repo accounts, one already handled under (b) (Larry Rudolph), the other 16 flagged the same way as (b). Net effect on `links.json`: 147 permanent-academic / 104 professional / 18 email / 5 personal / 3 linkedin / 1 memorial / **90 residue** (up from 68) -- dropping bad and unverifiable GitHub matches necessarily surfaces more people with no reliable link, not fewer; that tradeoff is the whole point of running this audit. Full per-person breakdown in `harvest/authors/github-audit-applied-report.md`. **Claimed as round-12 Lane B (ACADEMIC PAGES) and Lane D (EXASCALE NAMES)** (sonnet, 2026-08-26 ~15:05): both lanes' deliverables already exist and were checked against current disk state before touching anything, per the no-guess/no-redo pattern this row has followed all along. Lane B: `git log a720e05f..HEAD` touches neither `harvest/authors/academic-pages.json` nor `harvest/authors/links.json` — population unchanged. Recomputed the population fresh from current `links.json` (`best_tier: professional` + an orcid.org-sourced candidate) and diffed it against `academic-pages.json`'s own recorded `not_found` set: **identical, 40/40 people, exact match** — no one has drifted into or out of the ORCID-only cohort since the hunt ran, nothing left to hunt. Lane D: `exascale-names.json` already has all 12 people (10 original + Campbell/Chien addendum), matching the queue's full round-12 scope; same zero-commits check confirms nothing changed underneath it either. Both lanes closed as verified-complete, no-op this round. |
| **site-citations** | `docs/citation-design.md`, `docs/impact-view-design.md`, `docs/summary-style.md`, `harvest/summaries/`, `data/citations/SCHEMA.md`, `data/citations/gscholar.json`, `data/citations/reception.json`, the 8 pilot `data/citations/<bibtexKey>.json` files, `data/citations/index.json` (bootstrap; merge script owns non-pilot rows), `prototype/`, `harvest/impactview/`, `data/repos/SCHEMA.md` + `data/repos/index.json` + `data/repos/papers/` (the ecosystems lane keeps `data/repos/<ecosystem>.json`), and — for the citation view only — `publications.html`, `assets/js/citations.js`, the citation-view additions in `assets/js/publications.js` + `assets/css/style.css` | **active** — the per-paper citation section, designed, prototyped, human-APPROVED, and now **integrated into `publications.html`** (task `site-integration`, 2026-08-24): one small `index.json` fetch at page load turns on a "Citations (N)" toggle for the 150 papers with data files; per-paper data lazy-loads on first expand. Three sort modes (Impact / Recency / Popularity) with a headers on/off toggle — all three render uniform collapsible groups, collapsed by default with counts (categories / years / count buckets); expanded Summary and Citations panels sit in a lightly-outlined shaded box; Recency and Popularity incorporate own-group citations chip-marked, Impact keeps them in their separate section. `prototype/` kept as reference. `data/citations/SCHEMA.md` remains the contract; non-pilot `<bibtexKey>.json` files belong to the classify-corpus merge. |
| **fulltext** | `harvest/fulltext/` | **active** — `harvest_fulltext.py` fetches full text of citing works for 8 pilot papers via free routes (OpenAlex OA location, arXiv, Unpaywall, PMC). Cached text/sidecars are gitignored; `harvest/fulltext/manifest.json` (committed) has per-paper yield stats. Does not touch `harvest/citations/`. Task `abstracts-all` (2026-08-24, complete): `harvest_abstracts_all.py` extended the abstract harvest from the 8 pilots to every non-pilot citing work, batch-fetched via OpenAlex's OR filter (100 ids/request) rather than one-by-one -- 167 papers, 21,545 citing works, 14,014 gained a real abstract (65%). Deliberately left the 3 sampled high-cited pilots' abstract files untouched (they're inert for reclassification -- pilots are permanently excluded from `curate/classify_citations.py`'s population). Fed the taxonomy lane's rejudge sweep (see its log). Task `login-worklist` (2026-08-25, complete): `build_login_worklist.py` finds citing-work judgments on the "detailed" side of the taxonomy at low confidence from contexts-only evidence, whose DOI belongs to a paywalled publisher (IEEE/ACM/Springer/Elsevier) -- reads pilot-classifications.json and every harvest/taxonomy/records/<key>/*.json, joins back to harvest/citations/ for the citing work's own metadata, fetches nothing. 26 rows (9 ACM, 8 IEEE, 6 Springer, 3 Elsevier) written to harvest/fulltext/login-worklist.json + a publisher-grouped checklist in login-worklist.md for the human's browser sitting. Task `fulltext-ingest` (2026-08-25, complete): the human worked the worklist and dropped 23 PDFs in `~/workspace/nextgen-fulltext`; `ingest_manual_pdfs.py` extracted all 23 (pypdf, surrogate-safe write, 2000-char floor -- 0 failures, 0 below floor), covering 54 (key, slug) pairs since several citing works cite more than one corpus paper. Found and fixed a real bug in `curate/classify_citations.py`'s fulltext evidence packing along the way (was head-truncating to 4000 chars, missing citations in the related-work section of any real-length paper -- now `windowed_fulltext()` searches in tiers for the cited paper's actual mentions). Re-judged all 54: 18 pilot rows via `rejudge_pilots_with_fulltext.py` (live calls, patches `pilot-classifications.json` directly -- pilots are otherwise frozen, but a genuine evidence upgrade earns a rejudge), 36 non-pilot via the normal batch pipeline. **36/53 rows with a prior judgment changed function or centrality (68%)** -- see lane logs for both. Task `login-worklist2` (2026-08-25, complete): expanded population (confidence low/medium contexts-only detailed-side, OR unknown, OR title-only-with-a-DOI; IEEE/ACM/Springer, Elsevier skipped this pass) deduped by DOI across the whole corpus -- `build_login_worklist2.py`, 3,641 rows (1,432 ACM / 1,243 IEEE / 966 Springer) with ready-to-fetch URLs, written to `harvest/fulltext/login-worklist2.json`. IEEE arnumbers resolved via Crossref's bulk filter API (40 DOIs/call, zero publisher requests) -- `resource.primary.URL`'s `/document/<arnumber>/` or the vor `link` entry's `?arnumber=`; 21 IEEE DOIs dropped for lack of either. Task `sitting2-ingest+audit` (round 9 task 1, 2026-08-26, complete): (a) ingested all 3,606 sitting-2 PDFs from `~/workspace/nextgen-fulltext` via `ingest_manual_pdfs.py` -- 3,599 ok / 5 below the 2,000-char floor / 0 extraction failures, 3,175 (key, slug) pairs gained fulltext evidence. Fixed two real bugs along the way: a perf bug (rescanned all 177 `harvest/citations/*.json` files, 135MB, once PER PDF -- fine for sitting #1's 23 files, would've taken hours over 3,606; now a single precomputed slug->keys index) and a crash (`errors='surrogateescape'` on write only rescues surrogates in the exact byte-range it creates on decode -- a malformed PDF font map handed back a lone surrogate outside that range on one file, killing the whole batch mid-run; now scrubs the full surrogate range right after extraction). (b-e) `audit_sitting2_misses.py`: diffed `login-worklist2.json` (3,641 rows) against disk -- **3,606/3,641 matched (99.0%), 58 misses**, all with a `_run-log*.json` entry (no unattempted/session-dead rows this round, unlike the task's anticipated categories) -- 37 `200-access-wall` (near-empty body), 20 real `404`, 1 network error. Verified all 58 at Crossref + OpenAlex title search: **6 had a genuine DOI/URL bug** (an OCR-style typo, a doi.org redirect to a reassigned DOI, a literal `10.1145/nnnnnnn.nnnnnnn` placeholder DOI upstream, two ACM-labeled DOIs whose real paper is actually IEEE, and one ACM proceedings-companion-vs-paper DOI collision where only one of two same-title DOIs actually serves a PDF) -- all repaired with the corrected DOI/URL. **3 are genuinely dead ends** (pre-2006 ACM papers with no valid DOI at Crossref or OpenAlex under any title search). Checked every remaining miss for a free OpenAlex OA route -- found only a deprecated, now-403 ACM `ft_gateway.cfm` link and one unconfirmed HAL landing page, neither safe to auto-apply. `harvest/fulltext/login-worklist3.json`: **55 rows** worth a login-sitting retry (6 repaired + 49 verified-correct, whose prior attempt hit a real access wall under an anonymous fetch -- exactly what a login sitting exists to get past, not evidence of unrecoverability). Full breakdown in `harvest/fulltext/sitting2-report.md`. STOP per the task: coordinator decides if a third sitting (~55 papers) is worth it. Task `thesis citations from our own corpus` (round 9 task 5, 2026-08-26, complete): `curate/mine_thesis_citations.py` -- scan (mechanical, free): word-boundary search all 3,681 distinct full-text documents already harvested for the ~87-107 no-DOI theses' first-author surname, tightened after a first pass (loose 3-word bar) hit 3,508 candidates dominated by common-surname noise to a two-tier bar (4+ title words alone, or 2+ with a thesis+MIT+year cluster) -- **976 candidates / 51 theses**. verify (Batch, $2.01): **584/976 confirmed (60%)**. `recheck-siblings` ($0.81, added mid-task after a real bug): 25 of 43 confirmed theses turned out to have a same-first-author, near-identically-titled PUBLISHED paper already in this corpus (the normal thesis -> conference-paper path, e.g. Gordon's S.M. thesis vs. its co-authored ASPLOS paper) -- the verify pass had no way to know, so it confirmed **435/584 (75%) of those 25 theses' citations as the PAPER's, not the thesis's** (multi-author, no thesis/dissertation language). Re-verified with the sibling's real title given: 7 re-confirmed as the thesis, 379 correctly reclassified to the paper, 49 neither. **156 citing-work pairs folded across 29 theses** (0 unresolvable) into brand-new `harvest/citations/<thesisKey>.json` files, then through the standard `classify_citations.py` (~$1.13) + `merge_taxonomy.py --write` -- these 29 theses now have real `data/citations/` files for the first time (138 distinct works after dedup: 65 passing / 34 detailed-citation / 15 uses-tool / etc). Full breakdown in `harvest/fulltext/thesis-mining-report.md`; honesty caveat there too (our-corpus-only, a lower bound -- 79 of ~108 no-DOI theses still have zero data). **Coordinated with a concurrent round-9 task-2 rejudge session throughout**: hit the same live-worktree pattern twice -- a duplicate classify-corpus batch (both sessions independently found the same 164 newly-unlocked candidates and submitted within 4 seconds of each other; harmless, ~$1 double-spend, second `--collect` just overwrites with an equally-valid judgment) and again on 8 final stragglers (22 seconds apart). The final `merge_taxonomy.py --write` in this commit therefore also picks up that concurrent session's now-essentially-complete rejudge sweep (180 `data/citations/` files touched total, not just this task's 29) -- credited here since it landed in the same working-tree state, not claimed as this task's own work. Also deduped `needs-review.jsonl` (43 -> 8 unique rows; every retry of the same ~8 persistently-empty-response citing-work records had been appending an exact-duplicate line rather than replacing it) -- the underlying empty-response bug on those 8 old Springer-LNCS-era DOIs is unresolved and is `classify_citations.py`'s own, pre-existing issue, not investigated further here (out of this task's scope). Round-10 task 4 ("carried, if not done" on all four round-9 items) checked, 2026-08-26: all four already landed by the time round 10 posted -- rejudge round 2 (`efe8e2c4`, 68.7% combined flip rate, pilot refolded), thesis-mining fold (`fa441aa5`, this row above), site round (TEMP button `5c6411e2`, halide tier-3 `dc241195`, tier-2 fold + browser-verify `695f6e69`), deephunt closure (`bdd654fc`). Nothing to redo. Task `data tails` (round 11 task 3, 2026-08-26, complete): (a) authors fold + backstop and (b) thesis-mining fold were already landed before this round posted (round-10 task 1 `9604dcc3`, round-9 task 5 `fa441aa5`/`3db9165d`/`e0c57e3a`) -- round 11's queue text re-listing (a) as open looks like it predates seeing those commits, nothing to redo. (d) sitting-3 ingest: only 6 of the 55 `login-worklist3.json` PDFs are on his disk so far (partial sitting, not the "fetched" the round-9 DONE note implied) -- ran `ingest_manual_pdfs.py`, which uncovered a real perf bug: it re-extracted PDF text for all 3,618 already-cached files on every run (only skipped the *write*, not the expensive pypdf extraction itself) -- a routine 6-new-file update was on track to take 45-60+ minutes. Fixed to skip extraction entirely when every citing key a slug maps to already has a cached `ok` sidecar (28+ min -> 6 sec on rerun, verified). 6 genuinely new (key, slug) pairs gained fulltext (all landing on theses this session's own thesis-mining task already touched: `saman:phd-thesis:1997`, `gordon:sm-thesis:2002`, `karczmarek:sm-thesis:2002`, `puppin:sm-thesis:2002`). (c) rejudge: of those 6, only `saman:phd-thesis:1997` had `confidence: low` (the round-6/round-9 clearing rule's bar); cleared and reclassified -- flipped from `passing-citation`/low/contexts to `adopts-idea`/`engaged`/medium/fulltext (a real citing work builds on the thesis's linear-inequality array dataflow analysis, not just a passing mention). The other 5 stay at their existing medium-confidence contexts-tier judgment per the same rule (not function:unknown or confidence:low, so not in scope for a clear-and-redo). Also deduped `needs-review.jsonl` again (16 -> 8 exact-duplicate rows from repeated retries of the same ~8 persistently-empty-response old Springer-LNCS records -- still unresolved, still pre-existing, still out of scope here). Claimed as round-12 Lane C (2026-08-26, `sonnet`, DATA TAILS): re-checked all four sub-tasks against current disk state before doing anything, per the "don't guess/don't redo" pattern established above. (a) authors fold + backstop and (c) rejudge round 2: `git log a720e05f..HEAD` over `harvest/citations/`, `harvest/fulltext/`, `harvest/theses/`, `harvest/authors/enriched.json` shows zero commits since round 12 posted -- both tasks are exactly the round-10/round-9 work already logged above and in the taxonomy row (`efe8e2c4`), nothing changed underneath them, nothing to redo. (b) thesis-mining fold: same -- already landed (`fa441aa5`/`3db9165d`/`e0c57e3a`), unchanged. (d) sitting-3 ingest: re-diffed `harvest/fulltext/login-worklist3.json`'s 55 rows against `~/workspace/nextgen-fulltext` on disk -- still only 6/55 present (same 6 this row's own round-11 entry already ingested), 49 still missing. This is an account-gated fetch (publisher login walls), squarely his job per the standing rule, not something a worker session can push further -- queuing rather than waiting: **flagging to him that sitting-3 (49 remaining PDFs) has been sitting untouched since round 11** in case it fell off his queue. Lane C is a no-op this round; nothing written. |
| **taxonomy** | `harvest/taxonomy/`, `docs/taxonomy-draft.md`, `curate/`, `data/citations/<bibtexKey>.json` for non-pilot papers, `data/citations/index.json` (owns it after the first merge run, preserving the pilot rows) | **active** — pilot human-reviewed (approved with one amendment, applied 2026-08-24 as codebook v0.2): two-dimension citation taxonomy (FUNCTION × CENTRALITY, plus flags/evidence-tier/confidence per row) drafted from a stratified deep read and applied to all 4,629 citing-work records of the 8 pilot papers (2,751 judged; 1,878 title-only left `unclassified`). v0.2 replaced residual `mentions` with `detailed-citation`/`passing-citation` and re-split all 701 affected rows (349/352). Deliverables: `docs/taxonomy-draft.md` (codebook, worked examples, per-pilot distributions, S2 `isInfluential`/`intents` comparison) + `harvest/taxonomy/pilot-classifications.json`. Built `curate/classify_citations.py` (task `classify-corpus`, Anthropic Batch API) and `curate/merge_taxonomy.py` (emits data/citations/SCHEMA.md's shape for non-pilot papers only, never touching the pilot files or gscholar.json). Dry-run cost estimate reported (~$69/10,021 requests), approved by the human; actual submit came in at 11,082 requests / 28 batches (see lane log) — all collected, 22 rule-level rejections fixed by a parser/repair fix and recovered, 11,082/11,082 classified. `merge_taxonomy.py --write` folded all 142 non-pilot papers into `data/citations/<bibtexKey>.json` + `index.json` (144 papers total, pilot rows and files untouched). Task `classify-corpus` complete. Task `cited_by verify`: harvest-layer backfill was site-citations/nextgen-a2's work (see their log); `merge_taxonomy.py` updated to set `cited_by` (max over dedup siblings, always present per SCHEMA.md) and rerun `--write` — all 142 non-pilot files now carry it, pilot files/gscholar.json verified untouched. Task `commit-papers redefine` (2026-08-24): added `is_saman()` (byte-identical to `prototype/build_pilot_data.py`'s copy) and replaced `own_group`/`n_own` with `commit`/`n_commit` per the human's schema refinement (COMMIT papers = Saman-authored citing works, not author-overlap-with-the-cited-paper); verified against both pilot files' `counts.commit` before rerunning `--write`. Task `abstracts-all + rejudge sweep` (2026-08-24, complete): after the abstracts-all pass (fulltext lane), cleared 603 existing staging records that were `function: unknown` or `confidence: low` and had just gained a real abstract, so they'd regenerate with better evidence; previously-title-only rows needed no clearing (`load_candidates()` picks up an evidence-tier upgrade automatically). Dry-run came to 7,766 requests / ~$56 (over the $20 auto-approve line) — human approved. Hit a duplicate-`custom_id` Batch API rejection mid-submission (3 literal duplicate citing records in `harvest/citations/`, same DOI twice with whitespace-differing titles); fixed by deduping `load_candidates()` on `(key, slug)`, collected the 1,600 already-sent requests first so they wouldn't be re-billed, then resubmitted the remaining 6,166 clean. Also fixed two more model-output quirks (bareword `"confidence": low`, an occasionally-omitted `flags` field) via the same parser/`repair()` pattern as classify-corpus. Final: 18,242 total staging records, folded into 165 non-pilot `data/citations/` files (up from 142 -- 23 papers with zero prior judgeable content, several from `idmap-review-rest`'s OpenAlex-only resolutions, now have their first citation page) totaling 18,554 works, 13,024 judged (70.2%, up from the classify-corpus baseline). `index.json` now has 173 papers. Task `rejudge round 2` (round 9 task 2, 2026-08-26, complete): re-judged every (key, slug) pair that gained fulltext evidence from the sitting-2 ingest (3,175 pairs -- 396 pilot / 2,779 non-pilot). Pilot: `rejudge_pilots_with_fulltext.py` (live calls) -- **396 rows, 325 changed function or centrality (82.1%)**, 305 function / 236 centrality changes; only `halide:pldi:2013` and `netblocks-pldi24` had any affected rows, refolded via `prototype/build_pilot_data.py --write` (merge_taxonomy.py never touches pilots -- confirmed the other 6 pilots' output was already in sync, no spurious rewrite). Non-pilot: cleared 2,744 existing staging records (35 of the 2,779 had never been staged at all -- picked up automatically), submitted via `classify_citations.py` in two under-$20 waves (the full 3,662-request backlog priced at ~$30.63, over the line) plus small cleanup rounds for empty-model-response failures -- **2,743 rows compared, 1,832 changed (66.8%)**, 1,759 function / 1,545 centrality changes. Combined: **3,139 rows with a prior judgment, 2,157 changed (68.7%)** -- consistent with round 1's 68% flip rate, confirming fulltext evidence upgrades reliably change judgments most of the time. 1 sitting-2 target row (plus 7 unrelated pre-existing backlog rows swept into the same batches) permanently stuck in `needs-review.jsonl` with a genuinely empty model response on every retry -- accepted as a logged residual per standing practice, not chased further. **Process note**: a concurrent session's broad `git add`-style commit (`fa441aa5`, their thesis-mining task) swept up this session's uncommitted non-pilot `data/citations/` + staging changes into their own commit before this session could commit them separately -- content verified intact (spot-checked 20 random affected rows, all correct) so no data was lost, but it meant this task's own work landed under someone else's commit message with no independent record. Caught because the pilot side's staleness (pilots are excluded from that sweep's build path) surfaced a real, separate, second issue: `prototype/build_pilot_data.py` hadn't been rerun after the pilot rejudge, so `halide:pldi:2013`'s data/citations file was still serving pre-rejudge evidence/confidence/centrality until this session ran it. Pinged `nextgen-a2` re: the shared-index collision (same failure mode logged earlier this project under `verified-quirks`'s lane -- "stage only right before commit" holds, but doesn't fully protect against a *concurrent* wide `git add` landing between your own edit and your own commit). |
| **docs** | `docs/refresh.md` | **active** — task `refresh-docs` (2026-08-25, complete): the every-few-months refresh procedure, one phase per pipeline stage (idmap → citations harvest → abstracts → classification → repos → merge → gscholar → reception/summaries), each naming its script, worker-vs-human, and cost-gating rule; a closing list of what never runs automatically (publications.json, gscholar.json, the pilot files, anything behind a login). |
| **ui-tests** / **Lane A (UI TESTS)** | `tests/ui/**` | **green, no STOPs for Lane E** — round-11 task 1 (old spec): 908 cases, 907 passed, 1 bug found, closed green by Fable (task 2, `cf72756e`). Round-11 task 1 (new spec, `tests/ui/SPEC.md`): `tests/ui/random_settings_test.py`, RUN COMPLETE — 100/100. Round-12 Lane A re-verification (2026-08-26, `a1a21701`) against Lane E's subsequent UI commits: `facet_test.py` **909 cases, 0 failed**; `random_settings_test.py` **RUN COMPLETE — 100 tests, 100 passed, 0 failed, seed 42**. Fixed a report-filename collision (both scripts wrote `tests/ui/report.md`; `facet_test.py` now writes `tests/ui/combinatorial-report.md`) and an oracle-staleness race (both now reload their data snapshot fresh every test case, since a concurrent lane's commit mid-run was otherwise misreadable as a site bug). **Lane E is clear to proceed — nothing outstanding from Lane A.** See lane log + `tests/ui/report.md` + `tests/ui/combinatorial-report.md`. |
| **ecosystems** | `harvest/ecosystems/` | **active** — task `halide-import` (round 7 task 6, 2026-08-25, complete): confirmed `data/repos/papers/halide:pldi:2013.json` had zero rows attributed to `samanamarasinghe/Halide-world` before this (its 8 tier-3 rows all came from this corpus's own generic descendants pass). `build_halide_import.py` fetches that repo's `data/site/halide-index.json` (schema v1, corpus-wide index of 16 Halide anchors) via the GitHub contents API and maps ONLY the `pldi2013-halide`-anchor slice onto `data/repos/SCHEMA.md`'s row shape -- mapping, not re-judging (every verdict/star/evidence value is Halide-world's own). Tier-3: 162 rows / 130 citing papers that published their own artifact repo (a bare "mentions another repo" does not qualify, matching this corpus's own idea-descendants rule) -- modest, panel-reasonable, safe to fold into `data/repos/` directly. Tier-2: 567 real code-level rows (verdict consumer/generator/uses_source → `uses`, halide_copy_or_fork → `builds-on`); deliberately excluded 2,828 `third_party_bundle` rows (Halide arrived only inside a vendored dependency) and 67 `prose_only` rows, both counted in the report, not hidden. **567 is a large single-paper ecosystem, on the order of the outside-user hunts round 7's strategy flagged for human approval (dynamorio)** -- staged in `harvest/ecosystems/halide-import.json` + `halide-import-report.md` rather than written into `data/repos/` (site-citations' claimed path), pending a human look at whether/how to render all 567 at once vs. a capped view. Task `ecosystems measure-step` (round 7 task 5, carried since round 4, checked while this lane was open): `harvest/ecosystems/candidates-report.md` was never absent-but-local, it never existed anywhere in this repo's history, and there is no separate "3 pilot tiers" pipeline distinct from what `data/repos/` + this halide-import already are -- the round-4 plan's `harvest/ecosystems/<repo>/` MEASURE step was superseded in practice by the actual build order this corpus took (verify_repos.py's tier-1 -> build_idea_descendants.py's tier-3 -> today's own-repo-deep-hunt/tier2-priority.md ranking -> this halide-import), which is a real ecosystem-size estimate per own-group repo, just not shaped like the round-4 spec expected. Treating task 5 as superseded rather than duplicating effort chasing a file path that was never going to be filled. **Retraction, same session**: a concurrent session started writing exactly that file (`harvest/ecosystems/candidates-report.md`, plus `candidates.json`/`enumerate_candidates.py`/`measure_candidates.py`/`verify_ecosystem_candidates.py`/`verified.json`, seen uncommitted in this shared worktree) minutes after the above was logged -- so it was not in fact abandoned, just not yet landed when this lane checked. Left every one of those files untouched (not mine, still in flight) and did not re-close task 5 a second way; whoever lands it should log there, not overwrite this entry. **Also, real bug found and fixed**: `curate/verify_deephunt.py`'s `build_request()` displayed a candidate's bare `owner/repo` string to the model as if it were "the URL" (preferred `c['repo']` over `c['url']` when both existed) -- the model dutifully echoed that bare string back as its own `url` field, so all 66 rows (53 own-inventory.json + 13 deephunt_review.json) from this session's batch stored a `url` with no `github.com`/`https://` at all. `harvest/impactview/build_repo_data.py` and `gen_tier2_priority.py` (site-citations, c4fc4da4) worked around the *filtering* symptom (dropped own-repo rows from the ranking) but their fix keys off the normalized name, not the url string -- so `data/repos/papers/<key>.json`'s `url` field for these 26 papers is STILL the bare, unlinkable string as of that commit. Fixed at the source: `own-inventory.json` and `deephunt_review.json`'s urls rewritten to real `https://github.com/...` links, and `build_request()` now always shows the real URL (falls back to constructing one from `repo` only if `url` is truly absent). **site-citations: `data/repos/papers/` for the 26 papers this session's deep-hunt touched needs a `build_repo_data.py` rerun to pick up the corrected urls** -- the ranking counts are already right, only the link field is stale. **Follow-up, round 8 task 1** (2026-08-25): folded `harvest/repos/own-inventory.json`'s confirmed rows into `harvest/repos/verified.json` (`curate/fold_own_inventory.py`, reuses `dedupe_verified_repos.py`'s `dedupe_paper()` verbatim -- canonical-over-fork by GitHub numeric repo id) -- the deferred merge both deep-hunt sessions left. 66 own-inventory rows: 43 folded in as new verified.json rows, 18 merged into an existing verified.json row for the same paper+repo (several genuine renames caught by numeric-id resolution, e.g. `finch-tensor/finch-jl-python` -> `willow-ahrens/finch-tensor`, `radha-patel/SySTeC` -> `radha-patel/symmetry-compiler`), 5 `website`-role rows left as the only content of `own-inventory.json` (inventory-only by existing design, never rendered). 29 papers gained their first own_group repo in verified.json. Reran `build_repo_data.py --write` + `gen_tier2_priority.py` after: `data/repos/index.json` and `tier2-priority.md` came out BYTE-IDENTICAL (only 3 papers' evidence text changed) -- `build_repo_data.py`'s own per-paper `(name, role)` dedup was already silently absorbing these same cross-file duplicates via GitHub-metadata name resolution, so this fold's real effect is data hygiene (one canonical own-repo source of truth, richer merged evidence, no longer relying on that incidental protection) rather than a site-visible change. `harvest/repos/verified.json` is now that single source; nothing else reads `own-inventory.json` except its residual 5 website rows. Did not touch `harvest/ecosystems/` (a concurrent session is actively building `candidates.json`/`verify_ecosystem_candidates.py`/`verified.json` there, uncommitted, for round 8 task 2 -- left untouched). **Halide tier-2 fold** (round 8 task 3, 2026-08-25, complete, human-approved): taught `build_repo_data.py` to read `harvest/ecosystems/halide-import.json` (specifically, by filename -- not a generic directory scan, since round-8 task 2's ecosystems hunt is concurrently writing other, differently-shaped files into the same directory) and fold its 567 tier-2 rows into `halide:pldi:2013`'s paper output verbatim (mapped, not re-judged -- no GitHub refetch; stars/evidence stay Halide-world's own). Only 565 landed as new rows -- 2 were already present among the paper's existing 7 `adopts` rows from this corpus's own generic descendants pass, correctly deduped by name rather than double-counted. Added a third sort bucket (`own` < `uses`/`builds-on` ecosystem tier-2 < `adopts` tier-3) since the existing two-bucket sort had no slot for the new group values; `index.json`'s tier-counting already had `using` bucket support for `uses`/`builds-on`/`benchmarks` pre-built and unused until now. `halide:pldi:2013` now: 573 rows (1 own / 565 using / 7 adopts), up from 8. Left tier-3's other 162 staged rows unfolded -- the round-8 task text and the human ruling both named only the 567 tier-2 rows, and folding tier-3 wasn't asked for this round. Task 3b (impact-view spot-render) is next and unclaimed. **Round-8 task 2, tier-2 outside-user hunt for all 71 own repos, complete (2026-08-25)**: `enumerate_candidates.py` fetched real candidate identities behind nextgen-a2's `ecosystem-measure.json` counts (dependents-graph scrape + the same README/description-mention search, re-run for actual hits) plus a new signal, forks pushed >30 days after their own creation checked against the real compare API for an actual `ahead_by` -- 763 candidates, 0 trimmed by the 300/repo cap. `verify_ecosystem_candidates.py` model-judged every one (SDV vocabulary, explicit reject bucket for curated "awesome-*" lists per nextgen-a2's flag) -- **266/763 confirmed (35%)**: 160 fork / 80 api_user / 18 derivative_work / 7 inherited / 1 uses_benchmark, expanded across every paper each own repo maps to (real mapping via `data/repos/papers/*.json`, not tier2-priority.md's truncated 3-paper column) into **1,241 rows across 103 papers**, `harvest/ecosystems/verified.json` keyed by bibtexKey, pre-shaped to `data/repos/SCHEMA.md`. Hit and fixed a resumability bug mid-run: the done-key was only recorded for confirmed candidates, so extending to the 19 newly-measured repos re-verified all 500 already-rejected ones from the first pass (live-call cost, no bad data) -- added `verify_seen.json`, a flat seen-set persisted regardless of `--write` since the model call's cost is already spent whether or not the result is kept. See `harvest/ecosystems/verified-report.md` for the full breakdown. Total spend across both enumeration+verify runs stayed well under the $20 line. Ready for nextgen-a2 to fold into the site's Builds-on-it/Uses-the-system/Uses-its-benchmarks groups. **Signal #4, fingerprint sweep for renamed embedded forks (2026-08-25, complete)**: the human caught `asolarlez/sketch-frontend` missing from StreamIt's tier-2 -- a renamed embedded fork invisible to dependents/mentions/fork-divergence (nextgen-a2 folded it by hand as an interim fix, `harvest/impactview/manual-rows.json`). `fingerprint_sweep.py` implements `docs/impact-view-design.md` section 7 for real: source-CONTENT code search on identifiers that survive a rename, scoped to the four own repos old/embedded enough for the pattern (streamit, taco, halide, dynamorio -- no sketch/SUIF own repo exists in this corpus to search from). Signatures pulled from each repo's own live source, not guessed: `streamit.frontend`/`SIRStream`/`at.dms.kjc` (streamit, section 7's own example), `TACO_TENSOR_T_DEFINED` (taco's runtime struct include-guard), `Halide::Internal` (Halide's IR namespace), `dr_fragment_t`/`dcontext_t` (DynamoRIO internals). 7 code-search queries -> 28 candidates -> verify pass (embedded-fork criterion added: renamed code + provenance/internal-identifier evidence = `derivative_work`) -- **26/28 confirmed (93%)**, far higher precision than the other three signals since matching real internal identifiers rarely coincidentally fires. `asolarlez/sketch-frontend` now correctly lands as `derivative_work` under `bthies/streamit` in `verified.json`, closing the human's gap with the harvest pipeline rather than the hand-patch. Other finds: `Granary/ARMed` and `ratel-enclave/ratel` (DynamoRIO-based systems with zero name resemblance), `StanfordAHA/Halide-to-Hardware_archive`, 8 repos embedding TACO's generated runtime as benchmark baselines (correctly split `derivative_work` vs `uses_benchmark` by whether the match was in the tool's own source vs. TACO-generated *output*). **Combined four-signal total: 292 confirmed across 791 candidates ever enumerated.** See `harvest/ecosystems/verified-report.md`. nextgen-a2's `manual-rows.json` hand-fix for sketch-frontend is now redundant with this harvested row -- worth a dedup check on their next fold. |

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

Full lane histories live verbatim in `docs/LANES-archive.md` (split 2026-08-26, cleanup batch D3). Each lane below keeps its latest entry only; append new entries here as before.

### setup

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

- **"Cited and Used by" facet** (2026-08-26, direct human request, not a
  queue task): a fifth facet — external people who cite one of our
  papers at real depth (citation centrality core/engaged, not a passing
  mention) or use one of our own repos (data/repos/ group in
  uses/builds-on/benchmarks/adopts) — replacing "Paper thresholds" in
  the cite-tools grid's 3rd column; Paper thresholds moved to its own
  full-width row below (human's choice among the layout options asked).
  `harvest/impactview/build_impact_authors.py` builds `data/
  impact-authors.json` (6,331 people): citing-work author names come
  from `harvest/citations/<key>.json`'s full `authors[]` array (matched
  back from `data/citations/<key>.json`'s judged population by the same
  DOI/title identity `build_citers.py` uses; falls back to parsing the
  truncated "A, B, C et al." display string only when no match); "used
  by" repo owners resolve to their GitHub profile `name` via `GET /users/
  {login}` (cached in `harvest/impactview/owner-profiles.json`, same
  pattern as `ghmeta.json`), falling back to the login/org name. Own-work
  exclusion (the human's explicit requirement — no author of one of our
  own papers, no owner of one of our own repos) matches on first+last
  name against `harvest/authors/authors.json`'s full 369-person set
  (name + variants), NOT bare surname+initial (that lane's own
  documented false-positive risk on common names) — **caught a real bug
  this way**: exact full-string matching missed "Saman Amarasinghe" vs.
  a citing work's "Saman P. Amarasinghe" and "Mary W. Hall" vs. "Mary
  Hall", so the first pass showed Saman and Mary Hall themselves as
  "external" citers of their own group's papers; first+last-only
  matching (ignoring middle names/initials) fixed both without
  introducing the surname-only risk. Known gap, not fixed: matches
  against papers-we've-authored, not the live people.xml roster, so a
  current lab member who hasn't yet authored an indexed paper (e.g. a
  new student using the group's own tools) can still surface as
  "external" — flagged, not solved, since fixing it risks the same
  common-name false-positive problem for a rarer case. Front end
  (`assets/js/publications.js`): mirrors the Authors facet exactly (sort
  by #papers/name, name search, OR-within-facet, dynamic per-item and
  header counts) via a new `listImpactAuthorsOf()` fed by an async
  post-boot fetch, same lazy-load convention as `citers.json`. Also,
  same session: every facet box (Years/Topics & Projects/Categories/
  Authors/Impact categories/Cited and Used by) now shows an
  "(N options)" count next to its label — generic hook in `buildFacetBox`
  keyed by a `.facet-count[data-for=<box id>]` span, so it tracks a
  name-search-narrowed count automatically; the Impact slider (discrete,
  step 1) gained visible tick marks via `<input list=...>` + `<datalist>`;
  the two Paper-thresholds sliders get a real gap now that they're not
  crammed into a third grid column. Browser-verified end to end
  (Playwright against a local static server): facet filtering, sort,
  search, header counts (including live narrowing while searching),
  Clear filters reset, tick marks rendering, mobile single-column
  fallback, zero console errors.

### ui-tests

- **Round-12 Lane A re-verification** (2026-08-26, `a1a21701`): re-ran both
  harnesses against Lane E's ~8 subsequent UI commits (box layout, Show All
  buttons, author-link rendering). First rerun of `random_settings_test.py`
  surfaced a false positive (`summary for 'How to do a million watchpoints...'
  contains literal 'undefined'`) — real text: "...undefined-value detection..."
  in `reception.json`, a legitimate CS term, not a leaked JS value; the
  undefined/null/NaN check was a blind substring match. Fixed to a bare-word
  match that also excludes hyphen-adjacent hits (compound words). Second
  rerun surfaced two flaky "order mismatch" failures on the same paper
  ("Adapting Convergent Scheduling Using Machine Learning") that vanished on
  a third rerun with no code change — traced to both harnesses loading their
  oracle's data snapshot ONCE at start while `page.reload()` re-fetches
  whatever's currently on disk on every single test case; since this repo is
  actively edited by four other concurrent lanes, a commit landing mid-run
  made the oracle and the live page look at two different moments in time.
  Fixed by reloading the oracle fresh right after every `reset()` in both
  scripts (~13ms per reload, negligible). Also found and fixed a real
  self-inflicted collision: `facet_test.py` and `random_settings_test.py`
  both wrote to `tests/ui/report.md`, so running the older harness silently
  clobbered the newer spec's named deliverable — `facet_test.py` now writes
  `tests/ui/combinatorial-report.md`; `tests/ui/report.md` stays exclusively
  `random_settings_test.py`'s per his `SPEC.md` instruction. Final clean
  results: `facet_test.py` 909/909, `random_settings_test.py` RUN COMPLETE
  — 100/100, seed 42. **No structural findings — nothing for Lane E to fix,
  Lane E is not blocked by Lane A.**

### cleanup

- **Phase-2 cleanup complete** (2026-08-26, batches A–G per
  `docs/cleanup-plan.md`): executed on an isolated worktree
  (`cleanup` branch), one concern per commit, with both UI harnesses +
  a golden behavioral snapshot (impact top-20, featured-10, overview
  totals) gating every batch — final state byte-identical to the
  pre-cleanup golden. Highlights: dead-code sweep of
  `publications.js`/`citations.js` and the oracle; single scoring
  module `assets/js/scoring.js` (the only JS home of the impact and
  featured formulas; `tests/ui/oracle.py` is the deliberate mirror);
  loud per-fetch boot failures (`.data-load-failures` line);
  `fileKeyOf()` centralizes the colon→underscore filename mapping;
  `reception`/`tiers`/`impact` residue stripped from shards and repo
  index (writers + readers + oracle moved together);
  `docs/DATA-FLOW.md` added; `docs/refresh.md` §8b site-data-build;
  ~6MB of closed-round intermediates deleted (own listed commits);
  `prototype/` retired, `build_pilot_data.py` promoted to `curate/`;
  10 one-off harvest scripts moved to `harvest/attic/`; this LANES
  split (D3). Full verification on the live repo's working tree before
  upload: 909/909 combinatorial + 100/100 random-settings, 370-file
  lazy-data sweep, Umami 4/4, console-clean, failure-injection retest,
  manual click-through. Deviation on record: batch B3's `git add -u`
  swept `docs/refresh.md` + test reports into its commit. Pending his
  ruling: the `papers/` legacy `.ps` archive (untouched).
- **`.ps` archive ruling resolved** (2026-08-27): the 3 PDF-less `.ps`
  files converted via ps2pdf (diego_SMT_MTEAC, sheldon-MEthesis,
  swenson-MEthesis; links repointed in `publications.json`, gate
  909/909 + 100/100), then on his instruction all 79 legacy
  `.ps`/`.ps.gz` files deleted from both repos after spot-checking 6
  ps/pdf pairs (identical page counts; text identical modulo the
  old-font extraction artifact). Live verified: `.pdf` twins 200,
  `.ps` 404. nextgen ad479772, commit-website e859e25.

### responsive

- **Responsive pass** (2026-08-27, `20a7db11` + `8e0e4597`, per
  `tasks/RESPONSIVE.md`): overlap bug first — `.cite-authors-block` was
  absolutely positioned over the cite-tools grid with a hand-computed
  width; when the ≤820px query stacked the grid it stayed pinned
  top-right and painted over the impact-category rows (his iOS
  screenshot). Now grid-area-anchored at desktop (pixel-identical:
  357.2px track, verified) and in normal flow when stacked. Two latent
  narrow bugs found under it: the unconditional multi-column
  `grid-template-columns` redefinitions later in the sheet overrode the
  820px stack rules (columns crushed to "2." slivers instead of
  stacking — stack rules now live at the end of the sheet), and plain
  `1fr` kept a min-content floor pushing the column past the viewport
  (now `minmax(0,1fr)`). Labels degrade by CSS class per tier
  (spans `.facet-label`/`.facet-cnt`/`.facet-detail`; full text in
  title + aria-label); fonts 13px rows / 12px headers at desktop (the
  one deliberate desktop change — everything else is behind max-width
  queries), 12/11px + 16px inputs below 700px. Below 700px: Filters
  collapses to one button with active count, accordion facets, Years
  chips, 44px rows, sticky result count; logo capped ≤940px. Gate:
  909/909 desktop combinatorial; random_settings 114/114 — 100 desktop
  + a new narrow-viewport layout pass (390×844, 768×1024: no
  horizontal scroll, no block overlap, every facet reachable).
  **Desktop is NOT byte-identical in rendering: the facet/header font
  sizes changed by his explicit ruling; the layout geometry is
  otherwise unmoved (authors track verified to the pixel).**
- **Responsive v2** (2026-08-27, `f112b87f` + `437b7f16`, per the
  updated `tasks/RESPONSIVE.md` v2 mid-flight — the v1 work above was
  never deployed): label tiers moved from viewport media queries to
  `@container` queries against each facet column (thresholds measured
  from where the real rows break: 359px full-prose, 239px badge), so a
  narrow column degrades even in a maximised window; fixed font steps
  replaced by `clamp()` (inputs hold 16px under the drawer
  breakpoint); below 700px the Filters button now opens a 100svh
  drawer with DEFERRED apply — selections update per-option counts and
  the pinned "Show N results" button live, the list renders only on
  the tap — plus removable active-filter chips above the results; the
  four facet columns are an intrinsic `repeat(auto-fit,
  minmax(220px,1fr))` grid (no media query). Logo got a 480w `srcset`;
  the result count is an `aria-live` region. **Desktop rendering: the
  facet columns are now four equal-width tracks instead of the
  0.54/1.4/1.12/0.94 proportional ones (deliberate, CHANGE 3), the
  facet type is fluid-clamped (~14px rows at wide windows), and the
  cite-tools row is pixel-identical (authors track delta 0.0px).
  Desktop filtering behavior unchanged — instant apply, no drawer, no
  chips.** Gate: 909/909; random 114/114 including the drawer
  count-match assertion at 390×844 (768×1024 has no drawer, by
  design). Screenshots before/after at both widths delivered for his
  review.

### alumni

- **Alumni page + roster** (2026-08-27, per `tasks/ALUMNI.md`). Sources: his
  103-thesis list (`harvest/theses/supervised-theses.json`, = 92 unique people
  after folding name variants — the file's `two_degrees_here` lists 9 but
  Sam(uel) Larsen and Jessica (Morgan) Ray are also two-degree people, 11
  total), and his UROP export (163 students with a non-cancelled term; the four
  all-cancelled — Biswal, Esteban, Malchik, Raza — excluded per spec). The
  export was taken from `~/Downloads/UROPS.xlsx` (319 term rows, 1997SU–2027FA;
  the spec's `~/workspace/alumni-roster/urop-roster.csv` had not been placed —
  counts match the spec exactly, so it is the same data; the derived
  `urop-roster.csv` now sits there for his records). **Emails, phones,
  addresses stay in `~/workspace/alumni-roster/` only; zero `@` in the repo.**

- **Thesis title conflicts, settled by title pages** (his rule): Frank =
  "SUDS: Automatic Parallelization for Raw Processors" (DSpace 1721.1/29629),
  Taylor = "Tiled Microprocessors" (DSpace 1721.1/38924) — in both the CORPUS
  was right and his list carried a working/paper title. Baron's corpus entry
  already had the title-page title. All recorded in
  `harvest/theses/title-resolutions.json`.

- **4 missing theses added to publications.json** (Garnett was a false
  missing): yap:meng-thesis:1999 ("SCAN: A Static Code Analyser for
  JavaScheme" — title-page spelling, Analyser with s; DSpace metadata's
  "statistic" is a cataloguing typo), wagner:meng-thesis:2006, tan:meng-
  thesis:2009 (PDFs pulled from DSpace, title pages read, local copies in
  papers/), and kelly:meng-thesis:2010 — **NO copy of Kelly's thesis found**
  (not in DSpace, not on the web, not in papers/): entry added from his list
  alone, no url, summary marked unverified. The four summaries are MY prose
  (from the theses' own abstracts), not his. Corpus now 331 entries; gates
  913/913 + 114/114.

- **people.xml regenerated**: 21 current (Kerdphoksup, Lichtstein, Keming Miao
  moved back to current — each has an approved 2026FA UROP term; Ege
  Kabasakaloglu + Aarush Vailaya added, same reason) and 244 alumni (was 85):
  13 thesis people added (Yishen Chen PhD'26+SM'21, Tammy Yap '99, Kevin Kelly
  '10, Alex Schwendner '10, Yoana Gyurova '15, Kevin Wu '15, Min Zhang '16,
  Malek Ben Romdhane '18, Sachin Shinde '19, Abdurrahman Akkas '19, Ricardo
  Gayle Jr. '23, Michael Bedford Taylor PhD'07, Jonathan Ragan-Kelley PhD'14)
  and 95 UROP-only students merged from the export with year spans. Kiriansky's
  two entries merged (PhD 2019 + MEng 2003, UROP 2000–02 span). Thesis always
  outranks UROP; two-degree people carry title2/year2 and the full span.
  Roles canonicalised (PhD/SM/MEng/UROP/Postdoc/Research Staff/Visiting
  Scholar/Visiting Student): Ph.D./MS/MENG spelling fixes; Research
  Scientist/Programmer/Affiliate → Research Staff; Postdoctoral Associate →
  Postdoc; Visiting Researcher (Okuda, Mitsubishi) → Visiting Scholar; all
  "Visting Graduate Student"/"Visiting PhD student"/bare "Visiting" → Visiting
  Student (ESI Algiers Tiramisu cohort + PoliMi + U-Mich, all enrolled
  elsewhere). Degree-from-thesis-list resolutions: Donenfeld → SM 2023,
  J. Ray → PhD 2023, Chou → PhD 2022, Shajii → PhD 2021, Bosboom → SM 2014,
  and UROP→MEng for Ziheng Wang '20, Manlaibaatar '20, Watanaprakornkul '12,
  Eric Wong '12. David Maze kept Research Staff 2004 with MEng 2001 as
  title2. Name fixes: Mathew→Matthew Drake, Michael→Michal Karczmarek (his
  list + LinkedIn). 19 year corrections to thesis years (Bruening 2005→2004,
  Chuvpilo 2003→2002, Amin 2008→2009, Dow, Dighe, Dima, Hsu, Agrawal
  2005→2004, etc. — full diff in git).

- **Current positions**: 43 alumni got a `position` attribute, rendered under
  the name in the facet-row clamp() step (people.js v110, style.css v110,
  `.person-position`). Sources: recorded LinkedIn sittings + academic-pages
  harvest + a small pass of faculty pages (Ragan-Kelley MIT, Amin Harvard,
  Chandramowlishwaran UC Irvine, Matsakis AWS, M. Gordon Aarno Labs, Olszewski
  cLabs/Celo). **Left blank + on the needs-him list (in the roster's Job
  source column)**: Rabbah (Postman vs "building Astro AI" — in flux), Puppin
  (Synthesia candidate, unanchored), Senanayake (stale Reservoir Labs),
  Sollee (identity below bar), Garnett/Akkas/Kleckner/Dighe/Steele/Tew/Vo/
  Petrov (sitting recorded a title but no employer), Changwan Hong (stale
  CSAIL directory), Yunming Zhang, Qin Zhao, Sam Larsen, Walter Lee,
  Chakrabarti, Kiriansky, Greenwald, Agrawal (identity confirmed, no current
  employer recorded). **Suspected wrong match flagged**: academic-pages.json
  equates Juan C. Reyes with Juan Carlos De los Reyes (MODEMAT Ecuador) —
  different career/degree history; not used.

- **Unresolved for him** (kept as "Graduate Student" on the page — no degree
  in his list, not guessing): Mit Kotak '25, Tom Chen '26, Logan Weber '24,
  Edward Wang '22, Amadou Ngom '21, Marek Olszewski '11 (his MIT PhD ~2012
  presumably co-advised). **Page claims a degree his list lacks** (kept,
  needs his confirm): Raphael/Chaudhary/Ruiz MEng '25, Saraff '24, Noyola
  '19, Birka '03, Jacobs '02, Chris Yu '04, Matsakis '99. **UROPs on the page
  but absent from the funded export** (kept): Minshu Zhan, Tom Pinckney,
  Haoran Xu, Hoi Wai Yu. **Weak match accepted, needs his eye**: page "Ted
  Allison" = export "Allison, Eric T." (2 terms, 2000). His list also spells
  Sitij **Agarwal** where page/corpus/LinkedIn say **Agrawal** — kept Agrawal.

- **UROP export vs no_link authors**: resolves the Artola spelling (corpus
  "Alexandro" → export **Alejandro** Artola, UROP 2000–01) and gives class-
  year + era anchors for Mathew Deeds, Matthew Drake, Zachary Holbrook,
  Christopher Leger, Sie Hendrata Dharmawan, Syed Raza (all-cancelled row) —
  evidence table WITH the historical addresses in
  `~/workspace/alumni-roster/no-link-evidence.csv` (kept local); links.json
  untouched per spec — coordinator folds via link-overrides.

- **Roster spreadsheet**: `~/workspace/alumni-roster/alumni-roster.{csv,xlsx}`
  — 499 people (262 alumni/current + 237 author-only), 162 historical emails
  (each dated), 320 URL-to-cite (from data/author-links.json, i.e. after
  overrides), 43 current jobs (each with source), 92 theses, 23 LinkedIn
  degrees (recorded sittings only). **Email (current) is entirely blank** —
  filling it means reading each person's own published page; that is a
  sitting-sized pass he should trigger separately. Historical addresses
  never became mailto: links anywhere.

- **Round 2, his answers folded in** (2026-08-27, tasks/ALUMNI-QUESTIONS.md):
  Tom Chen + Yishen Chen merged into "Yishen 'Tom' Chen" (PhD 2026); alumni
  rows now show ONLY the highest role — no second degree, no year ranges (his
  ruling; title2/year2/startyear stay in the XML for the roster); Kelly's
  corpus entry DROPPED ("no, drop him"); Pinckney year 1997; Lugato → Visiting
  Scholar; the nine page-MEngs confirmed by him. Thesis hunt for those nine:
  Chris Yu 2004 FOUND and added (yu:meng-thesis:2004, DSpace title page says
  Thesis Supervisor Saman P. Amarasinghe; PDF in papers/2004/); Raphael/
  Chaudhary/Ruiz/Noyola were already in the corpus; **Birka's thesis title
  page says supervisor Michael D. Ernst and Jacobs' says Larry Rudolph** —
  neither added, back to him; the only DSpace Matsakis MEng is Nicholas E.
  (1999, Paul Viola) — a different person from Niko (Nicholas D.), back to
  him; Saraff 2024 not in DSpace. Corpus stays 331 (−Kelly +Yu).
- **LinkedIn sitting in his browser** (his instruction; ~28 lookups; full rows
  in `harvest/authors/linkedin-results-alumni.json`): 23 more positions
  printed (page now shows 66) — highlights: Puppin → Principal Engineer,
  Genesis Therapeutics; Juan Carlos Reyes → SWE, Facebook (mutuals Cuevas +
  Agrawal; CONFIRMS the MODEMAT record was a wrong match); Senanayake (now
  displays as "Ryan Seneca") → Sunday Robotics; Kleckner → NVIDIA (left
  Google); Yunming Zhang → MTS, Microsoft AI; Walter Lee → Google — **and a
  BAD LINK flag: links.json's /in/walterwlee/ is a Wells Fargo person; correct
  profile /in/walter-lee-8059b7a3/, for the coordinator to fold via
  link-overrides**; Chuvpilo → co-founder/CEO of Thor Dynamics (where
  Karczmarek is VP Eng); Larsen → Meta; Qin Zhao → Google; Chakrabarti →
  Zentropi; Changwan Hong → building Standard Kernel; Stephen Chou upgraded
  to Staff SWE, Google. One 2nd-degree accept flagged for his veto
  (Mitrovska → Google DeepMind). Not settled: Binh Vo (invite pending),
  Saraff (3rd+ xAI), Jonathan Zhou (ambiguous), Ricardo Ruiz (stale) — in
  round 2 of the questions file.
- **Current-email pass** (his "yes"): 11 published present-day addresses
  (faculty pages + own sites) now fill Email (current) in the roster, each
  with its source page. Roster names normalized to his "<Last>, <First> <MI.>"
  convention (his note on inconsistency); export spelling kept for
  export-sourced people; multi-word surnames (Del Sozzo, Ben Romdhane, …)
  handled. Roster: 498 people, 66 jobs, 11 current + 162 historical emails.

## Cross-lane requests

All resolved; moved verbatim to `docs/LANES-archive.md`. Open new requests here.
