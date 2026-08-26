# UI combinatorial test run — report

Oracle: `tests/ui/oracle.py`, computed directly from `data/publications.json` + `data/citations/*` + `data/repos/*`. Driver: Playwright against `http://localhost:8123`.

## Summary

- Total cases: **908**
- Passed: **907**
- Failed: **1**

- boot sanity: 1 cases
- clear-filters bug repro: 1 cases
- single-facet values: 586 cases
- pairwise combos: 200 cases
- 3-4-way combos: 100 cases
- sort modes + Show toggles (sample): 21 cases

## Scope notes (coverage intentionally bounded)

- SCOPE NOTE: citeAuthor facet sampled 30 of 6215 values (exhaustive impractical)

## Failures (repro selections included)

### STRUCTURAL BUG (STOP for Fable): "Clear filters" permanently disables the Years / Topics & Projects / Categories checkboxes for the rest of the session
- after Clear Filters, clicking year 2026 did not filter the list (click result='clicked:false', paper count stayed at 327)
- after Clear Filters, clicking topic GPUs did not filter the list (click result='clicked:false', paper count stayed at 327)
- after Clear Filters, clicking type inproceedings did not filter the list (click result='clicked:false', paper count stayed at 327)
- control check failed too (Authors facet after Clear Filters, click='clicked:true', count=202) -- re-verify the diagnosis by hand
- Repro: load publications.html, click "Clear filters" once, then try to check any Year / Topic / Project / Category (Type or Venue) checkbox -- it visually snaps back unchecked and the paper count never changes. Authors and "Cited and Used by" still work fine (their facets are rebuilt by clearAll(); the other three are not).
- Root cause: assets/js/publications.js clearAll() (~line 1508) does `state.years = {}; state.keywords = {}; state.types = {};` -- NEW object literals -- but each facet's checkbox onchange handler closed over the OLD state.<facet> object reference when buildFacetBox() first ran at boot, and clearAll() never rebuilds those three boxes (only rebuildAuthorFacet()/rebuildCiteAuthorFacet() run). So a later click mutates a discarded object; updateFacetCounts() then reads the real (still-empty) state.<facet> and resets the checkbox to unchecked, masking the failure as a silent no-op.
- Fix sketch: either rebuild all five facet boxes in clearAll() (call rebuildKeywordFacet()/ rebuildTypeFacet() and rebuild years the same way Authors/CiteAuthors already are), or stop reassigning the state objects and instead delete their keys in place (`for (var k in state.years) delete state.years[k];`) so the closures stay valid.

