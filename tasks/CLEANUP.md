# Cleanup and simplification pass — worker spec (Fable)

His instruction, 2026-08-26, after the site went to production: assess the
data structures, the code, the documentation, and the accumulated debris,
then improve them.

**Two phases, and phase 1 changes nothing.** He asked questions ("are the
data structures good?", "should we move to better ones?") — those are
assessment questions, and the answers decide the work. Audit first, report,
get his ruling, then execute. Do not begin refactoring during the audit.

The site is LIVE. Every change from here risks a working system. The bar is
not "cleaner" — it is "cleaner and demonstrably still correct".

---

## Phase 1 — audit (produce `docs/cleanup-audit.md`, change nothing)

### 1. Data structures

Answer with measurements, not impressions:

- What does the publications page actually load on first paint, in bytes and
  in requests? What does it load lazily on expand? Where does the time go —
  network, parse, or render?
- `publications.json`, `data/citations/**`, `data/repos/**`,
  `data/impact-authors.json`, `citers.json`: which are read whole when only a
  slice is needed? Which are shaped for the writer's convenience rather than
  the reader's?
- Is the per-paper shard layout paying for itself, or would an index plus
  lazy shards (or the reverse) be simpler AND faster? Say which, with the
  numbers that justify it.
- Redundancy: the same fact stored in several files, derived data checked in
  alongside its source, counts cached that could be computed. List them.
- Anything genuinely awkward: fields that mean different things in different
  files, keys that are sometimes a DOI and sometimes a bibtexKey, nullable
  fields the reader has to defend against everywhere.

Recommend a target shape only where you can state the benefit concretely
(fewer bytes on first paint, one fewer fetch on expand, one less special
case in the reader). "More normalized" is not a benefit.

### 2. Code

- `assets/js/publications.js` (~85KB) and `citations.js` (~38KB) are the two
  monoliths. What is actually in them? Which parts are cohesive units that
  would survive being separated, and which are tangled enough that splitting
  would only move the mess?
- Duplication across `publications.js`, `pubs.js`, `pubs_index.js`,
  `common.js` — same logic written twice, drifted slightly.
- The harvest scripts: which are the durable pipeline (named in
  `docs/refresh.md` and `tasks/HARVEST-AND-UPDATE.md`), and which were
  one-off repairs that will never run again?
- Dead code: functions nothing calls, branches nothing reaches, options no
  caller passes, `TEMP`/debug leftovers.
- Error handling that silently swallows — a bare `catch {}` around a fetch
  is how a missing data file becomes an empty panel instead of a loud
  failure.

### 3. Documentation

- Is `docs/refresh.md` still true after everything that changed today? Walk
  it against the actual scripts; note every step that no longer matches.
- `docs/LANES.md` is now very long and mostly historical. Propose a split:
  the current state worth reading versus an archive.
- Known stale: `harvest/authors/links-residue.md` (superseded by the
  sittings and the academic-page hunt).
- What a newcomer cannot currently find out: how the data flows end to end,
  which files are source and which are derived, what regenerates what. If
  that diagram does not exist, it is the single most valuable doc to add.

### 4. Debris

- Files nothing reads: intermediate outputs, superseded worklists, old
  prototypes, `.bak`/scratch files, anything under `prototype/` that the
  pilots no longer need.
- Data files the site never fetches — **verify by reading the code, not by
  guessing from names.** A file loaded lazily on expand looks unused to a
  grep of first-paint code.
- Duplicate PDFs, orphaned `papers/` entries with no publication record, and
  the reverse: publication records pointing at missing PDFs.
- Repo size: what is large, and is it large for a reason?

For every deletion candidate: state what it was for, what proves it is
unused, and whether git history alone is sufficient to recover it.

---

## Phase 2 — execute (only after he rules on the audit)

Rules that make this safe:

1. **Both UI harnesses green before and after every batch** —
   `tests/ui/facet_test.py` and `tests/ui/random_settings_test.py`. Not at
   the end; after each batch, so a failure names its cause.
2. **One concern per commit**, and never mix a data-format change with a code
   change in the same commit. If a format changes, the writer, the reader,
   the harness oracle and `docs/refresh.md` all move together — a format
   change that leaves the refresh scripts behind breaks the next
   "harvest and update", months from now, with nobody watching.
3. **Deletions in their own commit**, listed in the message, nothing else in
   it. Easy to revert, easy to audit.
4. Behaviour-preserving refactors must be exactly that. If a refactor
   changes what renders, it is not a refactor — stop and report.
5. Re-verify the live site after the final batch (`tasks/CUTOVER.md` step 5),
   including that the Umami tag is still on every page.

## Do not touch

- `harvest/authors/links.json` — written only through
  `link-overrides.json` + `apply_link_overrides.py`. Do not "simplify" that
  indirection; it exists because his rulings must survive a re-harvest.
- The pilot classifications and `prototype/build_pilot_data.py`'s outputs.
- `publications.json` content — summaries and receptions are his voice, not
  refactorable text.
- The frozen exceptions in `tasks/HARVEST-AND-UPDATE.md` (Anant's LinkedIn,
  the two name spellings, adadima).
- Anything in `tasks/` that records a human ruling.

## Report

`docs/cleanup-audit.md` for phase 1, and a short summary in chat: what is
genuinely wrong, what is merely untidy, and what you recommend leaving alone.
Distinguish those three — a pass that treats every imperfection as work to do
will spend his money making the system different rather than better.
