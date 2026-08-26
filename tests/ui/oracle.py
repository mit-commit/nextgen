#!/usr/bin/env python3
"""Independent Python re-implementation of assets/js/publications.js's
dedupe / facet / filter / sort / group logic, computed straight from the
data files (data/publications.json, data/citations/*, data/repos/*).

Kept deliberately line-for-line faithful to the JS (same variable names
where practical) rather than "improved," since its only job is to agree
with the real code -- a cleverer reimplementation would just be a second
place for the two to silently diverge.
"""
import json
import math
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

THESIS_TYPES = {'mastersthesis', 'phdthesis', 'sciencethesis', 'sbthesis'}

VENUE_SHORT_MAP = {
    'acm transactions on graphics': 'TOG',
    'communications of the acm': 'CACM',
    'acm transactions on programming languages and systems': 'TOPLAS',
    'acm transactions on architecture and code optimization': 'TACO',
    'acm transactions on computer systems': 'TOCS',
    'ieee micro': 'IEEE Micro',
    'ieee computer': 'IEEE Computer',
    'ieee transactions on computers': 'IEEE TC',
    'international journal of parallel programming': 'IJPP',
    'journal of instruction-level parallelism': 'JILP',
}

TYPE_LABELS = {
    'inproceedings': 'Conference Pub',
    'article': 'Journal Article',
    'mastersthesis': 'M.Eng. Thesis',
    'phdthesis': 'PhD Thesis',
    'techreport': 'Tech Report',
    'book': 'Book',
    'incollection': 'Book Chapter',
    'misc': 'Other',
    'sciencethesis': 'SM Thesis',
    'sbthesis': 'SB Thesis',
}

