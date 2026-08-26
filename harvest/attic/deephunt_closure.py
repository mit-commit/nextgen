#!/usr/bin/env python3
"""Round-9 task 4: close out the deephunt_review lane.

curate/deephunt_confidence_pass.py's independent re-judgment DISAGREED
with the original verdict on 4 rows and correctly declined to auto-apply
either side (logged both to harvest/repos/deephunt_review_resolved.json,
left pending in harvest/repos/deephunt_review.json). The coordinator's
round-9 ruling settles all 4: "own repo" means THIS paper's own artifact
-- a same-lab/group repo that isn't the paper's own artifact is not
own_group for that paper, so all 4 are rejected as own_group=false
(3 already had that verdict originally and were only reopened because the
re-judgment argued "same lab" without re-establishing "this paper's
artifact"; the 4th, ray:phd-thesis:2023, flips the other way -- from the
original's borrowed "companion tool, same group" reasoning to the
reconsidered pass's is a genuinely different research group's project).

own_group=false means nothing merges into verified.json (matching
deephunt_confidence_pass.py's own "agreed own_group=false" convention) --
these rows are simply dropped from deephunt_review.json, which is now
empty, closing the lane.

    python3 curate/deephunt_closure.py --write
"""
import argparse
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REVIEW_PATH = os.path.join(ROOT, 'harvest', 'repos', 'deephunt_review.json')
RESOLVED_PATH = os.path.join(ROOT, 'harvest', 'repos', 'deephunt_review_resolved.json')

RULING = ('coordinator ruling 2026-08-25: "own repo" means THIS paper\'s own '
         'artifact -- a same-lab/group repo that isn\'t the paper\'s own '
         'artifact is not own_group for that paper, even when the '
         'reconsidered pass correctly identified a shared author/lab.')


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()

    review = json.load(open(REVIEW_PATH))
    resolved = json.load(open(RESOLVED_PATH))

    assert set(review) == {'akkas2019', 'gottschlich:mapl:2018',
                           'ishibe:xsig:2026', 'ray:phd-thesis:2023'}, \
        f'expected exactly the 4 disagreement rows, got {sorted(review)}'

    for key, rows in review.items():
        assert len(rows) == 1
        row = rows[0]
        entry = resolved[key][0]
        assert entry['verdict'] == 'disagreed'
        entry['final'] = {
            'own_group': False,
            'role': 'third_party',
            'confidence': 'low',
            'evidence': f'{row["evidence"]} ({RULING})',
        }
        print(f'{key}: closed -> own_group=false, dropped from review '
             f'(original own_group was {row["own_group"]})')

    if args.write:
        with open(RESOLVED_PATH, 'w') as fh:
            json.dump(resolved, fh, indent=1, sort_keys=True, ensure_ascii=False)
            fh.write('\n')
        with open(REVIEW_PATH, 'w') as fh:
            json.dump({}, fh, indent=1, sort_keys=True, ensure_ascii=False)
            fh.write('\n')
        print(f'\nwrote {RESOLVED_PATH} + emptied {REVIEW_PATH}')
    else:
        print('\ndry run -- nothing written. Pass --write to commit.')


if __name__ == '__main__':
    main()
