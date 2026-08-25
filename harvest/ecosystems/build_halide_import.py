#!/usr/bin/env python3
"""Queue task `halide-import` (carried from round 4, reconfirmed round 7):
halide:pldi:2013's tier-2 (ecosystem users of halide/Halide) and tier-3
(idea-descendant citing works with their own repo) rows should come from
the existing samanamarasinghe/Halide-world index, never a fresh harvest or
model judgment of our own -- that project has already done exactly this
curation for the whole "Halide world" of papers.

Fetches data/site/halide-index.json from that repo (schema_version 1: a
flat `entries` list of kind anchor/paper/repo/person) via the GitHub
contents API, and maps ONLY the halide:pldi:2013-relevant slice onto our
own data/repos/SCHEMA.md row shape:

  - tier-2: every `repo` entry (Halide-world's own curated pool of
    repositories with Halide in them, verdict-judged) EXCEPT
    `prose_only` (no real code integration) and `third_party_bundle`
    (2,828 rows of "Halide arrived inside someone else's dependency" --
    real, but reports it separately rather than importing 2,828 near-zero
    -signal rows into a single paper's panel; see the report). Verdict ->
    our group taxonomy: halide_copy_or_fork -> builds-on, everything else
    code-level (consumer/generator/uses_source) -> uses. The raw verdict
    is kept verbatim in `sdv` for the chip.
  - tier-3: every `paper` entry whose `anchors` includes `pldi2013-halide`
    AND has a nonempty `artifacts` list (the citing work's OWN published
    repo -- Halide-world's `mentions` field, a repo the citing work only
    names, is NOT a descendant claim and is left out here for the same
    reason our own build_idea_descendants.py never promotes a bare
    mention to `located: true`).

Every row carries evidence + a `source` field attributing
samanamarasinghe/Halide-world (with the index's own generated date) so a
reader can tell this apart from rows this corpus harvested itself. Maps,
does not re-judge: no verdict, evidence, or star count here was decided
by this script.

Output: harvest/ecosystems/halide-import.json (this paper's own
data/repos/-shaped row set, kept out of that lane's claimed path per
LANES.md until a human has seen the tier-2 count) +
harvest/ecosystems/halide-import-report.md.

    GITHUB_TOKEN=... python3 harvest/ecosystems/build_halide_import.py
"""
import json
import os
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT_JSON = os.path.join(HERE, 'halide-import.json')
OUT_REPORT = os.path.join(HERE, 'halide-import-report.md')

SOURCE_REPO = 'samanamarasinghe/Halide-world'
INDEX_PATH = 'data/site/halide-index.json'
BUILD_INFO_PATH = 'data/site/build-info.json'
ANCHOR_ID = 'pldi2013-halide'
KEY = 'halide:pldi:2013'

# Real code-level verdicts only -- prose_only carries no code integration,
# third_party_bundle is reported separately (see module docstring).
TIER2_VERDICT_GROUP = {
    'halide_copy_or_fork': 'builds-on',
    'consumer': 'uses',
    'generator': 'uses',
    'uses_source': 'uses',
}
EXCLUDED_VERDICTS = {'prose_only', 'third_party_bundle', None}


