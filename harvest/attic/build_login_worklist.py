#!/usr/bin/env python3
"""Task `login-worklist`: build the closed-citing-papers worklist for the
human's browser sitting.

Population: citing-work judgments where
  - function is on the "detailed" side (extends, uses-tool, adopts-idea,
    uses-benchmark, baseline, positions, surveys, supports-claim,
    detailed-citation -- see data/citations/SCHEMA.md's split rule), so the
    citation is worth getting right;
  - confidence is low;
  - evidence tier is exactly "contexts" (a bare S2 snippet, no abstract or
    full text) -- the kind of thin evidence a real look at the paper would
    most plausibly upgrade;
  - the citing work's DOI prefix belongs to a paywalled publisher (IEEE
    10.1109, ACM 10.1145, Springer 10.1007, Elsevier 10.1016) the human can
    reach through an institutional/personal login.

Reads both judgment sources: harvest/taxonomy/pilot-classifications.json
(the 9 pilots) and harvest/taxonomy/records/<key>/*.json (everyone else).
Does NOT fetch anything -- this is a worklist, not a harvest.

Output:
  harvest/fulltext/login-worklist.json  -- one row per candidate, grouped
    by publisher, with everything needed to find and read the citing paper
    and re-judge it: title, DOI/link, our paper's title, the current
    function/confidence/note, and the S2 contexts already on file.
  harvest/fulltext/login-worklist.md    -- the one-page run sheet: a
    publisher-grouped checklist a human can work through in one sitting.

    python3 harvest/fulltext/build_login_worklist.py
"""
import glob
import hashlib
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
PILOT_CLASSIFICATIONS = os.path.join(ROOT, 'harvest', 'taxonomy', 'pilot-classifications.json')
RECORDS_DIR = os.path.join(ROOT, 'harvest', 'taxonomy', 'records')
CITATIONS_DIR = os.path.join(ROOT, 'harvest', 'citations')
PUBLICATIONS = os.path.join(ROOT, 'data', 'publications.json')
OUT_JSON = os.path.join(ROOT, 'harvest', 'fulltext', 'login-worklist.json')
OUT_MD = os.path.join(ROOT, 'harvest', 'fulltext', 'login-worklist.md')

DETAILED = {'extends', 'uses-tool', 'adopts-idea', 'uses-benchmark', 'baseline',
            'positions', 'surveys', 'supports-claim', 'detailed-citation'}
PUBLISHER_PREFIX = {'10.1109': 'IEEE', '10.1145': 'ACM', '10.1007': 'Springer',
                    '10.1016': 'Elsevier'}


def slug_for(c):
    doi = c.get('doi')
    if doi:
        return re.sub(r'[^a-z0-9._-]', '_', doi.lower())
    oa = c.get('openalex')
    if oa:
        return 'oa-' + oa.rsplit('/', 1)[-1]
    s2 = c.get('s2')
    if s2:
        return 's2-' + s2[:16]
    return 'noid-' + hashlib.sha1((c.get('title') or '').encode('utf-8')).hexdigest()[:16]


def candidate_rows():
    pubs = {p['bibtexKey']: p for p in json.load(open(PUBLICATIONS))}
    citing_cache = {}

    def citing_for(key):
        if key not in citing_cache:
            path = os.path.join(CITATIONS_DIR, key + '.json')
            citing_cache[key] = json.load(open(path))['citing'] if os.path.exists(path) else []
        return citing_cache[key]

    def qualifies(r):
        return (r.get('function') in DETAILED and r.get('confidence') == 'low'
                and r.get('evidence') == 'contexts')

    rows = []

    tax = json.load(open(PILOT_CLASSIFICATIONS))
    for r in tax['rows']:
        if qualifies(r):
            rows.append((r['pilot'], r))

    for d in sorted(glob.glob(os.path.join(RECORDS_DIR, '*'))):
        if not os.path.isdir(d):
            continue
        key = os.path.basename(d)
        for f in sorted(glob.glob(os.path.join(d, '*.json'))):
            r = json.load(open(f))
            if qualifies(r):
                rows.append((key, r))

    worklist = []
    for key, r in rows:
        citing = next((c for c in citing_for(key) if slug_for(c) == r['slug']), None)
        if not citing or not citing.get('doi'):
            continue
        prefix = citing['doi'].split('/')[0].lower()
        publisher = PUBLISHER_PREFIX.get(prefix)
        if not publisher:
            continue
        pub = pubs.get(key, {})
        worklist.append({
            'publisher': publisher,
            'our_paper': {'bibtexKey': key, 'title': pub.get('title') or key},
            'citing_work': {
                'title': citing.get('title'),
                'year': citing.get('year'),
                'venue': citing.get('venue'),
                'doi': citing['doi'],
                'url': 'https://doi.org/' + citing['doi'],
            },
            'current_judgment': {
                'function': r.get('function'),
                'confidence': r.get('confidence'),
                'note': r.get('note'),
            },
            's2_contexts': citing.get('contexts') or [],
        })
    return worklist


def write_json(worklist):
    with open(OUT_JSON, 'w') as fh:
        json.dump(worklist, fh, indent=1, ensure_ascii=False)
        fh.write('\n')


def write_run_sheet(worklist):
    by_pub = {}
    for row in worklist:
        by_pub.setdefault(row['publisher'], []).append(row)

    lines = [
        '# Login worklist -- closed-citing-papers browser sitting',
        '',
        f'{len(worklist)} rows: citations judged on the "detailed" side of the taxonomy '
        '(they engage our paper specifically -- extends, uses-tool, adopts-idea, '
        'uses-benchmark, baseline, positions, surveys, supports-claim, or '
        'detailed-citation) at LOW confidence, from a bare S2 context snippet only '
        '(no abstract, no full text) -- the kind of thin evidence a real read of the '
        'paper would most plausibly upgrade or correct. Grouped by publisher so one '
        'login covers a whole block.',
        '',
        'For each row: open the DOI link (behind your institutional/personal login), '
        'find the citation to our paper, and check whether the current function/'
        'confidence call still holds. Nothing here was fetched automatically.',
        '',
    ]
    for publisher in sorted(by_pub, key=lambda p: -len(by_pub[p])):
        rows = by_pub[publisher]
        lines.append(f'## {publisher} ({len(rows)})')
        lines.append('')
        for row in rows:
            cw = row['citing_work']
            cj = row['current_judgment']
            lines.append(f"- [ ] **{cw['title']}** ({cw.get('year')}) -- {cw['url']}")
            lines.append(f"      cites: *{row['our_paper']['title']}* "
                         f"(`{row['our_paper']['bibtexKey']}`)")
            lines.append(f"      current call: `{cj['function']}` / low confidence")
            if row['s2_contexts']:
                lines.append(f"      S2 context: {row['s2_contexts'][0][:200]!r}")
            lines.append('')
    with open(OUT_MD, 'w') as fh:
        fh.write('\n'.join(lines) + '\n')


def main():
    worklist = candidate_rows()
    write_json(worklist)
    write_run_sheet(worklist)
    from collections import Counter
    counts = Counter(r['publisher'] for r in worklist)
    print(f'{len(worklist)} rows across {len(counts)} publishers: {dict(counts)}')
    print(f'wrote {OUT_JSON}')
    print(f'wrote {OUT_MD}')


if __name__ == '__main__':
    main()
