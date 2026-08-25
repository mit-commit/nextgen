#!/usr/bin/env python3
"""Regenerate reception texts at scale (task F1, summaries-at-scale), in
waves of ~25 papers ordered by displayed citation count descending.

    python3 harvest/summaries/generate_receptions.py --list          # wave plan
    python3 harvest/summaries/generate_receptions.py --wave 1 --submit --dry-run
    python3 harvest/summaries/generate_receptions.py --wave 1 --submit
    python3 harvest/summaries/generate_receptions.py --wave 1 --status
    python3 harvest/summaries/generate_receptions.py --wave 1 --collect

Needs ANTHROPIC_BATCH_KEY (NOT ANTHROPIC_API_KEY — that breaks Claude Code
logins). The system prompt embeds docs/summary-style.md verbatim, so the
style doc stays the single source of truth.

Each request asks the model to REVISE the paper's existing reception (all
149 exist from the corpus pass) against the style doc and to integrate the
repository register — one natural closing sentence naming the verified
own-group implementation repo and/or badged artifact from
harvest/repos/verified.json and harvest/artifacts/found.json. Papers with
neither get no repository sentence. Pilot papers are approved prose and
are never in a wave. Output goes to harvest/summaries/wave<N>_out.json for
the reviewer pass; nothing lands in data/citations/reception.json until
the reviewed texts are merged by hand (merge_wave.py).
"""
import argparse
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
MAX_TOKENS = 1200
WAVE_SIZE = 25
PILOTS = {'halide:pldi:2013', 'thies:cc:2002', 'taylor:micro:2002',
          'amarasinghe:ijpp:2005', 'petkov:ipdps:2002', 'thies:toplas:2007',
          'levison:istas:2002', 'netblocks-pldi24',
          'Kjolstad:2017:TTG:3155562.3155683'}


def strip_html(t):
    return html.unescape(re.sub(r'<[^>]+>', '', t or ''))


def load_inputs():
    idx = json.load(open(f'{ROOT}/data/citations/index.json'))['papers']
    pubs = {p.get('bibtexKey'): p for p in json.load(open(f'{ROOT}/data/publications.json'))}
    rec = json.load(open(f'{ROOT}/data/citations/reception.json'))
    repos = json.load(open(f'{ROOT}/harvest/repos/verified.json'))
    artifacts = json.load(open(f'{ROOT}/harvest/artifacts/found.json'))
    return idx, pubs, rec, repos, artifacts


def waves():
    """Non-pilot papers with a reception, by displayed count desc, in waves."""
    idx, pubs, rec, repos, artifacts = load_inputs()
    pop = [(k, max(r['verified'] or 0, r['gscholar'] or 0))
           for k, r in idx.items() if k not in PILOTS and k in rec]
    pop.sort(key=lambda kv: -kv[1])
    keys = [k for k, _ in pop]
    return [keys[i:i + WAVE_SIZE] for i in range(0, len(keys), WAVE_SIZE)]


def build_pack(key, idx, pubs, rec, repos, artifacts):
    row = idx[key]
    pub = pubs.get(key) or {}
    d = json.load(open(f'{ROOT}/data/citations/{key}.json'))
    ext = [c for c in d['citations'] if not c.get('commit') and c['split']]

    def rank(c):
        pri = 0 if c.get('centrality') == 'core' else (
            1 if c['function'] in ('extends', 'uses-tool', 'adopts-idea',
                                   'uses-benchmark', 'baseline') else 2)
        return (pri, -(c.get('cited_by') or 0))
    notable = sorted(ext, key=rank)[:10]

    own = [r for r in repos.get(key, [])
           if r.get('own_group') and r.get('role') in ('implementation', 'artifact', 'benchmark')
           and r.get('confidence') in ('high', 'medium')]
    art = artifacts.get(key)
    judged = sum(row['functions'].values())
    return {
        'key': key,
        'title': pub.get('title'),
        'venue': pub.get('journal') or pub.get('booktitle') or pub.get('series') or '',
        'year': pub.get('year'),
        'summary': strip_html(pub.get('summary')),
        'previous_reception': rec.get(key),
        'counts': {'works': row['verified'], 'judged_external': judged,
                   'commit_papers': d['counts'].get('commit', 0)},
        'functions': row['functions'],
        'centrality': row.get('centrality', {}),
        'notable': [{'title': c['title'], 'function': c['function'],
                     'centrality': c.get('centrality'), 'year': c.get('year'),
                     'venue': c.get('venue'), 'cited_by': c.get('cited_by'),
                     'authors': c.get('authors')} for c in notable],
        'verified_repos': [{'url': r['url'], 'role': r['role'],
                            'confidence': r['confidence'], 'evidence': r['evidence']}
                           for r in own],
        'artifact': ({'badges': art.get('badges'), 'artifact_url': art.get('artifact_url')}
                     if art else None),
        'two_paragraphs': judged >= 300,
    }


