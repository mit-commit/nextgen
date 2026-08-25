#!/usr/bin/env python3
"""Ecosystems VERIFY, signal #4: fingerprint sweep for renamed embedded
forks (docs/impact-view-design.md section 7, "the sketch-frontend
lesson"). The human caught a real miss: asolarlez/sketch-frontend
embeds StreamIt's compiler frontend/IR under renamed packages, invisible
to all three prior signals (dependents graph, README/description
mentions -- which only matches the literal "owner/repo" string, not a
general project-name text search -- and fork-divergence, since it's not
a GitHub fork relationship at all, just a manually copied codebase).

Section 7 prescribes searching source CONTENT for identifiers that
survive a rename: namespace/package fragments, distinctive grammar/IR
file or type names, and provenance strings. Scoped per nextgen-a2's
request to repos "old or embedded enough to be copied rather than
forked/imported" -- the pre-GitHub, library-shaped systems among the 71
own repos. No standalone sketch/SUIF own repo exists in this corpus
(checked harvest/impactview/ecosystem-measure.json), so this covers the
four that do: streamit, taco, halide, dynamorio. Signatures were pulled
from each repo's own source (fetched live, not guessed) -- streamit's
three are exactly section 7's own worked example.

  bthies/streamit:       "streamit.frontend", "SIRStream", "at.dms.kjc"
  tensor-compiler/taco:  "TACO_TENSOR_T_DEFINED" (taco's runtime tensor
                         struct include-guard -- survives even when
                         generated code is vendored without the taco
                         package name anywhere)
  halide/Halide:         "Halide::Internal" (the IR's C++ namespace)
  DynamoRIO/dynamorio:   "dr_fragment_t", "dcontext_t" (core internal
                         types christened deep in the runtime, not part
                         of any public API someone would import by name)

One code-search call per signature (10/min code_search bucket), capped
at the first 100 hits (GitHub's default relevance ordering), deduped to
distinct repos, one core-API follow-up per unique repo for real stars/
description (code search's embedded repo object omits both). Appends
into harvest/ecosystems/candidates.json under each own repo's list,
tagged source=["fingerprint:<signature>"], for the existing verify step
to judge.

    python3 harvest/ecosystems/fingerprint_sweep.py
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'harvest', 'impactview'))
from find_own_repos import known_owners  # noqa: E402

CANDIDATES = os.path.join(HERE, 'candidates.json')
UA = 'nextgen-ecosystems-fingerprint/1.0'

SIGNATURES = {
    'bthies/streamit': ['"streamit.frontend"', '"SIRStream"', '"at.dms.kjc"'],
    'tensor-compiler/taco': ['"TACO_TENSOR_T_DEFINED"'],
    'halide/Halide': ['"Halide::Internal"'],
    'DynamoRIO/dynamorio': ['"dr_fragment_t"', '"dcontext_t"'],
}


def token():
    return os.environ.get('GITHUB_TOKEN') or sys.exit('need GITHUB_TOKEN')


def gh_core(path):
    req = urllib.request.Request(
        f'https://api.github.com{path}',
        headers={'authorization': f'Bearer {token()}',
                 'accept': 'application/vnd.github+json', 'user-agent': UA})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            if exc.code in (403, 429):
                reset = exc.headers.get('X-RateLimit-Reset')
                wait = max(1.0, float(reset) - time.time()) if reset else 30.0
                time.sleep(min(wait, 90))
                continue
            return None
        except Exception:
            time.sleep(2 * (attempt + 1))
    return None


_last_code_search = 0.0


def gh_code_search(query):
    global _last_code_search
    gap = time.time() - _last_code_search
    if gap < 6.5:
        time.sleep(6.5 - gap)
    _last_code_search = time.time()
    url = 'https://api.github.com/search/code?' + urllib.parse.urlencode({'q': query, 'per_page': 100})
    req = urllib.request.Request(url, headers={
        'authorization': f'Bearer {token()}', 'accept': 'application/vnd.github+json', 'user-agent': UA})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            if exc.code == 422:
                return {'items': [], 'total_count': 0}
            if exc.code in (403, 429):
                reset = exc.headers.get('X-RateLimit-Reset')
                wait = max(1.0, float(reset) - time.time()) if reset else 60.0
                time.sleep(min(wait, 90))
                _last_code_search = time.time()
                continue
            return {'items': [], 'total_count': 0}
        except Exception:
            time.sleep(2 * (attempt + 1))
    return {'items': [], 'total_count': 0}


def main():
    own_owners = {o.lower() for o in known_owners()}
    candidates = json.load(open(CANDIDATES))

    for own_repo, sigs in SIGNATURES.items():
        existing = {c['repo'].lower() for c in candidates.get(own_repo, {}).get('candidates', [])}
        found = {}  # full_name.lower() -> {"repo", "sig"}
        for sig in sigs:
            data = gh_code_search(sig)
            hits = data.get('items', [])
            print(f'{own_repo} | {sig}: {data.get("total_count")} total, {len(hits)} fetched', flush=True)
            for item in hits:
                repo = item['repository']
                full_name = repo['full_name']
                key = full_name.lower()
                if key == own_repo.lower() or full_name.split('/')[0].lower() in own_owners:
                    continue
                if key in existing:
                    continue
                found.setdefault(key, {'repo': full_name, 'sigs': set(), 'paths': set()})
                found[key]['sigs'].add(sig)
                found[key]['paths'].add(item.get('path', ''))

        new_cands = []
        for key, info in found.items():
            meta = gh_core(f'/repos/{info["repo"]}')
            new_cands.append({
                'repo': info['repo'],
                'stars': (meta or {}).get('stargazers_count'),
                'description': (meta or {}).get('description'),
                'source': [f'fingerprint:{s}' for s in sorted(info['sigs'])],
                'fingerprint_paths': sorted(info['paths'])[:5],
            })
            time.sleep(0.05)

        candidates.setdefault(own_repo, {'candidates': [], 'trimmed_unverified': 0})
        candidates[own_repo]['candidates'].extend(new_cands)
        print(f'{own_repo}: {len(new_cands)} new fingerprint candidates '
             f'(of {len(found)} raw hits, {len(found) - len(new_cands)} already known)', flush=True)

    with open(CANDIDATES + '.tmp', 'w') as fh:
        json.dump(candidates, fh, indent=1, ensure_ascii=False)
    os.replace(CANDIDATES + '.tmp', CANDIDATES)
    total_new = sum(len([c for c in candidates[r]['candidates'] if any(
        s.startswith('fingerprint:') for s in c.get('source', []))]) for r in SIGNATURES)
    print(f'\n{total_new} total new fingerprint candidates -> {CANDIDATES}')


if __name__ == '__main__':
    main()