def _fetch_raw(path, token):
    url = 'https://api.github.com/repos/%s/contents/%s' % (SOURCE_REPO, path)
    req = urllib.request.Request(url, headers={
        'Authorization': 'Bearer ' + token,
        'Accept': 'application/vnd.github.raw',
        'User-Agent': 'nextgen-halide-import/1.0',
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        sys.exit('%s fetching %s: %s' % (exc.code, url, exc.read().decode()[:300]))


def fetch_index():
    token = os.environ.get('GITHUB_TOKEN', '').strip()
    if not token:
        sys.exit('GITHUB_TOKEN not set')
    return _fetch_raw(INDEX_PATH, token), _fetch_raw(BUILD_INFO_PATH, token)


def repo_row(entry, group):
    year = None
    if entry.get('pushed_at'):
        year = int(entry['pushed_at'][:4])
    return {
        'name': entry.get('title') or entry.get('id'),
        'url': entry.get('url'),
        'group': group,
        'sdv': entry.get('verdict'),
        'desc': entry.get('description'),
        'stars': entry.get('stars'),
        'active': year,
        'evidence': entry.get('evidence') or entry.get('reason') or entry.get('verdict'),
        'source': SOURCE_REPO,
    }


def descendant_row(paper, artifact_full_name, repos_by_id):
    repo = repos_by_id.get(artifact_full_name)
    row = {
        'name': artifact_full_name,
        'url': repo.get('url') if repo else 'https://github.com/%s' % artifact_full_name,
        'group': 'adopts',
        'citing_title': paper.get('title'),
        'citing_year': paper.get('year'),
        'evidence': 'citing work\'s own published artifact repo (Halide-world paper id %s)' % paper.get('id'),
        'source': SOURCE_REPO,
    }
    if repo:
        row['desc'] = repo.get('description')
        row['stars'] = repo.get('stars')
    return row


def main():
    index, build_info = fetch_index()
    entries = index.get('entries') or []
    repos = [e for e in entries if e.get('kind') == 'repo']
    papers = [e for e in entries if e.get('kind') == 'paper']
    repos_by_id = {r['id']: r for r in repos}

    tier2_rows = []
    tier2_excluded = {'prose_only': 0, 'third_party_bundle': 0, 'no_verdict': 0}
    for r in repos:
        verdict = r.get('verdict')
        if verdict in TIER2_VERDICT_GROUP:
            tier2_rows.append(repo_row(r, TIER2_VERDICT_GROUP[verdict]))
        elif verdict == 'prose_only':
            tier2_excluded['prose_only'] += 1
        elif verdict == 'third_party_bundle':
            tier2_excluded['third_party_bundle'] += 1
        else:
            tier2_excluded['no_verdict'] += 1

    citing = [p for p in papers if ANCHOR_ID in (p.get('anchors') or [])]
    tier3_rows = []
    mentions_only = 0
    for p in citing:
        artifacts = p.get('artifacts') or []
        if artifacts:
            for a in artifacts:
                tier3_rows.append(descendant_row(p, a, repos_by_id))
        elif p.get('mentions'):
            mentions_only += 1

    out = {
        'schema': 1,
        'key': KEY,
        'source': SOURCE_REPO,
        'source_index_generated': build_info.get('built'),
        'source_schema_version': index.get('schema_version'),
        'imported': None,  # stamped by the caller/committer, not this script
        'tier2': tier2_rows,
        'tier3': tier3_rows,
    }
    with open(OUT_JSON, 'w') as fh:
        json.dump(out, fh, indent=1, sort_keys=True, ensure_ascii=False)
        fh.write('\n')

    report = f"""# Halide-world import for `{KEY}`

Source: `{SOURCE_REPO}`'s `{INDEX_PATH}` (schema_version {index.get('schema_version')},
{index.get('counts', {}).get('repos')} repos / {index.get('counts', {}).get('papers')} citing
papers indexed corpus-wide). Mapped, not re-judged -- every verdict, star
count, and evidence string here is Halide-world's own.

## Tier-2 (repositories with Halide in them -- ecosystem users)

Imported **{len(tier2_rows)}** real code-level rows (verdict
consumer/generator/uses_source -> `uses`, halide_copy_or_fork -> `builds-on`).

Deliberately excluded:
- **{tier2_excluded['third_party_bundle']}** `third_party_bundle` rows (Halide arrived only
  inside a vendored third-party dependency -- real signal, but importing all of them
  into one paper's panel would swamp it; available in the source index's `lane_a`/
  `lane_b_classified` pools if a future pass wants a capped, star-sorted subset).
- **{tier2_excluded['prose_only']}** `prose_only` rows (no real code integration).
- **{tier2_excluded['no_verdict']}** rows with no verdict at all (pre-curation).

**{len(tier2_rows)} rows is a large single-paper ecosystem** -- comparable in scale to
the outside-user hunts the round-7 strategy flagged as needing explicit human
approval before going live (e.g. dynamorio). Recommend the same here: this file is
staged in `harvest/ecosystems/`, not `data/repos/`, until a human has seen the count
and the site-citations lane decides how (or whether) to render all {len(tier2_rows)} at
once vs. a capped/sorted view.

## Tier-3 (idea-descendants: citing works with their own repo)

**{len(tier3_rows)}** rows, from **{len([p for p in citing if p.get('artifacts')])}**
citing papers linked to the `{ANCHOR_ID}` anchor that published their own artifact repo
(of {len(citing)} citing papers total). A further **{mentions_only}** citing papers only
*mention* another repo without publishing their own -- left out, matching this corpus's
own idea-descendants rule that a bare mention is not a located descendant.

This tier is a much more modest addition (same order of magnitude as this corpus's own
idea-descendants waves) and is reasonable to fold into `data/repos/papers/{KEY}.json`
directly, gated only on the usual dedup-against-existing-rows step.

## Confirms

Before this import, `data/repos/papers/{KEY}.json` had 0 rows attributed to
Halide-world -- its only tier-3 rows (8, group `adopts`) came from this corpus's own
generic `curate/build_idea_descendants.py` pass, and it had no tier-2 rows at all. Per
the round-4 spec ("import... do not re-harvest or re-judge... attribute the source"),
this was the gap task `halide-import` asked to close.
"""
    with open(OUT_REPORT, 'w') as fh:
        fh.write(report)

    print('tier-2: %d imported, excluded %s' % (len(tier2_rows), tier2_excluded))
    print('tier-3: %d rows from %d citing papers (%d mentions-only skipped)' % (
        len(tier3_rows), len([p for p in citing if p.get('artifacts')]), mentions_only))
    print('wrote', OUT_JSON)
    print('wrote', OUT_REPORT)


if __name__ == '__main__':
    main()