TASK = """You revise ONE paper's reception text for a research-group
website. The style document above is binding. Revise the paper's
previous_reception (keep whatever already satisfies the style document —
minimal edits are preferred over rewrites) so that it:

1. fully satisfies the style document (voice, truth rules, seam, shape);
2. closes with the repository register — one natural sentence naming the
   verified own-group repository and/or the badged artifact from the
   evidence pack, per style-doc section 5. If the pack lists neither,
   add NO repository sentence;
3. names nothing the evidence pack does not support.

Return ONLY the final reception text (paragraphs separated by a blank
line). No preamble, no commentary, no markdown fences."""


def system_prompt():
    style = open(f'{ROOT}/docs/summary-style.md').read()
    return style + '\n\n---\n\n' + TASK


def build_request(pack):
    return {
        'custom_id': 'rec-' + re.sub(r'[^A-Za-z0-9_-]', '_', pack['key'])[:56],
        'params': {
            'model': MODEL,
            'max_tokens': MAX_TOKENS,
            'system': system_prompt(),
            'messages': [{'role': 'user', 'content':
                          'EVIDENCE PACK:\n' + json.dumps(pack, indent=1, ensure_ascii=False)}],
        },
    }


def call(method, path, payload=None, tries=6):
    key = os.environ.get('ANTHROPIC_BATCH_KEY')
    if not key:
        sys.exit('set ANTHROPIC_BATCH_KEY first (NOT ANTHROPIC_API_KEY)')
    url = path if path.startswith('http') else f'{API}{path}'
    body = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(url, data=body, method=method, headers={
        'x-api-key': key, 'anthropic-version': '2023-06-01',
        'content-type': 'application/json', 'user-agent': 'nextgen-summaries'})
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


def state_path(wave):
    return f'{HERE}/wave{wave}_state.json'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--list', action='store_true')
    ap.add_argument('--wave', type=int)
    ap.add_argument('--submit', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--status', action='store_true')
    ap.add_argument('--collect', action='store_true')
    args = ap.parse_args()

    ws = waves()
    if args.list:
        idx = json.load(open(f'{ROOT}/data/citations/index.json'))['papers']
        for i, w in enumerate(ws, 1):
            tops = ', '.join(w[:3])
            n = sum(max(idx[k]['verified'] or 0, idx[k]['gscholar'] or 0) for k in w)
            print(f'wave {i}: {len(w)} papers, {n:,} citations  ({tops}, …)')
        return
    if not args.wave:
        sys.exit('need --wave N (or --list)')
    keys = ws[args.wave - 1]

    if args.submit:
        idx, pubs, rec, repos, artifacts = load_inputs()
        packs = [build_pack(k, idx, pubs, rec, repos, artifacts) for k in keys]
        reqs = [build_request(p) for p in packs]
        json.dump(packs, open(f'{HERE}/wave{args.wave}_packs.json', 'w'),
                  indent=1, ensure_ascii=False)
        size = sum(len(json.dumps(r)) for r in reqs)
        in_tok = size // 4
        out_tok = 400 * len(reqs)
        cost = in_tok / 1e6 * 3 / 2 + out_tok / 1e6 * 15 / 2  # batch = half rate
        print(f'{len(reqs)} requests, ~{in_tok:,} input tokens, est ${cost:.2f} (batch)')
        if args.dry_run:
            print('dry run; sent nothing')
            return
        if cost >= 20:
            sys.exit('estimate >= $20 — stop for approval per standing rule')
        result = json.loads(call('POST', '/messages/batches', {'requests': reqs}))
        json.dump({'batch': result['id'], 'keys': keys},
                  open(state_path(args.wave), 'w'), indent=1)
        print(f'submitted {result["id"]}')
    elif args.status:
        st = json.load(open(state_path(args.wave)))
        info = json.loads(call('GET', f'/messages/batches/{st["batch"]}'))
        print(info.get('processing_status'), json.dumps(info.get('request_counts')))
    elif args.collect:
        st = json.load(open(state_path(args.wave)))
        info = json.loads(call('GET', f'/messages/batches/{st["batch"]}'))
        if info.get('processing_status') != 'ended':
            sys.exit(f'not ended: {info.get("processing_status")}')
        body = call('GET', info['results_url'])
        out = {}
        cid_to_key = {('rec-' + re.sub(r'[^A-Za-z0-9_-]', '_', k)[:56]): k
                      for k in st['keys']}
        for line in body.splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            key = cid_to_key.get(row.get('custom_id'))
            result = row.get('result') or {}
            if result.get('type') != 'succeeded' or not key:
                print('FAILED:', row.get('custom_id'), result.get('type'))
                continue
            text = ''.join(b.get('text', '') for b in
                           (result.get('message') or {}).get('content', []))
            out[key] = text.strip()
        path = f'{HERE}/wave{args.wave}_out.json'
        json.dump(out, open(path, 'w'), indent=1, ensure_ascii=False)
        print(f'{len(out)}/{len(st["keys"])} texts -> {path}')
        print('review against docs/summary-style.md, then merge_wave.py')


if __name__ == '__main__':
    main()
