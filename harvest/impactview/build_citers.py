#!/usr/bin/env python3
"""Build data/citations/citers.json — per-paper lists of DISTINCT citing-
work ids with one id per work ACROSS papers, so the publications page can
union them ("N distinct citing works" in the overview, the proper version
of the reverse index).

    python3 harvest/impactview/build_citers.py [--write]

Reads the already-merged site files data/citations/<bibtexKey>.json
(pilot and non-pilot alike), so neither generation pipeline changes.
Identity: the work's DOI when its url carries one, else its normalized
title. Regenerate after any citation refresh.
"""
import argparse
import glob
import json
import os
import re
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SKIP = {'index.json', 'reception.json', 'gscholar.json', 'citers.json'}


def ident(c):
    url = (c.get('url') or '').lower()
    m = re.search(r'doi\.org/(10\.\S+)', url)
    if m:
        return 'd:' + m.group(1).rstrip('/.')
    t = unicodedata.normalize('NFKD', c.get('title') or '')
    t = re.sub(r'[^a-z0-9]+', '', t.encode('ascii', 'ignore').decode().lower())
    return 't:' + t if t else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--generated', default='2026-08-26')
    args = ap.parse_args()

    id_of, papers = {}, {}
    for path in sorted(glob.glob(f'{ROOT}/data/citations/*.json')):
        if os.path.basename(path) in SKIP:
            continue
        d = json.load(open(path))
        ids = set()
        for c in d.get('citations', []):
            k = ident(c)
            if not k:
                continue
            if k not in id_of:
                id_of[k] = len(id_of)
            ids.add(id_of[k])
        papers[d['key']] = sorted(ids)

    total = sum(len(v) for v in papers.values())
    print(f'{len(papers)} papers, {total:,} citer refs, {len(id_of):,} distinct works')
    if not args.write:
        print('report only (use --write)')
        return
    out = {'schema': 1, 'generated': args.generated, 'papers': papers}
    with open(f'{ROOT}/data/citations/citers.json', 'w') as fh:
        json.dump(out, fh, separators=(',', ':'))
        fh.write('\n')
    print(f"wrote data/citations/citers.json "
          f"({os.path.getsize(f'{ROOT}/data/citations/citers.json'):,} bytes)")


if __name__ == '__main__':
    main()
