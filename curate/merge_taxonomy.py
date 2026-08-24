#!/usr/bin/env python3
"""Fold citation-function judgments into data/citations/<bibtexKey>.json +
index.json, per data/citations/SCHEMA.md.

Two record sources, generalizing prototype/build_pilot_data.py's reference
implementation (same schema, same dedup rule -- kept in sync deliberately,
not re-derived):

  - the 8 pilot papers: harvest/taxonomy/pilot-classifications.json, which
    already carries one row per citing work, including `unclassified`
    title-only rows. Left to prototype/build_pilot_data.py -- not written
    here (see SCHEMA.md's file-ownership table).
  - every other paper: harvest/taxonomy/records/<key>/*.json (classify_
    citations.py staging output, judged rows only) plus
    harvest/citations/<key>.json (the full citing list), used to synthesize
    an `unclassified` row for every slug with no staging record -- unjudged
    for lack of evidence, the same convention the pilot pass used for
    title-only rows.

Usage: python3 curate/merge_taxonomy.py [--keys k1,k2,...] [--write]
Dry-run by default (prints per-paper counts); --write writes
data/citations/<key>.json for the target keys (default: every non-pilot
paper with at least one harvest/taxonomy/records/<key>/ file) and refreshes
data/citations/index.json for those keys, preserving every other paper's
existing index row (including the pilots').
"""
import argparse
import glob
import hashlib
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CITATIONS_DIR = os.path.join(ROOT, 'harvest', 'citations')
RECORDS_DIR = os.path.join(ROOT, 'harvest', 'taxonomy', 'records')
PILOT_CLASSIFICATIONS = os.path.join(ROOT, 'harvest', 'taxonomy', 'pilot-classifications.json')
OUT_DIR = os.path.join(ROOT, 'data', 'citations')
GSCHOLAR_PATH = os.path.join(OUT_DIR, 'gscholar.json')
INDEX_PATH = os.path.join(OUT_DIR, 'index.json')

PILOT_KEYS = {
    'thies:cc:2002', 'halide:pldi:2013', 'taylor:micro:2002',
    'amarasinghe:ijpp:2005', 'petkov:ipdps:2002', 'thies:toplas:2007',
    'levison:istas:2002', 'netblocks-pldi24',
}

EVIDENCE_RANK = {'fulltext': 4, 'abstract+contexts': 3, 'contexts': 2,
                 'abstract': 1, 'title_only': 0}
DETAILED = {'extends', 'uses-tool', 'adopts-idea', 'uses-benchmark',
            'baseline', 'positions', 'surveys', 'supports-claim',
            'detailed-citation'}
PASSING = {'exemplifies', 'passing-citation'}
FUNCTION_ORDER = ['extends', 'uses-tool', 'adopts-idea', 'uses-benchmark',
                  'baseline', 'positions', 'surveys', 'supports-claim',
                  'exemplifies', 'detailed-citation', 'passing-citation',
                  'unknown', 'unclassified']


def is_saman(name):
    """True iff this author name is Saman Amarasinghe (drives the COMMIT-papers
    separation; see SCHEMA.md). Handles 'Saman', 'Saman P.', and 'S.' forms,
    including glued PDF-extraction artifacts, while excluding other
    Amarasinghes (Gayashan, Yasith, ...). Kept byte-identical to
    prototype/build_pilot_data.py's copy -- the two emitters must agree."""
    n = re.sub(r'[^a-z]+', ' ', (name or '').lower()).strip()
    if 'amarasinghe' not in n:
        return False
    return 'saman' in n or bool(re.search(r'(^| )s (p )?amarasinghe', n))


def slug_for(citing):
    doi = citing.get('doi')
    if doi:
        return re.sub(r'[^a-z0-9._-]', '_', doi.lower())
    oa = citing.get('openalex')
    if oa:
        return 'oa-' + oa.rsplit('/', 1)[-1]
    s2 = citing.get('s2')
    if s2:
        return 's2-' + s2[:16]
    h = hashlib.sha1((citing.get('title') or '').encode('utf-8')).hexdigest()[:16]
    return 'noid-' + h


