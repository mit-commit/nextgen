#!/usr/bin/env python3
"""Verify the light-search candidates in harvest/repos/descendants.json.

build_idea_descendants.py's --search step accepts a repo if its name/
description shares a handful of words with the citing work's title -- a
crude heuristic that turns out to produce a high false-positive rate on
inspection (a nonsense-named repo "jettbrains/-L-" matched 6 unrelated
papers via junk overlap; a C# tutorial repo matched a StreamIt-lineage
paper on shared words like "language"/"applications"). Titles in this
population are typically generic short phrases, unlike our own papers'
distinctive project names, so word overlap alone is not trustworthy
enough for "no guessing".

This re-checks every `evidence` starting with "light GitHub" with one live
model call each: given the citing work's title/authors/year and the
candidate repo's name/description/stars, is this genuinely the code for
that paper, or a coincidental word match? Downgrades a rejected candidate
back to `located: false` and records the rejection reason; a confirmed
match gets its evidence field replaced with the model's reasoning.

Live calls (a few dozen at most, not batch-scale).

    python3 curate/verify_descendants.py --write
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_PATH = os.path.join(ROOT, 'harvest', 'repos', 'descendants.json')
PUBLICATIONS = os.path.join(ROOT, 'data', 'publications.json')

API = 'https://api.anthropic.com/v1'
MODEL = 'claude-sonnet-4-6'

SYSTEM_PROMPT = """You are checking whether a GitHub repository found via a keyword search is
genuinely the code for a specific academic paper, or just a coincidental word
match. You are given the paper's title/authors/year and the source paper it
cites (for context on the research area), and the candidate repo's name,
description, and star count. You cannot fetch anything else.

Return ONE JSON object and nothing else: {"match": true|false, "reason": "..."}

`reason` is one short sentence: what confirmed the match, or what makes it a
coincidental word overlap rather than a real one. Be skeptical by default --
generic titles ("Elastic computing", "Resource recycling", "No bit left
behind") produce a lot of false positives against unrelated repos that happen
to share a common word. Only answer true when the repo's actual subject
matter plausibly matches the paper's, not just its vocabulary."""


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
        'user-agent': 'nextgen-verify-descendants',
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()

    out = json.load(open(OUT_PATH))
    pubs = {p['bibtexKey']: p for p in json.load(open(PUBLICATIONS))}

    checked = confirmed = rejected = 0
    for key, entries in out.items():
        our_title = pubs.get(key, {}).get('title') or key
        for e in entries:
            evidence = e.get('evidence', '')
            if not e.get('located') or not evidence.startswith('light GitHub repository search'):
                continue  # skip already-verified rows (evidence starts "light GitHub search, ...")
            checked += 1
            prompt = (
                f"SOURCE PAPER (for context, not the one being matched): {our_title!r}\n\n"
                f"CITING PAPER: {e.get('citing_title')!r}\n"
                f"  year: {e.get('citing_year')}\n\n"
                f"CANDIDATE REPO: {e.get('repo')}\n"
                f"  description: {e.get('description')!r}\n"
                f"  stars: {e.get('stars')}\n"
            )
            resp = json.loads(call('POST', '/messages', {
                'model': MODEL, 'max_tokens': 500,
                'system': SYSTEM_PROMPT,
                'messages': [{'role': 'user', 'content': prompt}],
            }))
            text = ''.join(b.get('text', '') for b in resp.get('content', []))
            try:
                parsed = parse_json(text)
                verdict, reason = bool(parsed['match']), parsed.get('reason', '')
            except Exception as exc:
                print(f'!! {key}/{e.get("repo")}: unparseable response '
                     f'({type(exc).__name__}) -- leaving as-is', file=sys.stderr)
                continue

            print(f'{"CONFIRM" if verdict else "REJECT "} {key} | '
                 f'{e.get("citing_title","")[:50]!r} -> {e.get("repo")} | {reason}')
            if verdict:
                confirmed += 1
                e['evidence'] = 'light GitHub search, model-confirmed: ' + reason
            else:
                rejected += 1
                e['located'] = False
                for f in ('repo', 'repo_url', 'stars', 'description'):
                    e.pop(f, None)
                e['evidence'] = 'rejected on verification: ' + reason
            time.sleep(0.3)

    print(f'\n{checked} checked, {confirmed} confirmed, {rejected} rejected')
    if args.write:
        with open(OUT_PATH, 'w') as fh:
            json.dump(out, fh, indent=1, sort_keys=True, ensure_ascii=False)
            fh.write('\n')
        print(f'wrote {OUT_PATH}')
    else:
        print('dry run -- nothing written. Pass --write to commit.')


if __name__ == '__main__':
    main()
