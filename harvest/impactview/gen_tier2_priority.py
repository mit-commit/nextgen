#!/usr/bin/env python3
"""Rank own repos for the tier-2/3 outside-user hunt (human directive:
stars x citations decides where hunting pays off).

    python3 harvest/impactview/gen_tier2_priority.py

Reads data/repos/papers/ (own rows) + data/citations/index.json; writes
harvest/impactview/tier2-priority.md. Score is deliberately simple and
visible: log10(stars+1) + log10(citations+1), where citations is the
best displayed count across the repo's papers. The human gates; this
only orders the conversation.
"""
import glob
import json
import math
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.abspath(__file__))

cid = json.load(open(f'{ROOT}/data/citations/index.json'))['papers']


def cites(key):
    r = cid.get(key)
    return max(r['verified'] or 0, r['gscholar'] or 0) if r else 0


repos = {}
for path in glob.glob(f'{ROOT}/data/repos/papers/*.json'):
    d = json.load(open(path))
    for r in d['repos']:
        if r.get('group') != 'own' or r.get('artifact') or 'github.com' not in (r.get('url') or ''):
            continue
        e = repos.setdefault(r['name'], {'stars': r.get('stars'), 'active': r.get('active'),
                                         'archived': r.get('archived'), 'papers': set()})
        e['papers'].add(d['key'])
        if (r.get('stars') or -1) > (e['stars'] or -1):
            e['stars'], e['active'] = r.get('stars'), r.get('active')

rows = []
for name, e in repos.items():
    c = max((cites(k) for k in e['papers']), default=0)
    s = e['stars'] or 0
    score = math.log10(s + 1) + math.log10(c + 1)
    rows.append((score, name, s, c, e))
rows.sort(reverse=True)

with open(f'{HERE}/tier2-priority.md', 'w') as fh:
    fh.write('# Tier-2/3 hunt priority — own repos by stars x citations\n\n')
    fh.write(f'{len(rows)} own GitHub repos (artifact records and websites '
             'excluded). Score = log10(stars+1) + log10(citations+1); '
             'citations = best displayed count among the repo\'s papers. '
             'Regenerate with harvest/impactview/gen_tier2_priority.py.\n\n')
    fh.write('| # | repo | stars | citations | last push | papers |\n')
    fh.write('|--:|------|------:|----------:|-----------|--------|\n')
    for i, (score, name, s, c, e) in enumerate(rows, 1):
        act = ('archived' if e.get('archived') else (e.get('active') or '?'))
        fh.write(f"| {i} | {name} | {s:,} | {c:,} | {act} | "
                 f"{', '.join(sorted(e['papers'])[:3])}"
                 f"{' …' if len(e['papers']) > 3 else ''} |\n")
print(f'{len(rows)} repos ranked -> harvest/impactview/tier2-priority.md')
for score, name, s, c, e in rows[:12]:
    print(f'  {name:40s} {s:>7,}* {c:>6,} cites')