MONTH_ABBR = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
MONTH_MAP = {'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
             'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12}

WEIGHTS = {
    'extends': 10, 'uses-tool': 8, 'adopts-idea': 8,
    'uses-benchmark': 5, 'baseline': 5, 'positions': 3,
    'surveys': 2, 'supports-claim': 2, 'exemplifies': 1,
    'detailed-citation': 1, 'passing-citation': 0.5,
}


def first_defined(*vals):
    for v in vals:
        if v is not None and v != '':
            return v
    return ''


def normalize_title(s):
    return re.sub(r'\s+', ' ', str(s or '')).strip().lower()


def normalize_type(t):
    return re.sub(r'\s+', ' ', str(t or 'misc')).strip().lower()


def normalize_author_name(name):
    t = str(name or '').strip()
    if not t:
        return ''
    comma = t.find(',')
    if comma >= 0:
        last = t[:comma].strip()
        first = t[comma + 1:].strip()
        if first:
            return first + ' ' + last
        return last
    return t


def _tokenize_authors(raw):
    s = str(raw or '').strip()
    if not s:
        return []
    if re.search(r'\band\b', s, re.I):
        return [x.strip() for x in re.split(r'\s+and\s+', s, flags=re.I) if x.strip()]
    parts = re.split(r'\s*,\s*', s)
    out = []
    i = 0
    while i < len(parts):
        if i + 1 < len(parts):
            out.append(parts[i] + ', ' + parts[i + 1])
        else:
            out.append(parts[i])
        i += 2
    return out


def list_normalized_authors_from_string(s):
    return [n for n in (normalize_author_name(t) for t in _tokenize_authors(s)) if n]


def authors_raw_of(it):
    return first_defined(it.get('author0'), it.get('authors'), it.get('author'))


def list_normalized_authors(it):
    return list_normalized_authors_from_string(authors_raw_of(it))


def first_author_of(it):
    a = list_normalized_authors(it)
    return a[0] if a else ''


def first_author_first_name(it):
    n = first_author_of(it)
    if not n:
        return ''
    return n.split()[0]


def first_author_last_name(it):
    n = first_author_of(it)
    if not n:
        return ''
    return n.split()[-1]


def type_label(k):
    k = (k or 'misc').lower().strip()
    return TYPE_LABELS.get(k, k[:1].upper() + k[1:] if k else k)


def month_num(s):
    if not s:
        return 0
    st = str(s).strip()
    if not st:
        return 0
    m = re.match(r'^(\d{1,2})$', st)
    if m:
        num = int(m.group(1))
        if 1 <= num <= 12:
            return num
    key = st[:3].lower()
    return MONTH_MAP.get(key, 0)


def month_label_from_parts(parts):
    if not parts or not parts.get('month'):
        return 'Other'
    base = MONTH_ABBR[parts['month']] if parts['month'] < len(MONTH_ABBR) else ''
    if not base:
        return 'Other'
    if parts.get('day'):
        return base + ' ' + str(parts['day'])
    return base


def parse_month_day(it):
    month = 0
    day = 0
    date = it.get('date') if it else None
    if date:
        m = re.match(r'^(\d{4})(?:-(\d{1,2})(?:-(\d{1,2}))?)?', str(date).strip())
        if m:
            if m.group(2):
                pm = int(m.group(2))
                if 1 <= pm <= 12:
                    month = pm
            if m.group(3):
                pd = int(m.group(3))
                day = max(0, pd)
    if not month and it and it.get('month'):
        month = month_num(it['month'])
    if not day and it and it.get('day'):
        try:
            day = max(0, int(it['day']))
        except (TypeError, ValueError):
            pass
    return {'month': month, 'day': day}


def month_day_value(it):
    parts = parse_month_day(it)
    if not parts['month']:
        return 0
    return parts['month'] * 100 + min(99, max(0, parts.get('day') or 0))


def month_label_of(it):
    if not it:
        return 'Other'
    parts = parse_month_day(it)
    if not parts['month']:
        return 'Other'
    if it.get('month') and month_num(it['month']) == parts['month']:
        return str(it['month'])
    return month_label_from_parts(parts)


def split_keywords(s):
    if not s:
        return []
    return [p.strip() for p in re.split(r'[,;]+', s) if p.strip()]


def topics_of(it):
    topics = it.get('topics') if it else None
    if not topics:
        return []
    if isinstance(topics, list):
        return [str(t).strip() for t in topics if str(t).strip()]
    return split_keywords(topics)


def projects_of(it):
    pr = str(it.get('project') or '').strip() if it else ''
    return [pr] if pr else []


def tags_of(it):
    out = list(topics_of(it))
    pr = str(it.get('project') or '').strip() if it else ''
    if pr and pr not in out:
        out.append(pr)
    return out


def venue_raw_of(it):
    return first_defined(it.get('booktitle'), it.get('journal'), it.get('series'))


def venue_of(it):
    return first_defined(it.get('journal'), it.get('booktitle'), it.get('series'),
                          it.get('type'), it.get('publisher'))


def venue_short_of(it):
    if it.get('venueShort'):
        return str(it['venueShort']).strip()
    raw = str(venue_raw_of(it) or '')
    m = re.search(r'\(([^()]{1,20})\)\s*$', raw)
    if m:
        abbr = m.group(1).strip()
        if abbr and re.search(r'[A-Za-z]', abbr) and not re.match(r'^\d', abbr):
            return abbr
    key = raw.lower().strip()
    return VENUE_SHORT_MAP.get(key, '')


def category_key_of(it, type_mode):
    t = (it.get('itemType') or 'misc').lower().strip()
    if type_mode != 'venue':
        return 'type:' + t
    if t in THESIS_TYPES or t == 'techreport':
        return 'type:' + t
    if t in ('inproceedings', 'article'):
        vs = venue_short_of(it)
        if vs:
            return 'venue:' + vs
    return 'venue:__other__'


def category_label_of(key):
    if key == 'venue:__other__':
        return 'Other'
    if key.startswith('type:'):
        return type_label(key[5:])
    if key.startswith('venue:'):
        return key[6:]
    return key


def category_bucket(key):
    if key == 'venue:__other__':
        return 2
    return 0 if key.startswith('type:') else 1


def bibtex_key_of(it):
    if it.get('bibtexKey'):
        return it['bibtexKey']
    t = re.sub(r'[^a-z0-9]+', '', (it.get('title') or 'untitled').lower())
    return t[:24] + (str(it['year']) if it.get('year') else '')


def title_of(it):
    return it.get('title') or 'Untitled'


# ---------- Load + dedupe (mirrors the boot-time IIFE) ----------

def load_data(root=ROOT):
    with open(os.path.join(root, 'data', 'publications.json')) as fh:
        raw = json.load(fh)
    return dedupe(raw)


def dedupe(data):
    def is_better(a, b):
        a_pdf, b_pdf = bool(a.get('url')), bool(b.get('url'))
        if a_pdf != b_pdf:
            return a_pdf
        a_doi, b_doi = bool(a.get('doi')), bool(b.get('doi'))
        if a_doi != b_doi:
            return a_doi
        a_sl, b_sl = bool(a.get('slides')), bool(b.get('slides'))
        if a_sl != b_sl:
            return a_sl
        return False

    best_by_key = {}
    order = []
    for it in data:
        key = normalize_title(it.get('title')) + '|' + normalize_type(it.get('itemType'))
        if key not in best_by_key:
            best_by_key[key] = it
            order.append(key)
        elif is_better(it, best_by_key[key]):
            best_by_key[key] = it
    return [best_by_key[k] for k in order]


def load_citations_index(root=ROOT):
    path = os.path.join(root, 'data', 'citations', 'index.json')
    if not os.path.exists(path):
        return {}
    with open(path) as fh:
        d = json.load(fh)
    return d.get('papers') or {}


def load_repos_index(root=ROOT):
    path = os.path.join(root, 'data', 'repos', 'index.json')
    if not os.path.exists(path):
        return {}
    with open(path) as fh:
        d = json.load(fh)
    return d.get('papers') or {}


def load_impact_authors(root=ROOT):
    path = os.path.join(root, 'data', 'impact-authors.json')
    if not os.path.exists(path):
        return {}, []
    with open(path) as fh:
        d = json.load(fh)
    people = d.get('people') or []
    by_paper = {}
    for p in people:
        for k in p.get('papers', []):
            by_paper.setdefault(k, []).append(p['name'])
    return by_paper, [p['name'] for p in people]


def display_count(row):
    if not row:
        return 0
    return max(row.get('verified') or 0, row.get('gscholar') or 0)


def impact_score(row):
    if not row or not row.get('functions'):
        return None
    s = 0.0
    for f, n in row['functions'].items():
        s += WEIGHTS.get(f, 0) * n
    # JS Math.round rounds halves UP; Python round() is half-to-even.
    # A paper whose only citation is passing (0.5) scores 1 on the page.
    return math.floor(s + 0.5)


def cite_count_of(it, cite_index):
    row = cite_index.get(bibtex_key_of(it))
    if not row:
        return -1
    return display_count(row)


IMPACT_NOW_Y = 2026  # mirrors new Date().getFullYear() at test time


def award_year_of(it):
    py = None
    try:
        py = int(it.get('year'))
    except (TypeError, ValueError):
        py = IMPACT_NOW_Y
    best = py
    for m in re.findall(r'\b((?:19|20)\d{2})\b', str(it.get('price') or '')):
        yy = int(m)
        if yy >= py and yy > best:
            best = yy
    return best


def venue_bonus(v):
    v = str(v or '')
    if re.search(r'\bPLDI\b', v):
        return 2.0
    if re.search(r'\bASPLOS\b|\bOOPSLA\b|\bISCA\b', v):
        return 1.0
    if 'HPCA Workshop' in v:
        return 0.0
    if re.search(r'\bCGO\b|\bMICRO\b|\bPACT\b|\bPPoPP\b|\bPOPL\b|\bSOSP\b'
                 r'|USENIX Security|P?VLDB|\bHPCA\b|Communications of the ACM|\bCACM\b', v):
        return 0.5
    if re.search(r'\bTOPLAS\b|Transactions on Programming Languages|\bTACO\b'
                 r'|Architecture and Code Optimization|Transactions on Graphics|SIGGRAPH'
                 r'|\bICML\b|\bICS\b|NeurIPS|MLSys|\bSC\b|Supercomputing', v):
        return 0.25
    return 0.0


def composite_impact_of(it, cite_index, repo_index):
    """His formula 2026-08-26: 2e^(-age/5) + [award] 5e^(-awardAge/10)
    + displayed citations/100 + repos/1000, theses -2. Every paper scores."""
    key = bibtex_key_of(it)
    try:
        age = IMPACT_NOW_Y - int(it.get('year'))
    except (TypeError, ValueError):
        age = 0
    s = 2 * math.exp(-age / 5.0)
    if it.get('price'):
        s += 5 * math.exp(-(IMPACT_NOW_Y - award_year_of(it)) / 10.0)
    c_row = cite_index.get(key)
    if c_row:
        s += (display_count(c_row) or 0) / 100.0
    r_row = repo_index.get(key)
    if r_row:
        s += (r_row.get('repos') or 0) / 1000.0
    s += venue_bonus(it.get('venue'))
    itype = str(it.get('itemType') or '').lower()
    if 'thesis' in itype:
        tt = str(it.get('type') or '').lower()
        if re.search(r'ph\.?\s*d', tt):
            s -= 1
        elif re.search(r's\.?\s*b', tt):
            s -= 4
        elif re.search(r'm\.?\s*eng', tt):
            s -= 3
        elif re.search(r's\.?\s*m', tt):
            s -= 2
        else:
            s -= 2
    elif itype not in ('inproceedings', 'article'):
        s -= 5  # not a conference or journal paper
    return s


class ImpactQuantiles(object):
    """Mirrors impactVals()/compositeQuantile(): descending list of every
    paper's composite impact (by key present in either index), memoized."""

    def __init__(self, cite_index, repo_index, items=None):
        items = items if items is not None else load_data()
        vals = []
        for it in items:
            v = composite_impact_of(it, cite_index, repo_index)
            if v is not None:
                vals.append(v)
        vals.sort(reverse=True)
        self.vals = vals

    def quantile(self, q):
        if not self.vals:
            return 0
        idx = min(len(self.vals) - 1, max(0, round(len(self.vals) * q) - 1))
        return self.vals[idx]

    def tier_label(self, score):
        if score is None or score < 0:
            return 'No impact data yet'
        if score >= self.quantile(0.03):
            return 'Top 3% by impact'
        if score >= self.quantile(0.10):
            return 'Top 10% by impact'
        if score >= self.quantile(0.25):
            return 'Top quarter by impact'
        if score >= self.quantile(0.50):
            return 'Top half by impact'
        return 'Lower half by impact'


# ---------- Facet state + filtering (mirrors filteredItems) ----------

class State(object):
    def __init__(self):
        self.title_query = ''
        self.years = set()
        self.keywords = set()   # values from tagsOf() regardless of kwMode
        self.authors = set()
        self.types = set()      # categoryKeyOf() values, mode-dependent
        self.cite_authors = set()
        self.type_mode = 'type'  # 'type' | 'venue'
        self.min_cites = 0
        self.min_impact = 0


def filtered_items(data, state, cite_index, repo_index, impact_by_paper,
                    exclude_facet=None):
    items = list(data)

    q = re.sub(r'\s+', ' ', state.title_query).strip().lower()
    if q:
        items = [it for it in items if q in (it.get('title') or '').lower()]

    if exclude_facet != 'years' and state.years:
        items = [it for it in items if it.get('year') and str(it['year']) in state.years]

    if exclude_facet != 'keywords' and state.keywords:
        items = [it for it in items if any(k in state.keywords for k in tags_of(it))]

    if exclude_facet != 'authors' and state.authors:
        items = [it for it in items
                 if any(a in state.authors for a in list_normalized_authors(it))]

    if exclude_facet != 'types' and state.types:
        items = [it for it in items if category_key_of(it, state.type_mode) in state.types]

    if exclude_facet != 'citeAuthors' and state.cite_authors:
        items = [it for it in items
                 if any(a in state.cite_authors
                        for a in impact_by_paper.get(bibtex_key_of(it), []))]

    if state.min_cites > 0:
        items = [it for it in items if cite_count_of(it, cite_index) >= state.min_cites]

    if state.min_impact > 0:
        def ok(it):
            imp = composite_impact_of(it, cite_index, repo_index)
            return imp is not None and imp >= state.min_impact
        items = [it for it in items if ok(it)]

    return items


def default_sorted(items):
    """applyFilters()'s final sort: year desc, then monthDayValue desc."""
    def key(it):
        y = int(it['year']) if it.get('year') else 0
        return (-y, -month_day_value(it))
    return sorted(items, key=key)


# ---------- Facet value universes (mirrors rebuild*Facet / buildYearGrid) ----------

def year_values(data):
    years = sorted({int(it['year']) for it in data if it.get('year')}, reverse=True)
    return [str(y) for y in years]


def type_values(data, type_mode):
    counts = {}
    for it in data:
        k = category_key_of(it, type_mode)
        counts[k] = counts.get(k, 0) + 1
    keys = list(counts.keys())
    keys.sort(key=lambda k: (category_bucket(k), category_label_of(k).lower()))
    return keys


def keyword_values(data, kw_mode):
    vals = set()
    for it in data:
        vals |= set(projects_of(it) if kw_mode == 'projects' else topics_of(it))
    return sorted(vals, key=lambda s: s.lower())


def author_values(data):
    vals = set()
    for it in data:
        vals |= set(list_normalized_authors(it))
    return vals


# ---------- Grouping/sort within the rendered list (mirrors renderList) ----------

def key_for(it, which, cite_index, repo_index):
    if which == 'year':
        return int(it['year']) if it.get('year') else 0
    if which == 'citations':
        ci = composite_impact_of(it, cite_index, repo_index)
        return -1 if ci is None else ci
    if which == 'month':
        return month_day_value(it)
    if which == 'type':
        return type_label(it.get('itemType') or 'misc')
    if which == 'authors':
        a = list_normalized_authors(it)
        return a[0] if a else 'zzz'
    if which == 'authorFirst':
        return first_author_first_name(it) or 'zzz'
    if which == 'authorLast':
        return first_author_last_name(it) or 'zzz'
    if which == 'keywords':
        ks = sorted(tags_of(it))
        return ks[0] if ks else 'zzz'
    return ''


def unique_order(arr):
    seen = set()
    out = []
    for k in arr:
        k = k or 'none'
        if k == 'none':
            out.append('none')
            continue
        if k not in seen:
            seen.add(k)
            out.append(k)
    while len(out) < 4:
        out.append('none')
    return out[:4]


def render_list_groups(items, sort_order, cite_index, repo_index, quantiles):
    """Returns (is_flat, ordered_headers, {header: [items]]}) mirroring
    renderList(): header order + per-group item order, ready to compare
    against the DOM's rendered h3 sequence and title order."""
    order = unique_order(sort_order)
    active = [k for k in order if k != 'none']

    def sort_key_cmp(which):
        if which in ('year', 'month', 'citations'):
            return lambda it: -key_for(it, which, cite_index, repo_index)
        return lambda it: str(key_for(it, which, cite_index, repo_index)).lower()

    if not active or order[0] == 'none':
        flat = list(items)
        for which in reversed(order):
            if which == 'none':
                continue
            flat = sorted(flat, key=sort_key_cmp(which))
        return True, ['__flat__'], {'__flat__': flat}

    primary = active[0]
    rest = [k for k in order if k != 'none' and k != primary]

    groups = {}
    group_sort_value = {}

    def add(label, it, sort_val=None):
        groups.setdefault(label, []).append(it)
        if sort_val is not None:
            cur = group_sort_value.get(label)
            if cur is None or sort_val > cur:
                group_sort_value[label] = sort_val

    for it in items:
        if primary == 'year':
            add(str(it['year']) if it.get('year') else 'Other', it)
        elif primary == 'month':
            label = month_label_of(it)
            sort_val = 0 if label == 'Other' else month_day_value(it)
            add(label, it, sort_val)
        elif primary == 'type':
            add(type_label(it.get('itemType') or 'misc'), it)
        elif primary == 'authors':
            aus = list_normalized_authors(it)
            if aus:
                for a in aus:
                    add(a, it)
            else:
                add('Other', it)
        elif primary == 'authorFirst':
            add(first_author_first_name(it) or 'Other', it)
        elif primary == 'authorLast':
            add(first_author_last_name(it) or 'Other', it)
        elif primary == 'keywords':
            ks = tags_of(it)
            if ks:
                for k in ks:
                    add(k, it)
            else:
                add('Other', it)
        elif primary == 'citations':
            n = key_for(it, 'citations', cite_index, repo_index)
            add(quantiles.tier_label(n), it, n)

    headers = list(groups.keys())

    def header_cmp(a, b):
        if primary == 'year':
            if a == 'Other' and b != 'Other':
                return 1
            if b == 'Other' and a != 'Other':
                return -1
            return (int(b) if b.isdigit() else 0) - (int(a) if a.isdigit() else 0)
        if primary == 'month':
            if a == 'Other' and b != 'Other':
                return 1
            if b == 'Other' and a != 'Other':
                return -1
            av = group_sort_value.get(a, 0)
            bv = group_sort_value.get(b, 0)
            if av != bv:
                return bv - av
            return -1 if a.lower() < b.lower() else (1 if a.lower() > b.lower() else 0)
        if primary == 'citations':
            av = group_sort_value.get(a, -1)
            bv = group_sort_value.get(b, -1)
            return bv - av
        return -1 if a.lower() < b.lower() else (1 if a.lower() > b.lower() else 0)

    import functools
    headers.sort(key=functools.cmp_to_key(header_cmp))

    out_groups = {}
    for label in headers:
        arr = list(groups[label])
        for which in reversed(rest):
            arr = sorted(arr, key=sort_key_cmp(which))
        if primary == 'citations':
            arr = sorted(arr, key=lambda it: -key_for(it, 'citations', cite_index, repo_index))
        out_groups[label] = arr

    return False, headers, out_groups


if __name__ == '__main__':
    data = load_data()
    ci = load_citations_index()
    ri = load_repos_index()
    ia, all_names = load_impact_authors()
    print('publications (deduped):', len(data))
    print('years:', year_values(data)[:5], '...')
    print('type facet values:', type_values(data, 'type'))
    print('venue facet values:', type_values(data, 'venue')[:10], '...')
    print('distinct authors:', len(author_values(data)))
    print('distinct topics:', len(keyword_values(data, 'topics')))
    print('cite-and-used-by names:', len(all_names))
    q = ImpactQuantiles(ci, ri)
    print('impact quantiles (50/25/10/3):',
          q.quantile(0.50), q.quantile(0.25), q.quantile(0.10), q.quantile(0.03))
