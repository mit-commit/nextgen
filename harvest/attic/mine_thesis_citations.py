#!/usr/bin/env python3
"""Round-9 task 5 (human ruling 2026-08-26): the ~108 no-DOI theses/TRs have
no external citation data at all -- OpenAlex/S2 never had anything to look
up. But this corpus's own full-text harvest (chased for OTHER, DOI'd
papers' citing works) is itself a citation index for them: a citing work
that names one of our theses in its reference list will say so in the same
PDF text we already extracted.

Four stages, run in order:

    python3 curate/mine_thesis_citations.py scan
    python3 curate/mine_thesis_citations.py verify --submit --dry-run
    python3 curate/mine_thesis_citations.py verify --submit
    python3 curate/mine_thesis_citations.py verify --collect
    python3 curate/mine_thesis_citations.py recheck-siblings --submit
    python3 curate/mine_thesis_citations.py recheck-siblings --collect
    python3 curate/mine_thesis_citations.py fold --write

`recheck-siblings` exists because many of these theses were later published
as a near-identically-titled paper by the same first author (a normal
thesis -> conference-paper path) -- e.g. Gordon's S.M. thesis "A
Stream-Aware Compiler for Communication-Exposed Architectures" (2002) vs.
the ASPLAS co-authored paper "A stream compiler for communication-exposed
architectures" (gordon:asplos:2002). The first verify pass has no way to
know a sibling exists, so it confirms plenty of citations that are
actually reference-list entries for the PAPER (multi-author, no "thesis"
in the citation text) rather than the solo-authored thesis specifically --
measured at 435/584 (75%) of round-1 confirmations for the 25 theses with
a detectable sibling. `recheck-siblings` re-verifies exactly that bucket
with the sibling's own title/venue given, asking explicitly which of the
two this citation is actually for.

`scan` is mechanical and free: for each no-DOI thesis, build a match
signature (first-author surname + significant title words + year), then
substring-search every distinct full-text document in harvest/fulltext/
for the surname, and within a window around each hit look for enough
title-word overlap (or a "thesis"+"MIT"+year cluster) to be worth a model
look. Writes harvest/fulltext/thesis_scan_candidates.json -- a candidate
here is NOT a confirmed citation, just something worth checking, exactly
like every other heuristic-scan step in this corpus's pipeline
(search_github.py, build_idea_descendants.py, enumerate_candidates.py).

`verify` is the model gate (Batch API, same call/parse/validate pattern as
verify_repos.py): does this window genuinely cite the specific thesis, or
is it a coincidental surname + common-word overlap? Confirmed pairs get a
clean extracted context string; rejected ones are dropped. This is
DELIBERATELY separate from and lighter than the full taxonomy
classification -- keeps the standard pipeline's population honest (real
citations only) rather than asking classify_citations.py to also do
citation-detection.

`fold` looks up each confirmed pair's citing work by its already-known
metadata (it's a citing work we harvested for some OTHER corpus paper --
same doi/openalex/s2/authors/year, just a new `contexts` entry) and
appends it into harvest/citations/<thesisKey>.json, a file that has never
existed for these keys before. classify_citations.py's own load_candidates()
then picks these up as ordinary new candidates on its next --submit run
(a separate, later wave -- no collision with any batch already in flight
against existing keys, since these are brand-new files).
"""
import argparse
import glob
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import classify_citations as cc  # noqa: E402
import verify_repos as vr  # noqa: E402 -- reuse call/parse_record/validate pattern

ROOT = cc.ROOT
FULLTEXT_DIR = cc.FULLTEXT_DIR
CANDIDATES_PATH = os.path.join(ROOT, 'harvest', 'fulltext', 'thesis_scan_candidates.json')
CONFIRMED_PATH = os.path.join(ROOT, 'harvest', 'fulltext', 'thesis_confirmed.json')
REPORT_PATH = os.path.join(ROOT, 'harvest', 'fulltext', 'thesis-mining-report.md')
STATE_PATH = os.path.join(ROOT, 'harvest', 'fulltext', '_thesis_verify_batches.json')
RECHECK_STATE_PATH = os.path.join(ROOT, 'harvest', 'fulltext', '_thesis_recheck_batches.json')
REQUESTS_DUMP = os.path.join(ROOT, 'harvest', 'fulltext', '_thesis_verify_requests_dry_run.json')

