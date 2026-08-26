#!/usr/bin/env python3
"""Qualify non-name-like entries in the "Cited and Used by" facet
(human, 2026-08-26: "ASSERT", "PKU ... Research Group", "10 Imaging
Inc.", "159336 at Massey" — find non-name-like names and do extra work
to qualify them).

    python3 harvest/impactview/qualify_impact_authors.py --screen
    python3 harvest/impactview/qualify_impact_authors.py --fetch     # GH profiles
    python3 harvest/impactview/qualify_impact_authors.py --submit [--dry-run]
    python3 harvest/impactview/qualify_impact_authors.py --status | --collect

Collect writes harvest/impactview/author-overrides.json:
  { "<display name>": {"action": "keep"|"rename"|"drop", "to": "...",
                       "kind": "person"|"organization"|"junk", "reason": "..."} }
build_impact_authors.py applies it at emit time (rename merges counts on
collision; drop removes). Human-overridable like embodiment.json.

Needs GITHUB_TOKEN for --fetch, ANTHROPIC_BATCH_KEY for submit/collect.
"""
import argparse
import glob
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
API = 'https://api.anthropic.com/v1'
MODEL = 'claude-sonnet-4-6'
FLAGGED = f'{HERE}/author-flagged.json'
QPROFILES = f'{HERE}/qualify-profiles.json'
STATE = f'{HERE}/qualify_state.json'
OUT = f'{HERE}/author-overrides.json'

ORG = re.compile(r'\b(inc|llc|ltd|corp|gmbh|co|group|lab|labs|laboratory|team|project'
                 r'|university|institute|research|dept|department|center|centre'
                 r'|foundation|systems|technologies|solutions|software|committee'
                 r'|consortium|association|society|community|org|organization)\b\.?', re.I)

SYSTEM = """You qualify one entry of a research group's "Cited and Used
by" list — external people and organizations who cite the group's papers
deeply or use its open-source systems. The entry's display name was
flagged as non-name-like. Using the evidence (GitHub profile when the
entry comes from repo usage: login, name, type User/Organization, bio,
company; the group's repos they use; their own repos' names and
descriptions; citing-work titles when from citations), decide:

- kind "person": a real individual. If the display name is a bare login
  or has junk around a real name, action "rename" with the best real
  name you can support from the evidence (e.g. "PKU Yun (Eric) Liang
  Research Group" -> "Yun (Eric) Liang"; a login whose profile or repos
  reveal the person's name -> that name). If only the login is known,
  action "keep" — an honest login beats a guessed name. NEVER invent a
  name.
- kind "organization": a genuine company/lab/institute account (e.g.
  "Adobe, Inc.", "Google Project Zero", "Stillwater Supercomputing,
  Inc."). These are legitimate users — action "keep" (or "rename" only
  to fix formatting). A lab named after its PI stays under the PI's name
  (rename) only when the evidence names the PI.
- kind "junk": course-assignment accounts, throwaway/numeric ids,
  malware-corpus mirrors, accounts whose usage is coursework rather than
  genuine adoption (e.g. "159336 at Massey" — a university course
  number). Action "drop".

Return ONLY JSON: {"action": "keep"|"rename"|"drop", "to": "<name if
rename>", "kind": "person"|"organization"|"junk", "reason": "<one
sentence>"}"""


def screen():
    d = json.load(open(f'{ROOT}/data/impact-authors.json'))
    flags = []
    for p in d['people']:
        n = p['name']
        why = []
        if re.search(r'\d', n): why.append('digits')
        if ORG.search(n): why.append('org-word')
        if len(n.split()) == 1 and not re.match(r'^[A-Z][a-z]+$', n): why.append('single-token')
        if re.search(r'\bat\b', n, re.I): why.append('at-pattern')
        if n.isupper() and len(n) > 2: why.append('all-caps')
        if re.search(r'[@/\\]', n): why.append('symbol')
        if why:
            flags.append({'name': n, 'count': p['count'], 'papers': p['papers'][:6],
                          'viaCites': p.get('viaCites', 0), 'viaUses': p.get('viaUses', 0),
                          'why': why})
    json.dump(flags, open(FLAGGED, 'w'), indent=1, ensure_ascii=False)
    print(f'{len(flags)} flagged -> {FLAGGED}')


def logins_for(display):
    """All cached logins whose display name matches."""
    prof = json.load(open(f'{HERE}/owner-profiles.json'))
    return [login for login, v in prof.items()
            if (v.get('name') or login) == display or login == display]


