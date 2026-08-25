#!/usr/bin/env python3
"""Task `authors-worklist`: prepare the human's authors browser sitting.

Two worklists in one sheet, from data already on disk -- nothing fetched,
LinkedIn never visited, only search URLs constructed for the human to open
and judge themselves:

  1. The 77 unresolved + 5 ambiguous people from harvest/authors/
     review.json, each with their papers (so the human can tell who this
     is), latest known affiliation if we have one, the OpenAlex candidate
     ids for the ambiguous ones, and best-guess search links (Google
     Scholar, OpenAlex, LinkedIn).
  2. A LinkedIn-presence checklist for all 369 people in authors.json --
     one row each, with a constructed LinkedIn people-search URL. Already-
     resolved people show their known affiliation/homepage/OpenAlex link
     as disambiguation context; unresolved people are flagged so the
     human's LinkedIn check doubles as another resolution attempt.

    python3 harvest/authors/build_session_sheet.py
"""
import json
import os
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
AUTHORS_PATH = os.path.join(HERE, 'authors.json')
ENRICHED_PATH = os.path.join(HERE, 'enriched.json')
REVIEW_PATH = os.path.join(HERE, 'review.json')
PUBLICATIONS = os.path.join(ROOT, 'data', 'publications.json')
OUT_PATH = os.path.join(HERE, 'session-sheet.md')


def linkedin_search_url(name):
    return ('https://www.linkedin.com/search/results/people/?keywords='
            + urllib.parse.quote(name))


def scholar_search_url(name):
    return 'https://scholar.google.com/scholar?q=' + urllib.parse.quote('"%s"' % name)


def openalex_author_url(openalex_id):
    return 'https://openalex.org/' + openalex_id


def paper_titles(paper_keys, pubs):
    out = []
    for k in paper_keys:
        p = pubs.get(k)
        title = p.get('title') if p else k
        year = p.get('year') if p else ''
        out.append(f'{title} ({year})' if year else title)
    return out


def main():
    authors = json.load(open(AUTHORS_PATH))
    enriched = {r['person_id']: r for r in json.load(open(ENRICHED_PATH))}
    review = json.load(open(REVIEW_PATH))
    pubs = {p['bibtexKey']: p for p in json.load(open(PUBLICATIONS))}

    unresolved = [r for r in review if r.get('type') == 'openalex_unresolved']
    ambiguous = [r for r in review if r.get('type') == 'openalex_ambiguous']

    lines = [
        '# Authors browser sitting -- session sheet',
        '',
        f'{len(unresolved)} unresolved + {len(ambiguous)} ambiguous people need a human '
        'look; a LinkedIn-presence checklist for all 369 people follows. Nothing here '
        'was fetched -- LinkedIn URLs are constructed, not visited.',
        '',
        '## Part 1 -- unresolved and ambiguous (best-guess links)',
        '',
    ]

    for r in unresolved:
        titles = paper_titles(r.get('papers') or [], pubs)
        lines.append(f"- [ ] **{r['name']}** -- unresolved ({r.get('reason', '')})")
        for t in titles:
            lines.append(f'      paper: {t}')
        lines.append(f"      Scholar: {scholar_search_url(r['name'])}")
        lines.append(f"      LinkedIn: {linkedin_search_url(r['name'])}")
        lines.append('')

    for r in ambiguous:
        lines.append(f"- [ ] **{r['name']}** -- ambiguous ({r.get('reason', '')})")
        for oa_id, papers in (r.get('candidates') or {}).items():
            titles = paper_titles(papers, pubs)
            lines.append(f'      candidate {openalex_author_url(oa_id)}: '
                         + '; '.join(titles))
        lines.append(f"      Scholar: {scholar_search_url(r['name'])}")
        lines.append(f"      LinkedIn: {linkedin_search_url(r['name'])}")
        lines.append('')

    flagged_names = {r['name'] for r in unresolved + ambiguous}

    lines += [
        '## Part 2 -- LinkedIn presence checklist, all %d people' % len(authors),
        '',
        'Sorted alphabetically. Resolved people show their known affiliation/homepage '
        'as disambiguation context on LinkedIn; `[NEEDS RESOLUTION]` marks people also '
        'in Part 1, where a LinkedIn hit could double as a resolution.',
        '',
    ]
    for a in sorted(authors, key=lambda a: a['name'].lower()):
        e = enriched.get(a['person_id'], {})
        flag = ' [NEEDS RESOLUTION]' if a['name'] in flagged_names else ''
        context_bits = []
        if e.get('affiliation'):
            context_bits.append(e['affiliation'])
        if e.get('homepage'):
            context_bits.append(e['homepage'])
        if e.get('openalex_id'):
            context_bits.append(openalex_author_url(e['openalex_id']))
        context = ' -- ' + '; '.join(context_bits) if context_bits else ''
        lines.append(f"- [ ] **{a['name']}**{flag}{context}")
        lines.append(f"      LinkedIn: {linkedin_search_url(a['name'])}")

    with open(OUT_PATH, 'w') as fh:
        fh.write('\n'.join(lines) + '\n')

    print(f'{len(unresolved)} unresolved, {len(ambiguous)} ambiguous, '
          f'{len(authors)} total people')
    print(f'wrote {OUT_PATH}')


if __name__ == '__main__':
    main()
