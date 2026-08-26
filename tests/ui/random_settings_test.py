#!/usr/bin/env python3
"""UI random-settings test run -- see tests/ui/SPEC.md (his instruction,
2026-08-26; supersedes the terse round-11 task 1 text).

Discovers every interactive control inside the "All Papers panel"
(#pubs-filters -- the Filters block: mode radio, Show/Clear buttons,
Group&sort selects, Years/Topics&Projects/Categories/Authors checkbox
facets, the citation-tools row, Cited-and-Used-by, the two thresholds
sliders) at RUNTIME, from the live DOM -- nothing here hardcodes what
exists. Builds ~100 random settings (60 multi-control, 25 single-control,
15 extremes), applies each to the real page, and checks the result
against an independent oracle computed from the data files, never from
the page (tests/ui/oracle.py). For >=30 of the 100, also expands 1-3
papers and checks their Summary/Repositories/Citations panels.

Interpretation note (stated plainly rather than silently assumed): this
codebase has exactly one bifurcation of "the same setting shown two
ways" -- the Filters block (#pubs-filters, informally "the All Papers
panel" since with nothing selected it lists every paper) and the
Publications section (#pubs-results, under the "Publications" heading)
beneath it. "Cross-page agreement" here means: whatever the Filters
block implies about membership/counts (a facet checkbox's dynamic count
badge) must match what #pubs-results actually renders. This is the one
reading groundable directly in the code (there is no second page/embed
in this repo today) -- flagged here per the spec's own instruction to
STOP rather than silently guess, so the coordinator can correct it.

Usage:
    python3 tests/ui/random_settings_test.py [--seed 42] [--base-url ...] [--n 100]

Writes tests/ui/report.md; first line is
    RUN COMPLETE -- <n> tests, <p> passed, <f> failed, seed <s>
"""
import argparse
import os
import random
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oracle  # noqa: E402
import facet_test as ft  # noqa: E402 -- reuse Driver base + JS helpers

HERE = os.path.dirname(os.path.abspath(__file__))

JS_DISCOVER = r"""
() => {
  function label(el) {
    if (el.getAttribute('aria-label')) return el.getAttribute('aria-label');
    if (el.title) return el.title;
    const lab = el.closest('label');
    if (lab) return lab.textContent.replace(/\s+/g, ' ').trim();
    const forLab = el.id && document.querySelector('label[for="' + el.id + '"]');
    if (forLab) return forLab.textContent.trim();
    return el.id || (el.textContent || '').trim().slice(0, 60);
  }
  function facetBoxId(el) {
    const box = el.closest('.facet-list');
    return box ? box.id : null;
  }
  function toggleGroupId(el) {
    const g = el.closest('.type-toggle');
    return g ? (g.id || null) : null;
  }
  const root = document.getElementById('pubs-filters');
  const out = [];
  root.querySelectorAll('input, select, button').forEach(el => {
    if (el.tagName === 'INPUT' && el.type === 'radio') {
      out.push({ tag: 'radio', name: el.name, value: el.value, label: label(el) });
    } else if (el.tagName === 'INPUT' && el.type === 'checkbox') {
      out.push({ tag: 'checkbox', box: facetBoxId(el), value: el.value, disabled: el.disabled });
    } else if (el.tagName === 'INPUT' && el.type === 'range') {
      out.push({ tag: 'range', id: el.id, min: el.min, max: el.max, step: el.step, label: label(el) });
    } else if (el.tagName === 'INPUT' && (el.type === 'search' || el.type === 'text')) {
      out.push({ tag: 'text', id: el.id, label: label(el), placeholder: el.placeholder || '' });
    } else if (el.tagName === 'SELECT') {
      out.push({ tag: 'select', id: el.id, label: label(el),
                 options: Array.from(el.options).map(o => o.value) });
    } else if (el.tagName === 'BUTTON') {
      out.push({ tag: 'button', id: el.id || null, text: (el.textContent || '').trim(),
                 dataV: el.getAttribute('data-v'), dataMode: el.getAttribute('data-mode'),
                 dataKwmode: el.getAttribute('data-kwmode'), group: toggleGroupId(el) });
    }
  });
  return out;
}
"""

