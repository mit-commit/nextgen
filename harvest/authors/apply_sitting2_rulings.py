#!/usr/bin/env python3
"""Round-11 task 5: apply the coordinator's LinkedIn-sitting-2 close-out
rulings (tasks/QUEUE.md, "HUMAN RULINGS 2026-08-26 (LinkedIn sitting 2
close-out)") to the harvest/authors/ identity files by hand -- these are
one-off human judgment calls (a merge, a rename, two confirmations), not
the general linkedin-results.json -> links.json join (that's round-11
task 4, a different, bulk mechanism for the other ~57 people).

(a) Richard P. Sollee III: confirmed as https://www.linkedin.com/in/solleer
    (2nd-degree; already on linkedin-connect-list.md).
(b) yee-lok-won merges into yee-lok-wong (one person): won's papers
    (ansel:cgo:2011, ansel:mitcsail-tr:2010) move onto wong's record in
    authors.json (won's name kept as a variant); won's row is dropped
    from enriched.json and links.json entirely. The merged person's
    LinkedIn is confirmed as https://www.linkedin.com/in/yee-lok-wong.
(c) y-zibin renamed to "Yoav Zibin" (name field only -- person_id keeps
    its original slug so nothing else that keys off it needs to change)
    in authors.json + enriched.json, with "Y. Zibin" kept as a variant.
    Confirmed as https://www.linkedin.com/in/yoav-zibin-6392651. The
    pre-existing review.json flag ("OpenAlex affiliation Google conflicts
    with known Come2Play") is resolved by this same sitting -- the
    evidence names him CTO/co-founder of Come2Play as his CURRENT role,
    so Google reads as a prior employer, not author-cluster contamination
    -- dropped from review.json rather than left open.

Idempotent: every step checks whether it's already applied and skips
with a note rather than raising, so a rerun after the fact (e.g. to
regenerate the log) is safe.

Also synced harvest/authors/linkedin-results.json's own `rows`/
`awaiting_him` bookkeeping so it doesn't show these two as still-pending
in the next session that reads it (round-11 task 4).

    python3 harvest/authors/apply_sitting2_rulings.py            # report
    python3 harvest/authors/apply_sitting2_rulings.py --write    # write
"""
import argparse
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
AUTHORS_PATH = os.path.join(HERE, 'authors.json')
ENRICHED_PATH = os.path.join(HERE, 'enriched.json')
LINKS_PATH = os.path.join(HERE, 'links.json')
REVIEW_PATH = os.path.join(HERE, 'review.json')
LI_RESULTS_PATH = os.path.join(HERE, 'linkedin-results.json')

SOLLEE_URL = 'https://www.linkedin.com/in/solleer'
WONG_URL = 'https://www.linkedin.com/in/yee-lok-wong'
ZIBIN_URL = 'https://www.linkedin.com/in/yoav-zibin-6392651'


def linkedin_candidate(url, evidence):
    return {'tier': 'linkedin', 'source': 'linkedin_sitting', 'url': url,
           'evidence': evidence, 'verified': True}


def apply_authors(people, log):
    won = next((p for p in people if p['person_id'] == 'yee-lok-won'), None)
    if won:
        wong = next(p for p in people if p['person_id'] == 'yee-lok-wong')
        wong['papers'] = sorted(set(wong['papers']) | set(won['papers']))
        if won['name'] not in wong['variants']:
            wong['variants'] = sorted(wong['variants'] + [won['name']])
        people.remove(won)
        log.append(f"authors.json: merged yee-lok-won into yee-lok-wong -> "
                  f"papers {wong['papers']}, variants {wong['variants']}")
    else:
        log.append('authors.json: yee-lok-won already merged, skipping')

    zibin = next(p for p in people if p['person_id'] == 'y-zibin')
    if zibin['name'] != 'Yoav Zibin':
        if zibin['name'] not in zibin['variants']:
            zibin['variants'] = sorted(zibin['variants'] + [zibin['name']])
        zibin['name'] = 'Yoav Zibin'
        log.append("authors.json: y-zibin renamed to 'Yoav Zibin' "
                  f"(variants now {zibin['variants']})")
    else:
        log.append("authors.json: y-zibin already renamed, skipping")
    return people


def apply_enriched(people, log):
    before = len(people)
    people = [p for p in people if p['person_id'] != 'yee-lok-won']
    if len(people) != before:
        log.append('enriched.json: dropped yee-lok-won row (merged away, '
                  "kept yee-lok-wong's existing OpenAlex resolution untouched)")
    else:
        log.append('enriched.json: yee-lok-won already dropped, skipping')
    for p in people:
        if p['person_id'] == 'y-zibin' and p['name'] != 'Yoav Zibin':
            p['name'] = 'Yoav Zibin'
            log.append("enriched.json: y-zibin's name field -> 'Yoav Zibin'")
    return people


