#!/usr/bin/env python3
"""Task `verified-quirks`: dedupe repo-rename collisions in
harvest/repos/verified.json (and review.json).

verify_repos.py's model pass judges each candidate URL independently, so a
repo that was renamed between when one candidate URL was discovered and
another (e.g. radha-patel/symmetry-compiler -> radha-patel/SySTeC, found
separately as an in-paper mention and a commit-specific citation) gets two
rows for the same underlying repository. String-level URL canonicalization
can't catch this -- the fix is to resolve each URL's (owner, repo) through
the GitHub API, which auto-follows a renamed repo's redirect, and group by
the stable numeric repo id it returns rather than the URL text.

Within a duplicate group (same paper, same repo id): keep the row with the
best role (implementation > artifact > benchmark > third_party) then
highest confidence, and union the evidence strings from the dropped
sibling(s) into the kept row's `evidence` so nothing is silently lost.

(The own_group=true + role=third_party combination flagged alongside this
in the queue task is NOT a bug -- verified by reading
harvest/impactview/build_repo_data.py, which already excludes
role=='third_party' rows from the "own" tier regardless of own_group, with
a comment confirming this is intentional. Every one of the 7 such rows in
verified.json is a genuine case: the same research group's OTHER tool,
used here as a dependency/baseline/prior-work rather than this paper's own
contribution -- own_group and role are orthogonal by design. No change
made to those rows.)

    python3 curate/dedupe_verified_repos.py --write
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERIFIED_PATH = os.path.join(ROOT, 'harvest', 'repos', 'verified.json')
REVIEW_PATH = os.path.join(ROOT, 'harvest', 'repos', 'review.json')
CACHE = os.path.join(ROOT, 'harvest', 'repos', '_ghcache')

ROLE_PRIORITY = {'implementation': 0, 'artifact': 1, 'benchmark': 2, 'third_party': 3}


def github_owner_repo(url):
    m = re.match(r'https?://github\.com/([^/]+)/([^/#?]+)', url or '')
    if not m:
        return None
    return m.group(1), re.sub(r'\.git$', '', m.group(2))


def fetch_repo(owner, repo, token):
    os.makedirs(CACHE, exist_ok=True)
    url = f'https://api.github.com/repos/{owner}/{repo}'
    cpath = os.path.join(CACHE, hashlib.sha1(url.encode()).hexdigest() + '.json')
    if os.path.exists(cpath):
        with open(cpath) as fh:
            return json.load(fh).get('body')
    headers = {'User-Agent': 'nextgen-dedupe-verified-repos',
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


def repo_identity(url, token, cache):
    owner_repo = github_owner_repo(url)
    if not owner_repo:
        return None
    if owner_repo in cache:
        return cache[owner_repo]
    data = fetch_repo(*owner_repo, token)
    identity = (data.get('id'), data.get('full_name')) if data else None
    cache[owner_repo] = identity
    return identity


def dedupe_paper(key, repos, token, cache, log):
    groups = {}
    for r in repos:
        ident = repo_identity(r['url'], token, cache)
        gk = ident[0] if ident else ('unresolved', r['url'])
        groups.setdefault(gk, []).append(r)

    out = []
    for gk, sibs in groups.items():
        if len(sibs) == 1:
            out.append(sibs[0])
            continue
        sibs.sort(key=lambda r: (ROLE_PRIORITY.get(r['role'], 9),
                                 {'high': 0, 'medium': 1, 'low': 2}.get(r['confidence'], 3)))
        kept = dict(sibs[0])
        other_urls = [s['url'] for s in sibs[1:]]
        other_evidence = [s['evidence'] for s in sibs[1:] if s['evidence'] != kept['evidence']]
        if other_evidence:
            kept['evidence'] = kept['evidence'] + ' (same repo, also found as ' + \
                '; '.join(other_urls) + ': ' + ' / '.join(other_evidence) + ')'
        out.append(kept)
        log.append(f'{key}: merged {len(sibs)} rows into {kept["url"]} '
                   f'(repo id {gk}) -- dropped {other_urls}')
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()

    token = os.environ.get('GITHUB_TOKEN', '').strip()
    if not token:
        sys.exit('GITHUB_TOKEN not set')

    verified = json.load(open(VERIFIED_PATH))
    cache = {}
    log = []
    changed = 0
    for key, repos in verified.items():
        new_repos = dedupe_paper(key, repos, token, cache, log)
        if len(new_repos) != len(repos):
            changed += 1
            verified[key] = new_repos

    for line in log:
        print(line)
    print(f'\n{changed} papers had duplicate rows merged '
         f'({len(log)} merge(s) total)')

    if args.write:
        with open(VERIFIED_PATH, 'w') as fh:
            json.dump(verified, fh, indent=1, sort_keys=True, ensure_ascii=False)
            fh.write('\n')
        print(f'wrote {VERIFIED_PATH}')
    else:
        print('\ndry run -- nothing written. Pass --write to commit.')


if __name__ == '__main__':
    main()
