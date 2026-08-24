#!/usr/bin/env python3
"""Classify citing-work records against the citation-function taxonomy, via the
Batch API. Built on the SDVworld-index curate/auto_curate.py pattern.

    python3 curate/classify_citations.py --pilot 5          # live calls, print, no batch
    python3 curate/classify_citations.py --submit --dry-run # build requests, write, send nothing
    python3 curate/classify_citations.py --submit           # create the batches
    python3 curate/classify_citations.py --status           # poll
    python3 curate/classify_citations.py --collect          # write records from finished batches
    python3 curate/classify_citations.py --recover          # re-validate needs-review.jsonl, no API call

Needs ANTHROPIC_BATCH_KEY (NOT ANTHROPIC_API_KEY -- that env var is read by the
Claude Code CLI itself and setting it here would break logins). Batch requests
are processed asynchronously at half the standard per-token rate; there is no
local rate to pace between submit and collect.

The codebook lives in docs/taxonomy-draft.md and is parsed into the system
prompt at request-build time (see system_prompt()) so the codebook stays the
single source of truth -- editing the taxonomy doc changes what gets asked
without a second copy to keep in sync.

Population: every data/idmap.json entry with a harvest/citations/<key>.json
file, excluding the 8 pilot papers (already hand-classified into
harvest/taxonomy/pilot-classifications.json) and every citing record with no
usable evidence (no cached full text, no cached abstract, no non-empty S2
contexts) -- those are left unclassified/title_only, same as the pilot
convention, and are not billed. Papers are processed in descending order of
citing-work count.

Output is STAGING, one record per citing work under
harvest/taxonomy/records/<bibtexKey>/<slug>.json, plus
harvest/taxonomy/records/needs-review.jsonl for anything that fails
validation. A citing work that already has a record is skipped on rerun, so
re-running --submit after a pass picks up exactly the failures. Nothing here
is folded into data/citations/ until a separate merge script runs (task says
"a merge script folds records + dedup ... for the site" -- not written by
this script).
"""
import argparse
import collections
import glob
import hashlib
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDMAP = os.path.join(ROOT, 'data', 'idmap.json')
PUBLICATIONS = os.path.join(ROOT, 'data', 'publications.json')
CITATIONS_DIR = os.path.join(ROOT, 'harvest', 'citations')
ABSTRACTS_DIR = os.path.join(ROOT, 'harvest', 'fulltext', 'abstracts')
FULLTEXT_DIR = os.path.join(ROOT, 'harvest', 'fulltext')
TAXONOMY_DRAFT = os.path.join(ROOT, 'docs', 'taxonomy-draft.md')
PILOT_CLASSIFICATIONS = os.path.join(ROOT, 'harvest', 'taxonomy', 'pilot-classifications.json')

OUT = os.path.join(ROOT, 'harvest', 'taxonomy', 'records')
REVIEW = os.path.join(OUT, 'needs-review.jsonl')
STATE = os.path.join(OUT, '_batches.json')
REQUESTS_DUMP = os.path.join(OUT, '_requests_dry_run.json')

API = 'https://api.anthropic.com/v1'
MODEL = 'claude-sonnet-4-6'
MAX_TOKENS = 3000       # small JSON object, but Sonnet spends output tokens
                        # deliberating before it writes it, and that comes out
                        # of the same budget -- see auto_curate.py's note.
PER_BATCH = 400
FULLTEXT_CHARS = 4000
ABSTRACT_CHARS = 3000
CONTEXTS_MAX = 12

# Batch API is 50% of standard per-token pricing (claude-sonnet-4-6: $3/$15
# per MTok standard -> $1.50/$7.50 batch). Used only for the --dry-run cost
# estimate; the API bills the real usage regardless of this constant.
BATCH_INPUT_PER_MTOK = 1.50
BATCH_OUTPUT_PER_MTOK = 7.50
EST_OUTPUT_TOKENS = 400   # rough per-request output budget for the estimate:
                          # a compact JSON object plus a little deliberation.

