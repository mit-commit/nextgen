#!/usr/bin/env python3
"""Task `repo-verify`: a model pass over every paper's repo evidence, via
the Batch API. Built on the classify_citations.py pattern.

Evidence per paper, combined and deduped by (owner, repo):
  - in-paper mentions (harvest/repos/mentions.json): URLs the paper itself
    prints, with the surrounding line -- these are sometimes the paper's
    own repo ("code is at github.com/...") and sometimes a citation to a
    third-party tool/benchmark (a bibliography entry), so they still need
    judgment, not an automatic "own" label.
  - GitHub search candidates (harvest/repos/candidates.json, from
    search_github.py): heuristically scored, with stars/description/
    created_at signal for judging canonical-vs-fork.

For each candidate URL the model returns role (implementation / artifact /
benchmark / third_party), own_group, confidence, and evidence, or omits it
entirely when the only support is name similarity (the paper says nothing
else about it, and no real project.dev signal like stars ties it back).
When two candidates are forks of the same project the model is asked to
keep only the canonical one.

Pilot papers (9 keys, matching assets/js/publications.js's PILOT_KEYS) are
processed and pushed first, per task instruction.

Output: harvest/repos/verified.json (confidence high/medium rows) and
harvest/repos/review.json (confidence low rows, for a human spot-check) --
one list of repo dicts per bibtexKey. A paper with no evidence at all gets
an empty list, no API call.

    python3 curate/verify_repos.py --submit --dry-run
    python3 curate/verify_repos.py --submit --pilots-only
    python3 curate/verify_repos.py --submit
    python3 curate/verify_repos.py --status
    python3 curate/verify_repos.py --collect
    python3 curate/verify_repos.py --recover
"""
import argparse
import glob
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MENTIONS_PATH = os.path.join(ROOT, 'harvest', 'repos', 'mentions.json')
CANDIDATES_PATH = os.path.join(ROOT, 'harvest', 'repos', 'candidates.json')
PUBLICATIONS = os.path.join(ROOT, 'data', 'publications.json')

OUT_DIR = os.path.join(ROOT, 'harvest', 'repos')
VERIFIED_PATH = os.path.join(OUT_DIR, 'verified.json')
REVIEW_PATH = os.path.join(OUT_DIR, 'review.json')
STATE_PATH = os.path.join(OUT_DIR, '_verify_batches.json')
REQUESTS_DUMP = os.path.join(OUT_DIR, '_verify_requests_dry_run.json')

API = 'https://api.anthropic.com/v1'
MODEL = 'claude-sonnet-4-6'
MAX_TOKENS = 2000
PER_BATCH = 400

BATCH_INPUT_PER_MTOK = 1.50
BATCH_OUTPUT_PER_MTOK = 7.50
EST_OUTPUT_TOKENS = 300

PILOT_KEYS = [
    'halide:pldi:2013', 'thies:cc:2002', 'taylor:micro:2002',
    'amarasinghe:ijpp:2005', 'petkov:ipdps:2002', 'thies:toplas:2007',
    'levison:istas:2002', 'netblocks-pldi24',
    'Kjolstad:2017:TTG:3155562.3155683',
]

ROLES = ('implementation', 'artifact', 'benchmark', 'third_party')

SYSTEM_PROMPT = """You are verifying the repo evidence gathered for ONE academic paper, for a
research-impact site. You are given the paper's metadata and every candidate
repository URL found for it -- some printed in the paper itself (with the
surrounding sentence), some found by a heuristic GitHub search (with a score,
star count, description, and creation date). You cannot fetch anything; judge
only from what's given.

Return ONE JSON object and nothing else. No prose, no markdown fence.

  {"repos": [ {"url", "role", "own_group", "confidence", "evidence"}, ... ]}

Include ONE entry per URL you judge worth keeping -- omit a candidate
entirely if the only support for it is name similarity to the paper's
project/software name, with nothing else (no in-paper mention, no
description/README signal, no author-owner match). A rejected candidate
should simply not appear in `repos`.

Fields per kept repo:
  url          the URL as given (do not rewrite it)
  role         implementation | artifact | benchmark | third_party
               - implementation: this repo IS the system/tool the paper
                 presents
               - artifact: a companion dataset/evaluation-artifact repo for
                 this paper (not the main system)
               - benchmark: a benchmark suite or workload the paper uses,
                 not something the paper's own group built
               - third_party: any other tool/dependency/prior-work repo the
                 paper cites or builds on, not the paper's own output
  own_group    true iff the repo's owner/org is plausibly this paper's own
               author(s) or their lab -- an in-paper "our code is at ..."
               statement is strong evidence; a bare bibliography citation
               to someone else's tool is not
  confidence   high | medium | low -- low means genuinely ambiguous
               (goes to a human review queue, not the confident list)
  evidence     one short sentence: what specifically justified this call
               (quote or paraphrase the context line, or name the signal --
               "in-paper: 'code is open-sourced at...'", "1300+ stars vs.
               0-star same-named repo", "author surname matches org", etc.)

CANONICAL-OVER-FORK RULE: when two or more candidates are clearly the same
underlying project (same name, one is a fork/clone of the other, or one is
an author's personal fork of an org repo), keep ONLY the canonical one --
the org/original with real activity (stars, description, wasn't created
right around a fork event) -- and drop the fork(s) from `repos` entirely
rather than listing both.

Do not guess. A repo with weak, ambiguous, or conflicting evidence should
still be included (so a human can look at it) but at confidence low, never
upgraded to look more certain than the evidence supports."""


