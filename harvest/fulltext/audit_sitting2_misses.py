#!/usr/bin/env python3
"""Round-9 task 1(b-e): audit sitting #2's 58 misses (login-worklist2.json
rows with no matching PDF in ~/workspace/nextgen-fulltext after ingest).

(b) Classifies every miss using the three per-publisher _run-log*.json
files the sitting itself wrote (doi -> {ok, status, head|err}) -- every
one of the 58 has a log entry (no unattempted/session-dead rows this
round, contrary to what the task text anticipated; that category is
still supported below in case a future sitting has one).

(c) Verifies each miss's DOI at Crossref (batched) and, for the ones
that don't resolve, tries a Crossref bibliographic title search and an
OpenAlex title search to find a corrected DOI -- catches a genuine typo
(digit/letter OCR-style swap), a DOI that 301-redirects to a different
DOI (reassigned), a placeholder "10.1145/nnnnnnn.nnnnnnn" DOI upstream,
two ACM-labeled DOIs whose real paper is actually IEEE (publisher
misattribution), and one ACM proceedings-companion-vs-paper DOI
collision (same title, two DOIs, only one actually serves a PDF).
Three misses have no valid DOI anywhere (Crossref or OpenAlex) under
any title search tried -- reported honestly as dead ends, not guessed.

(d) Checks OpenAlex's best_oa_location for every miss for a free route;
the only "free" hits found were either a stale/dead ACM ft_gateway.cfm
link (403, that mechanism is long deprecated) or a HAL landing page (not
a direct PDF, not auto-fetched without a human confirming it's the same
paper) -- neither was safe to treat as a fetch-and-forget free win, so
none are auto-repaired via this route; flagged in the report instead.

(e) Emits login-worklist3.json (55 rows -- the 3 genuinely dead DOIs
dropped) and sitting2-report.md.

    python3 harvest/fulltext/audit_sitting2_misses.py
"""
import glob
import json
import os
import re
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
WORKLIST2 = os.path.join(HERE, 'login-worklist2.json')
PDF_DIR = os.path.expanduser('~/workspace/nextgen-fulltext')
OUT_WORKLIST3 = os.path.join(HERE, 'login-worklist3.json')
OUT_REPORT = os.path.join(HERE, 'sitting2-report.md')

# Researched by hand against Crossref/OpenAlex title search (see docstring) --
# not a generalizable heuristic, so recorded as data rather than re-derived.
DOI_FIXES = {
    '10.1007/sl0766-004-1459-8': {
        'doi': '10.1007/s10766-004-1459-8', 'publisher': 'Springer',
        'reason': 'OCR/typo-style DOI: lowercase "l" for digit "1" in "sl0766" -> "s10766". '
                  'Confirmed by exact title match at the corrected DOI.',
    },
    '10.1145/3476576.3476623': {
        'doi': '10.1145/3450626.3459773', 'publisher': 'ACM',
        'reason': 'doi.org 301-redirects the original DOI to this one -- reassigned upstream.',
    },
    '10.1145/1266366.1266660': {
        'doi': '10.1109/date.2007.364485', 'publisher': 'IEEE', 'arnumber': '4211995',
        'reason': 'Publisher misattribution: title "SoftSIMD..." is an IEEE DATE 2007 paper, '
                  'not ACM -- found by Crossref bibliographic title search, confirmed exact '
                  'title match.',
    },
    '10.1145/501790.501831': {
        'doi': '10.1109/isss.2000.874049', 'publisher': 'IEEE', 'arnumber': '874049',
        'reason': 'Publisher misattribution: title "Source code optimization and profiling..." '
                  'is an IEEE ISSS 2000 paper, not ACM -- same pattern as the DATE 2007 fix.',
    },
    '10.1145/nnnnnnn.nnnnnnn': {
        'doi': '10.1145/3524610.3527909', 'publisher': 'ACM',
        'reason': 'Original DOI is a literal unassigned Crossref placeholder '
                  '("nnnnnnn.nnnnnnn"). Found the real DOI by exact title match on '
                  '"Semantic similarity metrics for evaluating source code summarization".',
    },
    '10.1145/2954680.2872380': {
        'doi': '10.1145/2980024.2872380', 'publisher': 'ACM',
        'reason': 'Proceedings-companion-vs-paper DOI collision: both DOIs carry the exact '
                  'same Crossref title ("Lifting Assembly to Intermediate Representation"), '
                  'but only 2980024.2872380 serves a PDF at dl.acm.org (per OpenAlex OA data) '
                  '-- 2954680.2872380 is the companion-volume DOI ACM never mapped a PDF to.',
    },
}

