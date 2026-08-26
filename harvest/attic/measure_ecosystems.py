#!/usr/bin/env python3
"""Tier-2 MEASURE step (human: hunt all 52 own repos; measure first, free).

    python3 harvest/impactview/measure_ecosystems.py

For every own code repo in the tier-2 priority list, gather free
ecosystem-size signals:
  - forks (REST repo record)
  - dependents: the count GitHub shows at /network/dependents (HTML —
    populated only for repos that are packages/libraries; 0/absent
    otherwise)
  - mentions: repositories whose name/description/README cite
    "owner/repo" (repo-search total_count, fork:false)

Writes harvest/impactview/ecosystem-measure.json + .md with a priced
estimate for the verification phase (depth caps per the ruling: the
long tail verifies fully, giants cap at VERIFY_CAP candidates).
Search API budget: 2.2s between calls (30/min limit).
"""
import glob
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.abspath(__file__))
VERIFY_CAP = 300          # giants: verify top-N dependents only
COST_PER_CANDIDATE = 0.01  # deliberately generous per-judgment estimate ($)


def api(path, token, accept='application/vnd.github+json'):
    req = urllib.request.Request(
        f'https://api.github.com{path}',
        headers={'authorization': f'Bearer {token}', 'accept': accept,
                 'user-agent': 'nextgen-ecosystem-measure'})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def dependents_count(fullname):
    req = urllib.request.Request(
        f'https://github.com/{fullname}/network/dependents',
        headers={'user-agent': 'Mozilla/5.0 (nextgen-ecosystem-measure)'})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode('utf-8', 'ignore')
    except Exception:
        return None
    m = re.search(r'([\d,]+)\s*\n?\s*Repositories', html)
    return int(m.group(1).replace(',', '')) if m else None


def main():
    token = os.environ.get('GITHUB_TOKEN') or sys.exit('need GITHUB_TOKEN')
    repos = set()
    for path in glob.glob(f'{ROOT}/data/repos/papers/*.json'):
        d = json.load(open(path))
        for r in d['repos']:
            if (r.get('group') == 'own' and not r.get('artifact')
                    and 'github.com' in (r.get('url') or '')):
                repos.add(r['name'])
    out_path = f'{HERE}/ecosystem-measure.json'
    out = json.load(open(out_path)) if os.path.exists(out_path) else {}
    for i, fn in enumerate(sorted(repos, key=str.lower), 1):
        if fn in out:
            continue
        row = {}
        try:
            meta = api(f'/repos/{fn}', token)
            row['stars'] = meta.get('stargazers_count')
            row['forks'] = meta.get('forks_count')
        except urllib.error.HTTPError as exc:
            row['error'] = exc.code
        row['dependents'] = dependents_count(fn)
        try:
            q = urllib.parse.quote(f'"{fn}" in:name,description,readme fork:false')
            row['mentions'] = api(f'/search/repositories?q={q}&per_page=1',
                                  token)['total_count']
        except Exception as exc:
            row['mentions'] = None
        out[fn] = row
        json.dump(out, open(out_path, 'w'), indent=1)
        print(f'[{i}/{len(repos)}] {fn}: stars={row.get("stars")} '
              f'forks={row.get("forks")} dependents={row.get("dependents")} '
              f'mentions={row.get("mentions")}')
        time.sleep(2.2)  # search rate limit

    rows = []
    for fn, r in out.items():
        dep = r.get('dependents') or 0
        men = r.get('mentions') or 0
        forks = r.get('forks') or 0
        candidates = dep + men
        capped = min(dep, VERIFY_CAP) + min(men, VERIFY_CAP)
        rows.append((candidates, capped, fn, r))
    rows.sort(reverse=True)
    total_c = sum(c for c, _, _, _ in rows)
    total_v = sum(v for _, v, _, _ in rows)
    est = total_v * COST_PER_CANDIDATE
    with open(f'{HERE}/ecosystem-measure.md', 'w') as fh:
        fh.write('# Tier-2 ecosystem measure — all own repos\n\n')
        fh.write(f'{len(rows)} repos. Raw candidates {total_c:,} '
                 f'(dependents + README/desc mentions); with the {VERIFY_CAP}'
                 f'-per-signal giant cap: {total_v:,} to verify, est '
                 f'~${est:,.0f} at ${COST_PER_CANDIDATE}/judgment '
                 '(generous). Dependents exist only for repos used as '
                 'packages; mentions catch the rest.\n\n')
        fh.write('| repo | stars | forks | dependents | mentions | verify (capped) |\n')
        fh.write('|------|------:|------:|-----------:|---------:|----------------:|\n')
        for c, v, fn, r in rows:
            fh.write(f"| {fn} | {r.get('stars') or 0:,} | {r.get('forks') or 0:,} "
                     f"| {r.get('dependents') if r.get('dependents') is not None else '—'} "
                     f"| {r.get('mentions') if r.get('mentions') is not None else '—'} "
                     f"| {v:,} |\n")
    print(f'\n{len(rows)} repos measured; {total_c:,} raw candidates, '
          f'{total_v:,} capped, est ~${est:,.0f}')
    print(f'-> {HERE}/ecosystem-measure.md')


if __name__ == '__main__':
    import urllib.parse
    main()
