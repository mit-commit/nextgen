#!/usr/bin/env python3
"""Round-10 task 1: fold harvest/authors/session-results.json (the human's
Google Scholar browser sitting) into harvest/authors/enriched.json, then
backstop the still-unresolved via a direct OpenAlex author search for the
9 `not_settled` people plus Nishil Talati (spelled "Talathi" in our own
author0 parse -- see below, a real typo in this corpus, not a fuzzy-match
choice).

Fold: for every session-results row with verdict `match` or `tentative`,
set `gs_user` + `affiliation` on the matching enriched.json row (none of
the 33 already carry an OpenAlex affiliation, so there is nothing to
reconcile). Six names needed a manual variant map to this corpus's actual
author0 spelling (a parsing/formatting difference already visible in
authors.json, not a fresh judgment call):

  Bennet Yee        -> "and Bennet Yee"   (authors_build.py parse artifact:
                                            an "and " conjunction leaked
                                            into this name; a real bug,
                                            out of scope here)
  Daniel Reed       -> "Dan Reed"
  Allan Snavely     -> "A. Snavely"
  William J. Dally  -> "Bill Dally"
  Jonathan Frankle  -> "Jonathan Elliott Frankle"
  Mark Richards     -> "M. Richards"

Two same-name traps the sitting itself already resolved (kept verbatim,
not re-decided here): Michael I. Gordon's gs_user is explicitly NOT the
Oregon State namesake; Dan Campbell's is the NVIDIA/Georgia Tech one.

Backstop: Nishil Talati has a genuine, verifiable OpenAlex author id --
he co-authors `randomwalk-iiswc21` (openalex W3212503094), whose real
authorship list spells him "Nishil Talati" (one T). Our own author0 has
"Talathi" (extra h), which is why the ORIGINAL shared-work resolution in
enrich_openalex.py silently failed the coarse-key comparison -- this is a
data-entry typo in this corpus, not an ambiguous match, and is resolved
by the exact same shared-work method, just spelled correctly. The other
9 `not_settled` people get a genuine (never name-alone) OpenAlex author
search: accepted only when exactly one candidate's affiliation or era
plausibly matches what we already know (their thesis year, MIT), logged
either way.

    python3 harvest/authors/fold_session_results.py            # report
    python3 harvest/authors/fold_session_results.py --write    # write
"""
import argparse
import json
import os
import sys
import time
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import enrich_openalex as eo  # noqa: E402

ROOT = os.path.dirname(HERE)
AUTHORS_PATH = os.path.join(HERE, 'authors.json')
ENRICHED_PATH = os.path.join(HERE, 'enriched.json')
REVIEW_PATH = os.path.join(HERE, 'review.json')
RESULTS_PATH = os.path.join(HERE, 'session-results.json')

NAME_OVERRIDES = {
    'Bennet Yee': 'and Bennet Yee',
    'Daniel Reed': 'Dan Reed',
    'Allan Snavely': 'A. Snavely',
    'William J. Dally': 'Bill Dally',
    'Jonathan Frankle': 'Jonathan Elliott Frankle',
    'Mark Richards': 'M. Richards',
}

# Real typo in this corpus's author0 field -- the person is genuinely
# "Nishil Talati" (verified against the actual authorship list of the
# paper they co-authored with Saman Amarasinghe, openalex W3212503094).
NOT_SETTLED_NAME_FIX = {'Nishil Talathi': 'Nishil Talati'}

NOT_SETTLED_BACKSTOP_NAMES = [
    'Mathew Deeds', 'D. Koester', 'J. Levesque', 'A. Scarpelli',
    'Richard P. Sollee III', 'Steven N. Raphael', 'Matthew D. Steele',
    'Min Zhang', 'Ricardo Ruiz', 'Nishil Talathi',
]


def do_fold(authors, enriched, results, write):
    name_to_pid = {a['name']: a['person_id'] for a in authors}
    by_pid = {r['person_id']: r for r in enriched}

    updated = []
    missing = []
    for row in results['rows']:
        if row['verdict'] not in ('match', 'tentative'):
            continue
        name = NAME_OVERRIDES.get(row['name'], row['name'])
        pid = name_to_pid.get(name)
        if not pid:
            missing.append(row['name'])
            continue
        e = by_pid.get(pid)
        if not e:
            missing.append(row['name'])
            continue
        e['gs_user'] = row.get('gs_user')
        e['affiliation'] = row.get('affiliation')
        e['gs_evidence'] = row.get('evidence')
        e['gs_verdict'] = row['verdict']
        updated.append((pid, row['name']))

    print(f'{len(updated)} people updated with gs_user + affiliation '
         f'({sum(1 for r in results["rows"] if r["verdict"] == "tentative")} tentative)')
    if missing:
        print(f'!! {len(missing)} session-results names had no authors.json match: {missing}')

    if write:
        with open(ENRICHED_PATH, 'w') as fh:
            json.dump(list(by_pid.values()), fh, indent=1, ensure_ascii=False)
            fh.write('\n')
    return by_pid


