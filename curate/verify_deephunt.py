#!/usr/bin/env python3
"""Batch curation half of `own-repo-deep-hunt` (round-7 queue task 1): a
model pass over harvest/repos/deephunt.json's mechanical candidates --
author's-own-GitHub-repo matches plus lingering medium-confidence rows the
earlier repos-search pass never got confirmed -- for every paper that still
has no own_group repo. Same pattern as curate/verify_repos.py (its
call/parse_record/validate are reused directly), tuned for this evidence
shape: candidates are scored by title-keyword overlap + date proximity to
an author's OWN GitHub account, not a generic name-guess search.

Appends accepted (high/medium confidence) rows into harvest/repos/
own-inventory.json -- the staging file a concurrent session's phase-A/B
own-repo hunt already established for exactly this purpose (a
verified.json-shaped row set, kept out of verified.json itself so two
sessions doing overlapping own-repo hunts in the same round don't race on
the same file). Appends to a paper's existing list if it already has
rows, never overwrites. Low-confidence rows go to
harvest/repos/deephunt_review.json. Folding own-inventory.json into
verified.json proper is a separate, explicit step
(curate/fold_own_inventory.py) run once after all concurrent hunts land.

    python3 curate/verify_deephunt.py --submit --dry-run
    python3 curate/verify_deephunt.py --submit
    python3 curate/verify_deephunt.py --status
    python3 curate/verify_deephunt.py --collect
    python3 curate/verify_deephunt.py --recover
"""
import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import verify_repos as vr  # noqa: E402 -- reuse call/parse_record/validate/write_result

ROOT = os.path.dirname(HERE)
DEEPHUNT_PATH = os.path.join(ROOT, 'harvest', 'repos', 'deephunt.json')
PUBLICATIONS = os.path.join(ROOT, 'data', 'publications.json')

OUT_DIR = os.path.join(ROOT, 'harvest', 'repos')
OWN_INVENTORY_PATH = os.path.join(OUT_DIR, 'own-inventory.json')
REVIEW_PATH = os.path.join(OUT_DIR, 'deephunt_review.json')
STATE_PATH = os.path.join(OUT_DIR, '_deephunt_batches.json')
REQUESTS_DUMP = os.path.join(OUT_DIR, '_deephunt_requests_dry_run.json')
NEEDS_REVIEW_PATH = os.path.join(OUT_DIR, '_deephunt_needs_review.jsonl')

PER_BATCH = vr.PER_BATCH
EST_OUTPUT_TOKENS = vr.EST_OUTPUT_TOKENS
BATCH_INPUT_PER_MTOK = vr.BATCH_INPUT_PER_MTOK
BATCH_OUTPUT_PER_MTOK = vr.BATCH_OUTPUT_PER_MTOK

SYSTEM_PROMPT = """You are verifying DEEP-HUNT repo candidates for ONE academic paper (usually an
MEng/PhD thesis or technical report) that a prior, shallower search found NO
confirmed own-group repository for. You are given the paper's metadata and
every candidate repository found this pass -- most from listing an AUTHOR'S
OWN GitHub account in full and scoring their repos by title-keyword overlap
and creation-date proximity to the paper, a few carried over from an earlier
generic name-guess search that a prior model pass saw and did NOT confirm
(marked "source: prior-search-medium" -- re-weigh these on their own merits,
don't assume the earlier rejection was right or wrong). You cannot fetch
anything; judge only from what's given.

Return ONE JSON object and nothing else. No prose, no markdown fence.

  {"repos": [ {"url", "role", "own_group", "confidence", "evidence"}, ... ]}

Include ONE entry per URL you judge worth keeping -- omit a candidate
entirely if the only support for it is a keyword or date coincidence, with
nothing else tying it to this specific paper (no title/topic match beyond a
generic word, no README/description signal, no name match strong enough to
be the paper's actual author). A repo from the author's own GitHub account
is a much stronger signal than an org repo matched purely by keyword --
weigh it accordingly, but still require the repo's actual content
(name/description/topics) to plausibly be THIS paper's project, not just
something else the same person happened to build.

Fields per kept repo:
  url          the URL as given (do not rewrite it)
  role         implementation | artifact | benchmark | third_party
               - implementation: this repo IS the system/tool the paper
                 presents (most likely for a thesis's own deep-hunt hit)
               - artifact: a companion dataset/evaluation-artifact repo
               - benchmark: a benchmark suite/workload the paper uses, not
                 something the paper's own group built
               - third_party: any other dependency/prior-work repo, not the
                 paper's own output
  own_group    true iff the repo is plausibly this paper's own author(s) or
                 their lab's work
  confidence   high | medium | low -- low means genuinely ambiguous (goes to
               a human review queue, not the confident list)
  evidence     one short sentence: what specifically justified this call

CANONICAL-OVER-FORK RULE: when two or more candidates are clearly the same
underlying project, keep ONLY the canonical one and drop the fork(s).

A thesis with a real but unglamorous or oddly-named repo ("cs6.s081-final",
"6.911-project", a personal account's only 2024 repo) is exactly what this
pass is for -- don't require a polished, well-named, popular repo. But do
not guess: if nothing in the given evidence actually ties a candidate to
THIS paper's specific subject, leave it out rather than include it at low
confidence to be safe."""


