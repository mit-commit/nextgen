#!/usr/bin/env python3
"""UI combinatorial test run (tasks/QUEUE.md round 11 task 1).

Cross-checks the live publications.html (served from the repo root, e.g.
`python3 -m http.server 8123`) against an independent Python oracle
(oracle.py) computed straight from data/publications.json + data/citations/*
+ data/repos/*, over every single-facet value, sampled pairwise and 3-4-way
combinations, a sample of Group&sort modes, and a sample of the citation
panel's global sort + Show-toggle buttons.

Usage:
    python3 tests/ui/facet_test.py [--base-url http://localhost:8123] [--headed]

Writes tests/ui/combinatorial-report.md with pass/fail counts and repro selections for
every failure found.
"""
import argparse
import functools
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oracle  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = oracle.ROOT

DEFAULT_SORT_ORDER = ['year', 'month', 'type', 'authorLast']


def load_page():
    from playwright.sync_api import sync_playwright
    return sync_playwright()


# ---------------- Oracle-side state + rendering ----------------

class Facts(object):
    def __init__(self):
        self.data = oracle.load_data()
        self.ci = oracle.load_citations_index()
        self.ri = oracle.load_repos_index()
        self.impact_by_paper, self.all_cite_authors = oracle.load_impact_authors()
        self.quantiles = oracle.ImpactQuantiles(self.ci, self.ri)


F = None  # set in main()


def oracle_titles_for(state, sort_order):
    items = oracle.filtered_items(F.data, state, F.ci, F.ri, F.impact_by_paper)
    items = oracle.default_sorted(items)
    is_flat, headers, groups = oracle.render_list_groups(items, sort_order, F.ci, F.ri, F.quantiles)
    total = len(items)
    if is_flat:
        return total, True, [oracle.title_of(it) for it in groups['__flat__']]
    else:
        return total, False, [(h, [oracle.title_of(it) for it in groups[h]]) for h in headers]


def parse_count(text):
    m = None
    import re
    mm = re.search(r'\((\d+)\)', text or '')
    return int(mm.group(1)) if mm else None


# ---------------- Browser-side actions (all via JS eval; avoids any
# CSS-selector-escaping issues with author/topic names full of
# punctuation) ----------------

JS_CLICK_CHECKBOX = """
([boxId, value]) => {
  const box = document.getElementById(boxId);
  if (!box) return 'no-box';
  const inputs = box.querySelectorAll('input[type=checkbox]');
  for (const cb of inputs) {
    if (cb.value === value) {
      if (cb.disabled) return 'disabled';
      cb.click();
      return 'clicked:' + cb.checked;
    }
  }
  return 'not-found';
}
"""

JS_BADGE_FOR = """
([boxId, value]) => {
  const box = document.getElementById(boxId);
  if (!box) return null;
  const inputs = box.querySelectorAll('input[type=checkbox]');
  for (const cb of inputs) {
    if (cb.value === value) {
      const span = cb.parentElement.querySelector('.cat-counts');
      return span ? span.textContent : null;
    }
  }
  return null;
}
"""

JS_READ_RENDER = """
() => {
  const mount = document.getElementById('pubs-results');
  const countText = document.getElementById('pubs-count').textContent;
  function titlesOfUl(ul) {
    return Array.from(ul.querySelectorAll('li.pub-item > .pub-title')).map(t => {
      let s = t.textContent || '';
      if (s.endsWith('.')) s = s.slice(0, -1);
      return s;
    });
  }
  const directUl = mount.querySelector(':scope > ul.pub-list');
  if (directUl) return { flat: true, titles: titlesOfUl(directUl), count: countText };
  const container = mount.firstElementChild;
  const groups = [];
  if (container) {
    Array.from(container.children).forEach(sec => {
      const h3 = sec.querySelector('h3');
      const ul = sec.querySelector('ul.pub-list');
      groups.push({ header: h3 ? h3.textContent : null, titles: ul ? titlesOfUl(ul) : [] });
    });
  }
  return { flat: false, groups: groups, count: countText };
}
"""