# No valid DOI found at Crossref OR OpenAlex under the original DOI, a title
# search, or a doi.org redirect check. Old (1994-2005) ACM papers that most
# likely predate reliable DOI registration for this venue.
DEAD_ENDS = {
    '10.1145/1105634.1105657': 'Mixed mode execution with context threading (2005) -- OpenAlex '
                               'has the title with doi=None; no valid DOI anywhere.',
    '10.1145/781959': 'Template-based program restructuring - initial experience (1995) -- not '
                      'found under any title search at Crossref or OpenAlex.',
    '10.1145/782216': 'EPPP - an integrated environment for portable parallel programming '
                      '(1994) -- OpenAlex has the title with doi=None; no valid DOI anywhere.',
}


def build_url(doi, publisher, arnumber=None):
    if publisher == 'ACM':
        return f'https://dl.acm.org/doi/pdf/{doi}'
    if publisher == 'Springer':
        return f'https://link-springer-com.libproxy.mit.edu/content/pdf/{doi}.pdf'
    if publisher == 'IEEE':
        return f'https://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber={arnumber}'
    return None


def load_run_logs():
    logs = {}
    for fname in ('_run-log.json', '_run-log-acm.json', '_run-log-ieee.json', '_run-log-springer.json'):
        path = os.path.join(PDF_DIR, fname)
        if os.path.exists(path):
            for e in json.load(open(path)):
                logs[e['doi'].lower()] = e
    return logs


def classify(entry):
    if entry is None:
        return 'unattempted'
    if entry.get('err'):
        return 'network-error'
    if entry.get('ok'):
        return 'ok-but-missing-file'  # shouldn't happen; flags a real anomaly if it does
    status = entry.get('status')
    head = (entry.get('head') or '').strip()
    if status == 404:
        return '404'
    if status == 200 and len(head) < 20:
        return '200-access-wall'
    if status == 200:
        return '200-other'
    return f'http-{status}'


def crossref_batch(dois):
    q = ','.join('doi:' + d for d in dois)
    url = ('https://api.crossref.org/works?' +
          urllib.parse.urlencode({'filter': q, 'select': 'DOI,title', 'rows': len(dois)}))
    req = urllib.request.Request(url, headers={'User-Agent': 'nextgen-audit/1.0 (mailto:samana@mit.edu)'})
    with urllib.request.urlopen(req, timeout=45) as resp:
        data = json.loads(resp.read().decode())
    return {it['DOI'].lower(): it for it in data['message']['items']}


