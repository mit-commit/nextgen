#!/usr/bin/env python3
"""Task `descendants-all`: tier-3 idea-descendant extraction, corpus-wide.

Population (per docs/impact-view-design.md's tier table plus the
"sketch-frontend lesson" widening, docs/LANES.md 2026-08-25): every judged
citing-work row across the corpus -- both the 9 taxonomy pilots
(harvest/taxonomy/pilot-classifications.json) and everyone else
(harvest/taxonomy/records/<key>/*.json) -- classified

  - extends or adopts-idea at centrality core or engaged, or
  - uses-tool at centrality core

(the widened rule: without uses-tool/core, Sketch-class descendants that
build directly on the cited system as their own new tool fall through the
original extends/adopts-idea-only rule).

Mechanical, no guessing: for each qualifying citing work, search whatever
evidence is already cached for it (OpenAlex abstract, cached full text,
S2 citation contexts, its own DOI/OpenAlex record) for a github.com URL.
Does NOT run a GitHub code/repository search for the citing work's own
project the way search_github.py does for our 268 papers -- at this
population's scale (1,795 rows) that would be a second search_github.py-
sized subsystem; out of scope for this mechanical first pass. A citing
work whose repo isn't mentioned anywhere in its own cached evidence is
recorded `located: false` ("paper-only"), never guessed at.

Any github.com URL found gets exactly one light existence check (GET
/repos/{owner}/{repo}, cached) to confirm it's real and grab stars/
description -- not a full verify_repos.py-style judgment pass.

Output: harvest/repos/descendants.json, one list of descendant-edge
records per source paper (bibtexKey).

    GITHUB_TOKEN=... python3 curate/build_idea_descendants.py
"""
import argparse
import glob
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PILOT_CLASSIFICATIONS = os.path.join(ROOT, 'harvest', 'taxonomy', 'pilot-classifications.json')
RECORDS_DIR = os.path.join(ROOT, 'harvest', 'taxonomy', 'records')
CITATIONS_DIR = os.path.join(ROOT, 'harvest', 'citations')
ABSTRACTS_DIR = os.path.join(ROOT, 'harvest', 'fulltext', 'abstracts')
FULLTEXT_DIR = os.path.join(ROOT, 'harvest', 'fulltext')
OUT_PATH = os.path.join(ROOT, 'harvest', 'repos', 'descendants.json')
CACHE = os.path.join(ROOT, 'harvest', 'repos', '_ghcache')

QUALIFY = {
    ('extends', 'core'), ('extends', 'engaged'),
    ('adopts-idea', 'core'), ('adopts-idea', 'engaged'),
    ('uses-tool', 'core'),
}
GITHUB_URL_RE = re.compile(r'https?://github\.com/([\w][\w.-]*)/([\w][\w.-]*)')


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
    return 'noid-' + hashlib.sha1((c.get('title') or '').encode('utf-8')).hexdigest()[:16]


def qualifying_rows():
    rows = []
    tax = json.load(open(PILOT_CLASSIFICATIONS))
    for r in tax['rows']:
        if (r.get('function'), r.get('centrality')) in QUALIFY:
            rows.append((r['pilot'], r))
    for d in sorted(glob.glob(os.path.join(RECORDS_DIR, '*'))):
        if not os.path.isdir(d):
            continue
        key = os.path.basename(d)
        for f in sorted(glob.glob(os.path.join(d, '*.json'))):
            r = json.load(open(f))
            if (r.get('function'), r.get('centrality')) in QUALIFY:
                rows.append((key, r))
    return rows


def evidence_text(key, slug, citing):
    parts = []
    ab_path = os.path.join(ABSTRACTS_DIR, key + '.json')
    if os.path.exists(ab_path):
        ab = json.load(open(ab_path)).get(slug, {})
        if ab.get('abstract'):
            parts.append(ab['abstract'])
    ft_path = os.path.join(FULLTEXT_DIR, key, slug + '.txt')
    if os.path.exists(ft_path):
        parts.append(open(ft_path, encoding='utf-8', errors='surrogateescape').read())
    parts.extend(citing.get('contexts') or [])
    return '\n'.join(parts)


def find_github_url(text):
    seen = []
    for m in GITHUB_URL_RE.finditer(text):
        owner, repo = m.group(1), re.sub(r'\.git$', '', m.group(2))
        if owner.lower() in ('search', 'topics', 'orgs', 'sponsors', 'marketplace', 'about'):
            continue
        candidate = f'{owner}/{repo}'
        if candidate not in seen:
            seen.append(candidate)
    return seen[0] if seen else None


def norm_words(text):
    return set(re.sub(r'[^a-z0-9]+', ' ', (text or '').lower()).split())


_last_search = [0.0]


