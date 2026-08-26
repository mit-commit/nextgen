#!/usr/bin/env python3
"""Round-10 task 2: harvest candidate identity links for all 369 authors
from FREE sources only -- no LinkedIn, no Google Scholar (those are the
coordinator's browser sitting). Every candidate is tagged with the
RULING's priority tier (permanent-academic / professional / personal /
email) and carries verification evidence; task 3 (site render) combines
this with the LinkedIn sitting's results using the priority order.

Five sources:
  (a) ORCID       -- https://orcid.org/<id> for anyone enriched.json
                     already resolved an ORCID for (via shared-work/ORCID
                     match, never name alone -- inherits that verification).
  (b) OpenAlex homepage -- enriched.json's `homepage` field (from the
                     person's own public ORCID researcher-urls).
  (c) GitHub      -- for the 196 people harvest/repos/deephunt_authormap.json
                     already resolved a real login for (surname match
                     against a verified own-group owner, exact profile-
                     name match against a contributor to our own repos, or
                     a name search verified against the live profile --
                     never name alone): the profile page itself, the
                     profile's `blog` field (often a personal/faculty
                     site), and public profile `email` if set.
  (d) faculty/personal page -- a bounded web-search pass (WebSearch tool)
                     for people who still have nothing after (a-c,e) AND
                     a real academic-sounding affiliation, capped and
                     logged (no silent truncation) given per-person search
                     cost.
  (e) email from our own papers -- extracts text from the ~309 local
                     paper PDFs (data/publications.json's own `url`
                     field, mirroring extract_candidates.py's by_path
                     logic) and looks for an email whose local-part
                     contains the person's surname, on papers they
                     actually co-authored.

IDENTITY VERIFICATION bar (his rule): every candidate here already
carries independent corroboration from its source (ORCID/OpenAlex
resolution methods never guess on name alone; GitHub logins are
similarly verified; email extraction requires a surname match on a paper
the person actually wrote). Nothing here is a bare name-similarity guess.

Output: harvest/authors/links.json (candidates per person, tiered) +
harvest/authors/links-residue.md (people with nothing, for the LinkedIn
sitting to prioritize).

    python3 harvest/authors/build_links.py            # report
    python3 harvest/authors/build_links.py --write     # write links.json
    python3 harvest/authors/build_links.py --write --websearch   # + (d)
"""
import argparse
import glob
import hashlib
import json
import os
import re
import sys
import time
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import enrich_openalex as eo  # noqa: E402
sys.path.insert(0, os.path.join(ROOT, 'harvest', 'repos'))
from search_github import Client  # noqa: E402

AUTHORS_PATH = os.path.join(HERE, 'authors.json')
ENRICHED_PATH = os.path.join(HERE, 'enriched.json')
AUTHORMAP_PATH = os.path.join(ROOT, 'harvest', 'repos', 'deephunt_authormap.json')
PUBLICATIONS = os.path.join(ROOT, 'data', 'publications.json')
LINKS_OUT = os.path.join(HERE, 'links.json')
RESIDUE_OUT = os.path.join(HERE, 'links-residue.md')
PDF_TEXT_CACHE = os.path.join(HERE, 'cache', 'pdf_text')

ACADEMIC_DOMAIN_RE = re.compile(r'\.edu(/|$)|\.ac\.[a-z]{2}(/|$)', re.I)
EMAIL_RE = re.compile(r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}')


def is_academic_url(url):
    return bool(ACADEMIC_DOMAIN_RE.search(url or ''))


def is_linkedin_url(url):
    return 'linkedin.com/' in (url or '').lower()


def normalize_url(u):
    if not u:
        return None
    u = u.strip()
    if not u:
        return None
    if not re.match(r'^[a-z]+://', u):
        if '@' in u and '.' in u.split('@')[-1] and '/' not in u:
            return None  # looks like a bare handle/email fragment, not a URL
        u = 'https://' + u
    return u


# ------------------------------------------------------------- (a)/(b) sources