PILOT_KEYS = {
    'thies:cc:2002', 'halide:pldi:2013', 'taylor:micro:2002',
    'amarasinghe:ijpp:2005', 'petkov:ipdps:2002', 'thies:toplas:2007',
    'levison:istas:2002', 'netblocks-pldi24',
}


# ------------------------------------------------------------------ codebook

def _section(text, start_marker, end_marker):
    start = text.index(start_marker)
    end = text.index(end_marker, start) if end_marker else len(text)
    return text[start:end]


def parse_function_order(text):
    """Pull the FUNCTION priority order out of the blockquote in §2."""
    marker = "rest go in `secondary`"
    idx = text.index(marker)
    lines = text[idx:].splitlines()
    quoted = []
    capturing = False
    for line in lines[1:]:
        if line.startswith('> '):
            capturing = True
            quoted.append(line[2:])
        elif capturing:
            break
    raw = ' '.join(quoted).strip().strip('`')
    return [v.strip() for v in raw.split('>') if v.strip()]


def parse_function_defs(text):
    """One (value, definition) pair per ### 2.N `value` heading in §2, taking
    the prose up to the first worked-example bullet (`- **...`) and dropping
    the examples themselves -- they cite pilot-specific paper names that mean
    nothing to a request about a different paper."""
    section = _section(text, '## 2. Dimension 1', '\n---\n\n## 3.')
    heading_re = re.compile(r'^### 2\.\d+ `([a-z-]+)`[^\n]*\n', re.M)
    matches = list(heading_re.finditer(section))
    defs = []
    for i, m in enumerate(matches):
        value = m.group(1)
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(section)
        body = section[body_start:body_end]
        cut = body.find('\n- ')
        prose = (body[:cut] if cut >= 0 else body).strip()
        defs.append((value, prose))
    return defs


def parse_table(text, start_marker, end_marker):
    """Parse a `| a | b | ... |` markdown table into a list of row-cell-lists,
    skipping the header and the `---` separator row."""
    section = _section(text, start_marker, end_marker)
    rows = []
    for line in section.splitlines():
        line = line.strip()
        if not line.startswith('|'):
            continue
        cells = [c.strip() for c in line.strip('|').split('|')]
        if all(re.fullmatch(r':?-+:?', c) for c in cells):
            continue
        rows.append(cells)
    return rows[1:]  # drop header row


def parse_codebook():
    text = open(TAXONOMY_DRAFT).read()
    order = parse_function_order(text)
    defs = dict(parse_function_defs(text))
    centrality_rows = parse_table(text, '## 3. Dimension 2', '\nWorked examples:')
    centrality = [(r[0].strip('`'), r[1]) for r in centrality_rows]
    guidance_start = text.index('Guidance used')
    guidance_end = text.index('\n\nWorked examples:', guidance_start)
    guidance = text[guidance_start:guidance_end].strip()
    flags_rows = parse_table(text, '## 4. Flags, evidence tiers',
                              '\n**Evidence tier**')
    flags = [(r[0].strip('`'), r[1]) for r in flags_rows]
    return {
        'order': order,               # 11 values, highest priority first
        'defs': defs,                 # value -> definition prose
        'centrality': centrality,     # [(value, definition), ...]
        'guidance': guidance,
        'flags': flags,               # [(flag, meaning), ...]
    }