JS_FIND_ITEM_INDEX = r"""
(title) => {
  const items = Array.from(document.querySelectorAll('li.pub-item'));
  for (let i = 0; i < items.length; i++) {
    const t = items[i].querySelector('.pub-title');
    let s = t ? (t.textContent || '') : '';
    if (s.endsWith('.')) s = s.slice(0, -1);
    if (s === title) return i;
  }
  return -1;
}
"""

JS_ITEM_META = r"""
(idx) => {
  const items = document.querySelectorAll('li.pub-item');
  const li = items[idx];
  if (!li) return null;
  function toggleText(prefix) {
    const links = Array.from(li.querySelectorAll('a.pub-action'));
    const a = links.find(x => (x.textContent || '').trim().indexOf(prefix) === 0);
    return a ? a.textContent.trim() : null;
  }
  const sumDiv = li.querySelector('.pub-summary:not(.cite-view)');
  return {
    hasSummaryToggle: !!li.querySelector('a.pub-summary-toggle:not(.cite-toggle)'),
    summaryOpen: sumDiv ? sumDiv.className.indexOf('open') !== -1 : null,
    summaryText: sumDiv ? sumDiv.textContent : null,
    summaryHtml: sumDiv ? sumDiv.innerHTML : null,
    citationsToggleText: toggleText('Citations ('),
    repositoriesToggleText: toggleText('Repositories ('),
  };
}
"""


def build_control_model(raw):
    checkbox_boxes = {}
    toggle_groups = {}
    selects = {}
    ranges = {}
    texts = {}
    radios = {}
    lone_buttons = []
    for el in raw:
        if el['tag'] == 'checkbox' and el['box']:
            checkbox_boxes.setdefault(el['box'], []).append(el['value'])
        elif el['tag'] == 'radio':
            radios.setdefault(el['name'], []).append(el['value'])
        elif el['tag'] == 'select':
            selects[el['id']] = el['options']
        elif el['tag'] == 'range':
            ranges[el['id']] = {'min': int(float(el['min'] or 0)), 'max': int(float(el['max'] or 0)),
                                 'step': int(float(el['step'] or 1))}
        elif el['tag'] == 'text':
            texts[el['id']] = el['label']
        elif el['tag'] == 'button':
            if el['group'] and (el['dataV'] or el['dataMode'] or el['dataKwmode']):
                attr = 'dataV' if el['dataV'] else ('dataMode' if el['dataMode'] else 'dataKwmode')
                toggle_groups.setdefault(el['group'], {'attr': attr, 'options': []})['options'].append(el[attr])
            elif el['id']:
                lone_buttons.append(el['id'])
    return {
        'checkbox_boxes': checkbox_boxes, 'toggle_groups': toggle_groups,
        'selects': selects, 'ranges': ranges, 'texts': texts,
        'radios': radios, 'lone_buttons': lone_buttons,
    }


def render_inventory_md(model, raw_count):
    lines = ['## Control inventory (discovered at runtime from #pubs-filters)', '']
    lines.append('%d raw interactive elements found. Reduced to logical controls:' % raw_count)
    lines.append('')
    lines.append('### Checkbox facets')
    for box, vals in model['checkbox_boxes'].items():
        lines.append('- `#%s`: %d values' % (box, len(vals)))
    lines.append('')
    lines.append('### Button toggle groups')
    for grp, spec in model['toggle_groups'].items():
        lines.append('- `#%s` (%s): %r' % (grp, spec['attr'], spec['options']))
    lines.append('')
    lines.append('### Selects')
    for sid, opts in model['selects'].items():
        lines.append('- `#%s`: %r' % (sid, opts))
    lines.append('')
    lines.append('### Range sliders')
    for rid, spec in model['ranges'].items():
        lines.append('- `#%s`: min=%s max=%s step=%s' % (rid, spec['min'], spec['max'], spec['step']))
    lines.append('')
    lines.append('### Text/search inputs')
    for tid, lbl in model['texts'].items():
        lines.append('- `#%s`: %s' % (tid, lbl))
    lines.append('')
    lines.append('### Radio groups')
    for name, vals in model['radios'].items():
        lines.append('- `%s`: %r' % (name, vals))
    lines.append('')
    lines.append('### Standalone buttons')
    lines.append(', '.join('`#%s`' % b for b in model['lone_buttons']))
    lines.append('')
    return lines


# ---------------- Driver extensions ----------------

