#!/usr/bin/env python3
"""Judge, per (paper, own-repo) pair, whether the repo EMBODIES the
paper's specific contribution (human criterion 2026-08-25: ecosystem
overlap between papers is OK only when "the new parts of the paper are
captured in that repo").

    python3 harvest/impactview/judge_embodiment.py --list
    python3 harvest/impactview/judge_embodiment.py --submit [--dry-run]
    python3 harvest/impactview/judge_embodiment.py --status
    python3 harvest/impactview/judge_embodiment.py --collect

Output: harvest/impactview/embodiment.json
  { "<bibtexKey>": { "<owner/repo>": {"embodies": bool, "confidence":
    "high|medium|low", "reason": "..."} } }
Human-reviewable and overridable — build_repo_data.py attaches ecosystem
rows (and repo-side impact) only through embodying anchors; own-repo
rows themselves stay on every paper. Unjudged pairs default to
embodies=true so a partial file never silently drops data.

Needs ANTHROPIC_BATCH_KEY (never ANTHROPIC_API_KEY).
"""
import argparse
import glob
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.abspath(__file__))
API = 'https://api.anthropic.com/v1'
MODEL = 'claude-sonnet-4-6'
STATE = f'{HERE}/embodiment_state.json'
OUT = f'{HERE}/embodiment.json'

SYSTEM = """You judge one (paper, repository) pair from a research
group's publication corpus. The repository is verified as the group's
own. Question: does this repository CONTAIN THE IMPLEMENTATION OF THIS
PAPER'S SPECIFIC CONTRIBUTION — did the paper's new ideas land in this
code?

Answer embodies=true when the paper's contribution is (or clearly
became part of) this codebase: the system paper for the repo; a
technique paper whose optimization/feature was implemented there; a
thesis whose chapters are the system's components.

Answer embodies=false when the paper merely belongs to the same
project: overviews, position papers, retrospectives, application/demo
papers that only USE the system, or work whose actual implementation
lives elsewhere.

Return ONLY JSON: {"embodies": true|false, "confidence":
"high"|"medium"|"low", "reason": "<one sentence>"}"""


def strip_html(t):
    return html.unescape(re.sub(r'<[^>]+>', '', t or ''))


def pairs():
    pubs = {p.get('bibtexKey'): p for p in json.load(open(f'{ROOT}/data/publications.json'))}
    out = []
    for path in sorted(glob.glob(f'{ROOT}/data/repos/papers/*.json')):
        d = json.load(open(path))
        eco_anchor = {r['name'] for r in d['repos'] if r.get('group') != 'own'} \
            and True
        for r in d['repos']:
            if r.get('group') == 'own' and r.get('role') == 'implementation':
                p = pubs.get(d['key']) or {}
                out.append({
                    'key': d['key'], 'repo': r['name'],
                    'title': p.get('title'), 'year': p.get('year'),
                    'type': p.get('type') or '',
                    'summary': strip_html(p.get('summary'))[:900],
                    'repo_desc': r.get('desc'),
                    'verify_evidence': r.get('evidence'),
                })
    return out


def call(method, path, payload=None, tries=6):
    key = os.environ.get('ANTHROPIC_BATCH_KEY')
    if not key:
        sys.exit('set ANTHROPIC_BATCH_KEY first (NOT ANTHROPIC_API_KEY)')
    url = path if path.startswith('http') else f'{API}{path}'
    body = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(url, data=body, method=method, headers={
        'x-api-key': key, 'anthropic-version': '2023-06-01',
        'content-type': 'application/json', 'user-agent': 'nextgen-embodiment'})
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                return response.read().decode()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode()[:300]
            if exc.code in (429, 500, 502, 503, 504, 529):
                wait = min(300, 10 * 2 ** attempt)
                print(f'    {exc.code}; sleeping {wait}s')
                time.sleep(wait)
                continue
            sys.exit(f'{exc.code} {detail}')
        except Exception as exc:
            print(f'    {type(exc).__name__}; retrying in 20s')
            time.sleep(20)
    sys.exit('gave up')


def cid_of(p):
    return 'emb-' + re.sub(r'[^A-Za-z0-9_-]', '_', p['key'] + '--' + p['repo'])[:56]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--list', action='store_true')
    ap.add_argument('--submit', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--status', action='store_true')
    ap.add_argument('--collect', action='store_true')
    args = ap.parse_args()

    ps = pairs()
    if args.list:
        print(len(ps), 'pairs')
        import collections
        c = collections.Counter(p['repo'] for p in ps)
        for r, n in c.most_common(10):
            print(f'  {r}: {n} papers')
        return
    if args.submit:
        reqs = [{'custom_id': cid_of(p), 'params': {
                    'model': MODEL, 'max_tokens': 300, 'system': SYSTEM,
                    'messages': [{'role': 'user', 'content': json.dumps(
                        {k: v for k, v in p.items()}, ensure_ascii=False)}]}}
                for p in ps]
        size = sum(len(json.dumps(r)) for r in reqs)
        cost = (size / 4) / 1e6 * 3 / 2 + 120 * len(reqs) / 1e6 * 15 / 2
        print(f'{len(reqs)} requests, est ${cost:.2f} (batch)')
        if args.dry_run:
            return
        if cost >= 20:
            sys.exit('>=$20: stop for approval')
        result = json.loads(call('POST', '/messages/batches', {'requests': reqs}))
        json.dump({'batch': result['id']}, open(STATE, 'w'))
        print('submitted', result['id'])
    elif args.status:
        st = json.load(open(STATE))
        info = json.loads(call('GET', f'/messages/batches/{st["batch"]}'))
        print(info.get('processing_status'), json.dumps(info.get('request_counts')))
    elif args.collect:
        st = json.load(open(STATE))
        info = json.loads(call('GET', f'/messages/batches/{st["batch"]}'))
        if info.get('processing_status') != 'ended':
            sys.exit('not ended: ' + str(info.get('processing_status')))
        body = call('GET', info['results_url'])
        by_cid = {cid_of(p): p for p in ps}
        out = {}
        bad = 0
        for line in body.splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            p = by_cid.get(row.get('custom_id'))
            res = row.get('result') or {}
            if res.get('type') != 'succeeded' or not p:
                bad += 1
                continue
            text = ''.join(b.get('text', '') for b in
                           (res.get('message') or {}).get('content', []))
            m = re.search(r'\{.*\}', text, re.S)
            try:
                j = json.loads(m.group(0))
                out.setdefault(p['key'], {})[p['repo']] = {
                    'embodies': bool(j['embodies']),
                    'confidence': j.get('confidence', 'low'),
                    'reason': j.get('reason', '')}
            except Exception:
                bad += 1
        json.dump(out, open(OUT, 'w'), indent=1, ensure_ascii=False)
        n = sum(len(v) for v in out.values())
        yes = sum(1 for v in out.values() for j in v.values() if j['embodies'])
        print(f'{n} judged ({bad} failed): {yes} embody, {n - yes} do not -> {OUT}')


if __name__ == '__main__':
    main()