def system_prompt(codebook):
    order = codebook['order']
    func_lines = []
    for value in order:
        func_lines.append(f"### `{value}`\n{codebook['defs'][value]}")
    func_block = '\n\n'.join(func_lines)
    centrality_block = '\n'.join(f"- `{v}`: {d}" for v, d in codebook['centrality'])
    flags_block = '\n'.join(f"- `{f}`: {m}" for f, m in codebook['flags'])

    return f"""You are classifying ONE citing-work record against a citation-function
taxonomy, for a research-impact analysis of an MIT compilers/systems paper. You are
given the cited (our) paper's metadata and the citing work's metadata plus whatever
evidence was harvested for it (Semantic Scholar citation contexts/intents, and
sometimes an abstract or cached full text). Judge only from that evidence. You
cannot fetch anything.

Return ONE JSON object and nothing else. No prose, no markdown fence.

Fields:
  function      the single PRIMARY function, in FUNCTION VALUES below
  secondary     list of any OTHER function values that also apply (e.g. the
                citing work both uses the tool and separately positions
                against it); [] if only one function applies
  centrality    one of CENTRALITY VALUES below
  flags         list of FLAG VALUES below that apply; [] if none
  confidence    high | medium | low
  anchored      named | numref | none -- named: the evidence names the cited
                work or its system/authors specifically; numref: only a bare
                bracket/number reference with no naming; none: no evidence
                text actually anchors to the cited work at all (this happens
                -- S2 contexts are sometimes mis-attributed; if so, function
                should usually be unknown and confidence low)
  note          one short sentence: what evidence drove the call

FUNCTION VALUES, in priority order (when several apply, `function` is the
highest-priority one and the rest go in `secondary`; the order encodes depth
of dependence: building on the artifact outranks running it, running it
outranks borrowing its idea, any use outranks any form of talking about it):

{' > '.join(f'`{v}`' for v in order)}

{func_block}

Use `unknown` for function when the evidence exists but is insufficient to
judge (e.g. contexts that never anchor to the cited work, or content too
thin to place) -- this is a real, expected outcome, not a failure.

CENTRALITY VALUES -- how load-bearing the citation is for the citing work,
judged independently of (but informed by) function:

{centrality_block}

{codebook['guidance']}

FLAG VALUES (multi-valued; [] if none apply):

{flags_block}

RULES THAT DECIDE MOST CASES:
- `exemplifies` requires the cited work to be presented as ONE CANONICAL
  EXAMPLE of a category, usually with a short gloss ("DSLs such as X, Y, Z").
  `passing-citation` is bare list membership with no gloss and no individual
  attention -- the difference is whether the sentence does any work to single
  out the cited paper specifically, or just enumerates it.
- `detailed-citation` requires EITHER >=2 distinct in-text citation sites for
  our paper, OR >=1 sentence that targets our paper specifically (describes,
  credits, defines, compares, or criticizes it in particular -- negative and
  comparative statements count, and so does a "secondhand" citation like
  "TVM extends Halide's X" where the sentence is still specifically about the
  cited work, not just naming it in a list). A gloss shared by an entire list
  of works does not count as targeting any one of them specifically.
- `baseline` requires a MEASURED comparison (numbers against numbers), not
  just prose contrasting the two approaches -- that is `positions`.
- `uses-tool` vs `extends`: if the citing work's contribution includes
  CHANGING the cited artifact, it is `extends`; if the artifact is consumed
  unmodified as infrastructure, it is `uses-tool`.
- `uses-tool` vs `adopts-idea`: concept in, code out is `adopts-idea` --
  borrowing the abstraction/design without running the actual artifact.
- `supports-claim` is the case where a specific NUMBER OR FINDING travels
  from the cited paper into the citing work's argument, not a system.
- unclear/insufficient evidence is `unknown`, never a guess. A citation
  context that does not anchor to the cited work at all (wrong paper, garbled
  extraction, whole-proceedings record) should be `unknown` with flag
  `polluted-contexts` and confidence low, not forced into a function.
- `own-group`: only when a citing-work author plausibly matches a listed
  author of the cited paper (a shared-authors fact is given in the evidence
  when this is possible) -- do not guess from institution alone.
- Never invent a value outside the lists above."""


# ---------------------------------------------------------------- selection

def load_idmap():
    return json.load(open(IDMAP))


def load_publications():
    return {p['bibtexKey']: p for p in json.load(open(PUBLICATIONS))}


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


