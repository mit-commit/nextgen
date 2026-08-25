#!/usr/bin/env python3
"""Ecosystems VERIFY step, part 2: model-judge the 760 candidates in
harvest/ecosystems/candidates.json (enumerate_candidates.py's output --
dependents graph + README/description mentions + real (compare-API)
fork divergence, for all 52 own repos).

One live model call per candidate. Classifies into the SDV integration
vocabulary (docs/impact-view-design.md): `derivative_work`, `fork`,
`api_user`, `inherited`, plus `uses_benchmark` for repos that only carry
the paper's workload/benchmark files (the "Uses its benchmarks" unified
group), and `reject` for anything that isn't real integration --
explicitly including the single biggest false-positive class in the
`mentions` source: curated/"awesome-*" list repos, blog posts, and course
materials that namedrop the project without using its code (flagged by
nextgen-a2 after eyeballing the raw candidates -- confirmed real,
e.g. tensor-compiler/taco pulled in "awesome-stars" list repos with
5-figure star counts that have nothing to do with tensor algebra).

Maps repo -> papers directly from data/repos/papers/*.json (own rows
whose `name` matches the ecosystem's canonical repo) rather than
tier2-priority.md's truncated 3-paper preview column.

Output: harvest/ecosystems/verified.json, keyed by bibtexKey (same
convention as harvest/repos/descendants.json / own-inventory.json /
halide-import.json) -- one row per (paper, confirmed candidate) pair,
shaped to drop straight into data/repos/SCHEMA.md:
  { "group": "builds-on"|"uses"|"benchmarks", "sdv": "<term>",
    "name": "<owner/repo>", "url": "...", "stars": N, "desc": "...",
    "own_repo": "<the ecosystem's anchor repo>", "source": [...],
    "evidence": "<model reason>" }

    python3 harvest/ecosystems/verify_ecosystem_candidates.py --write
"""
import argparse
import glob
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

CANDIDATES = os.path.join(HERE, 'candidates.json')
PUBLICATIONS = os.path.join(ROOT, 'data', 'publications.json')
REPOS_PAPERS_GLOB = os.path.join(ROOT, 'data', 'repos', 'papers', '*.json')
OUT_PATH = os.path.join(HERE, 'verified.json')
SEEN_PATH = os.path.join(HERE, 'verify_seen.json')

API = 'https://api.anthropic.com/v1'
MODEL = 'claude-sonnet-4-6'

SDV_TO_GROUP = {
    'derivative_work': 'builds-on',
    'fork': 'builds-on',
    'api_user': 'uses',
    'inherited': 'uses',
    'uses_benchmark': 'benchmarks',
}

SYSTEM_PROMPT = """You are classifying whether a candidate GitHub repository has a genuine
CODE-LEVEL relationship to an academic research tool's own repository, or
is a false positive from a mechanical discovery signal (GitHub's
dependents graph, a README/description text search, or a fork that was
merely pushed to after creation).

Classify into exactly one of:
  - "fork": a GitHub fork with its own meaningful changes/commits ahead
    of upstream (not just a stale mirror).
  - "derivative_work": a separate (non-fork) project that copies or
    substantially adapts the tool's code. This INCLUDES a renamed
    embedded fork -- a candidate found via a source-code fingerprint
    (an internal namespace fragment, a distinctive grammar/IR file or
    type name, a comment) rather than the tool's own name, where the
    renamed code is corroborated by provenance (an AUTHORS/CREDITS/
    LICENSE file naming the origin team or developers, matching
    `@author` tags, or comments describing the origin system) -- treat
    that combination as real derivative_work even though the package/
    repo name no longer matches at all.
  - "api_user": imports/calls the tool as a library or dependency,
    using its published interface, without modifying its internals.
  - "inherited": depends on the tool transitively (e.g. vendors or wraps
    it through another layer) rather than importing it directly.
  - "uses_benchmark": uses the tool's benchmark suite / workload files
    as input data, not the tool's own code.
  - "reject": not real integration. This explicitly INCLUDES curated
    list repos ("awesome-X", "my-stars", link/resource aggregators),
    blog posts, course/teaching materials, papers-about-the-tool that
    just namedrop it in a README, and coincidental name matches. A repo
    that only appears because it MENTIONS the project's name/URL in a
    long list of unrelated links is a reject, even with many stars.

You are given the tool's own repo name/description and the paper(s) it
implements (title + summary), and the candidate's name, description,
stars, how it was found (dependents graph / README mention / a fork
found to be N commits ahead via the real GitHub compare API), and that
ahead-by count when applicable. You cannot fetch anything else -- if the
description alone doesn't establish real integration, prefer "reject"
over guessing.

Return ONE JSON object and nothing else:
{"verdict": "fork"|"derivative_work"|"api_user"|"inherited"|"uses_benchmark"|"reject",
 "reason": "one short sentence"}"""


def call(method, path, payload=None, tries=6):
    key = os.environ.get('ANTHROPIC_BATCH_KEY')
    if not key:
        sys.exit('set ANTHROPIC_BATCH_KEY first (NOT ANTHROPIC_API_KEY)')
    url = path if path.startswith('http') else f'{API}{path}'
    body = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(url, data=body, method=method, headers={
        'x-api-key': key, 'anthropic-version': '2023-06-01',
        'content-type': 'application/json', 'user-agent': 'nextgen-verify-ecosystems',
    })
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return response.read().decode()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode()[:300]
            if exc.code in (429, 500, 502, 503, 504, 529):
                time.sleep(min(60, 10 * 2 ** attempt))
                continue
            sys.exit(f'{exc.code} {detail}')
        except Exception:
            time.sleep(10)
    sys.exit('gave up after repeated failures')


