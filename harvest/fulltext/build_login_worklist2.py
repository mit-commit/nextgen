#!/usr/bin/env python3
"""Task `login-worklist2`: expanded closed-citing-papers worklist.

Wider population than build_login_worklist.py's first pass: every citing
work (deduped by DOI -- the same PDF regardless of which of our papers it
cites) where

  - confidence is low or medium, evidence is exactly "contexts", and
    function is on the "detailed" side (extends, uses-tool, adopts-idea,
    uses-benchmark, baseline, positions, surveys, supports-claim,
    detailed-citation -- data/citations/SCHEMA.md's split rule), OR
  - function is unknown, OR the citing work has no judgment at all
    (title-only/unclassified) but does have a DOI,

and the DOI belongs to IEEE (10.1109), ACM (10.1145), or Springer
(10.1007) -- Elsevier is deliberately skipped this pass. Excludes any DOI
whose text is already cached under any paper's harvest/fulltext/<key>/
directory.

For IEEE rows, resolves the arnumber (IEEE's own document id, required for
the stamp-PDF URL, distinct from the DOI) via Crossref's bulk filter API,
batched 40 DOIs/call -- zero requests to any publisher. Crossref carries it
in `resource.primary.URL` (.../document/<arnumber>/) and in the vor `link`
entry's `?arnumber=<n>` query param; either one is read here.

Output: harvest/fulltext/login-worklist2.json, one row per qualifying DOI:
{doi, publisher, url, name}. `url` is the ready-to-fetch page for a human
with an institutional login -- IEEE Xplore's stamp PDF, ACM DL's PDF
endpoint, or Springer via the MIT library proxy. `name` is the DOI with
"/" replaced by "_", for saving the fetched file.

    python3 harvest/fulltext/build_login_worklist2.py
"""
import glob
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
PILOT_CLASSIFICATIONS = os.path.join(ROOT, 'harvest', 'taxonomy', 'pilot-classifications.json')
RECORDS_DIR = os.path.join(ROOT, 'harvest', 'taxonomy', 'records')
CITATIONS_DIR = os.path.join(ROOT, 'harvest', 'citations')
FULLTEXT_DIR = HERE
OUT_PATH = os.path.join(HERE, 'login-worklist2.json')

DETAILED = {'extends', 'uses-tool', 'adopts-idea', 'uses-benchmark', 'baseline',
            'positions', 'surveys', 'supports-claim', 'detailed-citation'}
PUBLISHER_PREFIX = {'10.1109': 'IEEE', '10.1145': 'ACM', '10.1007': 'Springer'}
MAILTO = 'samana@mit.edu'


def slug_for(c):
    doi = c.get('doi')
    if doi:
        return re.sub(r'[^a-z0-9._-]', '_', doi.lower())
    oa = c.get('openalex')
    if oa:
        return 'oa-' + oa.rsplit('/', 1)[-1]
    s2 = c.get('s2')
    if s2:
        return 's2-' + s2[:16]
    import hashlib
    return 'noid-' + hashlib.sha1((c.get('title') or '').encode('utf-8')).hexdigest()[:16]


def qualifies(function, confidence, evidence):
    if function in DETAILED and confidence in ('low', 'medium') and evidence == 'contexts':
        return True
    if function == 'unknown':
        return True
    return False


def already_cached(slug):
    return bool(glob.glob(os.path.join(FULLTEXT_DIR, '*', slug + '.txt')))


def collect_candidates():
    """Returns {doi_lower: publisher} for every qualifying, uncached DOI."""
    judged_by_key_slug = {}
    tax = json.load(open(PILOT_CLASSIFICATIONS))
    for r in tax['rows']:
        judged_by_key_slug[(r['pilot'], r['slug'])] = r
    for d in glob.glob(os.path.join(RECORDS_DIR, '*')):
        if not os.path.isdir(d):
            continue
        key = os.path.basename(d)
        for f in glob.glob(os.path.join(d, '*.json')):
            r = json.load(open(f))
            judged_by_key_slug[(key, r['slug'])] = r

    candidates = {}
    skipped_cached = 0
    for path in glob.glob(os.path.join(CITATIONS_DIR, '*.json')):
        key = os.path.basename(path)[:-5]
        if key.startswith('.'):
            continue
        citing_list = json.load(open(path)).get('citing') or []
        for c in citing_list:
            doi = c.get('doi')
            if not doi:
                continue
            prefix = doi.split('/')[0].lower()
            publisher = PUBLISHER_PREFIX.get(prefix)
            if not publisher:
                continue
            slug = slug_for(c)
            r = judged_by_key_slug.get((key, slug))
            if r:
                ok = qualifies(r.get('function'), r.get('confidence'), r.get('evidence'))
            else:
                ok = True  # title-only/unclassified: no judgment at all, but has a DOI
            if not ok:
                continue
            if already_cached(slug):
                skipped_cached += 1
                continue
            candidates[doi.lower()] = publisher
    return candidates, skipped_cached