def load_abstracts(key):
    path = os.path.join(ABSTRACTS_DIR, key + '.json')
    if not os.path.exists(path):
        return {}
    return json.load(open(path))


def load_fulltext(key, slug):
    path = os.path.join(FULLTEXT_DIR, key, slug + '.txt')
    if not os.path.exists(path):
        return None
    with open(path) as fh:
        return fh.read()


def evidence_tier(citing, abstract, fulltext):
    has_contexts = bool(citing.get('contexts'))
    if fulltext:
        return 'fulltext'
    if abstract and has_contexts:
        return 'abstract+contexts'
    if abstract:
        return 'abstract'
    if has_contexts:
        return 'contexts'
    return 'title_only'


def author_surnames(author0):
    names = re.split(r'\s+and\s+', author0 or '')
    out = []
    for n in names:
        n = n.strip()
        if ',' in n:
            out.append(n.split(',')[0].strip().lower())
        elif n:
            out.append(n.split()[-1].lower())
    return set(s for s in out if s)


def shared_authors(pub, citing):
    ours = author_surnames(pub.get('author0'))
    theirs = {a.split()[-1].lower() for a in (citing.get('authors') or []) if a}
    return sorted(ours & theirs)


def load_candidates():
    """One entry per judgeable citing work, papers ordered by total citing
    count descending (task instruction), citing works within a paper in
    their existing harvest order."""
    idmap = load_idmap()
    pubs = load_publications()
    done = {
        tuple(os.path.relpath(p, OUT).split(os.sep))
        for p in glob.glob(os.path.join(OUT, '*', '*.json'))
    }
    done = {(d, os.path.splitext(s)[0]) for d, s in done}

    papers = []
    for path in glob.glob(os.path.join(CITATIONS_DIR, '*.json')):
        key = os.path.basename(path)[:-5]
        if key in PILOT_KEYS or key not in idmap:
            continue
        data = json.load(open(path))
        citing_list = data.get('citing') or []
        papers.append((key, citing_list))
    papers.sort(key=lambda kv: len(kv[1]), reverse=True)

    candidates = []
    for key, citing_list in papers:
        pub = pubs.get(key, {})
        abstracts = load_abstracts(key)
        for citing in citing_list:
            slug = slug_for(citing)
            if (key, slug) in done:
                continue
            abstract = abstracts.get(slug, {}).get('abstract')
            fulltext = load_fulltext(key, slug)
            tier = evidence_tier(citing, abstract, fulltext)
            if tier == 'title_only':
                continue
            candidates.append((key, slug, pub, citing, tier, abstract, fulltext))
    return candidates


# ---------------------------------------------------------------- the prompt

def pack_evidence(key, pub, citing, tier, abstract, fulltext):
    parts = [
        f"CITED PAPER (ours): {pub.get('title') or key!r}",
        f"  authors: {pub.get('author0') or '(unknown)'}",
        f"  year: {pub.get('year')}   venue: "
        f"{pub.get('venue') or pub.get('booktitle') or pub.get('journal') or '(unknown)'}",
        '',
        f"CITING WORK: {citing.get('title') or '(untitled)'!r}",
        f"  authors: {'; '.join(citing.get('authors') or []) or '(unknown)'}",
        f"  year: {citing.get('year')}   venue: {citing.get('venue') or '(unknown)'}"
        f"   doi: {citing.get('doi') or '(none)'}",
    ]
    shared = shared_authors(pub, citing)
    if shared:
        parts.append(f"  possible shared authors (surname match with cited paper): "
                     f"{', '.join(shared)}")
    if pub.get('doi') and citing.get('doi') and pub['doi'].lower() == (citing.get('doi') or '').lower():
        parts.append('  NOTE: this citing record shares the cited paper\'s own DOI '
                     '-- likely the paper citing itself (self-version).')

    parts.append('')
    parts.append(f"evidence tier: {tier}")
    infl = citing.get('isInfluential')
    parts.append(f"S2 isInfluential: {infl if infl is not None else '(no S2 match)'}")
    intents = citing.get('intents')
    if intents:
        parts.append(f"S2 intents: {', '.join(intents)}")

    contexts = citing.get('contexts') or []
    if contexts:
        parts.append(f"S2 citation contexts ({len(contexts)} total, showing up to "
                     f"{CONTEXTS_MAX}), verbatim sentences from the citing work that "
                     f"cite the cited paper:")
        for c in contexts[:CONTEXTS_MAX]:
            parts.append(f"  - {c}")

    if abstract:
        parts.append('')
        parts.append('CITING WORK ABSTRACT:')
        parts.append(abstract[:ABSTRACT_CHARS])

    if fulltext:
        parts.append('')
        parts.append('CITING WORK FULL TEXT (truncated):')
        parts.append(fulltext[:FULLTEXT_CHARS])

    return '\n'.join(parts)


