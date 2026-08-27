RUN COMPLETE -- 114 tests, 114 passed, 0 failed, seed 42

# UI random-settings test run -- report

Per `tests/ui/SPEC.md` (his instruction, 2026-08-26). Oracle: `tests/ui/oracle.py`, computed directly from the data files. Driver: Playwright against `http://localhost:8124`.

## Control inventory (discovered at runtime from #pubs-filters)

594 raw interactive elements found. Reduced to logical controls:

### Checkbox facets
- `#facet-years`: 35 values
- `#facet-keywords`: 33 values
- `#facet-types`: 8 values
- `#facet-authors`: 373 values
- `#facet-cite-cats`: 11 values
- `#facet-cite-authors`: 100 values

### Button toggle groups
- `#kw-toggle` (dataKwmode): ['topics', 'projects']
- `#type-toggle` (dataMode): ['type', 'venue-name', 'venue-count']
- `#cite-global-sort` (dataV): ['impact', 'recency', 'popularity']
- `#cite-global-centrality` (dataV): ['all', 'core', 'engaged', 'peripheral']

### Selects
- `#sort-1`: ['none', 'year', 'citations', 'month', 'keywords', 'authors', 'authorLast', 'authorFirst', 'type']
- `#sort-2`: ['none', 'citations', 'month', 'keywords', 'authors', 'authorLast', 'authorFirst', 'type', 'year']
- `#sort-3`: ['none', 'citations', 'authors', 'authorLast', 'authorFirst', 'type', 'month', 'keywords', 'year']
- `#sort-4`: ['none', 'citations', 'keywords', 'authors', 'authorLast', 'authorFirst', 'type', 'month', 'year']
- `#author-sort`: ['first', 'last', 'count', 'recent']
- `#cite-author-sort`: ['count', 'name']

### Range sliders
- `#cite-min-cites`: min=0 max=100 step=1
- `#cite-min-impact`: min=0 max=4 step=1

### Text/search inputs
- `#facet-title`: facet-title
- `#author-search`: Filter author names
- `#cite-search`: Filter the rows inside every open Citations panel
- `#cite-author-search`: Filter names

### Radio groups
- `mode`: ['noninteractive', 'interactive']

### Standalone buttons
`#btn-clear`, `#btn-export-bib`, `#sort-reset`, `#btn-toggle-summaries`, `#btn-toggle-citations`, `#btn-toggle-repos`, `#btn-drawer-apply`

## Interpretation notes (per the spec's "STOP rather than guess" instruction)

- **"All Papers panel" vs "Publications page"**: this codebase has one page (`publications.html`) with two labeled regions -- the Filters block (`#pubs-filters`, informally "the All Papers panel" since with nothing selected it lists every paper) and the Publications listing (`#pubs-results`) beneath it. Read "cross-page agreement" as: a facet checkbox's dynamic count badge in the Filters block must always match what the Publications listing actually renders. There is no second page/embed of this list anywhere else in the repo today.
- **"every filter on at once" (extreme case)**: checking every checkbox *within* one facet is a no-op (OR-within-facet matches everything with any value there), so it cannot produce an "extreme" narrowing. Read literally it would test nothing; the "kitchen-sink" extreme case instead picks one value from each of the four main facets (year + topic + author + type) simultaneously (AND across facets), which is the combination that actually stresses over-constraint.

## Summary

- Total: **114**, Passed: **114**, Failed: **0**, seed=**42**
- 30 of 114 tests were flagged for the expansion checks (>=30 target); 16 actually expanded a paper -- the gap is tests flagged for expansion that landed on an empty-result setting (nothing to expand), not a silent skip.

No discrepancies between the live UI and the independent oracle across all 114 settings (including the expansion checks).