class Driver(object):
    def __init__(self, page):
        self.page = page
        self.console_errors = []
        page.on('console', self._on_console)
        page.on('pageerror', lambda exc: self.console_errors.append(str(exc)))

    def _on_console(self, msg):
        if msg.type == 'error':
            self.console_errors.append(msg.text)

    def goto(self, base_url):
        self.page.goto(base_url + '/publications.html')
        self.page.wait_for_function(
            "document.getElementById('pubs-count').textContent.trim().length > 0")

    def reset(self):
        # NOT '#btn-clear' -- see the dedicated clear-filters-bug case: after
        # Clear Filters is used once, Years/Topics&Projects/Categories
        # checkboxes silently stop filtering for the rest of the session
        # (stale closures over a state object clearAll() replaces). A fresh
        # reload is the only reset that doesn't contaminate every later case.
        self.page.reload()
        self.page.wait_for_function(
            "document.getElementById('pubs-count').textContent.trim().length > 0")
        self.console_errors[:] = []
        # This is a live, actively-edited shared repo -- reload() just
        # re-fetched whatever's CURRENTLY on disk, so the oracle must look
        # at the same snapshot or a concurrent commit mid-run reads as a
        # false site bug (oracle and page compared at two different moments).
        global F
        F = Facts()

    def click_clear_button(self):
        self.page.click('#btn-clear')
        self.page.wait_for_timeout(20)

    def click_checkbox(self, box_id, value):
        return self.page.evaluate(JS_CLICK_CHECKBOX, [box_id, value])

    def badge_for(self, box_id, value):
        return self.page.evaluate(JS_BADGE_FOR, [box_id, value])

    def set_type_mode(self, mode):
        self.page.click('#type-toggle button[data-mode="%s"]' % mode)

    def set_kw_mode(self, mode):
        self.page.click('#kw-toggle button[data-kwmode="%s"]' % mode)

    def search_cite_author(self, text):
        self.page.fill('#cite-author-search', text)
        self.page.wait_for_timeout(20)

    def clear_cite_author_search(self):
        self.page.fill('#cite-author-search', '')
        self.page.wait_for_timeout(20)

    def set_sort(self, slot, value):
        self.page.select_option('#sort-%d' % slot, value)

    def reset_sort(self):
        self.page.click('#sort-reset')

    def click_cite_global(self, group_id, value):
        self.page.click('#%s button[data-v="%s"]' % (group_id, value))

    def click_show_toggle(self, btn_id):
        self.page.click('#' + btn_id)

    def read_render(self):
        return self.page.evaluate(JS_READ_RENDER)


# ---------------- Test case application (mirrors both DOM + oracle State) ----------------

FACET_BOX = {
    'year': None,       # handled specially (year buttons)
    'topic': 'facet-keywords',
    'project': 'facet-keywords',
    'author': 'facet-authors',
    'type': 'facet-types',
    'venue': 'facet-types',
    'citeAuthor': 'facet-cite-authors',
}


def apply_action(drv, state, kind, value):
    """Applies one (kind, value) selection to both the live DOM and the
    oracle State, returning an error string on click failure or None."""
    if kind == 'year':
        r = drv.click_checkbox('facet-years', str(value))
        if not r.startswith('clicked'):
            return 'year click failed: %s (%r)' % (r, value)
        state.years.add(str(value))
    elif kind == 'topic':
        r = drv.click_checkbox('facet-keywords', value)
        if not r.startswith('clicked'):
            return 'topic click failed: %s (%r)' % (r, value)
        state.keywords.add(value)
    elif kind == 'project':
        r = drv.click_checkbox('facet-keywords', value)
        if not r.startswith('clicked'):
            return 'project click failed: %s (%r)' % (r, value)
        state.keywords.add(value)
    elif kind == 'author':
        r = drv.click_checkbox('facet-authors', value)
        if not r.startswith('clicked'):
            return 'author click failed: %s (%r)' % (r, value)
        state.authors.add(value)
    elif kind == 'type':
        r = drv.click_checkbox('facet-types', value)
        if not r.startswith('clicked'):
            return 'type click failed: %s (%r)' % (r, value)
        state.types.add(value)
    elif kind == 'venue':
        r = drv.click_checkbox('facet-types', value)
        if not r.startswith('clicked'):
            return 'venue click failed: %s (%r)' % (r, value)
        state.types.add(value)
    elif kind == 'citeAuthor':
        drv.search_cite_author(value)
        r = drv.click_checkbox('facet-cite-authors', value)
        drv.clear_cite_author_search()
        if not r.startswith('clicked'):
            return 'citeAuthor click failed: %s (%r)' % (r, value)
        state.cite_authors.add(value)
    else:
        return 'unknown action kind %r' % kind
    return None