def build_request(key, slug, pub, citing, tier, abstract, fulltext, codebook):
    custom_id = hashlib.sha1(f'{key}\x00{slug}'.encode()).hexdigest()[:40]
    return {
        'custom_id': custom_id,
        'params': {
            'model': MODEL,
            'max_tokens': MAX_TOKENS,
            'system': system_prompt(codebook),
            'messages': [{'role': 'user',
                          'content': pack_evidence(key, pub, citing, tier, abstract, fulltext)}],
        },
    }


# ---------------------------------------------------------------- validation

REQUIRED = ('function', 'secondary', 'centrality', 'flags', 'confidence', 'anchored', 'note')


def parse_record(text):
    text = (text or '').strip()
    text = re.sub(r'^```(?:json)?\s*|\s*```$', '', text)
    start, end = text.find('{'), text.rfind('}')
    if start < 0 or end <= start:
        raise ValueError('no JSON object in the response')
    return json.loads(text[start:end + 1])


def validate(record, codebook):
    problems = []
    for field in REQUIRED:
        if field not in record:
            problems.append(f'missing field {field}')
    if problems:
        return problems

    function_values = set(codebook['order']) | {'unknown'}
    if record['function'] not in function_values:
        problems.append(f"function {record['function']!r} not in vocabulary")
    if not isinstance(record['secondary'], list):
        problems.append('secondary is not a list')
    else:
        for v in record['secondary']:
            if v not in function_values:
                problems.append(f'secondary: {v!r} not in vocabulary')

    centrality_values = {v for v, _ in codebook['centrality']} | {'unknown'}
    if record['centrality'] not in centrality_values:
        problems.append(f"centrality {record['centrality']!r} not in vocabulary")

    flag_values = {f for f, _ in codebook['flags']}
    if not isinstance(record['flags'], list):
        problems.append('flags is not a list')
    else:
        for v in record['flags']:
            if v not in flag_values:
                problems.append(f'flags: {v!r} not in vocabulary')

    if record['confidence'] not in ('high', 'medium', 'low'):
        problems.append(f"confidence {record['confidence']!r} not high/medium/low")
    if record['anchored'] not in ('named', 'numref', 'none'):
        problems.append(f"anchored {record['anchored']!r} not named/numref/none")
    if not isinstance(record['note'], str) or not record['note'].strip():
        problems.append('note is empty')
    return problems


def finalize(record, key, slug, citing, tier):
    return {
        'paper': key,
        'slug': slug,
        'function': record['function'],
        'centrality': record['centrality'],
        'flags': record['flags'],
        'secondary': record['secondary'],
        'confidence': record['confidence'],
        'evidence': tier,
        'anchored': record['anchored'],
        'note': record['note'],
        'title': citing.get('title'),
        'year': citing.get('year'),
        's2_isInfluential': citing.get('isInfluential'),
        's2_intents': citing.get('intents'),
        'model': MODEL,
    }