def load_evidence():
    mentions = json.load(open(MENTIONS_PATH))
    candidates = json.load(open(CANDIDATES_PATH))
    pubs = {p['bibtexKey']: p for p in json.load(open(PUBLICATIONS))}

    per_paper = {}
    for key, rec in mentions.items():
        urls = rec.get('urls') or []
        cands = candidates.get(key) or []
        if not urls and not cands:
            continue
        per_paper[key] = {'mentions': urls, 'candidates': cands, 'pub': pubs.get(key, {})}
    return per_paper


def pack_evidence(key, ev):
    pub = ev['pub']
    parts = [
        f"PAPER: {pub.get('title') or key!r}",
        f"  authors: {pub.get('author0') or '(unknown)'}",
        f"  year: {pub.get('year')}   venue: {pub.get('venue') or '(unknown)'}",
        f"  project field in our records: {pub.get('project') or '(none)'}",
    ]
    if ev['mentions']:
        parts.append('\nURLS PRINTED IN THE PAPER:')
        for m in ev['mentions']:
            parts.append(f"  - {m.get('url')}")
            if m.get('context_line'):
                parts.append(f"    context: {m['context_line'][:220]!r}")
    if ev['candidates']:
        parts.append('\nGITHUB SEARCH CANDIDATES (heuristically scored, not verified):')
        for c in ev['candidates']:
            parts.append(f"  - {c.get('url')}  (heuristic score={c.get('score')}, "
                         f"confidence={c.get('confidence')}, stars={c.get('stars')}, "
                         f"created={c.get('created_at')})")
            if c.get('description'):
                parts.append(f"    description: {c['description'][:200]!r}")
            if c.get('evidence'):
                parts.append(f"    heuristic evidence: {c['evidence']}")
    return '\n'.join(parts)


def build_request(key, ev):
    custom_id = hashlib.sha1(key.encode()).hexdigest()[:40]
    return {
        'custom_id': custom_id,
        'params': {
            'model': MODEL,
            'max_tokens': MAX_TOKENS,
            'system': SYSTEM_PROMPT,
            'messages': [{'role': 'user', 'content': pack_evidence(key, ev)}],
        },
    }


# ---------------------------------------------------------------- validation

def parse_record(text):
    text = (text or '').strip()
    text = re.sub(r'^```(?:json)?\s*|\s*```$', '', text)
    # A model occasionally over-escapes an apostrophe inside a JSON string
    # ("Baron\'s thesis") -- \' is not a valid JSON escape (only " needs
    # escaping inside a double-quoted string), so plain json.loads rejects
    # it outright. Safe to strip everywhere: a real `\\'` (escaped
    # backslash then a literal quote) never occurs in this schema's prose.
    text = text.replace("\\'", "'")
    end = text.rfind('}')
    if end < 0:
        raise ValueError('no JSON object in the response')
    starts = [m.start() for m in re.finditer('{', text[:end + 1])]
    last_error = ValueError('no JSON object in the response')
    for start in reversed(starts):
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError as exc:
            last_error = exc
    raise last_error


