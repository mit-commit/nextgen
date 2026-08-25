#!/usr/bin/env python3
"""Round-8 task 4: re-judge harvest/repos/deephunt_review.json's 12 papers
(13 low-confidence candidate rows) with FULLER evidence -- the repo's
actual README + root file listing, plus the paper's own summary, not just
the heuristic score/description the first pass saw -- via an independent
Batch call with extended thinking enabled (the "high reasoning effort"
the queue asked for; the Messages API's lever for that is a thinking
budget, not a separate effort field).

Compares the new verdict's `own_group` boolean against the original row's:
  - AGREE -> finalize with the new (richer-evidence) verdict. An
    own_group=true agreement merges into verified.json via the same
    canonical/rename-safe dedupe curate/fold_own_inventory.py uses; an
    own_group=false agreement just confirms the original rejection was
    right (removed from deephunt_review.json, nothing to merge).
  - DISAGREE -> NOT auto-applied either direction. A single independent
    re-judgment flipping the call is a genuine-ambiguity signal, not a
    verdict -- logged to harvest/repos/deephunt_review_resolved.json with
    both verdicts and left in deephunt_review.json for a human, per the
    task's "demote disagreements to rejected with the reason logged"
    (the reason is the disagreement itself; nothing new is asserted).

    python3 curate/deephunt_confidence_pass.py --submit --dry-run
    python3 curate/deephunt_confidence_pass.py --submit
    python3 curate/deephunt_confidence_pass.py --status
    python3 curate/deephunt_confidence_pass.py --collect
"""
import argparse
import base64
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'harvest', 'repos'))
import verify_repos as vr  # noqa: E402
from search_github import Client  # noqa: E402
from dedupe_verified_repos import dedupe_paper  # noqa: E402

REVIEW_PATH = os.path.join(ROOT, 'harvest', 'repos', 'deephunt_review.json')
VERIFIED_PATH = os.path.join(ROOT, 'harvest', 'repos', 'verified.json')
RESOLVED_PATH = os.path.join(ROOT, 'harvest', 'repos', 'deephunt_review_resolved.json')
PUBLICATIONS = os.path.join(ROOT, 'data', 'publications.json')
EVIDENCE_CACHE = os.path.join(ROOT, 'harvest', 'repos', '_confidence_evidence.json')

STATE_PATH = os.path.join(ROOT, 'harvest', 'repos', '_confidence_batches.json')
REQUESTS_DUMP = os.path.join(ROOT, 'harvest', 'repos', '_confidence_requests_dry_run.json')

MODEL = vr.MODEL
THINKING_BUDGET = 3000
MAX_TOKENS = 4500

SYSTEM_PROMPT = """You are RE-JUDGING repo candidates that a prior pass already looked at and
parked at LOW confidence -- your job is to look harder with fuller evidence
than that pass had (the candidate repo's actual README and root file
listing, plus the paper's own abstract/summary, not just a description
snippet and a heuristic score) and give an independent, careful verdict.
Think it through before answering. You cannot fetch anything further;
judge only from what's given.

Return ONE JSON object and nothing else. No prose, no markdown fence.

  {"repos": [ {"url", "role", "own_group", "confidence", "evidence"}, ... ]}

Return exactly one entry per candidate URL given, even if your verdict
matches the original -- do not omit any.

Fields per repo:
  url          the URL as given (do not rewrite it)
  role         implementation | artifact | benchmark | third_party
  own_group    true iff the repo is plausibly this paper's own author(s)
               or their lab's work -- judge this fresh from the README/
               file listing/paper summary given, not from the original
               pass's evidence string alone
  confidence   high | medium | low
  evidence     one or two sentences: what in the README/file listing/
               paper summary specifically justified this call -- name
               the actual signal (a matching function/class name in the
               listing, a README sentence, an author/institution match),
               not just "seems related"

A repo whose README/files show it is really just a fork, mirror, or an
unrelated user's project with a name/topic coincidence should get
own_group=false regardless of what the original heuristic score
suggested -- you have more evidence than that pass did, use it."""


def fullname_of(url):
    if 'github.com/' not in url:
        return None
    return url.split('github.com/')[-1].strip('/')


def fetch_evidence(client, fullname):
    readme_text = ''
    data = client.get('/repos/%s/readme' % fullname)
    if data and data.get('content'):
        try:
            readme_text = base64.b64decode(data['content']).decode('utf-8', 'replace')[:3000]
        except Exception:
            readme_text = ''
    listing = client.get('/repos/%s/contents/' % fullname)
    names = [item.get('name') for item in (listing or []) if isinstance(item, dict)][:60]
    repo_info = client.get('/repos/%s' % fullname)
    return {
        'readme': readme_text,
        'file_listing': names,
        'description': (repo_info or {}).get('description'),
        'stars': (repo_info or {}).get('stargazers_count'),
    }