def write_result(key, slug, citing, tier, text, codebook, usage=None):
    out_dir = os.path.join(OUT, key)
    os.makedirs(out_dir, exist_ok=True)
    try:
        parsed = parse_record(text)
        problems = validate(parsed, codebook)
    except Exception as exc:
        parsed, problems = None, [f'{type(exc).__name__}: {exc}']

    if problems:
        os.makedirs(OUT, exist_ok=True)
        with open(REVIEW, 'a') as fh:
            fh.write(json.dumps({'paper': key, 'slug': slug, 'problems': problems,
                                 'raw': (text or '')[:4000]}, ensure_ascii=False) + '\n')
        return None

    record = finalize(parsed, key, slug, citing, tier)
    if usage:
        record['usage'] = usage
    path = os.path.join(out_dir, slug + '.json')
    with open(path, 'w') as fh:
        json.dump(record, fh, indent=1, ensure_ascii=False)
    return record


def do_recover(codebook):
    """Re-validate needs-review.jsonl against the CURRENT rules and promote
    whatever now passes. Makes no API call."""
    if not os.path.exists(REVIEW):
        print('no review file'); return
    with open(REVIEW) as fh:
        rows = [json.loads(line) for line in fh if line.strip()]

    idmap = load_idmap()
    citing_by_key = {}

    def citing_for(key, slug):
        if key not in citing_by_key:
            path = os.path.join(CITATIONS_DIR, key + '.json')
            data = json.load(open(path)) if os.path.exists(path) else {'citing': []}
            citing_by_key[key] = {slug_for(c): c for c in data.get('citing') or []}
        return citing_by_key[key].get(slug, {})

    promoted, remaining = [], []
    for row in rows:
        key, slug = row['paper'], row['slug']
        if os.path.exists(os.path.join(OUT, key, slug + '.json')):
            continue
        try:
            parsed = parse_record(row.get('raw'))
            problems = validate(parsed, codebook)
        except Exception as exc:
            problems = [f'{type(exc).__name__}: {exc}']
        if problems:
            row['problems'] = problems
            remaining.append(row)
            continue
        citing = citing_for(key, slug)
        record = finalize(parsed, key, slug, citing, evidence_tier(citing, None, None))
        out_dir = os.path.join(OUT, key)
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, slug + '.json'), 'w') as fh:
            json.dump(record, fh, indent=1, ensure_ascii=False)
        promoted.append((key, slug))

    with open(REVIEW, 'w') as fh:
        for row in remaining:
            fh.write(json.dumps(row, ensure_ascii=False) + '\n')

    print(f'{len(promoted)} promoted to records/, {len(remaining)} still in review')
    reasons = collections.Counter(str(p)[:60] for row in remaining for p in row['problems'])
    for reason, count in reasons.most_common():
        print(f'  {count:4d}  {reason}')


# ---------------------------------------------------------------- http

def call(method, path, payload=None, tries=6):
    key = os.environ.get('ANTHROPIC_BATCH_KEY')
    if not key:
        sys.exit('set ANTHROPIC_BATCH_KEY first (NOT ANTHROPIC_API_KEY -- that '
                 'breaks Claude Code logins)')
    url = path if path.startswith('http') else f'{API}{path}'
    body = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(url, data=body, method=method, headers={
        'x-api-key': key,
        'anthropic-version': '2023-06-01',
        'content-type': 'application/json',
        'user-agent': 'nextgen-classify-citations',
    })
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                return response.read().decode()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode()[:300]
            if exc.code in (429, 500, 502, 503, 504, 529):
                wait = min(300, 10 * 2 ** attempt)
                print(f'    {exc.code}; sleeping {wait}s  {detail[:120]}')
                time.sleep(wait)
                continue
            sys.exit(f'{exc.code} {detail}')
        except Exception as exc:
            print(f'    {type(exc).__name__}; retrying in 20s')
            time.sleep(20)
    sys.exit('gave up after repeated failures')


# ---------------------------------------------------------------- modes