def validate(record):
    problems = []
    if not isinstance(record, dict) or 'repos' not in record:
        return ['missing field repos']
    repos = record['repos']
    if not isinstance(repos, list):
        return ['repos is not a list']
    for i, r in enumerate(repos):
        for field in ('url', 'role', 'own_group', 'confidence', 'evidence'):
            if field not in r:
                problems.append(f'repos[{i}] missing field {field}')
        if problems:
            continue
        if r['role'] not in ROLES:
            problems.append(f"repos[{i}] role {r['role']!r} not in {ROLES}")
        if not isinstance(r['own_group'], bool):
            problems.append(f'repos[{i}] own_group is not a bool')
        if r['confidence'] not in ('high', 'medium', 'low'):
            problems.append(f"repos[{i}] confidence {r['confidence']!r} not high/medium/low")
    return problems


def write_result(key, text, verified, review, needs_review_out):
    try:
        parsed = parse_record(text)
        problems = validate(parsed)
    except Exception as exc:
        parsed, problems = None, [f'{type(exc).__name__}: {exc}']

    if problems:
        needs_review_out.append({'key': key, 'problems': problems, 'raw': (text or '')[:4000]})
        return False

    high_med = [r for r in parsed['repos'] if r['confidence'] in ('high', 'medium')]
    low = [r for r in parsed['repos'] if r['confidence'] == 'low']
    verified[key] = high_med
    if low:
        review[key] = low
    return True


# ---------------------------------------------------------------- http

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
        'user-agent': 'nextgen-verify-repos',
    })
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                return response.read().decode()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode()[:300]
            if exc.code in (429, 500, 502, 503, 504, 529):
                wait = min(300, 10 * 2 ** attempt)
                print(f'    {exc.code}; sleeping {wait}s  {detail[:120]}')
                time.sleep(wait)
                continue
            sys.exit(f'{exc.code} {detail}')
        except Exception as exc:
            print(f'    {type(exc).__name__}; retrying in 20s')
            time.sleep(20)
    sys.exit('gave up after repeated failures')


# ---------------------------------------------------------------- modes

def target_keys(pilots_only, done_keys):
    per_paper = load_evidence()
    keys = [k for k in per_paper if k not in done_keys]
    if pilots_only:
        keys = [k for k in keys if k in PILOT_KEYS]
    else:
        # pilots always go in front of a mixed run too, per task instruction
        keys.sort(key=lambda k: (k not in PILOT_KEYS, k))
    return keys, per_paper


def load_state():
    return json.load(open(STATE_PATH)) if os.path.exists(STATE_PATH) else {'batches': [], 'items': {}}