WINDOW = 400  # chars of context kept on each side of a surname hit
MIN_TITLE_WORD_HITS = 4  # base bar: title-word overlap alone (no thesis/MIT/year marker)
MIN_TITLE_WORD_HITS_WITH_MARKER = 2  # lower bar allowed when thesis+MIT+year all cluster nearby
THESIS_MARKERS = ('thesis', 'dissertation')

STOPWORDS = {
    'a', 'an', 'the', 'of', 'for', 'and', 'or', 'with', 'on', 'in', 'to',
    'towards', 'toward', 'via', 'using', 'based', 'system', 'systems',
    'language', 'compiler', 'compilers', 'optimization', 'optimizing',
    'programming', 'analysis', 'design', 'implementation', 'framework',
    'approach', 'model', 'models', 'computing', 'processing', 'general',
    'purpose', 'high', 'performance', 'their', 'this', 'that', 'from',
}


def norm_words(text):
    return [w for w in re.split(r'[^a-z0-9]+', (text or '').lower()) if len(w) >= 4 and w not in STOPWORDS]


def is_thesis_or_tr(pub):
    t = (pub.get('type') or '').lower()
    venue = (pub.get('booktitle') or pub.get('journal') or pub.get('note') or '').lower()
    key = pub['bibtexKey'].lower()
    return 'thesis' in t or 'thesis' in venue or 'thesis' in key or t == 'tr' or 'techreport' in t


def first_author_surname(author0):
    surnames = cc.author_surnames(author0)
    # author_surnames() returns a set; for a match KEY we want the first
    # listed author specifically (citations name the first author), not
    # an arbitrary member of the set.
    first = re.split(r'\s+and\s+', author0 or '')[0].strip()
    if ',' in first:
        return first.split(',')[0].strip().lower()
    parts = first.split()
    return parts[-1].lower() if parts else None


def build_keys():
    idmap = json.load(open(os.path.join(ROOT, 'data', 'idmap.json')))
    pubs = {p['bibtexKey']: p for p in json.load(open(os.path.join(ROOT, 'data', 'publications.json')))}
    keys = []
    for key, entry in idmap.items():
        if entry.get('kind') != 'no_doi':
            continue
        pub = pubs.get(key)
        if not pub or not is_thesis_or_tr(pub):
            continue
        surname = first_author_surname(pub.get('author0'))
        if not surname or len(surname) < 3:
            continue
        title_words = norm_words(pub.get('title'))
        if len(title_words) < MIN_TITLE_WORD_HITS_WITH_MARKER:
            continue
        keys.append({
            'key': key, 'title': pub.get('title'), 'author0': pub.get('author0'),
            'year': pub.get('year'), 'surname': surname, 'title_words': title_words,
        })
    return keys


def unique_fulltext_files():
    seen = {}
    for path in glob.glob(os.path.join(FULLTEXT_DIR, '*', '*.txt')):
        slug = os.path.basename(path)[:-4]
        if slug not in seen:
            seen[slug] = path
    return seen  # slug -> one representative path


