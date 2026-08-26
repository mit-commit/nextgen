#!/usr/bin/env python3
"""Join the LinkedIn-sitting results into links.json's candidates and emit
data/author-links.json — the site's author-name link map (round-11 task 4).

Ruling (2026-08-26): LinkedIn default; a permanent academic page replaces
it; else best active site; else email. Identity POSITIVELY verified —
unverified candidates are never used, unconfirmables go to him (they stay
unlinked here, never guessed).

    python3 harvest/authors/join_links.py [--write]

Output: { schema, generated, links: { "<folded name>": url } } with one
entry per confirmed person, keyed by every name variant (folded), for the
publications page to link author names.
"""
import argparse
import json
import os
import re
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

# Human rulings 2026-08-26 (tasks/QUEUE.md, sitting-2 close-out):
# to_him rows resolved by him after the sitting.
RULED = {
    'richard p. sollee iii': 'https://www.linkedin.com/in/solleer',
    'yee lok wong': 'https://www.linkedin.com/in/yee-lok-wong',
}


def fold(s):
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode()
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z. ]', ' ', s.lower())).strip()


def choose(person, li_row):
    """The ruling's precedence, verified candidates only."""
    cands = [c for c in person.get('candidates', []) if c.get('verified')]

    def first(tier):
        for c in cands:
            if c.get('tier') == tier:
                return c['url']
        return None

    academic = first('permanent-academic')
    if academic:
        return academic, 'permanent-academic'
    if li_row:
        verdict = li_row.get('verdict', '')
        if verdict.startswith('confirmed') and li_row.get('linkedin'):
            return li_row['linkedin'], 'linkedin-confirmed'
        if verdict == 'to_him':
            ruled = RULED.get(fold(li_row.get('name')))
            if ruled:
                return ruled, 'linkedin-ruled'
    incidental = first('linkedin_incidental')  # verified via the person's
    if incidental:                             # own site/profile linkage
        return incidental, 'linkedin-incidental'
    pro = first('professional')
    if pro:
        return pro, 'professional'
    personal = first('personal')
    if personal:
        return personal, 'personal'
    email = first('email')
    if email:
        return ('mailto:' + email if '@' in email and not email.startswith('mailto:')
                else email), 'email'
    return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--generated', default='2026-08-26')
    args = ap.parse_args()

    links = json.load(open(f'{HERE}/links.json'))
    authors = {a['person_id']: a for a in json.load(open(f'{HERE}/authors.json'))}
    li = json.load(open(f'{HERE}/linkedin-results.json'))
    li_by_name = {fold(r['name']): r for r in li['rows']}

    out, sources = {}, {}
    linked = 0
    for p in links['people']:
        li_row = li_by_name.get(fold(p['name']))
        url, src = choose(p, li_row)
        if not url:
            continue
        linked += 1
        sources[src] = sources.get(src, 0) + 1
        names = [p['name']] + (authors.get(p['person_id'], {}).get('variants') or [])
        for nm in names:
            f = fold(nm)
            if f:
                out[f] = url

    print(f"{linked} of {len(links['people'])} people linked; "
          f"{len(out)} name keys; by source: {sources}")
    if not args.write:
        print('report only (use --write)')
        return
    doc = {'schema': 1, 'generated': args.generated,
           'ruling': 'LinkedIn default; permanent academic page replaces it; '
                     'else best active site; else email. Verified only.',
           'links': out}
    with open(f'{ROOT}/data/author-links.json', 'w') as fh:
        json.dump(doc, fh, indent=1, ensure_ascii=False)
        fh.write('\n')
    print('wrote data/author-links.json '
          f"({os.path.getsize(f'{ROOT}/data/author-links.json'):,} bytes)")


if __name__ == '__main__':
    main()
