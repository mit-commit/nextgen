# "Harvest and update" — the coordinator's playbook

When he says **"harvest and update"**, this is the plan. Read it end to end
before queueing anything. `docs/refresh.md` is the per-script operating
manual — this file is the order of work, the gates, and the judgment calls
that are already settled so nobody relitigates them.

Two things make this more than a re-run: **new papers change old papers**
(a new paper that extends an earlier one means the earlier one's summary is
now incomplete), and **new citations change old judgments** (a paper whose
reception profile shifts needs its reception prose revisited). Both are
explicit phases below, not afterthoughts.

---

## Phase 0 — intake (needs him, ~10 minutes)

Ask for, in one message:

1. New papers since the last run: PDFs into `papers/<year>/`, plus the
   `publications.json` fields he already uses (bibtexKey, title, authors,
   venue, year, url).
2. Anything else that changed: new group members, a paper that moved from
   arXiv to a venue, a repo that was renamed or made public.
3. Whether he wants full-text login sittings this round (see Phase 3).

Record the run's start SHA — every phase's damage is revertable to it.

## Phase 1 — identity and identifiers

- `harvest/idmap_build.py` for the new entries only. New keys land as
  `exact`, `no_doi`, or in `idmap-review.json`.
- Resolve the review rows the same way as before: fetch the candidate's real
  Crossref/OpenAlex record and compare venue + year + authors. **Never accept
  on title similarity alone.** Unresolvable rows stay unresolved with a note.
- New authors get parsed by `authors_build.py`; exact-name dedupe only,
  near-misses to `review.json` for a human, never auto-merged.

## Phase 2 — citations harvest

- `harvest_citations.py --pass openalex` then `--pass s2` — resumable, keyed
  per paper, so it only fetches what is missing.
- `backfill_cited_by.py` for any citing record without a count.
- Then `harvest_abstracts_all.py`: abstracts are the cheap evidence tier and
  they materially change judgments.

## Phase 3 — full text (needs him, optional)

Free routes first (`harvest_fulltext.py`) — expect roughly 8% yield, that is
the bot-wall ceiling, not a bug. Then, if he wants the accuracy:

- `build_login_worklist2.py` builds the paywalled worklist.
- He runs a console-paste fetcher in a logged-in, **proxied** browser tab and
  drops PDFs in `~/workspace/nextgen-fulltext`; `ingest_manual_pdfs.py` takes
  them from there.
- Publisher reality, learned the hard way in sitting #3: ACM must be reached
  through `dl-acm-org.libproxy.mit.edu` or it redirects PDFs to `/doi/abs/`;
  Springer reference-work entries (`/rwe/`) often have no PDF at all; a
  cross-origin redirect to `spawn-queue.acm.org` cannot be followed by
  `fetch()` at all. Build the runner to resolve the PDF from the landing page
  rather than assuming a URL shape, and to skip a dead item rather than stop.
- Worth it because fulltext evidence flips ~68% of prior judgments. Not worth
  it for a tail of a few dozen rows — sitting #3 was abandoned on that ground.

## Phase 4 — classification and rejudge

- New citing works: `classify_citations.py` (Batch API) then
  `merge_taxonomy.py --write`.
- **Rejudge, not reclassify**: clear only the staging records that are
  `function: unknown`, `confidence: low`, or that gained a better evidence
  tier since last time. Everything else stands.
- Pilots are frozen except on a genuine evidence upgrade, and they never go
  through `merge_taxonomy.py` — use `rejudge_pilots_with_fulltext.py` and
  rebuild with `prototype/build_pilot_data.py --write`.
- Cost gate: dry-run first; anything over $20 goes to him with the number.

## Phase 5 — repositories

- New papers: in-paper URL scan, then GitHub search, then **model
  verification** — the mechanical step alone has a ~93% false-positive rate,
  so nothing is auto-accepted, ever.
- Own repos: re-run the account enumeration for new authors. Theses are the
  known weak spot (a thesis repo is usually named after the tool, not the
  thesis).
- Tier 2 (outside users) and tier 3 (idea descendants) re-run for papers whose
  citation set grew. Canonical-over-fork, resolved by GitHub's numeric repo
  id — URL text lies after a rename.
- Any new GitHub account attached to a person gets the **match audit** of
  §"Author links" below before it can render.

## Phase 6 — summaries and receptions (the part that is easy to skip)

This is where "update everything including the summaries of other papers"
lives. Three distinct jobs:

