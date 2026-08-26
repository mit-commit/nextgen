#!/usr/bin/env python3
"""Build data/impact-authors.json -- the "Cited and Used by" facet.

External people who cite one of our papers at real depth (citation
centrality core/engaged -- peripheral list-mentions are excluded, same
signal-worthy bar the corpus already uses for tier-3 idea-descendants)
or use one of our own repos (data/repos/ group in uses/builds-on/
benchmarks/adopts). Anyone who is themselves an author of one of our own
papers is excluded from the citing side; anyone who owns one of our own
GitHub repos is excluded from the using side -- this is impact FROM
outside the group, not a second copy of the Authors facet.

Reads (read-only):
  data/publications.json, harvest/authors/authors.json   our own author set
  data/citations/<key>.json      the site's judged citation population
  harvest/citations/<key>.json   full author arrays for those same works
  data/repos/papers/<key>.json   the site's repo relationship rows
  harvest/repos/verified.json + own-inventory.json   own-repo owner logins

Writes data/impact-authors.json:
  { schema: 1, generated,
    people: [ {name, count, papers: [key, ...], viaCites: n, viaUses: n}, ... ] }
`count` is the number of OUR papers this person cites or uses (union, not
sum -- citing and using the same paper counts once).

GitHub owner display names are resolved via GET /users/{login} (GITHUB_TOKEN),
cached in harvest/impactview/owner-profiles.json; a login with no real
`name` set falls back to the login/org name itself.

    python3 harvest/impactview/build_impact_authors.py            # report
    python3 harvest/impactview/build_impact_authors.py --write    # write
"""
import argparse
import glob
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT_PATH = os.path.join(ROOT, 'data', 'impact-authors.json')
PROFILES_PATH = os.path.join(HERE, 'owner-profiles.json')
CENTRALITY_OK = {'core', 'engaged'}
GROUP_OK = {'uses', 'builds-on', 'benchmarks', 'adopts'}
SKIP_CITE_FILES = {'index.json', 'reception.json', 'gscholar.json', 'citers.json'}


def fold(name):
    n = unicodedata.normalize('NFKD', name or '')
    n = ''.join(c for c in n if not unicodedata.combining(c))
    n = re.sub(r'[^a-z ]', ' ', n.lower())
    return re.sub(r'\s+', ' ', n).strip()


def first_last(name):
    # ignores middle names/initials -- "Saman Amarasinghe" must match
    # "Saman P. Amarasinghe", "Mary Hall" must match "Mary W. Hall"; a
    # bare surname+initial match is deliberately NOT used (false-positive
    # risk on common names, per harvest/authors/authors_build.py's own
    # documented reasoning), but exact first+last is safe and is the
    # actual failure mode seen here.
    toks = fold(name).split()
    return (toks[0], toks[-1]) if len(toks) >= 2 else None


def own_author_names():
    people = json.load(open(f'{ROOT}/harvest/authors/authors.json'))
    exact, fl = set(), set()
    for p in people:
        for nm in [p['name']] + (p.get('variants') or []):
            f = fold(nm)
            if f:
                exact.add(f)
            pair = first_last(nm)
            if pair:
                fl.add(pair)
    return exact, fl


def is_own_author(name, exact, fl):
    f = fold(name)
    if not f:
        return True  # empty/unparseable -- never show as a "person"
    if f in exact:
        return True
    pair = first_last(name)
    return pair in fl if pair else False


def own_repo_owners():
    owners = set()
    for path in (f'{ROOT}/harvest/repos/verified.json', f'{ROOT}/harvest/repos/own-inventory.json'):
        if not os.path.exists(path):
            continue
        for rows in json.load(open(path)).values():
            for r in rows:
                if r.get('own_group'):
                    m = re.match(r'https?://github\.com/([^/]+)/', r.get('url') or '')
                    if m:
                        owners.add(m.group(1).lower())
    return owners


def cite_ident(c):
    url = (c.get('url') or '').lower()
    m = re.search(r'doi\.org/(10\.\S+)', url)
    if m:
        return 'd:' + m.group(1).rstrip('/.')
    t = fold(c.get('title') or '').replace(' ', '')
    return 't:' + t if t else None


def load_harvest_author_index():
    """ident (doi/title) -> full author list, from harvest/citations/*.json."""
    index = {}
    for path in glob.glob(f'{ROOT}/harvest/citations/*.json'):
        d = json.load(open(path))
        for c in d.get('citing', []):
            k = cite_ident(c)
            if k and c.get('authors'):
                index[k] = c['authors']
    return index


def fallback_authors(display):
    # "Gengyu Rao, Jingji Chen, Jason Yik et al." -> best-effort name list;
    # used only when the full-harvest author array can't be matched.
    s = re.sub(r'\s*et al\.?\s*$', '', display or '', flags=re.I)
    return [p.strip() for p in s.split(',') if p.strip()]