def compare_render(desc, state, sort_order, drv, results, badge_checks=None):
    exp_total, exp_flat, exp_payload = oracle_titles_for(state, sort_order)
    got = drv.read_render()
    got_count = parse_count(got['count'])
    problems = []
    if got_count != exp_total:
        problems.append('count: expected %s, got %s (%r)' % (exp_total, got_count, got['count']))
    if exp_flat != got['flat']:
        problems.append('flat/grouped mismatch: expected flat=%s, got flat=%s' % (exp_flat, got['flat']))
    elif exp_flat:
        if exp_payload != got['titles']:
            problems.append('flat title-order mismatch (expected %d titles, got %d); first diff at %s'
                             % (len(exp_payload), len(got['titles']),
                                _first_diff(exp_payload, got['titles'])))
    else:
        got_groups = [(g['header'], g['titles']) for g in got['groups']]
        exp_headers = [h for h, _ in exp_payload]
        got_headers = [h for h, _ in got_groups]
        if exp_headers != got_headers:
            problems.append('header sequence mismatch: expected %r, got %r' % (exp_headers, got_headers))
        else:
            for (eh, et), (gh, gt) in zip(exp_payload, got_groups):
                if et != gt:
                    problems.append('group %r title-order mismatch; first diff at %s'
                                     % (eh, _first_diff(et, gt)))
    if badge_checks:
        for box_id, value, expected in badge_checks:
            got_badge = drv.badge_for(box_id, value)
            if got_badge != expected:
                problems.append('badge for %r in %s: expected %r, got %r'
                                 % (value, box_id, expected, got_badge))
    if drv.console_errors:
        problems.append('console errors: %s' % drv.console_errors[:3])
        drv.console_errors[:] = []
    ok = not problems
    results.append({'case': desc, 'ok': ok, 'problems': problems})
    return ok


def _first_diff(a, b):
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return 'index %d: expected %r got %r' % (i, x, y)
    if len(a) != len(b):
        return 'length: expected %d got %d, tail=%r' % (len(a), len(b), (a[len(b):] or b[len(a):])[:3])
    return 'no diff found?'


def dynamic_badge_expected(state, box_id, kind, values):
    """Mirrors updateDynamicCounts() for the one facet just tested: count
    of items matching all OTHER active filters (this facet excluded) that
    also carry each candidate value."""
    exclude = {'facet-years': 'years', 'facet-keywords': 'keywords', 'facet-authors': 'authors',
               'facet-types': 'types', 'facet-cite-authors': 'citeAuthors'}.get(box_id)
    items = oracle.filtered_items(F.data, state, F.ci, F.ri, F.impact_by_paper, exclude_facet=exclude)
    counts = {}
    for it in items:
        if kind == 'year':
            vs = [str(it['year'])] if it.get('year') else []
        elif kind in ('topic', 'project'):
            vs = (oracle.projects_of(it) if kind == 'project' else oracle.topics_of(it))
        elif kind == 'author':
            vs = oracle.list_normalized_authors(it)
        elif kind in ('type', 'venue'):
            vs = [oracle.category_key_of(it, state.type_mode)]
        elif kind == 'citeAuthor':
            vs = F.impact_by_paper.get(oracle.bibtex_key_of(it), [])
        else:
            vs = []
        for v in vs:
            counts[v] = counts.get(v, 0) + 1
    out = {}
    for v in values:
        out[v] = '(%d)' % counts.get(v, 0)
    return out


# ---------------- Test phases ----------------