1. **New papers need a summary**, written to `publications.json` in his voice
   — see `docs/summary-style.md`, which is binding, and the pilot exemplars
   embedded in it.
2. **Older papers whose story changed need their summaries revisited.** When
   a new paper extends, supersedes, or reframes an earlier one, the earlier
   paper's summary should say so. Find these by looking at the new papers'
   own citations into this corpus, not by re-reading all 327 — the new
   paper's reference list names exactly the predecessors that need a look.
3. **Receptions regenerate where the profile materially moved** — a paper
   that gained substantial citations, or whose function/centrality mix
   shifted, or that gained its first real repo. `generate_receptions.py`
   revises rather than rewrites; `merge_wave.py` refuses pilots.
   Wave, then a reviewer pass against the style doc, then his spot check on
   the first wave before the rest go.

Style rules that keep being violated and must be checked every time: no
superlatives, no present-anchoring ("currently", "now the leading"), no
numeric counts in prose, COMMIT-internal work is never presented as external
reception, and the seam between summary and reception must read as one voice.

## Phase 7 — author links

Standing rulings, already settled — apply, do not re-ask:

- LinkedIn is the default target; an **active permanent academic page
  replaces it** and ends the question for that person; else best active
  professional or personal site; else a `mailto:`.
- Identity must be **positively verified** — education or employer plus
  timeframe consistent with the paper. Name similarity is never enough.
  A **1st-degree LinkedIn connection is itself identity evidence.**
- Unconfirmable goes to him, never guessed, never silently dropped.
- Confirmed people who are not 1st-degree go on
  `harvest/authors/linkedin-connect-list.md` for him to invite. The sittings
  never send invitations or messages.
- GitHub accounts are **identity evidence** (do the repos match the paper's
  subject and era?), not just link targets. Audit every new one: a name match
  proves nothing — `thehen` really is named Henry Hoffman.
- When a GitHub account is dropped, drop everything harvested from it too —
  the profile's blog and email belong to the same wrong person.
- Frozen exceptions: Anant Agarwal renders his LinkedIn, not his CSAIL page.
  The spellings "Henry Hoffman" and "Ronald Dresklinski" stay as they are.
  `adadima` is Alexandra Dima's.
- `links.json` is written only through `link-overrides.json` +
  `apply_link_overrides.py`, never by hand.

## Phase 8 — rebuild, test, publish

1. Rebuild the derived layer: `build_repo_data.py`, `build_citers.py`,
   `build_impact_authors.py`, `gen_tier2_priority.py`, the citations index.
2. Run both UI harnesses (`tests/ui/facet_test.py`,
   `tests/ui/random_settings_test.py`). **Green is the gate.** The oracle is
   computed from the data files, never read off the page.
3. Migrate to the live repo per `tasks/CUTOVER.md`: branch, rollback SHA in
   the commit message, harness green, merge, then verify the live URLs.
4. Confirm the Umami snippet (`tasks/UMAMI.md`) is still on every page — a
   page that loses it reports nothing, silently.
5. Tell him plainly what changed and what is now live.

---

## How to run it

Parallel lanes with **disjoint path ownership**, as in round 12 — see
`tasks/QUEUE.md` for the pattern. The rules that prevented collisions:
`assets/js/*` has exactly one writer; `links.json` has none during a round;
`publications.json` is read-only for every lane. Sessions claim in
`docs/LANES.md` in the same commit as their first change.

His involvement, and nothing more: intake, cost approvals over $20, login
sittings, LinkedIn sittings, the first summary wave's spot check, and the
final render review.

## Do not redo

- Sitting #3's 49 remaining rows — closed deliberately, see `tasks/QUEUE.md`.
- The 19 held GitHub handles — they publish only when a second signal
  appears, not on a re-run.
- The pilot classifications — frozen absent a real evidence upgrade.

## Known open items to carry forward

- 39 of 368 authors have no link; Johnathan Babb and Eric Wong have nothing
  at all.
- 11 people have a wrong ORCID/OpenAlex resolution in `enriched.json`
  (6 still unresolved) — clear these before the next enrich pass inherits
  the bad steer.
- P. Negi, C. Pacheco and F. Sherwood were misfiled as exascale-report
  co-authors; they belong to other papers and still need identity work.
- Sitting-1 degree backfill: Agrawal, Barrett, Cooper, Dasika, Erlingsson.
- Theses remain the weakest repo coverage in the corpus.