def gh_user(login, cache, token):
    if login in cache:
        return cache[login]
    req = urllib.request.Request(
        f'https://api.github.com/users/{login}',
        headers={'authorization': f'Bearer {token}', 'accept': 'application/vnd.github+json',
                 'user-agent': 'nextgen-impact-authors'})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            d = json.loads(resp.read().decode())
        cache[login] = {'name': d.get('name'), 'login': d.get('login') or login}
    except urllib.error.HTTPError as exc:
        cache[login] = {'name': None, 'login': login, 'error': exc.code}
    except Exception as exc:
        cache[login] = {'name': None, 'login': login, 'error': type(exc).__name__}
    time.sleep(0.1)
    return cache[login]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--generated', default='2026-08-26')
    args = ap.parse_args()

    own_exact, own_fl = own_author_names()
    own_owners = own_repo_owners()
    harvest_idx = load_harvest_author_index()

    # people[name] -> {papers: set(key), viaCites: set(key), viaUses: set(key)}
    people = {}

    def add(name, key, via):
        name = ' '.join(name.split())
        if len(fold(name)) < 2 or is_own_author(name, own_exact, own_fl):
            return  # too short to be a real name (stray initial, parse noise)
        e = people.setdefault(name, {'papers': set(), 'viaCites': set(), 'viaUses': set()})
        e['papers'].add(key)
        e[via].add(key)

    n_cite_records = 0
    for path in glob.glob(f'{ROOT}/data/citations/*.json'):
        if os.path.basename(path) in SKIP_CITE_FILES:
            continue
        d = json.load(open(path))
        key = d['key']
        for c in d.get('citations', []):
            if c.get('centrality') not in CENTRALITY_OK:
                continue
            n_cite_records += 1
            ci = cite_ident(c)
            names = harvest_idx.get(ci) if ci else None
            if not names:
                names = fallback_authors(c.get('authors'))
            for nm in names:
                add(nm, key, 'viaCites')

    token = os.environ.get('GITHUB_TOKEN', '').strip()
    profiles = json.load(open(PROFILES_PATH)) if os.path.exists(PROFILES_PATH) else {}
    n_use_rows = 0
    for path in glob.glob(f'{ROOT}/data/repos/papers/*.json'):
        d = json.load(open(path))
        key = d['key']
        for r in d.get('repos', []):
            if r.get('group') not in GROUP_OK:
                continue
            m = re.match(r'https?://github\.com/([^/]+)/', r.get('url') or '')
            if not m:
                continue
            login = m.group(1).lower()
            if login in own_owners:
                continue
            n_use_rows += 1
            prof = gh_user(login, profiles, token) if token else {'name': None, 'login': login}
            add(prof.get('name') or prof.get('login') or login, key, 'viaUses')

    if token:
        json.dump(profiles, open(PROFILES_PATH, 'w'), indent=1)

    # human-reviewable name qualifications (qualify_impact_authors.py):
    # rename merges into the target (counts union), drop removes
    ov_path = os.path.join(HERE, 'author-overrides.json')
    overrides = json.load(open(ov_path)) if os.path.exists(ov_path) else {}
    merged = {}
    n_dropped = n_renamed = 0
    for name, e in people.items():
        o = overrides.get(name)
        if o and o.get('action') == 'drop':
            n_dropped += 1
            continue
        final = o['to'] if (o and o.get('action') == 'rename' and o.get('to')) else name
        if final != name:
            n_renamed += 1
        t = merged.setdefault(final, {'papers': set(), 'viaCites': set(), 'viaUses': set()})
        t['papers'] |= set(e['papers'])
        t['viaCites'] |= set(e['viaCites'])
        t['viaUses'] |= set(e['viaUses'])
    if overrides:
        print(f'overrides: {n_renamed} renamed, {n_dropped} dropped')
    people = merged

    out_people = []
    for name, e in people.items():
        out_people.append({
            'name': name,
            'count': len(e['papers']),
            'papers': sorted(e['papers']),
            'viaCites': len(e['viaCites']),
            'viaUses': len(e['viaUses']),
        })
    out_people.sort(key=lambda p: (-p['count'], p['name'].lower()))

    print(f'{n_cite_records} core/engaged citation records, {n_use_rows} used-by repo rows scanned')
    print(f'{len(out_people)} distinct external people '
         f'({sum(1 for p in out_people if p["viaCites"]):,} via citing, '
         f'{sum(1 for p in out_people if p["viaUses"]):,} via using, '
         f'{sum(1 for p in out_people if p["viaCites"] and p["viaUses"]):,} both)')

    if args.write:
        with open(OUT_PATH, 'w') as fh:
            json.dump({'schema': 1, 'generated': args.generated, 'people': out_people},
                     fh, indent=1, ensure_ascii=False)
            fh.write('\n')
        print(f'wrote {OUT_PATH}')
    else:
        print('report only (use --write)')


if __name__ == '__main__':
    main()
