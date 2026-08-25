#!/usr/bin/env python3
"""Merge a REVIEWED wave of reception texts into data/citations/reception.json.

    python3 harvest/summaries/merge_wave.py --wave 1            # diff report
    python3 harvest/summaries/merge_wave.py --wave 1 --write

Reads harvest/summaries/wave<N>_out.json (hand-fixed during review — edit
that file directly). Refuses to touch pilot keys. Never writes summary
prose anywhere; reception.json only.
"""
import argparse
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.abspath(__file__))
PILOTS = {'halide:pldi:2013', 'thies:cc:2002', 'taylor:micro:2002',
          'amarasinghe:ijpp:2005', 'petkov:ipdps:2002', 'thies:toplas:2007',
          'levison:istas:2002', 'netblocks-pldi24',
          'Kjolstad:2017:TTG:3155562.3155683'}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--wave', type=int, required=True)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()

    out = json.load(open(f'{HERE}/wave{args.wave}_out.json'))
    path = f'{ROOT}/data/citations/reception.json'
    rec = json.load(open(path))
    changed = same = 0
    for k, text in out.items():
        assert k not in PILOTS, f'pilot key in wave output: {k}'
        if rec.get(k) == text:
            same += 1
        else:
            changed += 1
            if not args.write:
                print(f'-- {k}: would update ({len(rec.get(k, ""))} -> {len(text)} chars)')
        rec[k] = text
    if args.write:
        json.dump(rec, open(path, 'w'), indent=1, ensure_ascii=False)
        print(f'wrote {path}: {changed} updated, {same} unchanged')
    else:
        print(f'dry run: {changed} would update, {same} unchanged (use --write)')


if __name__ == '__main__':
    main()