def build_request(key, candidates, pub):
    parts = [
        f"PAPER: {pub.get('title') or key!r}",
        f"  authors: {pub.get('author0') or '(unknown)'}",
        f"  year: {pub.get('year')}   venue: {pub.get('venue') or '(unknown)'}",
        '\nDEEP-HUNT CANDIDATES:',
    ]
    for c in candidates:
        parts.append(f"  - {c.get('repo') or c.get('url')}  "
                     f"(score={c.get('score')}, confidence={c.get('confidence')}, "
                     f"stars={c.get('stars')}, created={c.get('created_at')}, "
                     f"source={c.get('source')})")
        if c.get('description'):
            parts.append(f"    description: {c['description'][:200]!r}")
        if c.get('evidence'):
            parts.append(f"    evidence: {c['evidence']}")
    content = '\n'.join(parts)
    custom_id = hashlib.sha1(key.encode()).hexdigest()[:40]
    return {
        'custom_id': custom_id,
        'params': {
            'model': vr.MODEL,
            'max_tokens': vr.MAX_TOKENS,
            'system': SYSTEM_PROMPT,
            'messages': [{'role': 'user', 'content': content}],
        },
    }


def load_state():
    return json.load(open(STATE_PATH)) if os.path.exists(STATE_PATH) else {'batches': [], 'items': {}}


def merge_write(key, high_med, low, verified, review):
    """Append (not overwrite) into a paper's existing own-inventory.json
    list -- a concurrent session may already have confirmed a row for
    this key."""
    if high_med:
        existing = verified.get(key, [])
        seen_urls = {r.get('url') for r in existing}
        verified[key] = existing + [r for r in high_med if r.get('url') not in seen_urls]
    if low:
        review[key] = review.get(key, []) + low


