#!/usr/bin/env python3
"""One-off: re-judge the pilot-corpus rows that just gained fulltext
evidence from a manual PDF ingestion (harvest/fulltext/ingest_manual_pdfs.py).

The 9 taxonomy pilots are permanently excluded from
curate/classify_citations.py's population (their evidence is a fixed,
hand-reviewed sample) -- but a genuine evidence upgrade (title-only or
S2-context-only -> real full text) is exactly the kind of thing worth
re-judging even there, so this reuses classify_citations.py's exact
system prompt / evidence-packing / validation machinery (same codebook,
same call, same parser) and patches the results directly into
harvest/taxonomy/pilot-classifications.json rather than the normal
per-file staging output.

Live calls, not Batch API -- pilot-scale (a few dozen rows at most) doesn't
need batching, and this is a one-off, not a recurring pipeline stage.

    python3 curate/rejudge_pilots_with_fulltext.py pairs.json [--write]
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import classify_citations as cc  # noqa: E402

PILOT_CLASSIFICATIONS = os.path.join(cc.ROOT, 'harvest', 'taxonomy', 'pilot-classifications.json')


def citing_for(key, slug, citing_cache):
    if key not in citing_cache:
        path = os.path.join(cc.CITATIONS_DIR, key + '.json')
        citing_cache[key] = json.load(open(path)).get('citing') or []
    for c in citing_cache[key]:
        if cc.slug_for(c) == slug:
            return c
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('pairs_json', help='JSON file: [{"key", "slug", "chars"}, ...]')
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()

    pairs = json.load(open(args.pairs_json))
    tax = json.load(open(PILOT_CLASSIFICATIONS))
    rows_by_key = {(r['pilot'], r['slug']): i for i, r in enumerate(tax['rows'])}
    pubs = cc.load_publications()
    codebook = cc.parse_codebook()
    citing_cache = {}

    changes = []
    for pair in pairs:
        key, slug = pair['key'], pair['slug']
        idx = rows_by_key.get((key, slug))
        if idx is None:
            print(f'!! no existing pilot-classifications row for {key}/{slug} -- skipping',
                 file=sys.stderr)
            continue
        old_row = tax['rows'][idx]
        citing = citing_for(key, slug, citing_cache)
        if not citing:
            print(f'!! no citing record for {key}/{slug} -- skipping', file=sys.stderr)
            continue

        pub = pubs.get(key, {})
        fulltext = cc.load_fulltext(key, slug)
        abstract = cc.load_abstracts(key).get(slug, {}).get('abstract')
        tier = cc.evidence_tier(citing, abstract, fulltext)
        request = cc.build_request(key, slug, pub, citing, tier, abstract, fulltext, codebook)

        response = json.loads(cc.call('POST', '/messages', request['params']))
        text = ''.join(b.get('text', '') for b in response.get('content', []))
        try:
            parsed = cc.repair(cc.parse_record(text))
            problems = cc.validate(parsed, codebook)
        except Exception as exc:
            problems = [f'{type(exc).__name__}: {exc}']
            parsed = None

        if problems:
            print(f'!! {key}/{slug}: {problems} -- leaving row unchanged', file=sys.stderr)
            continue

        new_row = dict(old_row)
        new_row.update({
            'function': parsed['function'],
            'centrality': parsed['centrality'],
            'flags': parsed['flags'],
            'secondary': parsed['secondary'],
            'confidence': parsed['confidence'],
            'evidence': tier,
            'anchored': parsed['anchored'],
            'note': parsed['note'],
        })
        changes.append({
            'key': key, 'slug': slug,
            'old_function': old_row['function'], 'new_function': new_row['function'],
            'old_confidence': old_row['confidence'], 'new_confidence': new_row['confidence'],
        })
        print(f"{key}/{slug}: {old_row['function']} ({old_row['confidence']}) -> "
             f"{new_row['function']} ({new_row['confidence']})")
        if args.write:
            tax['rows'][idx] = new_row
        time.sleep(0.5)

    if args.write and changes:
        tmp = PILOT_CLASSIFICATIONS + '.tmp'
        with open(tmp, 'w') as fh:
            json.dump(tax, fh, indent=1, sort_keys=True, ensure_ascii=False)
            fh.write('\n')
        os.replace(tmp, PILOT_CLASSIFICATIONS)
        print(f'\nwrote {PILOT_CLASSIFICATIONS}')
    elif not args.write:
        print('\ndry run -- nothing written. Pass --write to commit.')

    fn_changed = sum(1 for c in changes if c['old_function'] != c['new_function'])
    print(f'\n{len(changes)} rows judged, {fn_changed} function changes')


if __name__ == '__main__':
    main()