def gather_all_evidence(review):
    client = Client(verbose=False)
    cache = json.load(open(EVIDENCE_CACHE)) if os.path.exists(EVIDENCE_CACHE) else {}
    for key, rows in review.items():
        for row in rows:
            fn = fullname_of(row['url'])
            if not fn or fn in cache:
                continue
            cache[fn] = fetch_evidence(client, fn)
    with open(EVIDENCE_CACHE + '.tmp', 'w') as fh:
        json.dump(cache, fh, indent=1, ensure_ascii=False)
    os.replace(EVIDENCE_CACHE + '.tmp', EVIDENCE_CACHE)
    return cache


def build_request(key, rows, pub, evidence):
    parts = [
        f"PAPER: {pub.get('title') or key!r}",
        f"  authors: {pub.get('author0') or '(unknown)'}",
        f"  year: {pub.get('year')}   venue: {pub.get('venue') or '(unknown)'}",
    ]
    if pub.get('summary'):
        parts.append(f"  summary: {pub['summary'][:1200]!r}")
    parts.append('\nCANDIDATES (original low-confidence pass + fuller evidence):')
    for r in rows:
        fn = fullname_of(r['url'])
        ev = evidence.get(fn, {}) if fn else {}
        parts.append(f"\n- {r['url']}")
        parts.append(f"    original verdict: own_group={r.get('own_group')}, role={r.get('role')}, "
                     f"confidence={r.get('confidence')}")
        parts.append(f"    original evidence: {r.get('evidence')}")
        if ev.get('description'):
            parts.append(f"    repo description: {ev['description']!r}")
        if ev.get('stars') is not None:
            parts.append(f"    stars: {ev['stars']}")
        if ev.get('file_listing'):
            parts.append(f"    root file listing: {ev['file_listing']}")
        if ev.get('readme'):
            parts.append(f"    README (first 3000 chars):\n{ev['readme']!r}")
        else:
            parts.append("    README: (none found)")
    content = '\n'.join(parts)
    custom_id = hashlib.sha1(key.encode()).hexdigest()[:40]
    return {
        'custom_id': custom_id,
        'params': {
            'model': MODEL,
            'max_tokens': MAX_TOKENS,
            'thinking': {'type': 'enabled', 'budget_tokens': THINKING_BUDGET},
            'system': SYSTEM_PROMPT,
            'messages': [{'role': 'user', 'content': content}],
        },
    }


def load_state():
    return json.load(open(STATE_PATH)) if os.path.exists(STATE_PATH) else {'batches': [], 'items': {}}


