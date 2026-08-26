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
    """Round-12 precedence over links.json candidates (overrides already
    materialized there): source:human above everything; publish:false is
    never rendered; never_primary is never the chosen link; otherwise the
    ruling's order — permanent academic page, confirmed LinkedIn, best
    active site, email. Verified identities only."""
    cands = [c for c in person.get('candidates', [])
             if c.get('publish') is not False and not c.get('never_primary')
             and (c.get('verified') or c.get('source') == 'human')]

    def first(pred, label):
        for c in cands:
            if pred(c):
                return c['url'], label
        return None

    human = first(lambda c: c.get('source') == 'human', 'human')
    if human:
        return human
    academic = first(lambda c: c.get('tier') == 'permanent-academic', 'permanent-academic')
    if academic:
        return academic
    if li_row:
        verdict = li_row.get('verdict', '')
        if verdict.startswith('confirmed') and li_row.get('linkedin'):
            return li_row['linkedin'], 'linkedin-confirmed'
        if verdict == 'to_him':
            ruled = RULED.get(fold(li_row.get('name')))
            if ruled:
                return ruled, 'linkedin-ruled'
    for tier, label in (('linkedin_incidental', 'linkedin-incidental'),
                        ('professional', 'professional'),
                        ('personal', 'personal')):
        hit = first(lambda c, t=tier: c.get('tier') == t, label)
        if hit:
            return hit
    email = first(lambda c: c.get('tier') == 'email', 'email')
    if email:
        url, label = email
        return ('mailto:' + url if '@' in url and not url.startswith('mailto:')
                else url), label
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
    # the professional-tier sittings file merges in (1st-degree = identity
    # evidence per the ruling; its confirmed rows carry linkedin urls)
    lp = json.load(open(f'{HERE}/linkedin-results-professional.json'))
    for r in lp.get('rows', []):
        li_by_name.setdefault(fold(r['name']), r)

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
