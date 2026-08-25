#!/usr/bin/env python3
"""Own-repo inventory phase B: personal-account hunt.

Phase A (find_own_repos.py) enumerated repos of the 121 already-known
own-group orgs/accounts. This covers the harder gap: papers whose repo
lives under a personal GitHub account we've never seen in
harvest/repos/verified.json -- mostly student authors and theses.

Population: the 191 papers absent from data/repos/index.json's "papers"
list. 163 of those already have a harvest/repos/search-plan.json entry
(built for the original repo-search pass) with guessed usernames per
author (surname, first-initial+surname, etc.); the other 28 are papers
added after that plan was built, so their author surnames come straight
from publications.json's `author0` field and guesses are generated here.

    python3 harvest/impactview/hunt_personal_repos.py --fetch   # check guessed usernames exist, enumerate their repos (core API, cheap)
    python3 harvest/impactview/hunt_personal_repos.py --match   # score candidates -> personal-repo-candidates.json + report

Candidates are mechanical only, same as phase A -- nothing here is
accepted until the model-verification pass (hunt_own_repos_verify.py)
judges both this phase's candidates and phase A's own-repo-candidates.json
together.
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
from find_own_repos import fold, tokens  # noqa: E402

ORG_POOL = os.path.join(HERE, 'owner-repos.json')          # phase A's cache (read-only here)
PERSONAL_POOL = os.path.join(HERE, 'personal-repos-pool.json')  # this phase's cache
OUT = os.path.join(HERE, 'personal-repo-candidates.json')
REPORT = os.path.join(HERE, 'personal-repo-report.md')

UA = 'nextgen-hunt-personal-repos'


def gh(path, token):
    req = urllib.request.Request(
        f'https://api.github.com{path}',
        headers={'authorization': f'Bearer {token}',
                 'accept': 'application/vnd.github+json',
                 'user-agent': UA})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.getcode(), json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return 404, None
            if exc.code in (403, 429):
                reset = exc.headers.get('X-RateLimit-Reset')
                wait = max(1.0, float(reset) - time.time()) if reset else 30.0
                time.sleep(min(wait, 90))
                continue
            return exc.code, None
        except Exception:
            time.sleep(2 * (attempt + 1))
    return None, None


def repo_less_papers():
    idx = json.load(open(f'{ROOT}/data/repos/index.json'))
    have = set(idx['papers'])
    pubs = json.load(open(f'{ROOT}/data/publications.json'))
    return [p for p in pubs if p['bibtexKey'] not in have]


def surname_guesses(author0):
    """Same handle shapes search-plan.json's username_candidates uses,
    for the 28 papers built after that plan existed."""
    guesses = []
    for author in (author0 or '').split(' and '):
        author = author.strip()
        if ',' in author:
            # "Surname, First [Middle]"
            last, first_part = author.split(',', 1)
            surname = fold(last).strip().replace(' ', '')
            first = fold(first_part).strip().split()[0] if fold(first_part).strip() else ''
        else:
            # "First [Middle] Surname"
            words = author.split()
            surname = fold(words[-1]).strip() if words else ''
            first = fold(words[0]).strip() if len(words) > 1 else ''
        if len(surname) < 3:
            continue
        guesses.append(surname)
        if first:
            guesses.append(first[0] + surname)
            guesses.append(first + surname)
            guesses.append(first + '-' + surname)
            guesses.append(first + '_' + surname)
    return list(dict.fromkeys(guesses))


def candidate_usernames(key, plan, pub):
    if plan:
        return list(dict.fromkeys(plan.get('username_candidates') or []))
    return surname_guesses(pub.get('author0'))


def fetch(token):
    plans = json.load(open(f'{ROOT}/harvest/repos/search-plan.json'))
    org_pool = json.load(open(ORG_POOL))
    pool = json.load(open(PERSONAL_POOL)) if os.path.exists(PERSONAL_POOL) else {}

    papers = repo_less_papers()
    all_usernames = set()
    for p in papers:
        key = p['bibtexKey']
        all_usernames.update(candidate_usernames(key, plans.get(key), p))

    todo = sorted(u for u in all_usernames if u and u not in org_pool and u not in pool)
    print(f'{len(all_usernames)} distinct username guesses, {len(org_pool)} already in the '
          f'phase-A org pool, {len(pool)} already checked this phase, {len(todo)} to check')

    checked_this_run = found = 0
    for i, username in enumerate(todo, 1):
        code, data = gh(f'/users/{username}', token)
        if code != 200 or not data:
            pool[username] = None  # confirmed not a real account (or inaccessible)
        else:
            repos, page = [], 1
            while True:
                rcode, batch = gh(f'/users/{username}/repos?per_page=100&page={page}&sort=pushed', token)
                if not batch:
                    break
                repos.extend({
                    'full_name': r['full_name'], 'description': r.get('description'),
                    'stars': r.get('stargazers_count'),
                    'created': (r.get('created_at') or '')[:4],
                    'fork': bool(r.get('fork')),
                } for r in batch if not r.get('fork'))
                if len(batch) < 100:
                    break
                page += 1
            pool[username] = repos
            found += 1
        checked_this_run += 1
        if i % 50 == 0 or i == len(todo):
            print(f'  [{i}/{len(todo)}] {found} real accounts found so far', flush=True)
            with open(PERSONAL_POOL + '.tmp', 'w') as fh:
                json.dump(pool, fh, indent=1)
            os.replace(PERSONAL_POOL + '.tmp', PERSONAL_POOL)

    with open(PERSONAL_POOL + '.tmp', 'w') as fh:
        json.dump(pool, fh, indent=1)
    os.replace(PERSONAL_POOL + '.tmp', PERSONAL_POOL)
    print(f'\n{checked_this_run} checked this run, {found} real accounts found this run')
    print(f'pool now covers {len(pool)} personal usernames (including confirmed-absent ones)')


def match():
    plans = json.load(open(f'{ROOT}/harvest/repos/search-plan.json'))
    org_pool = json.load(open(ORG_POOL))
    personal_pool = json.load(open(PERSONAL_POOL))
    verified = json.load(open(f'{ROOT}/harvest/repos/verified.json'))
    known_repos = set()
    for rows in verified.values():
        for r in rows:
            m = re.search(r'github\.com/([^/]+/[^/#?]+)', r.get('url', ''))
            if m:
                known_repos.add(m.group(1).lower().removesuffix('.git'))

    papers = repo_less_papers()
    cands = []
    for p in papers:
        key = p['bibtexKey']
        year = int(p.get('year') or 0)
        title_t = tokens(p.get('title'))
        usernames = candidate_usernames(key, plans.get(key), p)
        for username in usernames:
            repos = org_pool.get(username) if username in org_pool else personal_pool.get(username)
            if not repos:
                continue
            for r in repos:
                if r['full_name'].lower() in known_repos:
                    continue
                hay_t = tokens(r['full_name'].split('/')[1] + ' ' + (r['description'] or ''))
                overlap = title_t & hay_t
                created = int(r['created'] or 0)
                in_window = year and created and (year - 4 <= created <= year + 2)
                score = 2 * len(overlap) + (1 if in_window else 0)
                if score >= 2 and overlap:
                    cands.append({
                        'key': key, 'year': year, 'title': p.get('title'),
                        'repo': r['full_name'], 'stars': r['stars'],
                        'created': r['created'], 'desc': r['description'],
                        'score': score, 'overlap': sorted(overlap),
                        'source': 'personal-account',
                    })
    cands.sort(key=lambda c: (-c['score'], c['key']))
    per_paper = {}
    kept = []
    for c in cands:
        if per_paper.get(c['key'], 0) >= 3:
            continue
        per_paper[c['key']] = per_paper.get(c['key'], 0) + 1
        kept.append(c)

    with open(OUT, 'w') as fh:
        json.dump(kept, fh, indent=1, ensure_ascii=False)
    papers_covered = len({c['key'] for c in kept})
    with open(REPORT, 'w') as fh:
        fh.write('# Own-repo inventory -- phase B personal-account candidates\n\n')
        fh.write(f'{len(kept)} candidates across {papers_covered} of {len(papers)} '
                 'repo-less papers, via personal-account repo listings '
                 '(guessed usernames confirmed to exist, all their non-fork repos '
                 'scored by title-token overlap).\n\n')
        for c in kept:
            fh.write(f"- `{c['key']}` ({c['year']}) <- **{c['repo']}** "
                     f"({c['stars']}★, created {c['created']}) score {c['score']}, "
                     f"overlap: {', '.join(c['overlap'])}\n"
                     f"    - {c['desc'] or '(no description)'}\n")
    print(f'{len(kept)} candidates across {papers_covered} papers -> {OUT}\nreport -> {REPORT}')


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
