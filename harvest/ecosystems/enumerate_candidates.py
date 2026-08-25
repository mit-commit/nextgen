#!/usr/bin/env python3
"""Ecosystems VERIFY step, part 1: enumerate actual candidate identities
behind nextgen-a2's MEASURE counts (harvest/impactview/ecosystem-
measure.json, 52 own repos, 810 raw dependents+mentions candidates,
pushed in ba11eb56).

That file has sizes only, not identities (by design -- MEASURE is
free/mechanical sizing, VERIFY needs the real candidates). This script
fetches the actual repos behind each count:

  1. dependents -- scrape github.com/{repo}/network/dependents
     (?dependent_type=REPOSITORY, 30 rows/page, cursor-paginated via
     `dependents_after`).
  2. mentions -- the same repo-search query nextgen-a2's MEASURE step
     used to get the count (`"{repo}" in:name,description,readme
     fork:false`), paginated for real hits this time.
  3. forks-with-divergence (this session's addition, not in nextgen-a2's
     MEASURE signals): re-scan each repo's forks (top 300 by stars, same
     as harvest/ecosystems/measure_candidates.py's proxy scan) and run
     the real compare API (`/repos/{owner}/{repo}/compare/{default}...
     {fork_owner}:{fork_default}`) on ones pushed >30 days after their
     own creation -- a free, mechanical way to separate "genuinely ahead
     of upstream" forks from "stale mirror that just got a sync push"
     before spending any model call on them. Only forks with a positive
     real `ahead_by` become candidates.

Dedupes candidates per repo (by full_name), excludes the repo's own
name and any already-known own-group owner (find_own_repos.py's
known_owners() -- those are covered by the own-repo hunt, not outside
users). Caps each repo's candidate list at 300 by stars, honestly
reporting how many were trimmed.

Output: harvest/ecosystems/candidates.json
  { "owner/repo": [ {"repo": "a/b", "stars": N, "description": "...",
                     "source": ["dependents"|"mentions"|"fork-divergence", ...],
                     "ahead_by": N (forks only)} ... ] }

    python3 harvest/ecosystems/enumerate_candidates.py
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'harvest', 'impactview'))
from find_own_repos import known_owners  # noqa: E402

MEASURE = os.path.join(ROOT, 'harvest', 'impactview', 'ecosystem-measure.json')
OUT = os.path.join(HERE, 'candidates.json')

UA = 'nextgen-ecosystems-enumerate/1.0'
CAP_PER_REPO = 300
FORK_SCAN_CAP = 300


def token():
    return os.environ.get('GITHUB_TOKEN') or sys.exit('need GITHUB_TOKEN')


def gh_core(path):
    req = urllib.request.Request(
        f'https://api.github.com{path}',
        headers={'authorization': f'Bearer {token()}',
                 'accept': 'application/vnd.github+json', 'user-agent': UA})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            if exc.code in (403, 429):
                reset = exc.headers.get('X-RateLimit-Reset')
                wait = max(1.0, float(reset) - time.time()) if reset else 30.0
                time.sleep(min(wait, 90))
                continue
            return None
        except Exception:
            time.sleep(2 * (attempt + 1))
    return None


_last_search = 0.0


def gh_search_repos(query, page):
    global _last_search
    gap = time.time() - _last_search
    if gap < 2.2:
        time.sleep(2.2 - gap)
    _last_search = time.time()
    url = ('https://api.github.com/search/repositories?' +
          urllib.parse.urlencode({'q': query, 'per_page': 100, 'page': page}))
    req = urllib.request.Request(url, headers={
        'authorization': f'Bearer {token()}', 'accept': 'application/vnd.github+json', 'user-agent': UA})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 429):
                reset = exc.headers.get('X-RateLimit-Reset')
                wait = max(1.0, float(reset) - time.time()) if reset else 60.0
                time.sleep(min(wait, 90))
                _last_search = time.time()
                continue
            return None
        except Exception:
            time.sleep(2 * (attempt + 1))
    return None


def scrape_dependents(owner, name, expected_count):
    if not expected_count:
        return []
    out, cursor, pages = [], None, 0
    while pages < 12:  # 12*30=360, comfortably above any observed count
        url = f'https://github.com/{owner}/{name}/network/dependents?dependent_type=REPOSITORY'
        if cursor:
            url += f'&dependents_after={cursor}'
        req = urllib.request.Request(url, headers={'user-agent': 'Mozilla/5.0 ' + UA})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                html = resp.read().decode('utf-8', 'replace')
        except Exception:
            break
        rows = re.findall(
            r'data-hovercard-type="repository" data-hovercard-url="/([^/"]+/[^/"]+)/hovercard"',
            html)
        if not rows:
            break
        # star count is the first octicon-star number after each repo link in its Box-row
        for full_name in dict.fromkeys(rows):  # de-dup within page, preserve order
            out.append({'repo': full_name, 'stars': None, 'description': None,
                       'source': ['dependents']})
        m = re.search(r'dependents_after=([^"&]+)', html)
        if not m or len(out) >= expected_count:
            break
        cursor = m.group(1)
        pages += 1
        time.sleep(1.0)
    return out[:expected_count + 5]


def search_mentions(owner, name, expected_count):
    if not expected_count:
        return []
    query = f'"{owner}/{name}" in:name,description,readme fork:false'
    out = []
    for page in range(1, 4):  # 3*100=300, our cap
        data = gh_search_repos(query, page)
        if not data or not data.get('items'):
            break
        for item in data['items']:
            out.append({'repo': item['full_name'], 'stars': item.get('stargazers_count'),
                       'description': item.get('description'), 'source': ['mentions']})
        if len(data['items']) < 100:
            break
    return out


def fork_divergence_candidates(owner, name):
    forks_meta = gh_core(f'/repos/{owner}/{name}')
    if not forks_meta or not forks_meta.get('forks_count'):
        return []
    default_branch = forks_meta.get('default_branch', 'main')
    proxy_hits = []
    for page in range(1, (FORK_SCAN_CAP // 100) + 1):
        batch = gh_core(f'/repos/{owner}/{name}/forks?sort=stargazers&per_page=100&page={page}')
        if not batch:
            break
        for f in batch:
            created, pushed = f.get('created_at'), f.get('pushed_at')
            if created and pushed and pushed > created:
                try:
                    dt_c = datetime.fromisoformat(created.replace('Z', '+00:00'))
                    dt_p = datetime.fromisoformat(pushed.replace('Z', '+00:00'))
                    if (dt_p - dt_c).days > 30:
                        proxy_hits.append(f)
                except ValueError:
                    pass
        if len(batch) < 100:
            break

    out = []
    for f in proxy_hits:
        fork_owner = f['owner']['login']
        fork_branch = f.get('default_branch', default_branch)
        cmp = gh_core(f'/repos/{owner}/{name}/compare/{default_branch}...{fork_owner}:{fork_branch}')
        if not cmp:
            continue
        ahead = cmp.get('ahead_by', 0)
        if ahead and ahead > 0:
            out.append({'repo': f['full_name'], 'stars': f.get('stargazers_count'),
                       'description': f.get('description'), 'source': ['fork-divergence'],
                       'ahead_by': ahead})
    return out


def main():
    measure = json.load(open(MEASURE))
    own_owners = {o.lower() for o in known_owners()}
    out = json.load(open(OUT)) if os.path.exists(OUT) else {}

    for i, (repo, sizes) in enumerate(sorted(measure.items()), 1):
        if repo in out:
            continue
        owner, name = repo.split('/', 1)
        cands = {}

        for c in scrape_dependents(owner, name, sizes.get('dependents') or 0):
            key = c['repo'].lower()
            if key == repo.lower() or c['repo'].split('/')[0].lower() in own_owners:
                continue
            cands.setdefault(key, c)

        for c in search_mentions(owner, name, sizes.get('mentions') or 0):
            key = c['repo'].lower()
            if key == repo.lower() or c['repo'].split('/')[0].lower() in own_owners:
                continue
            if key in cands:
                cands[key]['source'] = list(set(cands[key]['source'] + ['mentions']))
                cands[key]['stars'] = cands[key]['stars'] or c['stars']
                cands[key]['description'] = cands[key]['description'] or c['description']
            else:
                cands[key] = c

        for c in fork_divergence_candidates(owner, name):
            key = c['repo'].lower()
            if key == repo.lower() or c['repo'].split('/')[0].lower() in own_owners:
                continue
            if key in cands:
                cands[key]['source'] = list(set(cands[key]['source'] + ['fork-divergence']))
                cands[key]['ahead_by'] = c.get('ahead_by')
            else:
                cands[key] = c

        merged = sorted(cands.values(), key=lambda c: (c['stars'] or 0), reverse=True)
        trimmed = len(merged) - CAP_PER_REPO if len(merged) > CAP_PER_REPO else 0
        capped = merged[:CAP_PER_REPO]
        out[repo] = {'candidates': capped, 'trimmed_unverified': trimmed}
        print(f'[{i}/{len(measure)}] {repo}: {len(merged)} candidates '
             f'({trimmed} trimmed, unverified)', flush=True)
        with open(OUT + '.tmp', 'w') as fh:
            json.dump(out, fh, indent=1, ensure_ascii=False)
        os.replace(OUT + '.tmp', OUT)

    total = sum(len(v['candidates']) for v in out.values())
    total_trimmed = sum(v['trimmed_unverified'] for v in out.values())
    print(f'\n{total} total candidates to verify across {len(out)} repos '
         f'({total_trimmed} trimmed as unverified)')
    print(f'wrote {OUT}')


if __name__ == '__main__':
    main()