def do_submit(dry_run, pilots_only, limit):
    verified = json.load(open(VERIFIED_PATH)) if os.path.exists(VERIFIED_PATH) else {}
    review = json.load(open(REVIEW_PATH)) if os.path.exists(REVIEW_PATH) else {}
    done_keys = set(verified) | set(review)

    keys, per_paper = target_keys(pilots_only, done_keys)
    if limit:
        keys = keys[:limit]
    if not keys:
        return print('nothing to submit')

    requests_ = [build_request(k, per_paper[k]) for k in keys]
    lookup = {r['custom_id']: k for r, k in zip(requests_, keys)}

    if dry_run:
        with open(REQUESTS_DUMP, 'w') as fh:
            json.dump(requests_, fh, indent=1, ensure_ascii=False)
        chars = sum(len(r['params']['system']) + len(r['params']['messages'][0]['content'])
                    for r in requests_)
        avg_tokens = (chars // len(requests_)) // 4
        total_in = avg_tokens * len(requests_)
        total_out = EST_OUTPUT_TOKENS * len(requests_)
        cost = total_in / 1e6 * BATCH_INPUT_PER_MTOK + total_out / 1e6 * BATCH_OUTPUT_PER_MTOK
        print(f'{len(requests_)} requests (pilots_only={pilots_only}), '
              f'~{avg_tokens} input tokens/request')
        print(f'COST ESTIMATE: ~${cost:,.2f} (batch pricing, no caching credit assumed)')
        print(f'wrote {REQUESTS_DUMP}; sent nothing')
        return

    state = load_state()
    state['items'].update(lookup)
    for start in range(0, len(requests_), PER_BATCH):
        chunk = requests_[start:start + PER_BATCH]
        result = json.loads(call('POST', '/messages/batches', {'requests': chunk}))
        state['batches'].append({'id': result['id'], 'n': len(chunk),
                                 'created': result.get('created_at'), 'collected': False})
        json.dump(state, open(STATE_PATH, 'w'), indent=1)
        print(f'  submitted {result["id"]}  {len(chunk)} requests')
    print(f'\n{len(state["batches"])} batches recorded in {STATE_PATH}')


def do_status():
    state = load_state()
    for batch in state['batches']:
        info = json.loads(call('GET', f'/messages/batches/{batch["id"]}'))
        counts = info.get('request_counts', {})
        print(f'{batch["id"]}  {info.get("processing_status"):12s} '
              f'{json.dumps(counts)}  collected={batch["collected"]}')


def do_collect():
    state = load_state()
    items = state.get('items', {})
    verified = json.load(open(VERIFIED_PATH)) if os.path.exists(VERIFIED_PATH) else {}
    review = json.load(open(REVIEW_PATH)) if os.path.exists(REVIEW_PATH) else {}
    needs_review = []
    if os.path.exists(os.path.join(OUT_DIR, '_verify_needs_review.jsonl')):
        with open(os.path.join(OUT_DIR, '_verify_needs_review.jsonl')) as fh:
            needs_review = [json.loads(l) for l in fh if l.strip()]

    written = failed = 0
    for batch in state['batches']:
        if batch['collected']:
            continue
        info = json.loads(call('GET', f'/messages/batches/{batch["id"]}'))
        if info.get('processing_status') != 'ended':
            print(f'{batch["id"]}: {info.get("processing_status")}, skipping')
            continue
        body = call('GET', info['results_url'])
        for line in body.splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            custom_id = row.get('custom_id')
            key = items.get(custom_id, custom_id)
            result = row.get('result') or {}
            if result.get('type') != 'succeeded':
                needs_review.append({'key': key, 'problems': [f'batch {result.get("type")}'],
                                     'raw': json.dumps(result)[:2000]})
                failed += 1
                continue
            message = result.get('message') or {}
            text = ''.join(b.get('text', '') for b in message.get('content', []))
            if write_result(key, text, verified, review, needs_review):
                written += 1
            else:
                failed += 1
        batch['collected'] = True
        json.dump(state, open(STATE_PATH, 'w'), indent=1)
        print(f'{batch["id"]}: collected')

    for path, payload in ((VERIFIED_PATH, verified), (REVIEW_PATH, review)):
        with open(path, 'w') as fh:
            json.dump(payload, fh, indent=1, sort_keys=True, ensure_ascii=False)
            fh.write('\n')
    with open(os.path.join(OUT_DIR, '_verify_needs_review.jsonl'), 'w') as fh:
        for row in needs_review:
            fh.write(json.dumps(row, ensure_ascii=False) + '\n')
    print(f'\n{written} papers written, {failed} sent to _verify_needs_review.jsonl')


def do_recover():
    review_path = os.path.join(OUT_DIR, '_verify_needs_review.jsonl')
    if not os.path.exists(review_path):
        return print('no review file')
    with open(review_path) as fh:
        rows = [json.loads(l) for l in fh if l.strip()]

    verified = json.load(open(VERIFIED_PATH)) if os.path.exists(VERIFIED_PATH) else {}
    review = json.load(open(REVIEW_PATH)) if os.path.exists(REVIEW_PATH) else {}
    remaining = []
    promoted = 0
    for row in rows:
        key = row['key']
        if key in verified or key in review:
            continue
        try:
            parsed = parse_record(row.get('raw'))
            problems = validate(parsed)
        except Exception as exc:
            problems = [f'{type(exc).__name__}: {exc}']
        if problems:
            row['problems'] = problems
            remaining.append(row)
            continue
        high_med = [r for r in parsed['repos'] if r['confidence'] in ('high', 'medium')]
        low = [r for r in parsed['repos'] if r['confidence'] == 'low']
        verified[key] = high_med
        if low:
            review[key] = low
        promoted += 1

    for path, payload in ((VERIFIED_PATH, verified), (REVIEW_PATH, review)):
        with open(path, 'w') as fh:
            json.dump(payload, fh, indent=1, sort_keys=True, ensure_ascii=False)
            fh.write('\n')
    with open(review_path, 'w') as fh:
        for row in remaining:
            fh.write(json.dumps(row, ensure_ascii=False) + '\n')
    print(f'{promoted} promoted, {len(remaining)} still in review')


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--submit', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--pilots-only', action='store_true')
    ap.add_argument('--limit', type=int)
    ap.add_argument('--status', action='store_true')
    ap.add_argument('--collect', action='store_true')
    ap.add_argument('--recover', action='store_true')
    args = ap.parse_args()

    if args.submit:
        do_submit(args.dry_run, args.pilots_only, args.limit)
    elif args.status:
        do_status()
    elif args.collect:
        do_collect()
    elif args.recover:
        do_recover()
    else:
        ap.error('pick one of --submit, --status, --collect, --recover')


if __name__ == '__main__':
    main()