def do_pilot(count, seed, codebook):
    candidates = load_candidates()
    random.Random(seed).shuffle(candidates)
    picked = candidates[:count]
    print(f'{len(candidates)} judgeable candidates; piloting {len(picked)}\n')
    for key, slug, pub, citing, tier, abstract, fulltext in picked:
        request = build_request(key, slug, pub, citing, tier, abstract, fulltext, codebook)
        response = json.loads(call('POST', '/messages', request['params']))
        text = ''.join(b.get('text', '') for b in response.get('content', []))
        usage = response.get('usage')
        record = write_result(key, slug, citing, tier, text, codebook, usage)
        print('=' * 78)
        print(key, slug, '->', 'OK' if record else 'NEEDS REVIEW', json.dumps(usage))
        print(json.dumps(record, indent=1, ensure_ascii=False) if record
              else (text or '')[:1500])
        time.sleep(1)
    print(f'\nrecords in {OUT}/<paper>/, failures in {REVIEW}')


def do_submit(codebook, dry_run, limit):
    candidates = load_candidates()
    if limit:
        candidates = candidates[:limit]
    if not candidates:
        return print('nothing to submit')
    requests_ = [build_request(key, slug, pub, citing, tier, abstract, fulltext, codebook)
                 for key, slug, pub, citing, tier, abstract, fulltext in candidates]
    lookup = {r['custom_id']: {'paper': key, 'slug': slug}
              for r, (key, slug, *_ ) in zip(requests_, candidates)}
    os.makedirs(OUT, exist_ok=True)

    if dry_run:
        with open(REQUESTS_DUMP, 'w') as fh:
            json.dump(requests_, fh, indent=1, ensure_ascii=False)
        size = os.path.getsize(REQUESTS_DUMP)
        chars = sum(len(r['params']['system']) + len(r['params']['messages'][0]['content'])
                    for r in requests_)
        avg_chars = chars // len(requests_)
        avg_input_tokens = avg_chars // 4
        total_input_tokens = avg_input_tokens * len(requests_)
        total_output_tokens = EST_OUTPUT_TOKENS * len(requests_)
        input_cost = total_input_tokens / 1e6 * BATCH_INPUT_PER_MTOK
        output_cost = total_output_tokens / 1e6 * BATCH_OUTPUT_PER_MTOK
        print(f'{len(requests_)} requests, {size / 1e6:.1f} MB total,')
        print(f'{avg_chars} chars of prompt each (~{avg_input_tokens} input tokens; '
              f'the system prompt is fixed at ~{len(system_prompt(codebook)) // 4} '
              f'tokens and repeats every request)')
        print(f'\nCOST ESTIMATE (model={MODEL}, batch pricing '
              f'${BATCH_INPUT_PER_MTOK}/${BATCH_OUTPUT_PER_MTOK} per MTok in/out):')
        print(f'  input:  ~{total_input_tokens/1e6:.2f}M tokens -> ${input_cost:,.2f}')
        print(f'  output: ~{total_output_tokens/1e6:.2f}M tokens (assuming '
              f'~{EST_OUTPUT_TOKENS} tokens/response) -> ${output_cost:,.2f}')
        print(f'  TOTAL:  ~${input_cost + output_cost:,.2f}')
        print('  (no prompt-caching credit assumed; actual cost may be lower)')
        print(f'\nwrote {REQUESTS_DUMP}; sent nothing')
        return

    state = json.load(open(STATE)) if os.path.exists(STATE) else {'batches': [], 'items': {}}
    state['items'].update(lookup)
    for start in range(0, len(requests_), PER_BATCH):
        chunk = requests_[start:start + PER_BATCH]
        result = json.loads(call('POST', '/messages/batches', {'requests': chunk}))
        state['batches'].append({'id': result['id'], 'n': len(chunk),
                                 'created': result.get('created_at'), 'collected': False})
        json.dump(state, open(STATE, 'w'), indent=1)
        print(f'  submitted {result["id"]}  {len(chunk)} requests')
    print(f'\n{len(state["batches"])} batches recorded in {STATE}')
    print('come back and run --status, then --collect')