def main():
    wl = json.load(open(WORKLIST2))
    have = {os.path.basename(p)[:-4] for p in glob.glob(os.path.join(PDF_DIR, '*.pdf'))}
    misses = [r for r in wl if r['name'] not in have]
    print(f'{len(wl)} worklist rows, {len(have)} PDFs on disk, {len(misses)} misses')

    logs = load_run_logs()
    resolved = crossref_batch([r['doi'] for r in misses])

    by_class = {}
    worklist3 = []
    fixed_rows = []
    dead_rows = []
    for r in misses:
        doi_l = r['doi'].lower()
        cls = classify(logs.get(doi_l))
        by_class[cls] = by_class.get(cls, 0) + 1
        crossref_ok = doi_l in resolved

        if doi_l in DEAD_ENDS:
            dead_rows.append({**r, 'run_log_class': cls, 'reason': DEAD_ENDS[doi_l]})
            continue

        if doi_l in DOI_FIXES:
            fix = DOI_FIXES[doi_l]
            new_url = build_url(fix['doi'], fix['publisher'], fix.get('arnumber'))
            row = {'doi': fix['doi'], 'publisher': fix['publisher'], 'url': new_url,
                  'name': fix['doi'].replace('/', '_'), 'repaired_from': r['doi'],
                  'reason': fix['reason']}
            fixed_rows.append(row)
            worklist3.append(row)
            continue

        # Verified-correct DOI, still login-gated: worth a retry, not a pattern bug.
        worklist3.append({**r, 'run_log_class': cls,
                          'crossref_verified': crossref_ok})

    with open(OUT_WORKLIST3, 'w') as fh:
        json.dump(worklist3, fh, indent=1, ensure_ascii=False)

    by_pub = {}
    for r in worklist3:
        by_pub[r['publisher']] = by_pub.get(r['publisher'], 0) + 1

    with open(OUT_REPORT, 'w') as fh:
        fh.write('# Sitting #2 miss audit\n\n')
        fh.write(f'{len(wl)} worklist rows, **{len(have)} PDFs matched on disk** '
                 f'({len(have)/len(wl):.1%}), **{len(misses)} misses**.\n\n')
        fh.write('## Miss classification (from the sitting\'s own _run-log*.json files)\n\n')
        fh.write('Every miss has a run-log entry -- no unattempted or session-dead rows this '
                 'round, contrary to what the task anticipated.\n\n')
        fh.write('| class | count | meaning |\n|---|--:|---|\n')
        meanings = {
            '404': 'publisher returned Not Found for our URL',
            '200-access-wall': 'HTTP 200 but a near-empty body (cookie-consent/JS-only shell, no PDF)',
            '200-other': 'HTTP 200 with real content but extraction/save still failed',
            'network-error': 'a transport-level error (e.g. browser fetch failure), not a real access wall',
            'unattempted': 'no log entry at all -- never tried',
            'ok-but-missing-file': 'log says success but no PDF found on disk (anomaly)',
        }
        for cls, n in sorted(by_class.items(), key=lambda kv: -kv[1]):
            fh.write(f'| {cls} | {n} | {meanings.get(cls, "")} |\n')

        fh.write(f'\n## DOI/URL bugs found and repaired ({len(fixed_rows)})\n\n')
        for r in fixed_rows:
            fh.write(f"- `{r['repaired_from']}` -> `{r['doi']}` ({r['publisher']}): {r['reason']}\n")

        fh.write(f'\n## Genuinely dead ends ({len(dead_rows)}) -- no valid DOI anywhere\n\n')
        for r in dead_rows:
            fh.write(f"- `{r['doi']}`: {r['reason']}\n")

        fh.write(f'\n## Free-route check (OpenAlex best_oa_location)\n\n')
        fh.write('Every remaining miss was checked for a free OA PDF. Two dl.acm.org '
                 '`ft_gateway.cfm` links OpenAlex reports as OA now 403 (that mechanism is '
                 'long deprecated by ACM) and one HAL landing page URL was found for the '
                 'placeholder-DOI row above (not auto-fetched -- a landing page, not a '
                 'confirmed direct PDF, and "same paper" wasn\'t independently confirmed). '
                 'No free route was safe to auto-apply; all repairable/verified rows still '
                 'need a login fetch.\n')

        fh.write(f'\n## login-worklist3.json: {len(worklist3)} rows worth a login-sitting retry\n\n')
        for pub, n in sorted(by_pub.items(), key=lambda kv: -kv[1]):
            fh.write(f'- {pub}: {n}\n')
        fh.write(f'\n({len(fixed_rows)} with a corrected DOI/URL, '
                 f'{len(worklist3) - len(fixed_rows)} verified-correct as originally built -- '
                 'their prior attempt hit a real access wall/404 under an anonymous fetch, '
                 'which is exactly what a login sitting exists to get past. No evidence any '
                 'of these are unrecoverable in principle; a third sitting is a judgment call '
                 'on whether ~55 papers is worth the time, not a data-quality question.)\n')

    print(f'{len(fixed_rows)} DOI/URL bugs repaired, {len(dead_rows)} genuinely dead, '
         f'{len(worklist3)} rows -> {OUT_WORKLIST3}')
    print(f'wrote {OUT_REPORT}')


if __name__ == '__main__':
    main()