def norm_title(t):
    return re.sub(r'[^a-z0-9]+', '', (t or '').lower())


def authors_short(names):
    names = [n for n in (names or []) if n]
    if not names:
        return None
    if len(names) > 3:
        return ', '.join(names[:3]) + ' et al.'
    return ', '.join(names)


def link_for(citing):
    if citing.get('doi'):
        return 'https://doi.org/' + citing['doi']
    if citing.get('openalex'):
        oa = citing['openalex']
        return oa if oa.startswith('http') else 'https://openalex.org/' + oa
    if citing.get('s2'):
        return 'https://www.semanticscholar.org/paper/' + citing['s2']
    return None


def split_of(function):
    if function in DETAILED:
        return 'detailed'
    if function in PASSING:
        return 'passing'
    return None


def unclassified_row(slug, citing):
    return {
        'slug': slug, 'function': 'unclassified', 'centrality': 'unclassified',
        'flags': [], 'secondary': [], 'confidence': None, 'evidence': 'title_only',
        'anchored': None, 'note': 'not judged: no usable evidence harvested',
        'title': citing.get('title'), 'year': citing.get('year'),
        's2_isInfluential': citing.get('isInfluential'), 's2_intents': citing.get('intents'),
    }


def tax_rows_for(key):
    """One taxonomy row per citing work, synthesizing `unclassified` for any
    slug classify_citations.py didn't produce a staging record for."""
    citing_path = os.path.join(CITATIONS_DIR, key + '.json')
    citing_list = (json.load(open(citing_path)).get('citing') or []
                   if os.path.exists(citing_path) else [])
    judged = {}
    records_dir = os.path.join(RECORDS_DIR, key)
    if os.path.isdir(records_dir):
        for path in glob.glob(os.path.join(records_dir, '*.json')):
            r = json.load(open(path))
            judged[r['slug']] = r
    rows = []
    for c in citing_list:
        slug = slug_for(c)
        rows.append(judged.get(slug) or unclassified_row(slug, c))
    return rows, citing_list


def build_paper(key, tax_rows, citing_list, generated):
    citing_by_slug = {slug_for(c): c for c in citing_list}
    records = [(r, citing_by_slug.get(r['slug'], {})) for r in tax_rows]

    groups = {}
    for r, c in records:
        gk = norm_title(r.get('title') or c.get('title')) or 'slug:' + r['slug']
        groups.setdefault(gk, []).append((r, c))

    entries = []
    n_commit = 0
    for _, sibs in groups.items():
        flags = sorted(set(f for r, _ in sibs for f in r['flags']))
        if 'self-version' in flags:
            continue
        sibs.sort(key=lambda rc: (
            EVIDENCE_RANK.get(rc[0]['evidence'], 0),
            rc[0]['function'] not in ('unknown', 'unclassified'),
            bool(rc[1].get('doi')),
            rc[0]['slug'],
        ), reverse=True)
        r, c = sibs[0]
        for _, c2 in sibs[1:]:
            for f in ('doi', 'venue', 'authors', 'openalex', 's2'):
                if not c.get(f) and c2.get(f):
                    c = dict(c)
                    c[f] = c2[f]
        e = {'title': r.get('title') or c.get('title') or 'Untitled',
             'function': r['function'],
             'split': split_of(r['function'])}
        if r.get('year') or c.get('year'):
            e['year'] = r.get('year') or c.get('year')
        for src, dst in ((c.get('venue'), 'venue'),
                        (authors_short(c.get('authors')), 'authors'),
                        (link_for(c), 'url')):
            if src:
                e[dst] = src
        # siblings are dedup'd variants of the same work (arXiv/DOI/venue
        # clones) with possibly inconsistent citation counts depending on
        # which index recorded them -- the citing work's own popularity is a
        # property of the work, not of which variant we kept, so take the
        # max rather than whichever sibling happened to survive the
        # evidence-rank sort above. Required-but-nullable per SCHEMA.md, so
        # always set it (unlike the omit-if-absent fields above).
        cited_by_values = [c2.get('cited_by') for _, c2 in sibs if c2.get('cited_by') is not None]
        e['cited_by'] = max(cited_by_values) if cited_by_values else None
        if r['function'] not in ('unknown', 'unclassified'):
            e['centrality'] = r['centrality']
            e['confidence'] = r['confidence']
        if r.get('secondary'):
            e['secondary'] = r['secondary']
        if flags:
            e['flags'] = flags
        e['evidence'] = r['evidence']
        if any(is_saman(a) for _, c2 in sibs for a in (c2.get('authors') or [])):
            e['commit'] = True
            n_commit += 1
        entries.append(e)

    forder = {f: i for i, f in enumerate(FUNCTION_ORDER)}
    entries.sort(key=lambda e: (forder.get(e['function'], 99),
                                -(e.get('year') or 0), e['title'].lower()))
    judged = sum(1 for e in entries if e['split'] is not None)
    return {
        'schema': 1,
        'key': key,
        'generated': generated,
        'codebook': '0.2',
        'counts': {
            'records_raw': len(tax_rows),
            'works': len(entries),
            'commit': n_commit,
            'judged': judged,
            'gscholar': None,
        },
        'citations': entries,
    }


