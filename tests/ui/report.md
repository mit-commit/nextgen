# UI combinatorial test run — report

Oracle: `tests/ui/oracle.py`, computed directly from `data/publications.json` + `data/citations/*` + `data/repos/*`. Driver: Playwright against `http://localhost:8123`.

## Summary

- Total cases: **908**
- Passed: **908**
- Failed: **0**

- boot sanity: 1 cases
- clear-filters bug repro: 1 cases
- single-facet values: 586 cases
- pairwise combos: 200 cases
- 3-4-way combos: 100 cases
- sort modes + Show toggles (sample): 21 cases

## Scope notes (coverage intentionally bounded)

- SCOPE NOTE: citeAuthor facet sampled 30 of 6215 values (exhaustive impractical)

No discrepancies found between the live UI and the independent oracle across every single-facet value, the sampled pairwise/3-4-way combinations, the sampled Group&sort modes, and the Show-toggle/citation-sort smoke checks.
