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
| **citations** | `harvest/citations/` | unclaimed |
| **artifacts** | `harvest/artifacts/` | unclaimed |
| **repos** | `harvest/repos/` | unclaimed |
| **authors** | `harvest/authors/` | unclaimed |

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

_(no entries)_

### artifacts

_(no entries)_

### repos

_(no entries)_

### authors

_(no entries)_

## Cross-lane requests

_(none open)_