def do_submit(dry_run, limit):
    deephunt = json.load(open(DEEPHUNT_PATH)) if os.path.exists(DEEPHUNT_PATH) else {}
    pubs = {p['bibtexKey']: p for p in json.load(open(PUBLICATIONS))}
    state = load_state()
    done = set(state.get('items', {}).values())

    keys = sorted(k for k in deephunt if k not in done)
    if limit:
        keys = keys[:limit]
    if not keys:
        return print('nothing to submit')

    requests_ = [build_request(k, deephunt[k], pubs.get(k, {})) for k in keys]
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
        print(f'{len(requests_)} requests, ~{avg_tokens} input tokens/request')
        print(f'COST ESTIMATE: ~${cost:,.2f} (batch pricing)')
        print(f'wrote {REQUESTS_DUMP}; sent nothing')
        return

    state.setdefault('items', {}).update(lookup)
    for start in range(0, len(requests_), PER_BATCH):
        chunk = requests_[start:start + PER_BATCH]
        result = json.loads(vr.call('POST', '/messages/batches', {'requests': chunk}))
        state.setdefault('batches', []).append({'id': result['id'], 'n': len(chunk),
                                                'created': result.get('created_at'), 'collected': False})
        json.dump(state, open(STATE_PATH, 'w'), indent=1)
        print(f'  submitted {result["id"]}  {len(chunk)} requests')
    print(f'\n{len(state["batches"])} batches recorded in {STATE_PATH}')


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
    verified = json.load(open(OWN_INVENTORY_PATH)) if os.path.exists(OWN_INVENTORY_PATH) else {}
    review = json.load(open(REVIEW_PATH)) if os.path.exists(REVIEW_PATH) else {}
    needs_review = []
    if os.path.exists(NEEDS_REVIEW_PATH):
        with open(NEEDS_REVIEW_PATH) as fh:
            needs_review = [json.loads(l) for l in fh if l.strip()]

    written = failed = 0
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
                needs_review.append({'key': key, 'problems': [f'batch {result.get("type")}'],
                                     'raw': json.dumps(result)[:2000]})
                failed += 1
                continue
            message = result.get('message') or {}
            text = ''.join(b.get('text', '') for b in message.get('content', []))
            try:
                parsed = vr.parse_record(text)
                problems = vr.validate(parsed)
            except Exception as exc:
                parsed, problems = None, [f'{type(exc).__name__}: {exc}']
            if problems:
                needs_review.append({'key': key, 'problems': problems, 'raw': (text or '')[:4000]})
                failed += 1
                continue
            high_med = [r for r in parsed['repos'] if r['confidence'] in ('high', 'medium')]
            low = [r for r in parsed['repos'] if r['confidence'] == 'low']
            merge_write(key, high_med, low, verified, review)
            written += 1
        batch['collected'] = True
        json.dump(state, open(STATE_PATH, 'w'), indent=1)
        print(f'{batch["id"]}: collected')

    for path, payload in ((OWN_INVENTORY_PATH, verified), (REVIEW_PATH, review)):
        with open(path, 'w') as fh:
            json.dump(payload, fh, indent=1, sort_keys=True, ensure_ascii=False)
            fh.write('\n')
    with open(NEEDS_REVIEW_PATH, 'w') as fh:
        for row in needs_review:
            fh.write(json.dumps(row, ensure_ascii=False) + '\n')
    print(f'\n{written} papers written, {failed} sent to {NEEDS_REVIEW_PATH}')


def do_recover():
    if not os.path.exists(NEEDS_REVIEW_PATH):
        return print('no review file')
    with open(NEEDS_REVIEW_PATH) as fh:
        rows = [json.loads(l) for l in fh if l.strip()]

    verified = json.load(open(OWN_INVENTORY_PATH)) if os.path.exists(OWN_INVENTORY_PATH) else {}
    review = json.load(open(REVIEW_PATH)) if os.path.exists(REVIEW_PATH) else {}
    remaining = []
    promoted = 0
    for row in rows:
        key = row['key']
        try:
            parsed = vr.parse_record(row.get('raw'))
            problems = vr.validate(parsed)
        except Exception as exc:
            problems = [f'{type(exc).__name__}: {exc}']
        if problems:
            row['problems'] = problems
            remaining.append(row)
            continue
        high_med = [r for r in parsed['repos'] if r['confidence'] in ('high', 'medium')]
        low = [r for r in parsed['repos'] if r['confidence'] == 'low']
        merge_write(key, high_med, low, verified, review)
        promoted += 1

    for path, payload in ((OWN_INVENTORY_PATH, verified), (REVIEW_PATH, review)):
        with open(path, 'w') as fh:
            json.dump(payload, fh, indent=1, sort_keys=True, ensure_ascii=False)
            fh.write('\n')
    with open(NEEDS_REVIEW_PATH, 'w') as fh:
        for row in remaining:
            fh.write(json.dumps(row, ensure_ascii=False) + '\n')
    print(f'{promoted} promoted, {len(remaining)} still in review')


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--submit', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--limit', type=int)
    ap.add_argument('--status', action='store_true')
    ap.add_argument('--collect', action='store_true')
    ap.add_argument('--recover', action='store_true')
    args = ap.parse_args()

    if args.submit:
        do_submit(args.dry_run, args.limit)
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