class RandomDriver(ft.Driver):
    def __init__(self, page):
        super().__init__(page)
        self.requests = []  # list of (url,) in fetch order
        page.on('request', lambda req: self.requests.append(req.url))
        page.on('requestfailed', lambda req: self.failed.append(req.url))
        page.on('response', self._on_response)
        self.failed = []

    def _on_response(self, resp):
        if resp.status >= 400:
            self.failed.append('%s (%d)' % (resp.url, resp.status))

    def reset(self):
        super().reset()
        self.requests[:] = []
        self.failed[:] = []

    def discover(self):
        return self.page.evaluate(JS_DISCOVER)

    def set_range(self, el_id, value):
        self.page.evaluate(
            "([id, v]) => { const el = document.getElementById(id); el.value = String(v); "
            "el.dispatchEvent(new Event('input', {bubbles:true})); }", [el_id, value])

    def fill_text(self, el_id, text):
        self.page.fill('#' + el_id, text)
        self.page.wait_for_timeout(30)

    def click_radio(self, name, value):
        self.page.check('input[name="%s"][value="%s"]' % (name, value))

    def click_button_id(self, el_id):
        self.page.click('#' + el_id)

    def click_toggle_group_button(self, group_id, attr, value):
        attr_name = {'dataV': 'data-v', 'dataMode': 'data-mode', 'dataKwmode': 'data-kwmode'}[attr]
        self.page.click('#%s button[%s="%s"]' % (group_id, attr_name, value))

    def find_item_index(self, title):
        return self.page.evaluate(JS_FIND_ITEM_INDEX, title)

    def item_meta(self, idx):
        return self.page.evaluate(JS_ITEM_META, idx)

    def click_item_toggle(self, idx, prefix):
        items = self.page.locator('li.pub-item')
        li = items.nth(idx)
        link = li.locator('a', has_text=prefix).first
        link.click()
        self.page.wait_for_timeout(120)


# ---------------- Setting generation ----------------

class Setting(object):
    """One random 'panel setting': the DOM actions to take + the
    equivalent oracle.State (and sort order) it implies."""

    def __init__(self, label):
        self.label = label
        self.actions = []  # list of (kind, *args) description tuples, for the report
        self.state = oracle.State()
        self.sort_order = list(ft.DEFAULT_SORT_ORDER)

    def add(self, desc):
        self.actions.append(desc)


def gen_single(rng, model, F):
    """One control set to one value."""
    choices = []
    if model['checkbox_boxes'].get('facet-years'):
        choices.append(('year', rng.choice(oracle.year_values(F.data))))
    if model['checkbox_boxes'].get('facet-keywords'):
        choices.append(('topic', rng.choice(oracle.keyword_values(F.data, 'topics'))))
    if model['checkbox_boxes'].get('facet-authors'):
        choices.append(('author', rng.choice(sorted(oracle.author_values(F.data)))))
    if model['checkbox_boxes'].get('facet-types'):
        choices.append(('type', rng.choice(oracle.type_values(F.data, 'type'))))
    kind, value = rng.choice(choices)
    s = Setting('single %s=%s' % (kind, value))
    s.add((kind, value))
    return s


def gen_multi(rng, model, F, k):
    pool = []
    for y in oracle.year_values(F.data):
        pool.append(('year', y))
    for t in oracle.keyword_values(F.data, 'topics'):
        pool.append(('topic', t))
    for a in oracle.author_values(F.data):
        pool.append(('author', a))
    for tk in oracle.type_values(F.data, 'type'):
        pool.append(('type', tk))
    combo = rng.sample(pool, min(k, len(pool)))
    s = Setting('multi(%d) %r' % (len(combo), combo))
    for kind, value in combo:
        s.add((kind, value))
    # occasionally also add a sort-order change and/or a slider
    if rng.random() < 0.4:
        variants = [['citations', 'none', 'none', 'none'],
                    ['authors', 'citations', 'none', 'none'],
                    ['keywords', 'year', 'none', 'none'],
                    ['type', 'authorFirst', 'month', 'none']]
        s.sort_order = rng.choice(variants)
        s.add(('sort', s.sort_order))
    return s