def apply_links(people, log):
    before = len(people)
    people = [p for p in people if p['person_id'] != 'yee-lok-won']
    if len(people) != before:
        log.append('links.json: dropped yee-lok-won row (merged away)')
    for p in people:
        if p['person_id'] == 'richard-p-sollee-iii' and p.get('best_tier') != 'linkedin':
            p['candidates'] = [linkedin_candidate(
                SOLLEE_URL,
                '2nd-degree; City of Jacksonville UI/UX->AI developer '
                "from Jul 2024, runs a Jacksonville HS project since 2019 "
                "-- fits an MIT MEng '24 (Richard:meng-thesis:2024) "
                'exactly; education section hidden but confirmed by the human')]
            p['best_tier'] = 'linkedin'
            log.append(f"links.json: richard-p-sollee-iii -> {SOLLEE_URL}")
        elif p['person_id'] == 'yee-lok-wong' and p.get('best_tier') != 'linkedin':
            p['candidates'] = [linkedin_candidate(
                WONG_URL,
                '2nd-degree; Singapore, regulatory-reporting delivery at '
                'Nasdaq/AxiomSL; mutuals Nicolas Pinto and Jean Yang '
                '(MIT-era) -- confirmed by the human as the same person as '
                'both the OpenAlex-resolved PetaBricks-era MIT co-author '
                '(ansel:cases:2012/chan:sc:2009/ansel:pldi:2009) and the '
                'merged yee-lok-won (ansel:cgo:2011/ansel:mitcsail-tr:2010)')]
            p['best_tier'] = 'linkedin'
            log.append(f"links.json: yee-lok-wong -> {WONG_URL}")
        elif p['person_id'] == 'y-zibin' and p.get('best_tier') != 'linkedin':
            p['name'] = 'Yoav Zibin'
            p['candidates'] = [linkedin_candidate(
                ZIBIN_URL,
                '1st-degree; CTO/co-founder of Come2Play, exactly the '
                'affiliation on perkins:sosp:2009; mutual Andrew Myers')]
            p['best_tier'] = 'linkedin'
            log.append(f"links.json: y-zibin -> 'Yoav Zibin', {ZIBIN_URL}")
    return people


def apply_review(rows, log):
    before = len(rows)
    rows = [r for r in rows if r.get('person_id') not in ('yee-lok-won', 'y-zibin')]
    if len(rows) != before:
        log.append(f'review.json: dropped {before - len(rows)} resolved flags '
                  '(yee-lok-won merged away; y-zibin\'s affiliation "conflict" '
                  'explained by the sitting -- Come2Play is his current role, '
                  'Google a prior one, not cluster contamination)')
    return rows


def apply_linkedin_results(d, log):
    for r in d.get('rows', []):
        if r.get('name') == 'Richard P. Sollee III' and r.get('verdict') == 'to_him':
            r['verdict'] = 'confirmed'
            r['linkedin'] = r.pop('candidate')
            log.append('linkedin-results.json: Sollee row -> confirmed')
        elif r.get('name') == 'Yee Lok Wong' and r.get('verdict') == 'to_him':
            r['verdict'] = 'confirmed'
            r['linkedin'] = r.pop('candidate')
            r['evidence'] += ('; confirmed by the human, and merged with '
                             'yee-lok-won (same person)')
            log.append('linkedin-results.json: Yee Lok Wong row -> confirmed')
    before = len(d.get('awaiting_him', []))
    d['awaiting_him'] = [a for a in d.get('awaiting_him', [])
                         if a.get('name') not in ('Richard P. Sollee III', 'Yee Lok Wong')]
    if len(d['awaiting_him']) != before:
        log.append(f"linkedin-results.json: awaiting_him {before} -> {len(d['awaiting_him'])}")
    else:
        log.append('linkedin-results.json: awaiting_him already clear, skipping')
    return d


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()

    log = []
    authors = apply_authors(json.load(open(AUTHORS_PATH)), log)
    enriched = apply_enriched(json.load(open(ENRICHED_PATH)), log)
    links = apply_links(json.load(open(LINKS_PATH))['people'], log)
    review = apply_review(json.load(open(REVIEW_PATH)), log)
    li_results = apply_linkedin_results(json.load(open(LI_RESULTS_PATH)), log)

    for line in log:
        print(line)

    if args.write:
        with open(AUTHORS_PATH, 'w') as fh:
            json.dump(authors, fh, indent=1, ensure_ascii=False)
            fh.write('\n')
        with open(ENRICHED_PATH, 'w') as fh:
            json.dump(enriched, fh, indent=1, ensure_ascii=False)
            fh.write('\n')
        links_doc = json.load(open(LINKS_PATH))
        links_doc['people'] = links
        with open(LINKS_PATH, 'w') as fh:
            json.dump(links_doc, fh, indent=1, ensure_ascii=False)
            fh.write('\n')
        with open(REVIEW_PATH, 'w') as fh:
            json.dump(review, fh, indent=1, ensure_ascii=False)
            fh.write('\n')
        with open(LI_RESULTS_PATH, 'w') as fh:
            json.dump(li_results, fh, indent=1, ensure_ascii=False)
            fh.write('\n')
        print(f'\nwrote {AUTHORS_PATH}, {ENRICHED_PATH}, {LINKS_PATH}, {REVIEW_PATH}, {LI_RESULTS_PATH}')
    else:
        print('\ndry run -- nothing written. Pass --write to commit.')


if __name__ == '__main__':
    main()