def gh(path, token):
    req = urllib.request.Request(f'https://api.github.com{path}', headers={
        'authorization': f'Bearer {token}', 'accept': 'application/vnd.github+json',
        'user-agent': 'nextgen-qualify'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def fetch():
    token = os.environ.get('GITHUB_TOKEN') or sys.exit('need GITHUB_TOKEN')
    flags = json.load(open(FLAGGED))
    cache = json.load(open(QPROFILES)) if os.path.exists(QPROFILES) else {}
    for f in flags:
        if not f.get('viaUses'):
            continue
        for login in logins_for(f['name']):
            if login in cache:
                continue
            try:
                u = gh(f'/users/{login}', token)
                cache[login] = {k: u.get(k) for k in
                                ('login', 'name', 'type', 'bio', 'company', 'blog')}
            except urllib.error.HTTPError as exc:
                cache[login] = {'error': exc.code}
            time.sleep(0.15)
    json.dump(cache, open(QPROFILES, 'w'), indent=1)
    print(f'{len(cache)} profiles cached')


def their_repos(logins):
    """This owner's repos as they appear in our relationship rows."""
    rows = []
    pref = tuple(l.lower() + '/' for l in logins)
    for path in glob.glob(f'{ROOT}/data/repos/papers/*.json'):
        for r in json.load(open(path))['repos']:
            nm = (r.get('name') or '').lower()
            if nm.startswith(pref):
                rows.append({'repo': r.get('name'), 'desc': r.get('desc'),
                             'uses': r.get('evidence', '')[:120]})
    seen, out = set(), []
    for r in rows:
        if r['repo'] not in seen:
            seen.add(r['repo'])
            out.append(r)
    return out[:6]


def build_packs():
    flags = json.load(open(FLAGGED))
    qprof = json.load(open(QPROFILES)) if os.path.exists(QPROFILES) else {}
    pubs = {p.get('bibtexKey'): p.get('title') for p in
            json.load(open(f'{ROOT}/data/publications.json'))}
    packs = []
    for f in flags:
        logins = logins_for(f['name']) if f.get('viaUses') else []
        packs.append({
            'name': f['name'], 'why_flagged': f['why'],
            'via_cites': f['viaCites'], 'via_uses': f['viaUses'],
            'github_profiles': [qprof.get(l) for l in logins if qprof.get(l)],
            'their_repos': their_repos(logins) if logins else [],
            'our_papers_engaged': [pubs.get(k, k) for k in f['papers']],
        })
    return packs


def cid_of(name):
    return 'qa-' + re.sub(r'[^A-Za-z0-9_-]', '_', name)[:56]


def call(method, path, payload=None, tries=6):
    key = os.environ.get('ANTHROPIC_BATCH_KEY')
    if not key:
        sys.exit('set ANTHROPIC_BATCH_KEY first (NOT ANTHROPIC_API_KEY)')
    url = path if path.startswith('http') else f'{API}{path}'
    body = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(url, data=body, method=method, headers={
        'x-api-key': key, 'anthropic-version': '2023-06-01',
        'content-type': 'application/json', 'user-agent': 'nextgen-qualify'})
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                return response.read().decode()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode()[:300]
            if exc.code in (429, 500, 502, 503, 504, 529):
                time.sleep(min(300, 10 * 2 ** attempt))
                continue
            sys.exit(f'{exc.code} {detail}')
        except Exception:
            time.sleep(20)
    sys.exit('gave up')


def main():
    ap = argparse.ArgumentParser()
    for a in ('screen', 'fetch', 'submit', 'dry-run', 'status', 'collect'):
        ap.add_argument('--' + a, action='store_true')
    args = ap.parse_args()
    if args.screen:
        screen()
    if args.fetch:
        fetch()
    if args.submit:
        packs = build_packs()
        reqs = [{'custom_id': cid_of(p['name']), 'params': {
                    'model': MODEL, 'max_tokens': 300, 'system': SYSTEM,
                    'messages': [{'role': 'user', 'content':
                                  json.dumps(p, ensure_ascii=False)}]}}
                for p in packs]
        size = sum(len(json.dumps(r)) for r in reqs)
        cost = (size / 4) / 1e6 * 3 / 2 + 120 * len(reqs) / 1e6 * 15 / 2
        print(f'{len(reqs)} requests, est ${cost:.2f} (batch)')
        if getattr(args, 'dry_run'):
            return
        if cost >= 20:
            sys.exit('>=$20: stop for approval')
        result = json.loads(call('POST', '/messages/batches', {'requests': reqs}))
        json.dump({'batch': result['id']}, open(STATE, 'w'))
        print('submitted', result['id'])
    if args.status:
        st = json.load(open(STATE))
        info = json.loads(call('GET', f'/messages/batches/{st["batch"]}'))
        print(info.get('processing_status'), json.dumps(info.get('request_counts')))
    if args.collect:
        st = json.load(open(STATE))
        info = json.loads(call('GET', f'/messages/batches/{st["batch"]}'))
        if info.get('processing_status') != 'ended':
            sys.exit('not ended: ' + str(info.get('processing_status')))
        body = call('GET', info['results_url'])
        by_cid = {cid_of(f['name']): f['name'] for f in json.load(open(FLAGGED))}
        out, bad = {}, 0
        for line in body.splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            name = by_cid.get(row.get('custom_id'))
            res = row.get('result') or {}
            if res.get('type') != 'succeeded' or not name:
                bad += 1
                continue
            text = ''.join(b.get('text', '') for b in
                           (res.get('message') or {}).get('content', []))
            m = re.search(r'\{.*\}', text, re.S)
            try:
                j = json.loads(m.group(0))
                assert j['action'] in ('keep', 'rename', 'drop')
                out[name] = {'action': j['action'], 'kind': j.get('kind'),
                             'reason': j.get('reason', '')}
                if j['action'] == 'rename':
                    out[name]['to'] = j['to']
            except Exception:
                bad += 1
        json.dump(out, open(OUT, 'w'), indent=1, ensure_ascii=False)
        import collections
        acts = collections.Counter(v['action'] for v in out.values())
        print(f'{len(out)} qualified ({bad} failed): {dict(acts)} -> {OUT}')


if __name__ == '__main__':
    main()