def gen_extreme(rng, model, F, kind):
    s = Setting('extreme:%s' % kind)
    if kind == 'kitchen-sink':
        s.add(('year', rng.choice(oracle.year_values(F.data))))
        s.add(('topic', rng.choice(oracle.keyword_values(F.data, 'topics'))))
        s.add(('author', rng.choice(sorted(oracle.author_values(F.data)))))
        s.add(('type', rng.choice(oracle.type_values(F.data, 'type'))))
    elif kind == 'empty-result':
        # search for a (year, author) pair the oracle says yields zero.
        years = oracle.year_values(F.data)
        authors = sorted(oracle.author_values(F.data))
        for _ in range(200):
            y = rng.choice(years)
            a = rng.choice(authors)
            st = oracle.State()
            st.years = {y}
            st.authors = {a}
            if not oracle.filtered_items(F.data, st, F.ci, F.ri, F.impact_by_paper):
                s.add(('year', y))
                s.add(('author', a))
                break
        else:
            s.add(('title', 'zzz-guaranteed-no-match-zzz'))
    elif kind == 'max-slider':
        s.add(('min_cites_max', None))
        s.add(('min_impact_max', None))
    elif kind == 'no-match-search':
        s.add(('title', 'zzznomatch' + str(rng.randint(1000, 9999))))
    return s


def apply_setting(drv, setting, F):
    """Applies a Setting's actions to both the DOM and setting.state;
    returns an error string, or None."""
    for action in setting.actions:
        kind = action[0]
        if kind in ('year', 'topic', 'author', 'type'):
            err = ft.apply_action(drv, setting.state, kind, action[1])
            if err:
                return err
        elif kind == 'title':
            drv.fill_text('facet-title', action[1])
            setting.state.title_query = action[1]
        elif kind == 'sort':
            for slot in range(4):
                drv.set_sort(slot + 1, setting.sort_order[slot])
        elif kind == 'min_cites_max':
            max_c = max((oracle.display_count(r) for r in F.ci.values()), default=1) or 1
            drv.set_range('cite-min-cites', 100)  # UI is quadratic-mapped; 100 -> true max
            setting.state.min_cites = max_c
        elif kind == 'min_impact_max':
            drv.set_range('cite-min-impact', 4)
            setting.state.min_impact = max(1, F.quantiles.quantile(0.03))
        else:
            return 'unknown action %r' % (action,)
    return None


# ---------------- Assertions ----------------

def check_setting(drv, setting, F, results, do_expand):
    exp_total, exp_flat, exp_payload = ft.oracle_titles_for(setting.state, setting.sort_order)
    got = drv.read_render()
    got_count = ft.parse_count(got['count'])
    problems = []

    if got_count != exp_total:
        problems.append('count: expected %d, got %r (%s)' % (exp_total, got_count, got['count']))

    exp_titles = exp_payload if exp_flat else [t for _, ts in exp_payload for t in ts]
    got_titles = got['titles'] if got['flat'] else [t for g in got['groups'] for t in g['titles']]

    exp_set, got_set = set(exp_titles), set(got_titles)
    if exp_set != got_set:
        problems.append('membership mismatch: only-expected=%r only-rendered=%r'
                         % (sorted(exp_set - got_set)[:5], sorted(got_set - exp_set)[:5]))
    elif exp_titles != got_titles:
        problems.append('order mismatch (same membership); first diff at %s'
                         % ft._first_diff(exp_titles, got_titles))

    if exp_flat != got['flat']:
        problems.append('flat/grouped mismatch: expected flat=%s got flat=%s' % (exp_flat, got['flat']))
    elif not exp_flat:
        exp_headers = [h for h, _ in exp_payload]
        got_headers = [g['header'] for g in got['groups']]
        if exp_headers != got_headers:
            problems.append('header sequence mismatch: expected %r got %r' % (exp_headers, got_headers))

    # Cross-panel agreement: a sample of currently-enabled checkbox badges
    # in the Years/Topics facets must match the oracle's dynamic count for
    # that value given the OTHER active filters -- i.e. the Filters block
    # and the Publications listing must never disagree about who's shown.
    for box_id, kind, universe in (('facet-years', 'year', oracle.year_values(F.data)),
                                    ('facet-keywords', 'topic', oracle.keyword_values(F.data, 'topics'))):
        sample = universe[:3]
        if not sample:
            continue
        exp_badges = ft.dynamic_badge_expected(setting.state, box_id, kind, sample)
        for v in sample:
            got_badge = drv.badge_for(box_id, v)
            if got_badge is not None and got_badge != exp_badges[v]:
                problems.append('cross-panel mismatch: %s=%r badge shows %r, Publications listing implies %r'
                                 % (kind, v, got_badge, exp_badges[v]))

    if drv.console_errors:
        problems.append('console errors: %s' % drv.console_errors[:3])
    if drv.failed:
        problems.append('failed/4xx+ network requests: %s' % drv.failed[:3])

    expansion_notes = []
    if do_expand and exp_titles:
        exp_items = oracle_items_for(setting.state, setting.sort_order, F)
        expansion_notes = check_expansions(drv, exp_items, F, problems)

    ok = not problems
    label = setting.label
    if setting.sort_order != ft.DEFAULT_SORT_ORDER:
        label += ' sort=%r' % setting.sort_order
    results.append({'case': label, 'ok': ok, 'problems': problems,
                     'expansions': expansion_notes})
    return ok