def run_single_facet_values(drv, results, rng):
    # Years
    for y in oracle.year_values(F.data):
        drv.reset()
        state = oracle.State()
        err = apply_action(drv, state, 'year', y)
        if err:
            results.append({'case': 'single year %r' % y, 'ok': False, 'problems': [err]})
            continue
        badge_exp = dynamic_badge_expected(oracle.State(), 'facet-years', 'year', [y])
        compare_render('single year=%s' % y, state, DEFAULT_SORT_ORDER, drv, results,
                        badge_checks=[('facet-years', y, badge_exp[y])])

    # Topics
    topics = oracle.keyword_values(F.data, 'topics')
    for t in topics:
        drv.reset()
        state = oracle.State()
        err = apply_action(drv, state, 'topic', t)
        if err:
            results.append({'case': 'single topic %r' % t, 'ok': False, 'problems': [err]})
            continue
        badge_exp = dynamic_badge_expected(oracle.State(), 'facet-keywords', 'topic', [t])
        compare_render('single topic=%s' % t, state, DEFAULT_SORT_ORDER, drv, results,
                        badge_checks=[('facet-keywords', t, badge_exp[t])])

    # Projects (switch kw mode)
    drv.reset()
    drv.set_kw_mode('projects')
    projects = oracle.keyword_values(F.data, 'projects')
    for p in projects:
        drv.reset()
        drv.set_kw_mode('projects')
        state = oracle.State()
        err = apply_action(drv, state, 'project', p)
        if err:
            results.append({'case': 'single project %r' % p, 'ok': False, 'problems': [err]})
            continue
        compare_render('single project=%s' % p, state, DEFAULT_SORT_ORDER, drv, results)
    drv.reset()
    drv.set_kw_mode('topics')

    # Authors
    authors = sorted(oracle.author_values(F.data))
    for a in authors:
        drv.reset()
        state = oracle.State()
        err = apply_action(drv, state, 'author', a)
        if err:
            results.append({'case': 'single author %r' % a, 'ok': False, 'problems': [err]})
            continue
        compare_render('single author=%s' % a, state, DEFAULT_SORT_ORDER, drv, results)

    # Types (default 'type' mode)
    types = oracle.type_values(F.data, 'type')
    for tk in types:
        drv.reset()
        state = oracle.State()
        state.type_mode = 'type'
        err = apply_action(drv, state, 'type', tk)
        if err:
            results.append({'case': 'single type %r' % tk, 'ok': False, 'problems': [err]})
            continue
        compare_render('single type=%s' % tk, state, DEFAULT_SORT_ORDER, drv, results)

    # Venue mode
    drv.reset()
    drv.set_type_mode('venue-name')
    venues = [v for v in oracle.type_values(F.data, 'venue') if v.startswith('venue:')]
    for vk in venues:
        drv.reset()
        drv.set_type_mode('venue-name')
        state = oracle.State()
        state.type_mode = 'venue'
        err = apply_action(drv, state, 'venue', vk)
        if err:
            results.append({'case': 'single venue %r' % vk, 'ok': False, 'problems': [err]})
            continue
        compare_render('single venue=%s' % vk, state, DEFAULT_SORT_ORDER, drv, results)
    drv.reset()
    drv.set_type_mode('type')

    # Cited-and-used-by: sample (6215 values -- exhaustive is impractical;
    # 30-name stratified sample: top-count names + a random tail sample).
    all_names = F.all_cite_authors
    sample = list(dict.fromkeys(all_names[:15] + rng.sample(all_names, min(15, len(all_names)))))
    for nm in sample[:30]:
        drv.reset()
        state = oracle.State()
        err = apply_action(drv, state, 'citeAuthor', nm)
        if err:
            results.append({'case': 'single citeAuthor %r' % nm, 'ok': False, 'problems': [err]})
            continue
        compare_render('single citeAuthor=%s' % nm, state, DEFAULT_SORT_ORDER, drv, results)
    results.append({'case': 'SCOPE NOTE: citeAuthor facet sampled 30 of %d values (exhaustive impractical)'
                     % len(all_names), 'ok': True, 'problems': []})