def parse_json(text):
    text = re.sub(r'^```(?:json)?\s*|\s*```$', '', (text or '').strip())
    start, end = text.find('{'), text.rfind('}')
    return json.loads(text[start:end + 1])


def repo_to_papers():
    mapping = {}
    for path in glob.glob(REPOS_PAPERS_GLOB):
        d = json.load(open(path))
        for r in d.get('repos', []):
            if r.get('group') == 'own' and r.get('name'):
                mapping.setdefault(r['name'].lower(), set()).add(d['key'])
    return mapping


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--limit', type=int)
    args = ap.parse_args()

    candidates = json.load(open(CANDIDATES))
    pubs = {p['bibtexKey']: p for p in json.load(open(PUBLICATIONS))}
    r2p = repo_to_papers()
    out = json.load(open(OUT_PATH)) if os.path.exists(OUT_PATH) else {}
    seen = set(json.load(open(SEEN_PATH))) if os.path.exists(SEEN_PATH) else set()
    # backfill from any rows written before verify_seen.json existed
    seen |= {row['_done_key'] for rows in out.values() for row in rows if '_done_key' in row}

    flat = []
    for own_repo, data in candidates.items():
        for c in data['candidates']:
            flat.append((own_repo, c))
    if args.limit:
        flat = flat[:args.limit]

    checked = confirmed = rejected = 0
    by_verdict = {}
    for i, (own_repo, c) in enumerate(flat, 1):
        done_key = f'{own_repo}::{c["repo"]}'.lower()
        if done_key in seen:
            continue

        papers = sorted(r2p.get(own_repo.lower(), set()))
        paper_ctx = []
        for key in papers[:3]:
            p = pubs.get(key, {})
            paper_ctx.append(f"- {p.get('title', key)!r} ({p.get('year')})")
        found_via = ', '.join(c['source'])
        if 'fork-divergence' in c['source']:
            found_via += f" (ahead_by={c.get('ahead_by')})"
        fp_note = ''
        if c.get('fingerprint_paths'):
            fp_note = (f"  matched in these files (not just the repo's name/description): "
                      f"{', '.join(c['fingerprint_paths'])}\n")

        prompt = (
            f"TOOL'S OWN REPO: {own_repo}\n"
            f"  implements paper(s):\n" + ('\n'.join(paper_ctx) if paper_ctx else '  (unknown)') + "\n\n"
            f"CANDIDATE: {c['repo']}\n"
            f"  description: {c.get('description')!r}\n"
            f"  stars: {c.get('stars')}\n"
            f"  found via: {found_via}\n"
            f"{fp_note}"
        )
        resp = json.loads(call('POST', '/messages', {
            'model': MODEL, 'max_tokens': 400,
            'system': SYSTEM_PROMPT,
            'messages': [{'role': 'user', 'content': prompt}],
        }))
        text = ''.join(b.get('text', '') for b in resp.get('content', []))
        try:
            parsed = parse_json(text)
            verdict, reason = parsed['verdict'], parsed.get('reason', '')
        except Exception as exc:
            print(f'!! {own_repo}/{c["repo"]}: unparseable ({type(exc).__name__}) -- skipping',
                 file=sys.stderr)
            continue

        checked += 1
        seen.add(done_key)
        by_verdict[verdict] = by_verdict.get(verdict, 0) + 1
        if i % 25 == 0 or verdict != 'reject':
            print(f'[{i}/{len(flat)}] {verdict:15s} {own_repo} | {c["repo"]} | {reason}', flush=True)

        if verdict == 'reject':
            rejected += 1
        else:
            confirmed += 1
            group = SDV_TO_GROUP[verdict]
            for key in papers:
                row = {
                    'group': group, 'sdv': verdict,
                    'name': c['repo'], 'url': f'https://github.com/{c["repo"]}',
                    'stars': c.get('stars'), 'desc': c.get('description'),
                    'own_repo': own_repo, 'source': c['source'],
                    'evidence': reason, '_done_key': done_key,
                }
                out.setdefault(key, [])
                if not any(r.get('_done_key') == done_key for r in out[key]):
                    out[key].append(row)
        if i % 20 == 0:
            with open(OUT_PATH + '.tmp', 'w') as fh:
                json.dump(out, fh, indent=1, sort_keys=True, ensure_ascii=False)
            os.replace(OUT_PATH + '.tmp', OUT_PATH)
            with open(SEEN_PATH + '.tmp', 'w') as fh:
                json.dump(sorted(seen), fh)
            os.replace(SEEN_PATH + '.tmp', SEEN_PATH)
        time.sleep(0.2)

    # seen-set reflects real API calls made (cost already spent) regardless
    # of --write, so it's always persisted -- a dry run must not be re-billed.
    with open(SEEN_PATH + '.tmp', 'w') as fh:
        json.dump(sorted(seen), fh)
    os.replace(SEEN_PATH + '.tmp', SEEN_PATH)

    print(f'\n{checked} checked this run, {confirmed} confirmed, {rejected} rejected')
    for v, n in sorted(by_verdict.items(), key=lambda kv: -kv[1]):
        print(f'  {v}: {n}')

    if args.write:
        with open(OUT_PATH, 'w') as fh:
            json.dump(out, fh, indent=1, sort_keys=True, ensure_ascii=False)
            fh.write('\n')
        print(f'wrote {OUT_PATH}')
    else:
        print('dry run -- nothing written. Pass --write to commit.')


if __name__ == '__main__':
    main()