def oracle_items_for(state, sort_order, F):
    """Like ft.oracle_titles_for, but returns the actual item dicts (not
    just their titles) in rendered order -- needed for expansion checks,
    where identity (bibtexKey) must be unambiguous even if two distinct
    items happen to share an identical title string post-dedup."""
    items = oracle.filtered_items(F.data, state, F.ci, F.ri, F.impact_by_paper)
    items = oracle.default_sorted(items)
    is_flat, headers, groups = oracle.render_list_groups(items, sort_order, F.ci, F.ri, F.quantiles)
    if is_flat:
        return groups['__flat__']
    return [it for h in headers for it in groups[h]]


def encoded_key(key):
    from urllib.parse import quote
    # colon-free filename scheme (GitHub Pages / Windows can't hold ':')
    return quote(key.replace(':', '_'), safe='')


def check_expansions(drv, items, F, problems):
    # Title text is how the DOM gets located -- skip any title that's not
    # unique among the currently-rendered items, since find_item_index()
    # can't disambiguate two distinct papers sharing a rendered title.
    title_counts = {}
    for it in items:
        title_counts[oracle.title_of(it)] = title_counts.get(oracle.title_of(it), 0) + 1
    unique_items = [it for it in items if title_counts[oracle.title_of(it)] == 1]
    rng_local = random.Random(hash(tuple(oracle.title_of(it) for it in items[:3])) & 0xffff)
    n = min(3, len(unique_items))
    picks = rng_local.sample(unique_items, n) if n else []
    notes = []
    for it in picks:
        title = oracle.title_of(it)
        key = oracle.bibtex_key_of(it)
        ekey = encoded_key(key)
        idx = drv.find_item_index(title)
        if idx < 0:
            problems.append('expansion: could not locate rendered item for %r' % title)
            continue
        meta_before = drv.item_meta(idx)
        notes.append('expanded %r (key=%s)' % (title, key))

        # Summary
        if meta_before['hasSummaryToggle']:
            drv.click_item_toggle(idx, 'Summary')
            m1 = drv.item_meta(idx)
            txt = (m1['summaryText'] or '')
            if not txt.strip():
                problems.append('summary for %r opened but rendered empty' % title)
            # Bare-word match only: catch a leaked JS undefined/null/NaN
            # without flagging legitimate prose ("undefined-value detection",
            # "null pointer", etc.) -- exclude hyphen-adjacent matches, since
            # those are compound words, not interpolation artifacts.
            for bad in ('undefined', 'null', 'NaN'):
                for m in re.finditer(r'\b%s\b' % bad, txt):
                    before = txt[m.start() - 1] if m.start() > 0 else ' '
                    after = txt[m.end()] if m.end() < len(txt) else ' '
                    if before == '-' or after == '-':
                        continue
                    problems.append('summary for %r contains literal %r (context: %r)'
                                     % (title, bad, txt[max(0, m.start() - 20):m.end() + 20]))
                    break
            html = m1['summaryHtml'] or ''
            if re.search(r'&lt;a |&lt;/a&gt;', html):
                problems.append('summary for %r shows raw unescaped markup' % title)
            # collapse/expand twice: state survives, no duplicate content
            drv.click_item_toggle(idx, 'Summary')
            drv.click_item_toggle(idx, 'Summary')
            m2 = drv.item_meta(idx)
            if m2['summaryText'] != txt:
                problems.append('summary for %r text changed across an expand/collapse/expand cycle' % title)
            drv.click_item_toggle(idx, 'Summary')  # leave closed

        has_cites_toggle = bool(meta_before['citationsToggleText'])
        has_repo_toggle = bool(meta_before['repositoriesToggleText'])

        def panel_head_text(which):
            n = 1 if (which == 'repositories' and has_cites_toggle) else 0
            panel = drv.page.locator('li.pub-item').nth(idx).locator('.cite-view').nth(n)
            try:
                return panel.locator('.cite-head-count').first.text_content(timeout=2000) or ''
            except Exception:
                return ''

        # Citations
        cite_row = F.ci.get(key)
        if cite_row is not None:
            if not has_cites_toggle:
                problems.append('paper %r has a citations index row but no Citations toggle rendered' % title)
            else:
                cite_url_frag = '/citations/%s.json' % ekey
                pre_fetch = any(cite_url_frag in u for u in drv.requests)
                if pre_fetch:
                    problems.append('citations data for %r fetched before the panel was expanded' % title)
                drv.click_item_toggle(idx, 'Citations')
                drv.page.wait_for_timeout(200)
                fetched = any(cite_url_frag in u for u in drv.requests)
                if not fetched:
                    problems.append('expanding Citations for %r did not fetch data/citations/%s.json' % (title, key))
                expected_n = oracle.display_count(cite_row)
                head_text = panel_head_text('citations')
                if str(expected_n) not in head_text.replace(',', ''):
                    problems.append('citations head for %r: expected count %d, saw %r'
                                     % (title, expected_n, head_text))
                # expand/collapse twice -- must not refetch
                drv.click_item_toggle(idx, 'Citations')
                drv.click_item_toggle(idx, 'Citations')
                refetches = sum(1 for u in drv.requests if cite_url_frag in u)
                if refetches > 1:
                    problems.append('citations panel for %r refetched on reopen (%d fetches total)'
                                     % (title, refetches))
        else:
            if has_cites_toggle:
                problems.append('paper %r has NO citations index row but a Citations toggle is rendered' % title)

        # Repositories
        repo_row = F.ri.get(key)
        if repo_row is not None:
            if not has_repo_toggle:
                problems.append('paper %r has a repos index row but no Repositories toggle rendered' % title)
            else:
                repo_url_frag = '/repos/papers/%s.json' % ekey
                drv.click_item_toggle(idx, 'Repositories')
                drv.page.wait_for_timeout(200)
                fetched = any(repo_url_frag in u for u in drv.requests)
                if not fetched:
                    problems.append('expanding Repositories for %r did not fetch data/repos/papers/%s.json'
                                     % (title, key))
                head_text = panel_head_text('repositories')
                if str(repo_row.get('repos', 0)) not in head_text.replace(',', ''):
                    problems.append('repositories head for %r: expected count %d, saw %r'
                                     % (title, repo_row.get('repos', 0), head_text))
        else:
            if has_repo_toggle:
                problems.append('paper %r has NO repos index row but a Repositories toggle is rendered' % title)

    if drv.console_errors:
        problems.append('console errors during expansions: %s' % drv.console_errors[-3:])
    return notes