def _candidate_pool():
    pool = []
    for y in oracle.year_values(F.data):
        pool.append(('year', y))
    for t in oracle.keyword_values(F.data, 'topics'):
        pool.append(('topic', t))
    for a in oracle.author_values(F.data):
        pool.append(('author', a))
    for tk in oracle.type_values(F.data, 'type'):
        pool.append(('type', tk))
    return pool


def _apply_combo(drv, combo):
    state = oracle.State()
    for kind, value in combo:
        err = apply_action(drv, state, kind, value)
        if err:
            return state, err
    return state, None


def run_pairwise(drv, results, rng, n=200):
    pool = _candidate_pool()
    seen = set()
    tries = 0
    made = 0
    while made < n and tries < n * 5:
        tries += 1
        a = rng.choice(pool)
        b = rng.choice(pool)
        if a == b:
            continue
        combo = tuple(sorted([a, b]))
        if combo in seen:
            continue
        seen.add(combo)
        drv.reset()
        state, err = _apply_combo(drv, combo)
        desc = 'pairwise %r' % (combo,)
        if err:
            results.append({'case': desc, 'ok': False, 'problems': [err]})
        else:
            compare_render(desc, state, DEFAULT_SORT_ORDER, drv, results)
        made += 1


def run_multiway(drv, results, rng, n=100):
    pool = _candidate_pool()
    made = 0
    tries = 0
    while made < n and tries < n * 5:
        tries += 1
        k = rng.choice([3, 4])
        combo = tuple(sorted(set(rng.sample(pool, k))))
        if len(combo) < 3:
            continue
        drv.reset()
        state, err = _apply_combo(drv, combo)
        desc = 'multiway %r' % (combo,)
        if err:
            results.append({'case': desc, 'ok': False, 'problems': [err]})
        else:
            compare_render(desc, state, DEFAULT_SORT_ORDER, drv, results)
        made += 1
    return made


def run_sort_modes_and_toggles(drv, results, rng, samples=15):
    pool = _candidate_pool()
    sort_variants = [
        ['year', 'month', 'type', 'authorLast'],       # default
        ['citations', 'none', 'none', 'none'],
        ['authors', 'citations', 'none', 'none'],
        ['keywords', 'year', 'none', 'none'],
        ['type', 'authorFirst', 'month', 'none'],
    ]
    for i in range(samples):
        k = rng.choice([1, 2])
        combo = tuple(sorted(set(rng.sample(pool, k))))
        drv.reset()
        state, err = _apply_combo(drv, combo)
        if err:
            results.append({'case': 'sortmode combo %r' % (combo,), 'ok': False, 'problems': [err]})
            continue
        so = sort_variants[i % len(sort_variants)]
        for slot in range(4):
            drv.set_sort(slot + 1, so[slot])
        desc = 'sortmode %r order=%r' % (combo, so)
        compare_render(desc, state, so, drv, results)
        drv.reset_sort()

    # Global citation Impact/Recency/Popularity + Show toggles: smoke-level
    # (these change per-panel internals, not the paper list's own membership
    # or count) -- verify the pub count line is unchanged and no JS errors.
    for combo_kind in ('impact', 'recency', 'popularity'):
        drv.reset()
        drv.click_cite_global('cite-global-sort', combo_kind)
        got = drv.read_render()
        cnt = parse_count(got['count'])
        problems = []
        if cnt != len(F.data):
            problems.append('cite-global-sort=%s changed the paper count to %s (expected %d)'
                             % (combo_kind, cnt, len(F.data)))
        if drv.console_errors:
            problems.append('console errors after cite-global-sort=%s: %s' % (combo_kind, drv.console_errors[:3]))
            drv.console_errors[:] = []
        results.append({'case': 'cite-global-sort=%s (smoke)' % combo_kind, 'ok': not problems, 'problems': problems})
    drv.reset()

    for btn_id, label in (('btn-toggle-summaries', 'summaries'),
                           ('btn-toggle-citations', 'citations'),
                           ('btn-toggle-repos', 'repos')):
        drv.reset()
        drv.click_show_toggle(btn_id)
        drv.page.wait_for_timeout(150)
        got = drv.read_render()
        cnt = parse_count(got['count'])
        problems = []
        if cnt != len(F.data):
            problems.append('Show %s changed the paper count to %s (expected %d)' % (label, cnt, len(F.data)))
        if drv.console_errors:
            problems.append('console errors after Show %s: %s' % (label, drv.console_errors[:3]))
            drv.console_errors[:] = []
        results.append({'case': 'show-toggle=%s (smoke)' % label, 'ok': not problems, 'problems': problems})
        drv.click_show_toggle(btn_id)  # toggle back off
    drv.reset()