def load_state():
    if not os.path.exists(STATE):
        sys.exit(f'no {STATE}; run --submit first')
    return json.load(open(STATE))


def do_status():
    state = load_state()
    for batch in state['batches']:
        info = json.loads(call('GET', f'/messages/batches/{batch["id"]}'))
        counts = info.get('request_counts', {})
        print(f'{batch["id"]}  {info.get("processing_status"):12s} '
              f'{json.dumps(counts)}  collected={batch["collected"]}')


def do_collect(codebook):
    state = load_state()
    items = state.get('items', {})
    # Need the citing record + evidence tier for every custom_id to finalize.
    # Rebuild the same candidate list (deterministic) rather than persist the
    # full evidence in state.json.
    candidates = {hashlib.sha1(f'{key}\x00{slug}'.encode()).hexdigest()[:40]:
                  (key, slug, citing, tier)
                  for key, slug, pub, citing, tier, abstract, fulltext in load_candidates()}

    written = failed = 0
    for batch in state['batches']:
        if batch['collected']:
            continue
        info = json.loads(call('GET', f'/messages/batches/{batch["id"]}'))
        if info.get('processing_status') != 'ended':
            print(f'{batch["id"]}: {info.get("processing_status")}, skipping')
            continue
        body = call('GET', info['results_url'])
        for line in body.splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            custom_id = row.get('custom_id')
            item = items.get(custom_id) or {}
            key, slug = item.get('paper'), item.get('slug')
            result = row.get('result') or {}
            if result.get('type') != 'succeeded':
                with open(REVIEW, 'a') as fh:
                    fh.write(json.dumps({'paper': key, 'slug': slug,
                                         'problems': [f'batch result {result.get("type")}'],
                                         'raw': json.dumps(result)[:2000]}) + '\n')
                failed += 1
                continue
            message = result.get('message') or {}
            text = ''.join(b.get('text', '') for b in message.get('content', []))
            cand = candidates.get(custom_id)
            if not cand:
                # already collected in a previous pass and removed from the
                # pending set by load_candidates()'s `done` filter
                citing_path = os.path.join(CITATIONS_DIR, (key or '') + '.json')
                citing = {}
                if key and os.path.exists(citing_path):
                    for c in json.load(open(citing_path)).get('citing') or []:
                        if slug_for(c) == slug:
                            citing = c
                            break
                tier = evidence_tier(citing, None, None)
            else:
                _, _, citing, tier = cand
            if write_result(key, slug, citing, tier, text, codebook, message.get('usage')):
                written += 1
            else:
                failed += 1
        batch['collected'] = True
        json.dump(state, open(STATE, 'w'), indent=1)
        print(f'{batch["id"]}: collected')
    print(f'\n{written} records written to {OUT}/<paper>/')
    print(f'{failed} sent to {REVIEW}')


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--pilot', type=int, metavar='N')
    parser.add_argument('--seed', type=int, default=17)
    parser.add_argument('--submit', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--limit', type=int)
    parser.add_argument('--status', action='store_true')
    parser.add_argument('--collect', action='store_true')
    parser.add_argument('--recover', action='store_true')
    parser.add_argument('--print-prompt', action='store_true',
                        help='print the generated system prompt and exit; no API call')
    args = parser.parse_args()

    codebook = parse_codebook()
    if args.print_prompt:
        print(system_prompt(codebook))
    elif args.pilot:
        do_pilot(args.pilot, args.seed, codebook)
    elif args.submit:
        do_submit(codebook, args.dry_run, args.limit)
    elif args.status:
        do_status()
    elif args.collect:
        do_collect(codebook)
    elif args.recover:
        do_recover(codebook)
    else:
        parser.error('pick one of --pilot N, --submit, --status, --collect, '
                     '--recover, --print-prompt')


if __name__ == '__main__':
    main()