def do_submit(dry_run, limit):
    review = json.load(open(REVIEW_PATH))
    pubs = {p['bibtexKey']: p for p in json.load(open(PUBLICATIONS))}
    evidence = gather_all_evidence(review)

    keys = sorted(review)
    if limit:
        keys = keys[:limit]
    requests_ = [build_request(k, review[k], pubs.get(k, {}), evidence) for k in keys]
    lookup = {r['custom_id']: k for r, k in zip(requests_, keys)}

    if dry_run:
        with open(REQUESTS_DUMP, 'w') as fh:
            json.dump(requests_, fh, indent=1, ensure_ascii=False)
        chars = sum(len(r['params']['system']) + len(r['params']['messages'][0]['content'])
                    for r in requests_)
        avg_tokens = (chars // len(requests_)) // 4
        total_in = avg_tokens * len(requests_)
        total_out = len(requests_) * (THINKING_BUDGET + 300)
        cost = total_in / 1e6 * vr.BATCH_INPUT_PER_MTOK + total_out / 1e6 * vr.BATCH_OUTPUT_PER_MTOK
        print(f'{len(requests_)} requests, ~{avg_tokens} input tokens/request')
        print(f'COST ESTIMATE: ~${cost:,.2f} (batch pricing, thinking budget {THINKING_BUDGET} tok/req)')
        print(f'wrote {REQUESTS_DUMP}; sent nothing')
        return

    state = load_state()
    state.setdefault('items', {}).update(lookup)
    result = json.loads(vr.call('POST', '/messages/batches', {'requests': requests_}))
    state.setdefault('batches', []).append({'id': result['id'], 'n': len(requests_),
                                            'created': result.get('created_at'), 'collected': False})
    json.dump(state, open(STATE_PATH, 'w'), indent=1)
    print(f'submitted {result["id"]}  {len(requests_)} requests')


def do_status():
    state = load_state()
    for batch in state.get('batches', []):
        info = json.loads(vr.call('GET', f'/messages/batches/{batch["id"]}'))
        counts = info.get('request_counts', {})
        print(f'{batch["id"]}  {info.get("processing_status"):12s} '
              f'{json.dumps(counts)}  collected={batch["collected"]}')


def do_collect():
    state = load_state()
    items = state.get('items', {})
    review = json.load(open(REVIEW_PATH))
    verified = json.load(open(VERIFIED_PATH))
    resolved = json.load(open(RESOLVED_PATH)) if os.path.exists(RESOLVED_PATH) else {}

    token = os.environ.get('GITHUB_TOKEN', '').strip()
    cache = {}
    log = []

    agreed_true = agreed_false = disagreed = failed = 0
    remaining_review = {}

    for batch in state.get('batches', []):
        if batch['collected']:
            continue
        info = json.loads(vr.call('GET', f'/messages/batches/{batch["id"]}'))
        if info.get('processing_status') != 'ended':
            print(f'{batch["id"]}: {info.get("processing_status")}, skipping')
            continue
        body = vr.call('GET', info['results_url'])
        for line in body.splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            custom_id = row.get('custom_id')
            key = items.get(custom_id, custom_id)
            result = row.get('result') or {}
            if result.get('type') != 'succeeded':
                failed += 1
                remaining_review[key] = review.get(key, [])
                continue
            message = result.get('message') or {}
            text = ''.join(b.get('text', '') for b in message.get('content', [])
                           if b.get('type') == 'text')
            try:
                parsed = vr.parse_record(text)
                problems = vr.validate(parsed)
            except Exception as exc:
                problems = [f'{type(exc).__name__}: {exc}']
                parsed = None
            if problems:
                failed += 1
                remaining_review[key] = review.get(key, [])
                continue

            new_by_url = {r['url']: r for r in parsed['repos']}
            key_resolved = []
            key_still_review = []
            for orig in review.get(key, []):
                new = new_by_url.get(orig['url'])
                if new is None:
                    key_still_review.append(orig)
                    continue
                if bool(new['own_group']) == bool(orig['own_group']):
                    key_resolved.append({'url': orig['url'], 'verdict': 'agreed',
                                         'own_group': new['own_group'], 'role': new['role'],
                                         'confidence': new['confidence'], 'evidence': new['evidence']})
                    if new['own_group']:
                        agreed_true += 1
                    else:
                        agreed_false += 1
                else:
                    key_resolved.append({
                        'url': orig['url'], 'verdict': 'disagreed',
                        'original': {'own_group': orig['own_group'], 'evidence': orig['evidence']},
                        'reconsidered': {'own_group': new['own_group'], 'confidence': new['confidence'],
                                        'evidence': new['evidence']},
                    })
                    key_still_review.append(orig)
                    disagreed += 1
            if key_resolved:
                resolved[key] = resolved.get(key, []) + key_resolved
            if key_still_review:
                remaining_review[key] = key_still_review

            # fold agreed own_group=true rows into verified.json
            agreed_own_rows = [dict(orig, **{'confidence': r['confidence'], 'evidence': r['evidence'],
                                             'role': r['role']})
                              for orig, r in ((o, new_by_url.get(o['url'])) for o in review.get(key, []))
                              if r and bool(r['own_group']) == bool(orig['own_group']) and r['own_group']]
            if agreed_own_rows:
                combined = verified.get(key, []) + agreed_own_rows
                deduped = dedupe_paper(key, combined, token, cache, log)
                verified[key] = deduped

        batch['collected'] = True

    for line in log:
        print(' ', line)

    json.dump(state, open(STATE_PATH, 'w'), indent=1)
    with open(VERIFIED_PATH, 'w') as fh:
        json.dump(verified, fh, indent=1, sort_keys=True, ensure_ascii=False)
        fh.write('\n')
    with open(RESOLVED_PATH, 'w') as fh:
        json.dump(resolved, fh, indent=1, sort_keys=True, ensure_ascii=False)
        fh.write('\n')
    with open(REVIEW_PATH, 'w') as fh:
        json.dump(remaining_review, fh, indent=1, sort_keys=True, ensure_ascii=False)
        fh.write('\n')

    print(f'\nagreed own_group=true (merged into verified.json): {agreed_true}')
    print(f'agreed own_group=false (confirmed rejection): {agreed_false}')
    print(f'disagreed (left in deephunt_review.json for a human, logged in '
         f'deephunt_review_resolved.json): {disagreed}')
    print(f'failed/unparsed (left in deephunt_review.json): {failed}')
    print(f'deephunt_review.json now has {len(remaining_review)} keys')


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--submit', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--limit', type=int)
    ap.add_argument('--status', action='store_true')
    ap.add_argument('--collect', action='store_true')
    args = ap.parse_args()

    if args.submit:
        do_submit(args.dry_run, args.limit)
    elif args.status:
        do_status()
    elif args.collect:
        do_collect()
    else:
        ap.error('pick one of --submit, --status, --collect')


if __name__ == '__main__':
    main()