def run_clear_filters_bug_case(drv, results):
    """Dedicated repro for a structural bug found while building this
    harness (not display-only -- flagged as a STOP for Fable, not fixed
    here): clearAll() (assets/js/publications.js ~line 1508) reassigns
    state.years / state.keywords / state.types to brand-new {} objects,
    but the Years / Topics&Projects / Categories checkbox facets are never
    rebuilt afterward (only rebuildAuthorFacet()/rebuildCiteAuthorFacet()
    run) -- so their onchange closures keep mutating the discarded old
    object. Every later click on one of those three facets silently
    no-ops: the checkbox visually snaps back unchecked (because
    updateFacetCounts() reads the *current* state.keywords, which never
    saw the click) and the paper list never filters. Authors and Cited-
    and-Used-by are unaffected, since their facet boxes ARE rebuilt.
    """
    drv.reset()
    drv.click_clear_button()
    problems = []
    for box_id, value, label in (
        ('facet-years', '2026', 'year 2026'),
        ('facet-keywords', 'GPUs', 'topic GPUs'),
        ('facet-types', 'type:inproceedings', 'type inproceedings'),
    ):
        r = drv.click_checkbox(box_id, value)
        cnt = parse_count(drv.read_render()['count'])
        if r.lower() == 'clicked:true' or (cnt is not None and cnt != len(F.data)):
            continue  # this run's build already fixed it -- nothing to report
        problems.append('after Clear Filters, clicking %s did not filter the list '
                         '(click result=%r, paper count stayed at %s)' % (label, r, cnt))
    # Control: Authors keeps working after Clear Filters (rebuilt facet).
    r = drv.click_checkbox('facet-authors', 'Saman Amarasinghe')
    cnt = parse_count(drv.read_render()['count'])
    control_ok = r.lower().startswith('clicked:true') and cnt not in (None, len(F.data))
    if not control_ok:
        problems.append('control check failed too (Authors facet after Clear Filters, '
                         'click=%r, count=%s) -- re-verify the diagnosis by hand' % (r, cnt))
    diagnosis = [
        'Repro: load publications.html, click "Clear filters" once, then try to check any '
        'Year / Topic / Project / Category (Type or Venue) checkbox -- it visually snaps '
        'back unchecked and the paper count never changes. Authors and "Cited and Used by" '
        'still work fine (their facets are rebuilt by clearAll(); the other three are not).',
        'Root cause: assets/js/publications.js clearAll() (~line 1508) does '
        '`state.years = {}; state.keywords = {}; state.types = {};` -- NEW object literals -- '
        'but each facet\'s checkbox onchange handler closed over the OLD state.<facet> object '
        'reference when buildFacetBox() first ran at boot, and clearAll() never rebuilds those '
        'three boxes (only rebuildAuthorFacet()/rebuildCiteAuthorFacet() run). So a later click '
        'mutates a discarded object; updateFacetCounts() then reads the real (still-empty) '
        'state.<facet> and resets the checkbox to unchecked, masking the failure as a silent no-op.',
        'Fix sketch: either rebuild all five facet boxes in clearAll() (call rebuildKeywordFacet()/ '
        'rebuildTypeFacet() and rebuild years the same way Authors/CiteAuthors already are), or '
        'stop reassigning the state objects and instead delete their keys in place '
        '(`for (var k in state.years) delete state.years[k];`) so the closures stay valid.',
    ]
    results.append({
        'case': 'STRUCTURAL BUG (STOP for Fable): "Clear filters" permanently disables the '
                'Years / Topics & Projects / Categories checkboxes for the rest of the session',
        'ok': not problems,
        'problems': (problems + diagnosis) if problems else diagnosis,
    })
    drv.reset()