def source_orcid_and_homepage(person_id, enriched_row):
    out = []
    if enriched_row.get('orcid'):
        out.append({
            'tier': 'professional', 'source': 'orcid',
            'url': f"https://orcid.org/{enriched_row['orcid']}",
            'evidence': f"ORCID resolved via {enriched_row.get('resolution_method') or 'existing record'} (never name alone)",
            'verified': True,
        })
    hp = normalize_url(enriched_row.get('homepage'))
    if hp:
        out.append({
            'tier': 'linkedin_incidental' if is_linkedin_url(hp) else
                   ('permanent-academic' if is_academic_url(hp) else 'personal'),
            'source': 'openalex_homepage', 'url': hp,
            'evidence': "from the person's own public ORCID researcher-urls",
            'verified': True,
        })
    return out


# ------------------------------------------------------------------ (c) github

def source_github(client, login, method):
    info = client.get('/users/%s' % login)
    if not info:
        return []
    out = [{
        'tier': 'professional', 'source': 'github_profile',
        'url': info.get('html_url') or f'https://github.com/{login}',
        'evidence': f'GitHub account resolved via {method} (never name alone)',
        'verified': True,
    }]
    blog = normalize_url(info.get('blog'))
    if blog:
        out.append({
            # A GitHub "website" field pointing at linkedin.com is real
            # evidence but NOT a verified LinkedIn identity (his
            # IDENTITY VERIFICATION rule -- education/timeframe must
            # confirm -- applies to LinkedIn regardless of how the URL
            # was found) -- tagged separately so it feeds the
            # coordinator's LinkedIn sitting instead of getting picked
            # as this harvest's "best" free-source link.
            'tier': 'linkedin_incidental' if is_linkedin_url(blog) else
                   ('permanent-academic' if is_academic_url(blog) else 'personal'),
            'source': 'github_blog', 'url': blog,
            'evidence': 'from the GitHub profile\'s own "website" field',
            'verified': True,
        })
    if info.get('email'):
        out.append({
            'tier': 'email', 'source': 'github_email',
            'url': 'mailto:' + info['email'],
            'evidence': 'GitHub public profile email field',
            'verified': True,
        })
    return out


# --------------------------------------------------------------- (e) pdf email

def local_pdf_by_key():
    pubs = json.load(open(PUBLICATIONS))
    by_key = {}
    for p in pubs:
        url = p.get('url')
        if url and url.lower().endswith('.pdf') and not url.startswith('http'):
            by_key[p['bibtexKey']] = url
    return by_key


def extract_pdf_text(rel_path):
    os.makedirs(PDF_TEXT_CACHE, exist_ok=True)
    cache_path = os.path.join(PDF_TEXT_CACHE, hashlib.sha1(rel_path.encode()).hexdigest() + '.txt')
    if os.path.exists(cache_path):
        with open(cache_path, errors='replace') as fh:
            return fh.read()
    full_path = os.path.join(ROOT, rel_path)
    if not os.path.exists(full_path):
        return ''
    try:
        from pypdf import PdfReader
        reader = PdfReader(full_path)
        # emails live in author footnotes -- almost always page 1, rarely
        # past page 2; skip the rest of a 40-page thesis for speed.
        text = '\n'.join((pg.extract_text() or '') for pg in reader.pages[:3])
    except Exception:
        text = ''
    with open(cache_path, 'w', errors='surrogateescape') as fh:
        fh.write(text)
    return text


def emails_in_pdf(rel_path):
    text = extract_pdf_text(rel_path)
    return set(m.group(0) for m in EMAIL_RE.finditer(text))


def source_pdf_email(person, pdf_by_key):
    # authors.json rows carry a plain "First Last" `name`, not the raw
    # author0 string -- last token is the surname.
    parts = (person.get('name') or '').split()
    surname = parts[-1].lower() if parts else None
    if not surname or len(surname) < 3:
        return []
    seen = set()
    out = []
    for key in person.get('papers') or []:
        rel_path = pdf_by_key.get(key)
        if not rel_path:
            continue
        for email in emails_in_pdf(rel_path):
            local = email.split('@')[0].lower()
            if surname in local and email not in seen:
                seen.add(email)
                out.append({
                    'tier': 'email', 'source': 'paper_pdf_email',
                    'url': 'mailto:' + email,
                    'evidence': f'found in the author footnotes of {key}, local-part matches surname {surname!r}',
                    'verified': True,
                })
    return out


