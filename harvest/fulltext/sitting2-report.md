# Sitting #2 miss audit

3641 worklist rows, **3606 PDFs matched on disk** (99.0%), **58 misses**.

## Miss classification (from the sitting's own _run-log*.json files)

Every miss has a run-log entry -- no unattempted or session-dead rows this round, contrary to what the task anticipated.

| class | count | meaning |
|---|--:|---|
| 200-access-wall | 37 | HTTP 200 but a near-empty body (cookie-consent/JS-only shell, no PDF) |
| 404 | 20 | publisher returned Not Found for our URL |
| network-error | 1 | a transport-level error (e.g. browser fetch failure), not a real access wall |

## DOI/URL bugs found and repaired (6)

- `10.1007/sl0766-004-1459-8` -> `10.1007/s10766-004-1459-8` (Springer): OCR/typo-style DOI: lowercase "l" for digit "1" in "sl0766" -> "s10766". Confirmed by exact title match at the corrected DOI.
- `10.1145/1266366.1266660` -> `10.1109/date.2007.364485` (IEEE): Publisher misattribution: title "SoftSIMD..." is an IEEE DATE 2007 paper, not ACM -- found by Crossref bibliographic title search, confirmed exact title match.
- `10.1145/2954680.2872380` -> `10.1145/2980024.2872380` (ACM): Proceedings-companion-vs-paper DOI collision: both DOIs carry the exact same Crossref title ("Lifting Assembly to Intermediate Representation"), but only 2980024.2872380 serves a PDF at dl.acm.org (per OpenAlex OA data) -- 2954680.2872380 is the companion-volume DOI ACM never mapped a PDF to.
- `10.1145/3476576.3476623` -> `10.1145/3450626.3459773` (ACM): doi.org 301-redirects the original DOI to this one -- reassigned upstream.
- `10.1145/501790.501831` -> `10.1109/isss.2000.874049` (IEEE): Publisher misattribution: title "Source code optimization and profiling..." is an IEEE ISSS 2000 paper, not ACM -- same pattern as the DATE 2007 fix.
- `10.1145/nnnnnnn.nnnnnnn` -> `10.1145/3524610.3527909` (ACM): Original DOI is a literal unassigned Crossref placeholder ("nnnnnnn.nnnnnnn"). Found the real DOI by exact title match on "Semantic similarity metrics for evaluating source code summarization".

## Genuinely dead ends (3) -- no valid DOI anywhere

- `10.1145/1105634.1105657`: Mixed mode execution with context threading (2005) -- OpenAlex has the title with doi=None; no valid DOI anywhere.
- `10.1145/781959`: Template-based program restructuring - initial experience (1995) -- not found under any title search at Crossref or OpenAlex.
- `10.1145/782216`: EPPP - an integrated environment for portable parallel programming (1994) -- OpenAlex has the title with doi=None; no valid DOI anywhere.

## Free-route check (OpenAlex best_oa_location)

Every remaining miss was checked for a free OA PDF. Two dl.acm.org `ft_gateway.cfm` links OpenAlex reports as OA now 403 (that mechanism is long deprecated by ACM) and one HAL landing page URL was found for the placeholder-DOI row above (not auto-fetched -- a landing page, not a confirmed direct PDF, and "same paper" wasn't independently confirmed). No free route was safe to auto-apply; all repairable/verified rows still need a login fetch.

## login-worklist3.json: 55 rows worth a login-sitting retry

- Springer: 30
- ACM: 22
- IEEE: 3

(6 with a corrected DOI/URL, 49 verified-correct as originally built -- their prior attempt hit a real access wall/404 under an anonymous fetch, which is exactly what a login sitting exists to get past. No evidence any of these are unrecoverable in principle; a third sitting is a judgment call on whether ~55 papers is worth the time, not a data-quality question.)
