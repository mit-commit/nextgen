# UI random-settings test — worker spec

Owner: whichever session claims `tests/ui` in docs/LANES.md.
Origin: his instruction, 2026-08-26. Supersedes the terse round-11 task 1.

## What he asked for

Exercise the real site the way a person would: pick random combinations of
the controls in the **All Papers panel** (buttons, selectors, toggles,
sliders, sort modes, search box), then also open **individual paper
expansions** — merged summary, repositories, citations — and check that what
the All Papers panel shows, and what the Publications page shows for that
same setting, makes sense. **About 100 individual tests.** Report back
explicitly when finished; say so plainly rather than leaving it implied.

## Ground rules

- Drive the actual site with Playwright (headed or headless) against a local
  server serving the repo. The pages are `publications.html` / the pubs index,
  with `assets/js/publications.js`, `pubs.js` and `citations.js` behind them.
- **Discover the controls at runtime, do not hardcode a list.** Enumerate
  every interactive element inside the All Papers panel — `button`,
  `select`, `input[type=checkbox]`, `input[type=range]`, `input[type=search]`
  — record its label and its value domain, and write that inventory into the
  report. If a control appears that this spec never anticipated, it still
  gets exercised; that is the point of enumerating.
- Seed the RNG (`--seed`, default 42) and print the seed. Every failure must
  be reproducible from seed + test index, and the report must carry the exact
  control settings for each failure.
- One test = one random setting of the panel + the assertions below. Aim for
  100 tests: roughly 60 with 2-4 controls set at once, 25 with a single
  control set (so a failure is attributable), 15 at extremes — every filter
  on at once, empty result sets, maximum slider values, a search string that
  matches nothing.

## Oracle

Compute expected results independently from the data files, never from the
page: `publications.json` for the paper set and its fields, `data/citations/*`
and `data/repos/*` for per-paper reception and repositories, plus whatever
the page fetches lazily. If the oracle needs a rule the data cannot settle
(e.g. what a slider at 3 is supposed to mean), STOP and ask the coordinator
rather than guessing the rule from the code's behaviour — an oracle copied
from the implementation cannot catch the implementation being wrong.

## Assertions per test

1. **Count** — the number of papers listed equals the oracle count, and any
   header/summary count on the page agrees with the list actually rendered.
2. **Membership** — the exact set of paper IDs matches the oracle, not just
   the size. Report symmetric difference on failure.
3. **Order** — under each sort mode the rendered order matches the oracle's,
   ties included; note the tie-break rule the site uses.
4. **Labels** — facet labels, chips and empty-state text describe the setting
   that is actually applied.
5. **Cross-page agreement** — the same setting, where it exists on both
   surfaces, yields a consistent picture in the All Papers panel and under
   Publications. A paper filtered out of one must not be present in the other.

## Expansions (part of the 100, not extra)

For at least 30 of the tests, expand 1-3 papers from the filtered list and
check:

- **Summary** — the merged summary renders, is not truncated mid-word, and
  contains no raw markup, `undefined`, `null`, `NaN` or empty bullet.
- **Repositories** — the repos shown are the ones the data holds for that
  paper, tier labels match, links resolve to a real path (check the href
  shape, do not crawl GitHub), and a paper with no repos shows an honest
  empty state rather than an empty box.
- **Citations** — the per-paper citation view loads lazily on open (assert
  the fetch happens on expand, not before), the counts shown match the data
  file, and the list is not silently truncated. Papers with zero citations
  must say so.
- Expand/collapse twice: state must survive, with no duplicate rendering and
  no leaked event handlers.
- Console: no uncaught errors or failed network requests during any test.
  A clean-looking page with a red console counts as a failure.

## Output

- `tests/ui/report.md` — the control inventory, seed, pass/fail per test,
  and for each failure: the exact settings, expected vs actual, and a
  one-line repro.
- Fix display-only bugs directly and note them. Anything structural (wrong
  filter semantics, wrong counts from the data layer, lazy-load regressions)
  gets a STOP entry for Fable rather than a patch.
- Keep the harness as the pre-cutover gate; note it in `docs/refresh.md`.
- **When the run is finished, say so explicitly in the session log and in
  `tests/ui/report.md` — first line: `RUN COMPLETE — <n> tests, <p> passed,
  <f> failed, seed <s>`.** He wants to be told, not to infer it.

## If 100 is not enough

Report the failure rate. If failures cluster in one area (one facet, one sort
mode, the citation lazy-load), say so and propose a targeted second run over
that area; he has said to ask if more would help.
