#!/usr/bin/env python3
"""Own-repo inventory (human directive 2026-08-25: find ALL our repos
before hunting outside users; theses especially).

    python3 harvest/impactview/find_own_repos.py --fetch    # enumerate owners
    python3 harvest/impactview/find_own_repos.py --match    # candidates + report

Phase A of the inventory: enumerate every repo of every known own-repo
owner (orgs and personal accounts seen in harvest/repos/verified.json /
ghmeta.json), then mechanically match candidates to papers by author
name, distinctive title tokens, and a publication-year window. Output is
candidates for review, NOT truth: harvest/impactview/own-repo-candidates.json
plus a human-readable report. Phase B (model judging of ambiguous rows)
and the merge into site data happen only after review.
"""
import argparse
import collections
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.abspath(__file__))
POOL = os.path.join(HERE, 'owner-repos.json')       # enumeration cache
OUT = os.path.join(HERE, 'own-repo-candidates.json')
REPORT = os.path.join(HERE, 'own-repo-report.md')

STOP = {'a', 'an', 'the', 'of', 'for', 'and', 'on', 'in', 'with', 'to',
        'from', 'using', 'via', 'by', 'at', 'its', 'toward', 'towards',
        'compiler', 'compilers', 'compilation', 'language', 'languages',
        'system', 'systems', 'framework', 'programming', 'program',
        'programs', 'code', 'generation', 'optimization', 'optimizing',
        'analysis', 'performance', 'high', 'fast', 'efficient', 'thesis'}


def gh(path, token):
    req = urllib.request.Request(
        f'https://api.github.com{path}',
        headers={'authorization': f'Bearer {token}',
                 'accept': 'application/vnd.github+json',
                 'user-agent': 'nextgen-own-repos'})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def fold(s):
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9 ]', ' ', s.lower())


def tokens(s):
    return {t for t in fold(s).split() if len(t) > 2 and t not in STOP}


def known_owners():
    """Own-group owners only: orgs/accounts holding a verified own_group
    repo. Third-party and descendant repo owners are OUTSIDE groups and
    would flood the pool (the first run pulled in Xilinx et al.)."""
    owners = set()
    verified = json.load(open(f'{ROOT}/harvest/repos/verified.json'))
    for rows in verified.values():
        for r in rows:
            if not r.get('own_group') or r.get('role') == 'third_party':
                continue
            m = re.search(r'github\.com/([^/]+)/', r.get('url', '') + '/')
            if m:
                owners.add(m.group(1))
    owners.add('mit-commit')  # the group's own GitHub org
    return sorted(owners, key=str.lower)


def fetch(token):
    pool = json.load(open(POOL)) if os.path.exists(POOL) else {}
    for owner in known_owners():
        if owner in pool:
            continue
        repos, page = [], 1
        try:
            while True:
                batch = gh(f'/users/{owner}/repos?per_page=100&page={page}'
                           '&sort=pushed', token)
                for r in batch:
                    repos.append({
                        'full_name': r['full_name'],
                        'description': r.get('description'),
                        'stars': r.get('stargazers_count'),
                        'created': (r.get('created_at') or '')[:4],
                        'pushed': (r.get('pushed_at') or '')[:4],
                        'fork': bool(r.get('fork')),
                        'archived': bool(r.get('archived')),
                    })
                if len(batch) < 100:
                    break
                page += 1
        except urllib.error.HTTPError as exc:
            print(f'  {owner}: HTTP {exc.code}')
        pool[owner] = repos
        print(f'  {owner}: {len(repos)} repos')
        time.sleep(0.3)
    json.dump(pool, open(POOL, 'w'), indent=1)
    total = sum(len(v) for v in pool.values())
    print(f'{len(pool)} owners, {total} repos in the pool')


def match():
    pool = json.load(open(POOL))
    pubs = json.load(open(f'{ROOT}/data/publications.json'))
    have = set(json.load(open(f'{ROOT}/data/repos/index.json'))['papers'])
    known = set()
    verified = json.load(open(f'{ROOT}/harvest/repos/verified.json'))
    for rows in verified.values():
        for r in rows:
            m = re.search(r'github\.com/([^/]+/[^/#?]+)', r.get('url', ''))
            if m:
                known.add(m.group(1).lower().removesuffix('.git'))

    own = set(known_owners())
    flat = [r for owner, rs in pool.items() if owner in own for r in rs
            if not r['fork'] and r['full_name'].lower() not in known]

    cands = []
    for p in pubs:
        key = p.get('bibtexKey')
        title_t = tokens(p.get('title'))
        year = int(p.get('year') or 0)
        authors = fold(p.get('author') or p.get('authors') or '')
        surnames = {w for w in authors.split() if len(w) > 3}
        for r in flat:
            hay_t = tokens(r['full_name'].split('/')[1] + ' ' + (r['description'] or ''))
            overlap = title_t & hay_t
            owner_l = fold(r['full_name'].split('/')[0]).replace(' ', '')
            owner_is_author = any(sn in owner_l for sn in surnames)
            created = int(r['created'] or 0)
            in_window = year and created and (year - 4 <= created <= year + 2)
            score = 0
            score += 2 * len(overlap)
            score += 3 if owner_is_author else 0
            score += 1 if in_window else 0
            if score >= 4 and overlap:
                cands.append({
                    'key': key, 'year': year, 'title': p.get('title'),
                    'repo': r['full_name'], 'stars': r['stars'],
                    'created': r['created'], 'desc': r['description'],
                    'score': score, 'overlap': sorted(overlap),
                    'owner_is_author': owner_is_author,
                    'paper_has_repo_already': key in have,
                })
    cands.sort(key=lambda c: (-c['score'], c['key']))
    # keep the best few per paper and per repo
    per_paper = collections.Counter()
    kept = []
    for c in cands:
        if per_paper[c['key']] >= 4:
            continue
        per_paper[c['key']] += 1
        kept.append(c)
    json.dump(kept, open(OUT, 'w'), indent=1, ensure_ascii=False)

    new_papers = {c['key'] for c in kept if not c['paper_has_repo_already']}
    with open(REPORT, 'w') as fh:
        fh.write('# Own-repo inventory — phase A candidates\n\n')
        fh.write(f'Pool: {len(flat)} non-fork repos across {len(pool)} known '
                 f'owners, minus {len(known)} already-verified repos.\n'
                 f'{len(kept)} candidate matches; {len(new_papers)} papers '
                 'would gain their first repo.\n\n'
                 'Score: 2/title-token overlap + 3 owner-is-author + '
                 '1 created-within-window. Mechanical only — review before '
                 'anything ships.\n\n')
        for c in kept:
            flag = '' if c['paper_has_repo_already'] else ' **[NEW]**'
            fh.write(f"- `{c['key']}` ({c['year']}){flag} ← "
                     f"**{c['repo']}** ({c['stars']}★, created {c['created']}) "
                     f"score {c['score']}, overlap: {', '.join(c['overlap'])}"
                     f"{' , owner-is-author' if c['owner_is_author'] else ''}\n"
                     f"    - {c['desc'] or '(no description)'}\n")
    print(f'{len(kept)} candidates ({len(new_papers)} papers would gain '
          f'their first repo) -> {OUT}\nreport -> {REPORT}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fetch', action='store_true')
    ap.add_argument('--match', action='store_true')
    args = ap.parse_args()
    if args.fetch:
        token = os.environ.get('GITHUB_TOKEN') or sys.exit('need GITHUB_TOKEN')
        fetch(token)
    if args.match:
        match()
    if not (args.fetch or args.match):
        print(__doc__)


if __name__ == '__main__':
    main()