def cmd_scan(args):
    keys = build_keys()
    print(f'{len(keys)} no-DOI theses/TRs with a usable match signature', file=sys.stderr)
    files = unique_fulltext_files()
    print(f'{len(files)} distinct full-text documents to scan', file=sys.stderr)

    surname_re = {k['key']: re.compile(r'\b' + re.escape(k['surname']) + r'\b') for k in keys}

    candidates = []
    for i, (slug, path) in enumerate(sorted(files.items()), 1):
        with open(path, errors='replace') as fh:
            text = fh.read()
        text_lower = text.lower()
        for k in keys:
            best = None
            for m in surname_re[k['key']].finditer(text_lower):
                idx = m.start()
                lo, hi = max(0, idx - WINDOW), min(len(text), idx + WINDOW)
                window = text[lo:hi]
                window_lower = window.lower()
                hits = sum(1 for w in k['title_words'] if w in window_lower)
                marker_hit = (any(mk in window_lower for mk in THESIS_MARKERS)
                             and 'mit' in window_lower
                             and (str(k['year']) in window_lower if k['year'] else False))
                # two-tier bar: a thesis/MIT/year cluster is a strong enough
                # signal to accept a weaker title-word overlap, but title
                # words alone (common surnames like "Lee"/"Chen" collide
                # constantly across an academic citation network) need more.
                qualifies = hits >= MIN_TITLE_WORD_HITS or \
                    (marker_hit and hits >= MIN_TITLE_WORD_HITS_WITH_MARKER)
                score = hits + (2 if marker_hit else 0)
                if qualifies and (best is None or score > best[0]):
                    best = (score, window, hits, marker_hit)
            if best:
                candidates.append({
                    'thesis_key': k['key'], 'slug': slug, 'score': best[0],
                    'title_word_hits': best[2], 'thesis_marker_hit': best[3],
                    'window': best[1],
                })
        if i % 500 == 0:
            print(f'  scanned {i}/{len(files)} files, {len(candidates)} candidates so far', file=sys.stderr)

    candidates.sort(key=lambda c: (c['thesis_key'], -c['score']))
    with open(CANDIDATES_PATH, 'w') as fh:
        json.dump(candidates, fh, indent=1, ensure_ascii=False)
        fh.write('\n')
    by_key = {}
    for c in candidates:
        by_key.setdefault(c['thesis_key'], 0)
        by_key[c['thesis_key']] += 1
    print(f'\n{len(candidates)} candidates across {len(by_key)} theses -> {CANDIDATES_PATH}')


# --------------------------------------------------------------- verify step

SYSTEM_PROMPT = """You are checking whether a passage of text from a citing work's PDF
genuinely cites a SPECIFIC thesis, or is a coincidental surname + common-word
match (e.g. a different paper by someone with the same surname, or a
reference-list entry for an unrelated work that happens to share generic
title words). You are given the thesis's real title/author/year and the
matched passage (a window of raw extracted PDF text, which may have OCR/
layout noise, hyphenation breaks, or run-together words -- read past that).

Return ONE JSON object and nothing else. No prose, no markdown fence.

  {"is_citation": bool, "context": string or null, "confidence": "high"|"medium"|"low"}

is_citation: true only if the passage actually names or clearly refers to
THIS thesis (a reference-list entry with matching author+title+venue, or
an in-text mention naming the thesis/its author in this specific context).
False for: a different paper/thesis by an author with the same surname, a
citing work's OWN unrelated content that happens to share title vocabulary,
or a reference-list entry for a different thesis at the same institution.

context: when is_citation is true, extract the actual citing sentence(s)
that reference the thesis -- the same shape as a Semantic Scholar citation
context (one or two sentences, verbatim or lightly cleaned of PDF
line-break artifacts). null when is_citation is false.

confidence: your confidence in the is_citation call, not in the context
extraction quality."""


def build_verify_request(cand, thesis):
    content = (
        f"THESIS: {thesis['title']!r}\n"
        f"  first author: {thesis['author0']}\n"
        f"  year: {thesis['year']}\n\n"
        f"MATCHED PASSAGE (raw extracted text, {WINDOW} chars each side of the surname hit):\n"
        f"{cand['window']!r}"
    )
    custom_id = hashlib.sha1(f"{cand['thesis_key']}|{cand['slug']}".encode()).hexdigest()[:40]
    return {
        'custom_id': custom_id,
        'params': {
            'model': vr.MODEL,
            'max_tokens': 800,
            'system': SYSTEM_PROMPT,
            'messages': [{'role': 'user', 'content': content}],
        },
    }


def load_state():
    return json.load(open(STATE_PATH)) if os.path.exists(STATE_PATH) else {'batches': [], 'items': {}}


def load_recheck_state():
    return json.load(open(RECHECK_STATE_PATH)) if os.path.exists(RECHECK_STATE_PATH) else {'batches': [], 'items': {}}