# ---------------------------------------------------------- Crossref (IEEE)

def fetch_crossref_batch(dois):
    # urlencode() does the one necessary percent-encoding pass over the
    # whole filter value -- pre-quoting each DOI first and THEN urlencoding
    # double-encodes every "/" to "%252F", which Crossref's filter parser
    # rejects with a 400.
    q = ','.join('doi:' + d for d in dois)
    url = ('https://api.crossref.org/works?' +
          urllib.parse.urlencode({'filter': q, 'select': 'DOI,resource,link', 'rows': len(dois)}))
    req = urllib.request.Request(url, headers={
        'User-Agent': f'commit-nextgen-worklist2/1.0 (mailto:{MAILTO})',
        'Accept': 'application/json',
    })
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                return json.loads(resp.read().decode('utf-8', 'replace'))
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(2 * (attempt + 1))
                continue
            print(f'!! Crossref batch failed: HTTP {exc.code}', file=sys.stderr)
            return None
        except Exception as exc:
            time.sleep(2 * (attempt + 1))
    return None


def resolve_arnumbers(ieee_dois):
    """{doi_lower: arnumber (str)} via Crossref, 40 DOIs/call."""
    out = {}
    batches = [ieee_dois[i:i + 40] for i in range(0, len(ieee_dois), 40)]
    for i, batch in enumerate(batches):
        data = fetch_crossref_batch(batch)
        if not data:
            continue
        for item in data.get('message', {}).get('items', []):
            doi = (item.get('DOI') or '').lower()
            arnumber = None
            resource_url = (item.get('resource') or {}).get('primary', {}).get('URL', '')
            m = re.search(r'/document/(\d+)', resource_url)
            if m:
                arnumber = m.group(1)
            if not arnumber:
                for link in item.get('link') or []:
                    m = re.search(r'arnumber=(\d+)', link.get('URL', ''))
                    if m:
                        arnumber = m.group(1)
                        break
            if arnumber:
                out[doi] = arnumber
        print(f'  Crossref arnumber batch {i + 1}/{len(batches)}: '
             f'{len(out)}/{sum(len(b) for b in batches[:i + 1])} resolved so far',
             file=sys.stderr)
        time.sleep(1.0)
    return out


def build_url(doi, publisher, arnumber):
    if publisher == 'ACM':
        return f'https://dl.acm.org/doi/pdf/{doi}'
    if publisher == 'Springer':
        return f'https://link-springer-com.libproxy.mit.edu/content/pdf/{doi}.pdf'
    if publisher == 'IEEE':
        if not arnumber:
            return None
        return f'https://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber={arnumber}'
    return None


def main():
    candidates, skipped_cached = collect_candidates()
    print(f'{len(candidates)} qualifying DOIs ({skipped_cached} already cached, skipped)',
         file=sys.stderr)

    ieee_dois = sorted(doi for doi, pub in candidates.items() if pub == 'IEEE')
    arnumbers = resolve_arnumbers(ieee_dois) if ieee_dois else {}

    rows = []
    by_publisher = {}
    unresolved_ieee = 0
    for doi, publisher in sorted(candidates.items()):
        arnumber = arnumbers.get(doi)
        url = build_url(doi, publisher, arnumber)
        if not url:
            unresolved_ieee += 1
            continue
        rows.append({
            'doi': doi,
            'publisher': publisher,
            'url': url,
            'name': doi.replace('/', '_'),
        })
        by_publisher[publisher] = by_publisher.get(publisher, 0) + 1

    with open(OUT_PATH, 'w') as fh:
        json.dump(rows, fh, indent=1, ensure_ascii=False)
        fh.write('\n')

    print(f'\n{len(rows)} rows written ({unresolved_ieee} IEEE DOIs dropped -- '
         f'Crossref had no arnumber)')
    for pub, n in sorted(by_publisher.items(), key=lambda kv: -kv[1]):
        print(f'  {pub}: {n}')
    print(f'wrote {OUT_PATH}')


if __name__ == '__main__':
    main()
