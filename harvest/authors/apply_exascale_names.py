#!/usr/bin/env python3
"""Round-11 task 6: fold harvest/authors/exascale-names.json's recovered
full names + 2008-09 affiliations into authors.json (name + latest_
affiliation, original initials-only form kept as a variant) and
enriched.json (name only, so it stays consistent with authors.json --
these 10 have no OpenAlex resolution to disturb). Also seeds links.json
with a permanent_page candidate for the 2 people exascale-names.json
found one for (Robert Harrison's live Stony Brook faculty page; Allan
Snavely's UCSD memorial profile -- flagged there as deceased, so he must
never be sent to a LinkedIn sitting).

    python3 harvest/authors/apply_exascale_names.py            # report
    python3 harvest/authors/apply_exascale_names.py --write    # write
"""
import argparse
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
AUTHORS_PATH = os.path.join(HERE, 'authors.json')
ENRICHED_PATH = os.path.join(HERE, 'enriched.json')
LINKS_PATH = os.path.join(HERE, 'links.json')
NAMES_PATH = os.path.join(HERE, 'exascale-names.json')


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()

    names = json.load(open(NAMES_PATH))['people']
    by_id = {p['person_id']: p for p in names}

    log = []
    authors = json.load(open(AUTHORS_PATH))
    for p in authors:
        n = by_id.get(p['person_id'])
        if not n:
            continue
        if p['name'] == n['original']:
            if n['original'] != n['full_name'] and n['original'] not in p['variants']:
                p['variants'] = sorted(p['variants'] + [n['original']])
            p['name'] = n['full_name']
            p['latest_affiliation'] = n['affiliation_2008_09']
            log.append(f"authors.json: {p['person_id']} -> '{n['full_name']}' "
                      f"({n['affiliation_2008_09']})")

    enriched = json.load(open(ENRICHED_PATH))
    for p in enriched:
        n = by_id.get(p['person_id'])
        if n and p['name'] == n['original']:
            p['name'] = n['full_name']
            log.append(f"enriched.json: {p['person_id']}'s name -> '{n['full_name']}'")

    links = json.load(open(LINKS_PATH))
    for p in links['people']:
        n = by_id.get(p['person_id'])
        if n and n.get('permanent_page'):
            p['name'] = n['full_name']
            p['candidates'] = [{
                'tier': 'permanent-academic' if 'stonybrook' in n['permanent_page']
                       else 'permanent-academic-memorial',
                'source': 'exascale_report_recovery',
                'url': n['permanent_page'],
                'evidence': n['permanent_page_note'],
                'verified': True,
            }]
            p['best_tier'] = p['candidates'][0]['tier']
            log.append(f"links.json: {p['person_id']} -> {n['permanent_page']}")

    for line in log:
        print(line)
    print(f'\n{len(log)} field updates across authors.json/enriched.json/links.json')

    if args.write:
        for path, doc in ((AUTHORS_PATH, authors), (ENRICHED_PATH, enriched), (LINKS_PATH, links)):
            with open(path, 'w') as fh:
                json.dump(doc, fh, indent=1, ensure_ascii=False)
                fh.write('\n')
        print(f'wrote {AUTHORS_PATH}, {ENRICHED_PATH}, {LINKS_PATH}')
    else:
        print('dry run -- nothing written. Pass --write to commit.')


if __name__ == '__main__':
    main()
