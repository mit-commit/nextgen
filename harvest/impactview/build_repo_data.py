#!/usr/bin/env python3
"""Build the impact view's per-paper repository data (task F2).

    python3 harvest/impactview/build_repo_data.py            # report only
    python3 harvest/impactview/build_repo_data.py --write    # write data/repos/

Inputs (read-only, other lanes):
  harvest/repos/verified.json      tier-1 own-group repos (+ third_party,
                                   which is the paper's OWN dependencies —
                                   the reverse direction — and is excluded)
  harvest/artifacts/found.json     badged archival artifacts
  harvest/ecosystems/**            tier-2, folded in when it exists
  harvest/repos/descendants*       tier-3, folded in when it exists

GitHub metadata (stars, description, last-push year, archived, canonical
name after renames) is fetched with GITHUB_TOKEN and cached in
harvest/impactview/ghmeta.json; rows render gracefully without it.

Outputs (data/repos/SCHEMA.md documents the shape):
  data/repos/papers/<bibtexKey>.json   loaded lazily on panel expand
  data/repos/index.json                one row per paper, for the toggles
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.abspath(__file__))
GHCACHE = os.path.join(HERE, 'ghmeta.json')


def gh_repo(fullname, cache, token):
    if fullname in cache:
        return cache[fullname]
    req = urllib.request.Request(
        f'https://api.github.com/repos/{fullname}',
        headers={'authorization': f'Bearer {token}',
                 'accept': 'application/vnd.github+json',
                 'user-agent': 'nextgen-impactview'})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            d = json.loads(resp.read().decode())
        cache[fullname] = {
            'full_name': d.get('full_name'),
            'description': d.get('description'),
            'stars': d.get('stargazers_count'),
            'pushed': (d.get('pushed_at') or '')[:4] or None,
            'archived': bool(d.get('archived')),
        }
    except urllib.error.HTTPError as exc:
        cache[fullname] = {'error': exc.code}
    except Exception as exc:
        cache[fullname] = {'error': type(exc).__name__}
    time.sleep(0.2)
    return cache[fullname]


def fullname_of(url):
    part = url.split('github.com/')[-1].strip('/')
    bits = part.split('/')
    return '/'.join(bits[:2]) if len(bits) >= 2 else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--generated', default='2026-08-25')
    args = ap.parse_args()

    token = os.environ.get('GITHUB_TOKEN', '')
    verified = json.load(open(f'{ROOT}/harvest/repos/verified.json'))
    artifacts = json.load(open(f'{ROOT}/harvest/artifacts/found.json'))
    cache = json.load(open(GHCACHE)) if os.path.exists(GHCACHE) else {}

    papers = {}
    for key, rows in verified.items():
        out = []
        seen = set()
        for r in rows:
            # third_party = the paper's dependencies (even when own-group
            # authored), the reverse direction of impact
            if not r.get('own_group') or r.get('role') == 'third_party':
                continue
            entry = {'url': r['url'], 'group': 'own', 'role': r['role'],
                     'confidence': r['confidence'], 'evidence': r['evidence']}
            fn = fullname_of(r['url']) if 'github.com/' in r['url'] else None
            if fn:
                meta = gh_repo(fn, cache, token) if token else {}
                if meta and not meta.get('error'):
                    entry['name'] = meta['full_name'] or fn
                    if meta.get('description'):
                        entry['desc'] = meta['description']
                    if meta.get('stars') is not None:
                        entry['stars'] = meta['stars']
                    if meta.get('pushed'):
                        entry['active'] = int(meta['pushed'])
                    if meta.get('archived'):
                        entry['archived'] = True
                else:
                    entry['name'] = fn
                    if meta.get('error') == 404:
                        entry['gone'] = True
            else:
                entry['name'] = r['url'].split('//')[-1]
            # same repo reached via different recorded URLs -> one row
            ident = (entry['name'].lower(), entry['role'])
            if ident in seen:
                continue
            seen.add(ident)
            out.append(entry)
        art = artifacts.get(key)
        if art:
            out.insert(0, {
                'name': 'Archival artifact', 'group': 'own', 'role': 'artifact',
                'artifact': True, 'url': art.get('artifact_url'),
                'badges': art.get('badges') or [],
                'evidence': 'badged artifact record (harvest/artifacts/found.json)',
            })
        if out:
            # artifact rows first, then by role: implementation, artifact, benchmark
            order = {'artifact': 0, 'implementation': 1, 'benchmark': 2}
            out.sort(key=lambda e: (0 if e.get('artifact') else 1,
                                    order.get(e.get('role'), 3)))
            papers[key] = out

    if token:
        json.dump(cache, open(GHCACHE, 'w'), indent=1)

    n_repos = sum(len(v) for v in papers.values())
    with_stars = sum(1 for v in papers.values() for e in v if e.get('stars') is not None)
    print(f'{len(papers)} papers with impact-view repo data, {n_repos} rows '
          f'({with_stars} with stars metadata)')

    if not args.write:
        print('report only (use --write)')
        return
    os.makedirs(f'{ROOT}/data/repos/papers', exist_ok=True)
    index = {'schema': 1, 'generated': args.generated, 'papers': {}}
    for key, rows in papers.items():
        doc = {'schema': 1, 'key': key, 'generated': args.generated, 'repos': rows}
        with open(f'{ROOT}/data/repos/papers/{key}.json', 'w') as fh:
            json.dump(doc, fh, indent=1, ensure_ascii=False)
            fh.write('\n')
        tiers = {'own': sum(1 for r in rows if r['group'] == 'own'),
                 'using': sum(1 for r in rows if r['group'] in
                              ('builds-on', 'uses', 'benchmarks')),
                 'adopts': sum(1 for r in rows if r['group'] == 'adopts')}
        index['papers'][key] = {'repos': len(rows),
                                'tiers': {k: v for k, v in tiers.items() if v}}
    with open(f'{ROOT}/data/repos/index.json', 'w') as fh:
        json.dump(index, fh, indent=1)
        fh.write('\n')
    print(f'wrote data/repos/papers/ ({len(papers)} files) + data/repos/index.json')


if __name__ == '__main__':
    main()