def target_keys():
    """Every non-pilot paper with at least one classify_citations.py record."""
    return sorted({
        os.path.basename(d) for d in glob.glob(os.path.join(RECORDS_DIR, '*'))
        if os.path.isdir(d) and os.path.basename(d) not in PILOT_KEYS
        and glob.glob(os.path.join(d, '*.json'))
    })


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--keys')
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--generated', default='2026-08-24')
    args = ap.parse_args()

    keys = ([k.strip() for k in args.keys.split(',') if k.strip()]
            if args.keys else target_keys())
    overlap = set(keys) & PILOT_KEYS
    if overlap:
        raise SystemExit(f'{sorted(overlap)} are pilot papers -- owned by '
                         'prototype/build_pilot_data.py, not this script')
    if not keys:
        print('no paper has new staging records; still refreshing gscholar '
             'figures in index.json')

    gscholar = json.load(open(GSCHOLAR_PATH)) if os.path.exists(GSCHOLAR_PATH) else {}
    index = (json.load(open(INDEX_PATH)) if os.path.exists(INDEX_PATH)
             else {'schema': 1, 'generated': None, 'papers': {}})

    for key in keys:
        tax_rows, citing_list = tax_rows_for(key)
        if not tax_rows:
            print(f'{key}: no citing works, skipping')
            continue
        paper = build_paper(key, tax_rows, citing_list, args.generated)
        gs = (gscholar.get(key) or {}).get('count')
        paper['counts']['gscholar'] = gs
        index['papers'][key] = {'verified': paper['counts']['works'], 'gscholar': gs}
        c = paper['counts']
        print(f"{key}: raw={c['records_raw']} works={c['works']} "
              f"commit={c['commit']} judged={c['judged']} gscholar={gs}")
        if args.write:
            with open(os.path.join(OUT_DIR, key + '.json'), 'w') as fh:
                json.dump(paper, fh, indent=1, ensure_ascii=False)
                fh.write('\n')

    # index.json is the publications page's hot path (max(verified, gscholar)
    # for every paper, computed client-side) -- refresh every OTHER paper's
    # gscholar figure from the current gscholar.json too, even papers with no
    # new staging records this run, so a Scholar-scrape update alone (no
    # reclassification) still reaches the page on the next merge run.
    refreshed = 0
    for key, row in index['papers'].items():
        if key in keys:
            continue
        gs = (gscholar.get(key) or {}).get('count')
        if row.get('gscholar') != gs:
            row['gscholar'] = gs
            refreshed += 1
    if refreshed:
        print(f'refreshed gscholar for {refreshed} other paper(s) already in index.json')

    index['generated'] = args.generated
    if args.write:
        os.makedirs(OUT_DIR, exist_ok=True)
        with open(INDEX_PATH, 'w') as fh:
            json.dump(index, fh, indent=1, ensure_ascii=False)
            fh.write('\n')
        print('wrote', OUT_DIR)


if __name__ == '__main__':
    main()