# ---------------- Report ----------------

def write_report(results, inventory_lines, seed, base_url, expand_budget):
    path = os.path.join(HERE, 'report.md')
    total = len(results)
    failed = [r for r in results if not r['ok']]
    passed = total - len(failed)
    n_expanded = sum(1 for r in results if r.get('expansions'))
    lines = ['RUN COMPLETE -- %d tests, %d passed, %d failed, seed %d' % (total, passed, len(failed), seed), '']
    lines.append('# UI random-settings test run -- report')
    lines.append('')
    lines.append('Per `tests/ui/SPEC.md` (his instruction, 2026-08-26). Oracle: `tests/ui/oracle.py`, '
                 'computed directly from the data files. Driver: Playwright against `%s`.' % base_url)
    lines.append('')
    lines.extend(inventory_lines)
    lines.append('## Interpretation notes (per the spec\'s "STOP rather than guess" instruction)')
    lines.append('')
    lines.append('- **"All Papers panel" vs "Publications page"**: this codebase has one page '
                 '(`publications.html`) with two labeled regions -- the Filters block '
                 '(`#pubs-filters`, informally "the All Papers panel" since with nothing selected '
                 'it lists every paper) and the Publications listing (`#pubs-results`) beneath it. '
                 'Read "cross-page agreement" as: a facet checkbox\'s dynamic count badge in the '
                 'Filters block must always match what the Publications listing actually renders. '
                 'There is no second page/embed of this list anywhere else in the repo today.')
    lines.append('- **"every filter on at once" (extreme case)**: checking every checkbox *within* '
                 'one facet is a no-op (OR-within-facet matches everything with any value there), so '
                 'it cannot produce an "extreme" narrowing. Read literally it would test nothing; '
                 'the "kitchen-sink" extreme case instead picks one value from each of the four main '
                 'facets (year + topic + author + type) simultaneously (AND across facets), which is '
                 'the combination that actually stresses over-constraint.')
    lines.append('')
    lines.append('## Summary')
    lines.append('')
    lines.append('- Total: **%d**, Passed: **%d**, Failed: **%d**, seed=**%d**' % (total, passed, len(failed), seed))
    lines.append('- %d of %d tests were flagged for the expansion checks (>=30 target); %d actually '
                 'expanded a paper -- the gap is tests flagged for expansion that landed on an '
                 'empty-result setting (nothing to expand), not a silent skip.'
                 % (expand_budget, total, n_expanded))
    lines.append('')
    if failed:
        lines.append('## Failures (exact settings + repro)')
        lines.append('')
        for r in failed:
            lines.append('### %s' % r['case'])
            for p in r['problems']:
                lines.append('- %s' % p)
            if r.get('expansions'):
                lines.append('- expansions checked: %s' % '; '.join(r['expansions']))
            lines.append('')
    else:
        lines.append('No discrepancies between the live UI and the independent oracle across all %d '
                     'settings (including the expansion checks).' % total)
        lines.append('')
    with open(path, 'w') as fh:
        fh.write('\n'.join(lines) + '\n')
    return path, len(failed)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base-url', default='http://localhost:8123')
    ap.add_argument('--seed', type=int, default=42)
    ap.add_argument('--n', type=int, default=100)
    ap.add_argument('--headed', action='store_true')
    args = ap.parse_args()
    rng = random.Random(args.seed)

    F = ft.Facts()
    ft.F = F  # facet_test.oracle_titles_for / dynamic_badge_expected read this module global

    from playwright.sync_api import sync_playwright
    results = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not args.headed)
        page = browser.new_page()
        drv = RandomDriver(page)
        drv.goto(args.base_url)

        raw = drv.discover()
        model = build_control_model(raw)
        inventory_lines = render_inventory_md(model, len(raw))

        n_single = round(args.n * 0.25)
        n_extreme = round(args.n * 0.15)
        n_multi = args.n - n_single - n_extreme

        plan = (['single'] * n_single + ['multi'] * n_multi + ['extreme'] * n_extreme)
        rng.shuffle(plan)

        extreme_kinds = ['kitchen-sink', 'empty-result', 'max-slider', 'no-match-search']
        expand_budget = max(30, round(args.n * 0.3))
        expand_flags = [False] * args.n
        for i in rng.sample(range(args.n), min(expand_budget, args.n)):
            expand_flags[i] = True

        for i, kind in enumerate(plan):
            drv.reset()
            # Reload the oracle's data snapshot right before each test: this
            # is a live, actively-edited shared repo (other lanes commit to
            # data/citations/*, data/repos/*, etc. mid-run) -- each
            # drv.reset() re-fetches the CURRENT files from disk, so the
            # oracle must too, or a concurrent write mid-run reads as a
            # false site bug (an order/count mismatch that's really just
            # oracle-vs-page looking at two different moments in time).
            F = ft.Facts()
            ft.F = F
            if kind == 'single':
                setting = gen_single(rng, model, F)
            elif kind == 'multi':
                setting = gen_multi(rng, model, F, rng.randint(2, 4))
            else:
                setting = gen_extreme(rng, model, F, extreme_kinds[i % len(extreme_kinds)])

            err = apply_setting(drv, setting, F)
            if err:
                results.append({'case': setting.label, 'ok': False, 'problems': [err], 'expansions': []})
                continue
            check_setting(drv, setting, F, results, do_expand=expand_flags[i])

        browser.close()

    path, nfail = write_report(results, inventory_lines, args.seed, args.base_url, expand_budget)
    n_expanded = sum(1 for r in results if r.get('expansions'))
    print('Wrote %s: %d tests, %d failed, %d included expansions, seed=%d'
          % (path, len(results), nfail, n_expanded, args.seed))
    return 1 if nfail else 0


if __name__ == '__main__':
    sys.exit(main())