def run_boot_sanity(drv, results):
    drv.reset()
    state = oracle.State()
    compare_render('boot: no filters, default sort order', state, DEFAULT_SORT_ORDER, drv, results)


# ---------------- Report ----------------

def write_report(results, base_url, phase_counts):
    path = os.path.join(HERE, 'combinatorial-report.md')
    test_results = [r for r in results if not r['case'].startswith('SCOPE NOTE')]
    total = len(test_results)
    failed = [r for r in test_results if not r['ok']]
    lines = []
    lines.append('# UI combinatorial test run — report')
    lines.append('')
    lines.append('Oracle: `tests/ui/oracle.py`, computed directly from `data/publications.json` + '
                  '`data/citations/*` + `data/repos/*`. Driver: Playwright against `%s`.' % base_url)
    lines.append('')
    lines.append('## Summary')
    lines.append('')
    lines.append('- Total cases: **%d**' % total)
    lines.append('- Passed: **%d**' % (total - len(failed)))
    lines.append('- Failed: **%d**' % len(failed))
    lines.append('')
    for name, n in phase_counts.items():
        lines.append('- %s: %d cases' % (name, n))
    lines.append('')
    scope_notes = [r for r in results if r['case'].startswith('SCOPE NOTE')]
    if scope_notes:
        lines.append('## Scope notes (coverage intentionally bounded)')
        lines.append('')
        for r in scope_notes:
            lines.append('- %s' % r['case'])
        lines.append('')
    if not failed:
        lines.append('No discrepancies found between the live UI and the independent oracle '
                      'across every single-facet value, the sampled pairwise/3-4-way combinations, '
                      'the sampled Group&sort modes, and the Show-toggle/citation-sort smoke checks.')
    else:
        lines.append('## Failures (repro selections included)')
        lines.append('')
        for r in failed:
            lines.append('### %s' % r['case'])
            for p in r['problems']:
                lines.append('- %s' % p)
            lines.append('')
    path_out = path
    with open(path_out, 'w') as fh:
        fh.write('\n'.join(lines) + '\n')
    return path_out, len(failed)


def main():
    global F
    ap = argparse.ArgumentParser()
    ap.add_argument('--base-url', default='http://localhost:8123')
    ap.add_argument('--headed', action='store_true')
    ap.add_argument('--seed', type=int, default=20260826)
    ap.add_argument('--pairwise', type=int, default=200)
    ap.add_argument('--multiway', type=int, default=100)
    ap.add_argument('--sort-samples', type=int, default=15)
    args = ap.parse_args()

    F = Facts()
    rng = random.Random(args.seed)
    results = []
    phase_counts = {}

    with load_page() as pw:
        browser = pw.chromium.launch(headless=not args.headed)
        page = browser.new_page()
        drv = Driver(page)
        drv.goto(args.base_url)

        n0 = len(results)
        run_boot_sanity(drv, results)
        phase_counts['boot sanity'] = len(results) - n0

        n0 = len(results)
        run_clear_filters_bug_case(drv, results)
        phase_counts['clear-filters bug repro'] = len(results) - n0

        n0 = len(results)
        run_single_facet_values(drv, results, rng)
        phase_counts['single-facet values'] = len(results) - n0

        n0 = len(results)
        run_pairwise(drv, results, rng, n=args.pairwise)
        phase_counts['pairwise combos'] = len(results) - n0

        n0 = len(results)
        run_multiway(drv, results, rng, n=args.multiway)
        phase_counts['3-4-way combos'] = len(results) - n0

        n0 = len(results)
        run_sort_modes_and_toggles(drv, results, rng, samples=args.sort_samples)
        phase_counts['sort modes + Show toggles (sample)'] = len(results) - n0

        browser.close()

    path, nfail = write_report(results, args.base_url, phase_counts)
    print('Wrote %s: %d cases, %d failed' % (path, len(results), nfail))
    return 1 if nfail else 0


if __name__ == '__main__':
    sys.exit(main())