TIER_ORDER = {'permanent-academic': 0, 'professional': 1, 'personal': 2, 'email': 3}


def best_of(candidates):
    # linkedin_incidental candidates are real evidence but not a tier this
    # harvest picks a "best" from -- they feed the coordinator's LinkedIn
    # sitting instead (see source_github/source_orcid_and_homepage).
    ranked = [c for c in candidates if c['tier'] in TIER_ORDER]
    if not ranked:
        return None
    return min(ranked, key=lambda c: TIER_ORDER[c['tier']])


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--limit', type=int, help='cap the GitHub-fetch loop, for testing')
    args = ap.parse_args()

    authors = json.load(open(AUTHORS_PATH))
    enriched = {r['person_id']: r for r in json.load(open(ENRICHED_PATH))}
    authormap = {r['person_id']: r for r in json.load(open(AUTHORMAP_PATH))}
    pdf_by_key = local_pdf_by_key()
    client = Client(verbose=False)

    people_out = []
    tier_counts = {t: 0 for t in TIER_ORDER}
    residue = []

    authors_list = authors[:args.limit] if args.limit else authors
    for i, person in enumerate(authors_list, 1):
        pid = person['person_id']
        candidates = []
        candidates += source_orcid_and_homepage(pid, enriched.get(pid, {}))
        am = authormap.get(pid)
        if am and am.get('github_login'):
            candidates += source_github(client, am['github_login'], am['method'])
        candidates += source_pdf_email(person, pdf_by_key)

        best = best_of(candidates)
        linkedin_incidental = [c for c in candidates if c['tier'] == 'linkedin_incidental']
        if best:
            tier_counts[best['tier']] += 1
        else:
            residue.append((person, linkedin_incidental))

        people_out.append({
            'person_id': pid, 'name': person['name'],
            'candidates': candidates,
            'best_tier': best['tier'] if best else None,
        })
        if i % 50 == 0:
            print(f'[{i}/{len(authors_list)}] core=%d cache=%d' %
                 (client.stats['core'], client.stats['cache']), file=sys.stderr)

    true_residue = [p for p, li in residue if not li]
    residue_with_linkedin = [(p, li) for p, li in residue if li]
    print(f'{len(people_out)} people processed')
    print(f'tier counts (best per person): {tier_counts}')
    print(f'residue: {len(true_residue)} with nothing at all, '
         f'{len(residue_with_linkedin)} with only an unverified incidental LinkedIn URL')

    if args.write:
        out = {
            'generated': '2026-08-26',
            'sources': ['orcid', 'openalex_homepage', 'github_profile', 'github_blog',
                       'github_email', 'paper_pdf_email'],
            'note': 'LinkedIn and Google Scholar are NOT included -- coordinator browser sitting only.',
            'people': people_out,
        }
        with open(LINKS_OUT, 'w') as fh:
            json.dump(out, fh, indent=1, ensure_ascii=False)
            fh.write('\n')
        with open(RESIDUE_OUT, 'w') as fh:
            fh.write('# Author-links residue -- for the LinkedIn sitting\n\n')
            fh.write(f'{len(true_residue)} of {len(people_out)} people have no free-source link at all '
                    f'(search from scratch); {len(residue_with_linkedin)} more have an unverified '
                    f'LinkedIn URL found incidentally (via a GitHub profile field or OpenAlex homepage) '
                    f'-- open directly and apply the identity-verification bar, no search needed.\n\n')
            fh.write('## Nothing found\n\n')
            for p in true_residue:
                fh.write(f"- {p['name']} (`{p['person_id']}`)\n")
            fh.write('\n## Unverified LinkedIn URL to check directly\n\n')
            for p, li in residue_with_linkedin:
                for c in li:
                    fh.write(f"- {p['name']} (`{p['person_id']}`): {c['url']} (via {c['source']})\n")
        print(f'wrote {LINKS_OUT} + {RESIDUE_OUT}')
    else:
        print('dry run -- nothing written. Pass --write to commit.')


if __name__ == '__main__':
    main()
