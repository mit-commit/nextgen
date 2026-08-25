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
    # own-inventory.json stores confirmed rows as a bare "owner/repo" (no
    # scheme); verified.json stores full URLs, occasionally on a non-GitHub
    # host (gitlab/bitbucket) that must NOT be parsed as an owner/repo pair.
    if '://' in url:
        if 'github.com/' not in url:
            return None
        part = url.split('github.com/')[-1].strip('/')
    else:
        part = url.strip('/')
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
    desc_path = f'{ROOT}/harvest/repos/descendants.json'
    descendants = json.load(open(desc_path)) if os.path.exists(desc_path) else {}
    inv_path = f'{ROOT}/harvest/repos/own-inventory.json'
    inventory = json.load(open(inv_path)) if os.path.exists(inv_path) else {}
    cache = json.load(open(GHCACHE)) if os.path.exists(GHCACHE) else {}
    # round-8 task 3: halide-import.json's tier-2 rows (samanamarasinghe/
    # Halide-world's own ecosystem-user index, mapped not re-judged -- stars/
    # evidence/etc. are Halide-world's own, never refetched from GitHub here).
    # Keyed to a single paper (halide:pldi:2013); tier-3 (162 rows) stays
    # unfolded per the round-8 task's literal scope (567 tier-2 rows only).
    halide_path = f'{ROOT}/harvest/ecosystems/halide-import.json'
    halide_import = json.load(open(halide_path)) if os.path.exists(halide_path) else None
    # tier2 + tier3: both are Halide-world's own verified rows (tier3 was
    # scoped out of the original round-8 fold; citing_title becomes the
    # row's paper label). Expanded to EVERY paper whose own repo is
    # halide/Halide — the same rule the ecosystem hunt uses — not just
    # the one canonical paper the round-8 task mapped it to.
    halide_rows = []
    if halide_import:
        halide_rows = halide_import['tier2'] + [
            dict(r, paper=r.get('citing_title')) for r in halide_import.get('tier3', [])]
    # corpus-wide tier-2: model-verified outside users of all 71 own repos
    # (harvest/ecosystems/verified.json, pre-shaped to SCHEMA.md rows)
    ecov_path = f'{ROOT}/harvest/ecosystems/verified.json'
    eco_verified = json.load(open(ecov_path)) if os.path.exists(ecov_path) else {}
    # hand-verified rows the automated signals cannot see (renamed embedded
    # forks etc.); keyed by own_repo, expanded to that ecosystem's papers
    man_path = os.path.join(HERE, 'manual-rows.json')
    manual = json.load(open(man_path))['rows'] if os.path.exists(man_path) else []
    own_map = {}
    for k2 in set(verified) | set(inventory):
        names = set()
        for r in verified.get(k2, []) + inventory.get(k2, []):
            if (r.get('own_group') and r.get('role') not in ('third_party', 'website')
                    and 'github.com' in (r.get('url') or '')):
                fn2 = fullname_of(r['url'])
                if fn2:
                    names.add(fn2.lower())
        own_map[k2] = names

    papers = {}
    for key in sorted(set(verified) | set(descendants) | set(inventory) | set(eco_verified)):
        # own-inventory rows are tier-1 like verified.json's; 'website'
        # repos stay inventory-only (project pages, not impact)
        rows = verified.get(key, []) + [
            r for r in inventory.get(key, []) if r.get('role') != 'website']
        out = []
        seen = set()
        for r in rows:
            # third_party = the paper's dependencies (even when own-group
            # authored), the reverse direction of impact
            if not r.get('own_group') or r.get('role') == 'third_party':
                continue
            entry = {'url': r['url'], 'group': 'own', 'role': r['role'],
                     'confidence': r['confidence'], 'evidence': r['evidence']}
            fn = fullname_of(r['url'])
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
        # tier 3: idea-descendant repos of citing works. Only located rows
        # render — unlocated ones already appear in the Citations panel,
        # and the unsearched widened bucket would swamp the view.
        for r in descendants.get(key, []):
            if not r.get('located') or not r.get('repo_url'):
                continue
            entry = {'url': r['repo_url'], 'group': 'adopts',
                     'name': r.get('repo') or fullname_of(r['repo_url']),
                     'paper': r.get('citing_title'),
                     'evidence': r.get('evidence')}
            fn = fullname_of(r['repo_url']) if 'github.com/' in r['repo_url'] else None
            if fn and token:
                meta = gh_repo(fn, cache, token)
                if meta and not meta.get('error'):
                    entry['name'] = meta['full_name'] or entry['name']
                    if meta.get('description'):
                        entry['desc'] = meta['description']
                    if meta.get('stars') is not None:
                        entry['stars'] = meta['stars']
                    if meta.get('pushed'):
                        entry['active'] = int(meta['pushed'])
                    if meta.get('archived'):
                        entry['archived'] = True
            if entry.get('desc') is None and r.get('description'):
                entry['desc'] = r['description']
            if entry.get('stars') is None and r.get('stars') is not None:
                entry['stars'] = r['stars']
            # skip if this repo already appears in any role for this paper
            if entry['name'].lower() in {n for n, _ in seen}:
                continue
            seen.add((entry['name'].lower(), 'adopts'))
            out.append(entry)
        # tier 2: corpus-wide verified outside users. GitHub-enriched via
        # the shared cache (264 distinct repos); own_repo goes into the
        # evidence tooltip so multi-ecosystem papers stay legible.
        for r in eco_verified.get(key, []) + [
                m for m in manual if m['own_repo'].lower() in own_map.get(key, set())]:
            entry = {'url': r['url'], 'group': r['group'], 'name': r['name'],
                     'evidence': (f"ecosystem of {r['own_repo']}: " if r.get('own_repo') else '')
                                 + (r.get('evidence') or '')}
            if r.get('sdv'):
                entry['sdv'] = r['sdv']
            fn = fullname_of(r['url']) if 'github.com/' in (r.get('url') or '') else None
            if fn and token:
                meta = gh_repo(fn, cache, token)
                if meta and not meta.get('error'):
                    entry['name'] = meta['full_name'] or entry['name']
                    if meta.get('description'):
                        entry['desc'] = meta['description']
                    if meta.get('stars') is not None:
                        entry['stars'] = meta['stars']
                    if meta.get('pushed'):
                        entry['active'] = int(meta['pushed'])
                    if meta.get('archived'):
                        entry['archived'] = True
            if entry.get('desc') is None and r.get('desc'):
                entry['desc'] = r['desc']
            if entry.get('stars') is None and r.get('stars') is not None:
                entry['stars'] = r['stars']
            if entry['name'].lower() in {n for n, _ in seen}:
                continue
            seen.add((entry['name'].lower(), entry['group']))
            out.append(entry)
        # tier 2: ecosystem-user rows imported from another repo's own
        # index (currently only halide-import.json). Mapped verbatim --
        # no GitHub refetch, no re-judging -- skip only an exact repo the
        # paper already carries under any other role/group.
        halide_here = halide_rows if 'halide/halide' in own_map.get(key, set()) else []
        for r in halide_here:
            name_l = r['name'].lower()
            if name_l in {n for n, _ in seen}:
                continue
            entry = {k: v for k, v in r.items() if v is not None}
            out.append(entry)
            seen.add((name_l, entry['group']))
        if out:
            # artifact/own rows first, then tier-2 ecosystem rows, then
            # tier-3 descendants
            group_order = {'adopts': 2}
            order = {'artifact': 0, 'implementation': 1, 'benchmark': 2}
            out.sort(key=lambda e: (group_order.get(e.get('group'), 0 if e.get('role') else 1),
                                    0 if e.get('artifact') else 1,
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
        # repo-side impact: outside repos weighted by relationship, the
        # same scale as the citation-function weights (extends 10,
        # uses-tool 8, uses-benchmark 5, adopts-idea 8) via the unified
        # taxonomy. Own rows and artifacts are the paper itself, weight 0.
        rw = {'builds-on': 10, 'uses': 8, 'benchmarks': 5, 'adopts': 8}
        impact = sum(rw.get(r['group'], 0) for r in rows)
        index['papers'][key] = {'repos': len(rows),
                                'tiers': {k: v for k, v in tiers.items() if v}}
        if impact:
            index['papers'][key]['impact'] = impact
    with open(f'{ROOT}/data/repos/index.json', 'w') as fh:
        json.dump(index, fh, indent=1)
        fh.write('\n')
    print(f'wrote data/repos/papers/ ({len(papers)} files) + data/repos/index.json')


if __name__ == '__main__':
    main()