def cmd_verify(args):
    candidates = json.load(open(CANDIDATES_PATH))
    keys = {k['key']: k for k in build_keys()}

    if args.submit:
        state = load_state()
        done = set(state.get('items', {}).values())
        pending = [c for c in candidates
                  if f"{c['thesis_key']}|{c['slug']}" not in done]
        requests_ = [build_verify_request(c, keys[c['thesis_key']]) for c in pending]
        lookup = {r['custom_id']: f"{c['thesis_key']}|{c['slug']}"
                 for r, c in zip(requests_, pending)}

        if not requests_:
            return print('nothing to submit')

        if args.dry_run:
            with open(REQUESTS_DUMP, 'w') as fh:
                json.dump(requests_, fh, indent=1, ensure_ascii=False)
            chars = sum(len(r['params']['system']) + len(r['params']['messages'][0]['content'])
                        for r in requests_)
            avg_tokens = (chars // len(requests_)) // 4
            total_in = avg_tokens * len(requests_)
            total_out = len(requests_) * 150
            cost = total_in / 1e6 * vr.BATCH_INPUT_PER_MTOK + total_out / 1e6 * vr.BATCH_OUTPUT_PER_MTOK
            print(f'{len(requests_)} requests, ~{avg_tokens} input tokens/request')
            print(f'COST ESTIMATE: ~${cost:,.2f} (batch pricing)')
            print(f'wrote {REQUESTS_DUMP}; sent nothing')
            return

        state.setdefault('items', {}).update(lookup)
        for start in range(0, len(requests_), 400):
            chunk = requests_[start:start + 400]
            result = json.loads(vr.call('POST', '/messages/batches', {'requests': chunk}))
            state.setdefault('batches', []).append({'id': result['id'], 'n': len(chunk),
                                                    'created': result.get('created_at'), 'collected': False})
            json.dump(state, open(STATE_PATH, 'w'), indent=1)
            print(f'  submitted {result["id"]}  {len(chunk)} requests')
        return

    if args.status:
        state = load_state()
        for batch in state.get('batches', []):
            info = json.loads(vr.call('GET', f'/messages/batches/{batch["id"]}'))
            counts = info.get('request_counts', {})
            print(f'{batch["id"]}  {info.get("processing_status"):12s} '
                 f'{json.dumps(counts)}  collected={batch["collected"]}')
        return

    if args.collect:
        state = load_state()
        items = state.get('items', {})
        by_pair = {f"{c['thesis_key']}|{c['slug']}": c for c in candidates}
        confirmed = json.load(open(CONFIRMED_PATH)) if os.path.exists(CONFIRMED_PATH) else []
        confirmed_pairs = {(c['thesis_key'], c['slug']) for c in confirmed}
        n_confirmed = n_rejected = n_failed = 0

        for batch in state.get('batches', []):
            if batch['collected']:
                continue
            info = json.loads(vr.call('GET', f'/messages/batches/{batch["id"]}'))
            if info.get('processing_status') != 'ended':
                print(f'{batch["id"]}: {info.get("processing_status")}, skipping')
                continue
            body = vr.call('GET', info['results_url'])
            for line in body.splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                custom_id = row.get('custom_id')
                pair_key = items.get(custom_id, custom_id)
                cand = by_pair.get(pair_key)
                result = row.get('result') or {}
                if result.get('type') != 'succeeded' or cand is None:
                    n_failed += 1
                    continue
                message = result.get('message') or {}
                text = ''.join(b.get('text', '') for b in message.get('content', []))
                try:
                    parsed = vr.parse_record(text)
                except Exception:
                    n_failed += 1
                    continue
                if not parsed.get('is_citation'):
                    n_rejected += 1
                    continue
                tk, slug = pair_key.split('|', 1)
                if (tk, slug) in confirmed_pairs:
                    continue
                confirmed.append({
                    'thesis_key': tk, 'slug': slug,
                    'context': parsed.get('context'),
                    'confidence': parsed.get('confidence'),
                })
                confirmed_pairs.add((tk, slug))
                n_confirmed += 1
            batch['collected'] = True

        json.dump(state, open(STATE_PATH, 'w'), indent=1)
        with open(CONFIRMED_PATH, 'w') as fh:
            json.dump(confirmed, fh, indent=1, ensure_ascii=False)
            fh.write('\n')
        print(f'confirmed: {n_confirmed}, rejected: {n_rejected}, failed/unparsed: {n_failed}')
        print(f'{len(confirmed)} total confirmed pairs -> {CONFIRMED_PATH}')
        return

    print('pick one of --submit [--dry-run], --status, --collect')


# ------------------------------------------------------- sibling-paper recheck

SIBLING_TITLE_OVERLAP = 3


def _norm_words(title):
    return set(w for w in re.split(r'[^a-z0-9]+', (title or '').lower()) if len(w) >= 4)


def _first_surname(author0):
    first = re.split(r'\s+and\s+', author0 or '')[0].strip()
    if ',' in first:
        return first.split(',')[0].strip().lower()
    parts = first.split()
    return parts[-1].lower() if parts else ''


def find_siblings(thesis_keys, pubs):
    """A same-first-author, title-overlapping OTHER corpus paper -- the
    common thesis -> conference-paper path. Returns {thesis_key: sibling_pub}."""
    siblings = {}
    for tk in thesis_keys:
        tp = pubs.get(tk, {})
        tsurname = _first_surname(tp.get('author0'))
        if not tsurname:
            continue
        twords = _norm_words(tp.get('title'))
        best = None
        for p in pubs.values():
            if p['bibtexKey'] == tk or _first_surname(p.get('author0')) != tsurname:
                continue
            overlap = len(twords & _norm_words(p.get('title')))
            if overlap >= SIBLING_TITLE_OVERLAP and (best is None or overlap > best[1]):
                best = (p, overlap)
        if best:
            siblings[tk] = best[0]
    return siblings


def split_ambiguous(confirmed, siblings):
    """A confirmed pair is ambiguous when its thesis has a detectable
    sibling paper AND the extracted context never says thesis/dissertation
    -- exactly the shape of a reference-list entry for the SIBLING, not
    the thesis (measured: 75% of round-1 confirmations for the 25 theses
    with a sibling). Safe otherwise: no sibling to confuse it with, or the
    context explicitly names this as thesis/dissertation work."""
    safe, ambiguous = [], []
    for x in confirmed:
        ctx_lower = (x.get('context') or '').lower()
        has_thesis_word = 'thesis' in ctx_lower or 'dissertation' in ctx_lower
        if x['thesis_key'] in siblings and not has_thesis_word:
            ambiguous.append(x)
        else:
            safe.append(x)
    return safe, ambiguous


RECHECK_SYSTEM_PROMPT = """You are re-checking a citation match for one of two possible targets that
share the same first author and a near-identical title -- a common
thesis -> conference/journal-paper path (the thesis work later published
with co-authors). You are given both candidates' real titles/venues/years
and the citing passage. Decide which one this specific citation is
actually for.

Return ONE JSON object and nothing else. No prose, no markdown fence.

  {"target": "thesis"|"paper"|"neither", "context": string or null, "confidence": "high"|"medium"|"low"}

target:
  "thesis"  the citation explicitly names this as a thesis/dissertation
            (institution, "S.M./M.Eng./PhD thesis", or matches the
            thesis's specific (usually single-author) attribution), or
            the paper given doesn't exist/wasn't given a match here and
            nothing points to it instead
  "paper"   the citation's author list/venue/format matches the published
            paper (multiple co-authors, a conference/journal venue, no
            thesis/dissertation language)
  "neither" the passage doesn't clearly cite either one (a different work
            entirely, despite the earlier name/title-overlap match)

context: when target is "thesis", the actual citing sentence(s) for the
thesis specifically. null otherwise.
confidence: your confidence in the target call."""


def build_recheck_request(cand, thesis, sibling, window):
    content = (
        f"CANDIDATE A (thesis): {thesis['title']!r}\n"
        f"  author: {thesis['author0']}, year {thesis['year']}\n\n"
        f"CANDIDATE B (published paper by the same first author): {sibling.get('title')!r}\n"
        f"  authors: {sibling.get('author0')}\n"
        f"  venue: {sibling.get('venue') or sibling.get('booktitle') or sibling.get('journal')}, "
        f"year {sibling.get('year')}\n\n"
        f"CITING PASSAGE:\n{window!r}"
    )
    custom_id = hashlib.sha1(f"recheck|{cand['thesis_key']}|{cand['slug']}".encode()).hexdigest()[:40]
    return {
        'custom_id': custom_id,
        'params': {
            'model': vr.MODEL,
            'max_tokens': 500,
            'system': RECHECK_SYSTEM_PROMPT,
            'messages': [{'role': 'user', 'content': content}],
        },
    }


def cmd_recheck(args):
    pubs = {p['bibtexKey']: p for p in json.load(open(os.path.join(ROOT, 'data', 'publications.json')))}
    confirmed = json.load(open(CONFIRMED_PATH))
    thesis_keys = sorted(set(x['thesis_key'] for x in confirmed))
    siblings = find_siblings(thesis_keys, pubs)
    safe, ambiguous = split_ambiguous(confirmed, siblings)
    print(f'{len(safe)} safe (no sibling, or already says thesis/dissertation), '
         f'{len(ambiguous)} ambiguous across {len(siblings)} theses with a sibling', file=sys.stderr)

    windows = {(c['thesis_key'], c['slug']): c['window'] for c in json.load(open(CANDIDATES_PATH))}
    thesis_by_key = {k['key']: k for k in build_keys()}

    if args.submit:
        state = load_recheck_state()
        done = set(state.get('items', {}).values())
        pending = [c for c in ambiguous if f"recheck|{c['thesis_key']}|{c['slug']}" not in done]
        requests_ = []
        lookup = {}
        for c in pending:
            window = windows.get((c['thesis_key'], c['slug']), c.get('context') or '')
            req = build_recheck_request(c, thesis_by_key[c['thesis_key']], siblings[c['thesis_key']], window)
            requests_.append(req)
            lookup[req['custom_id']] = f"recheck|{c['thesis_key']}|{c['slug']}"

        if not requests_:
            return print('nothing to submit')

        if args.dry_run:
            with open(REQUESTS_DUMP, 'w') as fh:
                json.dump(requests_, fh, indent=1, ensure_ascii=False)
            chars = sum(len(r['params']['system']) + len(r['params']['messages'][0]['content'])
                        for r in requests_)
            avg_tokens = (chars // len(requests_)) // 4
            total_in = avg_tokens * len(requests_)
            total_out = len(requests_) * 120
            cost = total_in / 1e6 * vr.BATCH_INPUT_PER_MTOK + total_out / 1e6 * vr.BATCH_OUTPUT_PER_MTOK
            print(f'{len(requests_)} requests, ~{avg_tokens} input tokens/request')
            print(f'COST ESTIMATE: ~${cost:,.2f} (batch pricing)')
            return

        state.setdefault('items', {}).update(lookup)
        for start in range(0, len(requests_), 400):
            chunk = requests_[start:start + 400]
            result = json.loads(vr.call('POST', '/messages/batches', {'requests': chunk}))
            state.setdefault('batches', []).append({'id': result['id'], 'n': len(chunk),
                                                    'created': result.get('created_at'), 'collected': False})
            json.dump(state, open(RECHECK_STATE_PATH, 'w'), indent=1)
            print(f'  submitted {result["id"]}  {len(chunk)} requests')
        return

    if args.status:
        state = load_recheck_state()
        for batch in state.get('batches', []):
            info = json.loads(vr.call('GET', f'/messages/batches/{batch["id"]}'))
            print(f'{batch["id"]}  {info.get("processing_status"):12s} '
                 f'{json.dumps(info.get("request_counts", {}))}  collected={batch["collected"]}')
        return

    if args.collect:
        state = load_recheck_state()
        items = state.get('items', {})
        by_pair = {f"recheck|{c['thesis_key']}|{c['slug']}": c for c in ambiguous}
        reconfirmed_as_thesis = []
        reclassified_paper = []
        neither = []
        n_failed = 0

        for batch in state.get('batches', []):
            if batch['collected']:
                continue
            info = json.loads(vr.call('GET', f'/messages/batches/{batch["id"]}'))
            if info.get('processing_status') != 'ended':
                print(f'{batch["id"]}: {info.get("processing_status")}, skipping')
                continue
            body = vr.call('GET', info['results_url'])
            for line in body.splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                pair_key = items.get(row.get('custom_id'), row.get('custom_id'))
                cand = by_pair.get(pair_key)
                result = row.get('result') or {}
                if result.get('type') != 'succeeded' or cand is None:
                    n_failed += 1
                    continue
                message = result.get('message') or {}
                text = ''.join(b.get('text', '') for b in message.get('content', []))
                try:
                    parsed = vr.parse_record(text)
                except Exception:
                    n_failed += 1
                    continue
                target = parsed.get('target')
                if target == 'thesis':
                    reconfirmed_as_thesis.append({
                        'thesis_key': cand['thesis_key'], 'slug': cand['slug'],
                        'context': parsed.get('context') or cand.get('context'),
                        'confidence': parsed.get('confidence'),
                    })
                elif target == 'paper':
                    reclassified_paper.append(cand)
                else:
                    neither.append(cand)
            batch['collected'] = True

        json.dump(state, open(RECHECK_STATE_PATH, 'w'), indent=1)
        final = safe + reconfirmed_as_thesis
        with open(CONFIRMED_PATH, 'w') as fh:
            json.dump(final, fh, indent=1, ensure_ascii=False)
            fh.write('\n')
        rejected_path = os.path.join(ROOT, 'harvest', 'fulltext', 'thesis_sibling_rejected.json')
        with open(rejected_path, 'w') as fh:
            json.dump({'reclassified_as_paper': reclassified_paper, 'neither': neither},
                     fh, indent=1, ensure_ascii=False)
            fh.write('\n')
        print(f're-confirmed as thesis: {len(reconfirmed_as_thesis)}, '
             f'reclassified as the sibling paper: {len(reclassified_paper)}, '
             f'neither: {len(neither)}, failed: {n_failed}')
        print(f'final confirmed total: {len(final)} ({len(safe)} safe + '
             f'{len(reconfirmed_as_thesis)} re-confirmed) -> {CONFIRMED_PATH}')
        return

    print('pick one of --submit [--dry-run], --status, --collect')


# ----------------------------------------------------------------- fold step

def find_citing_record(slug):
    """A confirmed pair's citing work already exists somewhere in
    harvest/citations/ (that's how we found its full text in the first
    place -- chased for some OTHER corpus paper). Reuse its real metadata
    rather than re-deriving it."""
    for path in glob.glob(os.path.join(cc.CITATIONS_DIR, '*.json')):
        data = json.load(open(path))
        for c in data.get('citing') or []:
            if cc.slug_for(c) == slug:
                return c
    return None


def cmd_fold(args):
    confirmed = json.load(open(CONFIRMED_PATH))
    by_thesis = {}
    for c in confirmed:
        by_thesis.setdefault(c['thesis_key'], []).append(c)

    cache = {}
    n_new_files = n_new_records = n_no_record_found = 0
    for thesis_key, pairs in sorted(by_thesis.items()):
        out_path = os.path.join(cc.CITATIONS_DIR, thesis_key + '.json')
        existing = json.load(open(out_path)) if os.path.exists(out_path) else \
            {'counts': {'openalex': 0, 's2': 0, 'thesis_mining': 0}, 'citing': []}
        existing_slugs = {cc.slug_for(c) for c in existing['citing']}
        added = 0
        for pair in pairs:
            slug = pair['slug']
            if slug not in cache:
                cache[slug] = find_citing_record(slug)
            record = cache[slug]
            if record is None:
                n_no_record_found += 1
                continue
            if slug in existing_slugs:
                continue
            new_record = dict(record)
            new_record['contexts'] = [pair['context']] if pair.get('context') else []
            new_record['_thesis_mining_confidence'] = pair.get('confidence')
            existing['citing'].append(new_record)
            existing_slugs.add(slug)
            added += 1
        if added:
            existing['counts']['thesis_mining'] = existing['counts'].get('thesis_mining', 0) + added
            if args.write:
                with open(out_path, 'w') as fh:
                    json.dump(existing, fh, indent=1, ensure_ascii=False)
                    fh.write('\n')
            n_new_files += 1
            n_new_records += added
            print(f'{thesis_key}: +{added} citing work(s)')

    print(f'\n{n_new_records} citing records added across {n_new_files} theses '
         f'({n_no_record_found} confirmed pairs had no findable source record, skipped)')
    if not args.write:
        print('dry run -- nothing written. Pass --write to commit.')


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)

    sub.add_parser('scan').set_defaults(func=cmd_scan)

    p = sub.add_parser('verify')
    p.add_argument('--submit', action='store_true')
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--status', action='store_true')
    p.add_argument('--collect', action='store_true')
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser('recheck-siblings')
    p.add_argument('--submit', action='store_true')
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--status', action='store_true')
    p.add_argument('--collect', action='store_true')
    p.set_defaults(func=cmd_recheck)

    p = sub.add_parser('fold')
    p.add_argument('--write', action='store_true')
    p.set_defaults(func=cmd_fold)

    args = ap.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
