#!/usr/bin/env python3
"""Own-repo inventory: model-verification judge for phase A + phase B candidates.

Both hunts are mechanical (title-token overlap, owner/author heuristics)
and produce a high false-positive rate on their own -- generic surnames
("wilson", "taylor", "agarwal") and short titles collide with unrelated
GitHub accounts/repos constantly. Same heuristic-then-verify pattern as
curate/verify_descendants.py and curate/verify_repos.py: one live model
call per candidate, given the paper's actual subject matter (title +
summary, not just title tokens) plus the candidate repo's name/owner/
description/stars, asks whether this is genuinely that paper's own
repository.

Judges harvest/impactview/own-repo-candidates.json (phase A, org/account
repos) and harvest/impactview/personal-repo-candidates.json (phase B,
personal-account repos) together. Confirmed rows are written to
harvest/repos/own-inventory.json, shaped like harvest/repos/verified.json
rows (own_group always true here) plus a `source` field recording which
hunt found it -- nothing here touches verified.json or data/repos/
directly; that merge belongs to whoever folds this in.

    python3 harvest/impactview/verify_own_repos.py --write
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

PHASE_A = os.path.join(HERE, 'own-repo-candidates.json')
PHASE_B = os.path.join(HERE, 'personal-repo-candidates.json')
PUBLICATIONS = os.path.join(ROOT, 'data', 'publications.json')
OUT_PATH = os.path.join(ROOT, 'harvest', 'repos', 'own-inventory.json')

API = 'https://api.anthropic.com/v1'
MODEL = 'claude-sonnet-4-6'

SYSTEM_PROMPT = """You are checking whether a GitHub repository found via a mechanical,
noisy heuristic (title-word overlap and/or an author's personal account)
is genuinely the author's OWN repository FOR THIS SPECIFIC PAPER -- its
code, artifact, dataset, or website -- as opposed to:
  - a coincidental word match against an unrelated repo,
  - a repo owned by someone who just happens to share a common surname
    with an author (very common with short/generic surnames),
  - a real repo of the actual author, but for a DIFFERENT, unrelated
    project of theirs (e.g. a personal dotfiles repo, a course exercise,
    a hobby project) rather than this paper's work.

You are given the paper's title, summary, authors, and year, and the
candidate repo's owner, name, description, stars, and creation year.
You cannot fetch anything else.

Return ONE JSON object and nothing else:
{"match": true|false, "role": "implementation"|"artifact"|"dataset"|"website"|"other", "reason": "..."}

`role` only matters when match is true (use "other" otherwise). `reason`
is one short sentence justifying the verdict. Be skeptical by default --
require the repo's actual subject matter to plausibly be this paper's
system/artifact, not just an author-name or vocabulary coincidence."""


def call(method, path, payload=None, tries=6):
    key = os.environ.get('ANTHROPIC_BATCH_KEY')
    if not key:
        sys.exit('set ANTHROPIC_BATCH_KEY first (NOT ANTHROPIC_API_KEY)')
    url = path if path.startswith('http') else f'{API}{path}'
    body = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(url, data=body, method=method, headers={
        'x-api-key': key,
        'anthropic-version': '2023-06-01',
        'content-type': 'application/json',
        'user-agent': 'nextgen-verify-own-repos',
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


def load_candidates():
    """Merge phase A + phase B candidates, deduped on (key, repo)."""
    seen = {}
    for path, source_default in ((PHASE_A, 'phase-a-org-repo'), (PHASE_B, 'personal-account')):
        if not os.path.exists(path):
            continue
        for c in json.load(open(path)):
            seen[(c['key'], c['repo'].lower())] = {**c, 'source': c.get('source', source_default)}
    return list(seen.values())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()

    candidates = load_candidates()
    pubs = {p['bibtexKey']: p for p in json.load(open(PUBLICATIONS))}
    out = json.load(open(OUT_PATH)) if os.path.exists(OUT_PATH) else {}

    checked = confirmed = rejected = 0
    by_source = {}
    for c in candidates:
        key = c['key']
        pub = pubs.get(key, {})
        prompt = (
            f"PAPER: {pub.get('title', c.get('title'))!r}\n"
            f"  authors: {pub.get('author0', '(unknown)')}\n"
            f"  year: {c.get('year')}\n"
            f"  summary: {(pub.get('summary') or '(no summary)')[:1200]!r}\n\n"
            f"CANDIDATE REPO: {c['repo']}\n"
            f"  description: {c.get('desc')!r}\n"
            f"  stars: {c.get('stars')}\n"
            f"  created: {c.get('created')}\n"
        )
        resp = json.loads(call('POST', '/messages', {
            'model': MODEL, 'max_tokens': 500,
            'system': SYSTEM_PROMPT,
            'messages': [{'role': 'user', 'content': prompt}],
        }))
        text = ''.join(b.get('text', '') for b in resp.get('content', []))
        try:
            parsed = parse_json(text)
            verdict, role = bool(parsed['match']), parsed.get('role', 'other')
            reason = parsed.get('reason', '')
        except Exception as exc:
            print(f'!! {key}/{c["repo"]}: unparseable response '
                 f'({type(exc).__name__}) -- skipping', file=sys.stderr)
            continue

        checked += 1
        src = c.get('source', 'unknown')
        by_source.setdefault(src, {'checked': 0, 'confirmed': 0})
        by_source[src]['checked'] += 1
        print(f'{"CONFIRM" if verdict else "REJECT "} {key} | {c["repo"]} ({src}) | {reason}')
        if verdict:
            confirmed += 1
            by_source[src]['confirmed'] += 1
            row = {
                'url': f'https://github.com/{c["repo"]}',
                'confidence': 'high',
                'evidence': f'model-confirmed own repo (mechanical score {c.get("score")}, '
                            f'overlap: {", ".join(c.get("overlap", []))}): {reason}',
                'own_group': True,
                'role': role,
                'stars': c.get('stars'),
                'source': src,
            }
            out.setdefault(key, [])
            if not any(r['url'] == row['url'] for r in out[key]):
                out[key].append(row)
        else:
            rejected += 1
        time.sleep(0.3)

    print(f'\n{checked} checked, {confirmed} confirmed, {rejected} rejected')
    for src, stats in by_source.items():
        print(f'  {src}: {stats["confirmed"]}/{stats["checked"]} confirmed')
    papers_with_new_repo = len(out)
    print(f'{papers_with_new_repo} papers now have >=1 confirmed own repo in own-inventory.json')

    if args.write:
        with open(OUT_PATH, 'w') as fh:
            json.dump(out, fh, indent=1, sort_keys=True, ensure_ascii=False)
            fh.write('\n')
        print(f'wrote {OUT_PATH}')
    else:
        print('dry run -- nothing written. Pass --write to commit.')


if __name__ == '__main__':
    main()
