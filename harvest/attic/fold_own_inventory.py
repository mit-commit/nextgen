#!/usr/bin/env python3
"""Round-8 task 1: fold harvest/repos/own-inventory.json's confirmed rows
into harvest/repos/verified.json -- the deferred merge both deep-hunt
sessions (own-repo-deep-hunt phase A/B + the concurrent verified-identity
hunt) left behind, per queue round 8.

Reuses curate/dedupe_verified_repos.py's identity resolution and
dedupe_paper() verbatim: each own-inventory row is combined with that
paper's existing verified.json rows and deduped by GitHub numeric repo id
(canonical-over-fork -- same role-priority + confidence tie-break, same
evidence-union-on-merge behavior already proven on verified.json's own
internal duplicates).

own-inventory.json rows sometimes carry a bare "owner/repo" url (no
scheme) -- see curate/verify_deephunt.py's b6... bug note; normalized to a
real https://github.com/... URL before dedup so identity resolution and
downstream consumers (build_repo_data.py) see a real link either way.

'website' role rows are NOT folded -- build_repo_data.py already excludes
them from the impact tier by design (project pages are not impact), and
that has been true since before this fold; they stay in own-inventory.json
as the only rows left there.

    python3 curate/fold_own_inventory.py            # report only
    python3 curate/fold_own_inventory.py --write    # write both files
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dedupe_verified_repos import dedupe_paper  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERIFIED_PATH = os.path.join(ROOT, 'harvest', 'repos', 'verified.json')
INVENTORY_PATH = os.path.join(ROOT, 'harvest', 'repos', 'own-inventory.json')


def normalize_url(url):
    return url if '://' in url else 'https://github.com/' + url.strip('/')


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()

    token = os.environ.get('GITHUB_TOKEN', '').strip()
    if not token:
        sys.exit('GITHUB_TOKEN not set')

    verified = json.load(open(VERIFIED_PATH))
    inventory = json.load(open(INVENTORY_PATH))
    cache = {}
    log = []

    new_papers = 0
    folded_rows = 0
    merged_rows = 0
    kept_inventory = {}

    for key, rows in sorted(inventory.items()):
        website_rows = [r for r in rows if r.get('role') == 'website']
        fold_rows = [dict(r, url=normalize_url(r['url']))
                    for r in rows if r.get('role') != 'website']
        if website_rows:
            kept_inventory[key] = website_rows
        if not fold_rows:
            continue

        before = verified.get(key, [])
        had_own_before = any(r.get('own_group') for r in before)
        combined = before + fold_rows
        deduped = dedupe_paper(key, combined, token, cache, log)
        merged_rows += len(combined) - len(deduped)
        folded_rows += len(fold_rows) - (len(combined) - len(deduped))
        verified[key] = deduped
        if not had_own_before and any(r.get('own_group') for r in deduped):
            new_papers += 1

    for line in log:
        print(line)
    print(f'\n{folded_rows} own-inventory rows folded in as new rows, '
         f'{merged_rows} merged into an existing verified.json row, '
         f'{new_papers} papers gained their first own_group repo, '
         f'{len(kept_inventory)} keys left in own-inventory.json (website rows only)')

    if args.write:
        with open(VERIFIED_PATH, 'w') as fh:
            json.dump(verified, fh, indent=1, sort_keys=True, ensure_ascii=False)
            fh.write('\n')
        with open(INVENTORY_PATH, 'w') as fh:
            json.dump(kept_inventory, fh, indent=1, sort_keys=True, ensure_ascii=False)
            fh.write('\n')
        print(f'wrote {VERIFIED_PATH} + {INVENTORY_PATH}')
    else:
        print('\ndry run -- nothing written. Pass --write to commit.')


if __name__ == '__main__':
    main()