def search_repo_by_title(title, token):
    """One light repository-search call on the citing work's own title --
    not the rich multi-signal heuristic search_github.py runs for our own
    268 papers (no search-plan.json-style candidate lists exist for an
    arbitrary citing work). Accepts the top hit only if its name+
    description overlaps the title by a real margin, to avoid guessing."""
    if not title or len(title) < 8:
        return None
    gap = time.time() - _last_search[0]
    if gap < 2.1:
        time.sleep(2.1 - gap)
    _last_search[0] = time.time()

    q = urllib.parse.urlencode({'q': title, 'per_page': 3})
    url = 'https://api.github.com/search/repositories?' + q
    headers = {'User-Agent': 'nextgen-build-idea-descendants',
              'Accept': 'application/vnd.github+json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode('utf-8', 'replace'))
    except Exception:
        return None

    title_words = norm_words(title)
    if not title_words:
        return None
    for item in data.get('items') or []:
        candidate_text = (item.get('name') or '') + ' ' + (item.get('description') or '')
        overlap = norm_words(candidate_text) & title_words
        if len(overlap) >= max(2, len(title_words) // 3):
            return item
    return None


def fetch_repo(owner_repo, token):
    os.makedirs(CACHE, exist_ok=True)
    url = f'https://api.github.com/repos/{owner_repo}'
    cpath = os.path.join(CACHE, hashlib.sha1(url.encode()).hexdigest() + '.json')
    if os.path.exists(cpath):
        with open(cpath) as fh:
            return json.load(fh).get('body')
    headers = {'User-Agent': 'nextgen-build-idea-descendants',
              'Accept': 'application/vnd.github+json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    req = urllib.request.Request(url, headers=headers)
    body = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = json.loads(resp.read().decode('utf-8', 'replace'))
            break
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                body = None
                break
            time.sleep(2 * (attempt + 1))
        except Exception:
            time.sleep(2 * (attempt + 1))
    with open(cpath + '.tmp', 'w') as fh:
        json.dump({'url': url, 'body': body}, fh)
    os.replace(cpath + '.tmp', cpath)
    return body


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--search', action='store_true',
                    help='also run the light repository-search fallback on rows '
                         'the mechanical scan left paper-only (slow: ~2.1s/row)')
    ap.add_argument('--wave', choices=['strong', 'widened', 'all'], default='all',
                    help='strong = extends/adopts-idea only; widened = uses-tool/core '
                         'only; all = both (default)')
    args = ap.parse_args()

    token = os.environ.get('GITHUB_TOKEN', '').strip()
    if not token:
        sys.exit('GITHUB_TOKEN not set')

    rows = qualifying_rows()
    print(f'{len(rows)} qualifying citing-work rows total', file=sys.stderr)

    def in_wave(function):
        if args.wave == 'strong':
            return function in ('extends', 'adopts-idea')
        if args.wave == 'widened':
            return function == 'uses-tool'
        return True

    out = json.load(open(OUT_PATH)) if os.path.exists(OUT_PATH) else {}
    existing = {(key, e['_slug']): e for key, entries in out.items() for e in entries
               if '_slug' in e}

    citing_cache = {}
    repo_cache = {}
    located = paper_only = searched = 0
    fresh_out = {}

    for i, (key, r) in enumerate(rows, 1):
        if key not in citing_cache:
            path = os.path.join(CITATIONS_DIR, key + '.json')
            citing_cache[key] = {slug_for(c): c for c in
                                 (json.load(open(path)).get('citing') or [] if os.path.exists(path) else [])}
        citing = citing_cache[key].get(r['slug'], {})

        entry = existing.get((key, r['slug'])) or {
            'citing_title': citing.get('title') or r.get('title'),
            'citing_doi': citing.get('doi'),
            'citing_year': citing.get('year') or r.get('year'),
            'function': r['function'],
            'centrality': r['centrality'],
            'located': False,
            '_slug': r['slug'],
        }

        if not entry.get('located') and 'evidence' not in entry:
            # mechanical scan: cheap, local, always run regardless of wave
            text = evidence_text(key, r['slug'], citing)
            owner_repo = find_github_url(text)
            if owner_repo:
                if owner_repo not in repo_cache:
                    repo_cache[owner_repo] = fetch_repo(owner_repo, token)
                repo = repo_cache[owner_repo]
                if repo and repo.get('full_name'):
                    entry.update({
                        'located': True, 'repo': repo['full_name'],
                        'repo_url': repo.get('html_url'),
                        'stars': repo.get('stargazers_count'),
                        'description': repo.get('description'),
                        'evidence': "github.com URL found in the citing work's own cached evidence",
                    })

        if not entry.get('located') and args.search and not entry.get('search_attempted') \
                and in_wave(r['function']):
            item = search_repo_by_title(entry['citing_title'], token)
            entry['search_attempted'] = True
            searched += 1
            if item:
                entry.update({
                    'located': True, 'repo': item['full_name'],
                    'repo_url': item.get('html_url'),
                    'stars': item.get('stargazers_count'),
                    'description': item.get('description'),
                    'evidence': "light GitHub repository search on the citing work's "
                               'own title found a plausible match',
                })

        if entry.get('located'):
            located += 1
        else:
            paper_only += 1
        fresh_out.setdefault(key, []).append(entry)

        if i % 100 == 0:
            print(f'  [{i}/{len(rows)}] located={located} paper_only={paper_only} '
                 f'searched={searched}', file=sys.stderr)
            with open(OUT_PATH, 'w') as fh:
                json.dump(fresh_out, fh, indent=1, sort_keys=True, ensure_ascii=False)
                fh.write('\n')

    out = fresh_out
    with open(OUT_PATH, 'w') as fh:
        json.dump(out, fh, indent=1, sort_keys=True, ensure_ascii=False)
        fh.write('\n')

    print(f'\n{len(rows)} qualifying rows across {len(out)} papers', file=sys.stderr)
    print(f'{located} descendant repos located, {paper_only} paper-only '
         f'(no repo in the citing work\'s own cached evidence)', file=sys.stderr)
    print(f'wrote {OUT_PATH}', file=sys.stderr)


if __name__ == '__main__':
    main()