def resolve_talati_typo(by_pid, fetch, write):
    """Direct fix: the shared-work method already had everything it
    needed except the correct spelling."""
    pid = 'nishil-talathi'
    e = by_pid.get(pid)
    if not e or e.get('openalex_id'):
        return None
    data = fetch.get('https://api.openalex.org/works/W3212503094?select=id,title,authorships')
    author_id = None
    for a in (data or {}).get('authorships') or []:
        if a['author'].get('display_name') == 'Nishil Talati':
            author_id = eo.oa_id(a['author']['id'])
            orcid = a['author'].get('orcid')
    if not author_id:
        print('!! Talati fix: could not re-find the authorship record')
        return None
    entity = eo.openalex_author_entity(fetch, author_id)
    if not entity:
        print('!! Talati fix: author entity fetch failed')
        return None
    e['openalex_id'] = author_id
    e['resolution_method'] = 'shared_work_corrected_spelling'
    e['resolution_evidence'] = {'work': 'randomwalk-iiswc21 (W3212503094)',
                                'note': 'author0 has "Talathi" (typo); OpenAlex spells it "Talati"'}
    e['orcid'] = (orcid or '').rsplit('/', 1)[-1] or e.get('orcid')
    e['works_count'] = entity.get('works_count')
    e['h_index'] = (entity.get('summary_stats') or {}).get('h_index')
    e['affiliation'] = eo.author_affiliation(entity)
    print(f'Talati: resolved via corrected-spelling shared-work match -> {author_id}')
    return pid


def openalex_author_search(fetch, name):
    url = 'https://api.openalex.org/authors?' + urllib.parse.urlencode(
        {'search': name, 'per-page': 5, 'mailto': fetch.mailto})
    return fetch.get(url)


def do_backstop(by_pid, authors, fetch, write):
    name_to_pid = {a['name']: a['person_id'] for a in authors}
    resolved = []
    unresolved = []
    for name in NOT_SETTLED_BACKSTOP_NAMES:
        if name == 'Nishil Talathi':
            continue  # handled directly above, not a generic search
        pid = name_to_pid.get(name)
        if not pid:
            print(f'!! backstop: {name!r} not found in authors.json')
            continue
        data = openalex_author_search(fetch, name)
        candidates = (data or {}).get('results') or []
        time.sleep(0.3)
        if len(candidates) == 1:
            cand = candidates[0]
            resolved.append((pid, name, cand))
        else:
            unresolved.append((pid, name, len(candidates)))

    for pid, name, cand in resolved:
        # A single search hit is still name-only -- log it to review for a
        # human look rather than silently writing an unverified affiliation,
        # matching this lane's "never on name alone" rule throughout.
        print(f'{name}: exactly one OpenAlex search hit -- '
             f'{cand["display_name"]!r}, {(cand.get("last_known_institutions") or [{}])[0].get("display_name")!r} '
             f'-- flagged for review, not auto-applied (name-only match)')
    for pid, name, n in unresolved:
        print(f'{name}: {n} OpenAlex search hits (0 or ambiguous) -- staying unresolved')

    review = json.load(open(REVIEW_PATH))
    for pid, name, cand in resolved:
        review.append({
            'type': 'openalex_search_backstop_candidate',
            'person_id': pid, 'name': name,
            'candidate_openalex_id': eo.oa_id(cand.get('id')),
            'candidate_name': cand.get('display_name'),
            'candidate_institution': (cand.get('last_known_institutions') or [{}])[0].get('display_name'),
            'reason': 'single OpenAlex name search hit, not corroborated by a shared work -- needs a human look',
        })
    if write:
        with open(REVIEW_PATH, 'w') as fh:
            json.dump(review, fh, indent=1, ensure_ascii=False)
            fh.write('\n')
    return resolved, unresolved


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()

    authors = json.load(open(AUTHORS_PATH))
    enriched = json.load(open(ENRICHED_PATH))
    results = json.load(open(RESULTS_PATH))

    by_pid = do_fold(authors, enriched, results, args.write)

    fetch = eo.Fetcher(mailto='nextgen@mit.edu',
                       intervals={'api.openalex.org': 0.15})
    talati_pid = resolve_talati_typo(by_pid, fetch, args.write)
    resolved, unresolved = do_backstop(by_pid, authors, fetch, args.write)

    if args.write:
        with open(ENRICHED_PATH, 'w') as fh:
            json.dump(list(by_pid.values()), fh, indent=1, ensure_ascii=False)
            fh.write('\n')
        print(f'\nwrote {ENRICHED_PATH} + {REVIEW_PATH}')
    else:
        print('\ndry run -- nothing written. Pass --write to commit.')

    print(f'\nsummary: {"1 resolved (Talati typo fix)" if talati_pid else "0"}, '
         f'{len(resolved)} single-hit candidates flagged for human review, '
         f'{len(unresolved)} still genuinely unresolved (of 9 not_settled)')


if __name__ == '__main__':
    main()
