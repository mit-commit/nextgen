/* Citation view — the expandable per-paper citation section.
   Design: docs/citation-design.md. Data contract: data/citations/SCHEMA.md.
   ES5, createElement, no deps. Graduated from prototype/citations.js
   (kept for reference) with only DATA_BASE and this header changed.
   publications.js calls CITATIONS.loadIndex() once at boot and
   CITATIONS.attachToggle() per paper that has a row in the index. */

var CITATIONS = (function(){
  'use strict';

  var DATA_BASE = 'data/citations/';

  /* Plain-language labels for FUNCTION values, in codebook priority order. */
  var FUNCTIONS = [
    { key: 'extends',           label: 'Builds on it',
      gloss: 'the cited system or technique is the substrate of their contribution' },
    { key: 'uses-tool',         label: 'Uses the system',
      gloss: 'runs it as working infrastructure' },
    { key: 'adopts-idea',       label: 'Adopts the idea',
      gloss: 'borrows the abstraction or design principle, not the code' },
    { key: 'uses-benchmark',    label: 'Uses its benchmarks',
      gloss: 'evaluates on workloads this paper introduced' },
    { key: 'baseline',          label: 'Measures against it',
      gloss: 'the system appears as a compared alternative, numbers against numbers' },
    { key: 'positions',         label: 'Positions against it',
      gloss: 'contrasts its own contribution with specifics of this work' },
    { key: 'surveys',           label: 'Surveys it',
      gloss: 'systematic descriptive treatment: surveys, taxonomies, textbooks' },
    { key: 'supports-claim',    label: 'Cites a result as evidence',
      gloss: 'a specific measurement or finding travels, not the system' },
    { key: 'exemplifies',       label: 'Names it as an example',
      gloss: 'one member of a list of examples of a category' },
    { key: 'detailed-citation', label: 'Mentions it specifically',
      gloss: 'a sentence about this work in particular, or several cite sites' },
    { key: 'passing-citation',  label: 'Cites it in a list',
      gloss: 'appears only inside multi-paper citation lists' }
  ];
  var CENTRALITIES = ['core', 'engaged', 'peripheral'];

  function el(tag, cls, txt){
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (txt !== undefined && txt !== null) e.appendChild(document.createTextNode(String(txt)));
    return e;
  }
  function fmt(n){ return Number(n).toLocaleString('en-US'); }
  /* Citation-count buckets, shared by the per-paper popularity sort and the
     publications page's citation ordering of the paper list itself. */
  function countBucket(n){
    if (n == null) return 'count unknown';
    if (n >= 1000) return '1,000+ citations';
    if (n >= 100) return '100–999 citations';
    if (n >= 10) return '10–99 citations';
    if (n >= 1) return '1–9 citations';
    return 'not yet cited';
  }
  /* THE displayed citation figure — max(verified, gscholar ?? 0). Single
     source of truth for the toggle label, the expanded headline, and the
     publications page's list-level Citations sort. */
  function displayCount(row){
    if (!row) return 0;
    return Math.max(row.verified || 0, row.gscholar || 0);
  }

  /* Impact score: each external judged citation weighted by what it does.
     Weights mirrored in data/citations/SCHEMA.md — change both together. */
  var WEIGHTS = {
    'extends': 10, 'uses-tool': 8, 'adopts-idea': 8,
    'uses-benchmark': 5, 'baseline': 5, 'positions': 3,
    'surveys': 2, 'supports-claim': 2, 'exemplifies': 1,
    'detailed-citation': 1, 'passing-citation': 0.5
  };
  function impactScore(row){
    if (!row || !row.functions) return null;
    var s = 0;
    for (var f in row.functions){ s += (WEIGHTS[f] || 0) * row.functions[f]; }
    return Math.round(s);
  }

  /* Page-level panel state: every open panel follows these; per-panel
     controls can still diverge afterwards. */
  var gPanel = { sort: 'impact', centrality: 'all', categories: null, search: '' };
  function rowMatchesGlobal(c){
    if (gPanel.categories && gPanel.categories.length &&
        gPanel.categories.indexOf(c.function) === -1) return false;
    if (gPanel.search){
      var hay = ((c.title || '') + ' ' + (c.authors || '') + ' ' + (c.venue || '')).toLowerCase();
      if (hay.indexOf(gPanel.search) === -1) return false;
    }
    return true;
  }
  function trackSafe(name, data){
    try { if (typeof track === 'function') track(name, data); } catch (e) {}
  }

  /* ---------- one citing-work row ---------- */
  function renderRow(c, showCites){
    var li = el('li', 'cite-row');
    var t = el('span', 'cite-row-title');
    if (c.url){
      var a = el('a', null, c.title);
      a.href = c.url; a.target = '_blank'; a.rel = 'noopener';
      t.appendChild(a);
    } else {
      t.appendChild(document.createTextNode(c.title));
    }
    li.appendChild(t);
    var bits = [];
    if (c.authors) bits.push(c.authors);
    if (c.venue) bits.push(c.venue);
    if (c.year) bits.push(String(c.year));
    if (bits.length) li.appendChild(el('span', 'cite-row-meta', ' — ' + bits.join('. ') + '.'));
    if (c.centrality === 'core') li.appendChild(el('span', 'cite-chip cite-chip-core', 'core'));
    if (c.commit) li.appendChild(el('span', 'cite-chip', 'COMMIT'));
    if (c.flags && c.flags.indexOf('lineage') !== -1)
      li.appendChild(el('span', 'cite-chip', 'via a successor system'));
    if (showCites && c.cited_by != null)
      li.appendChild(el('span', 'cite-chip', fmt(c.cited_by) + ' cites'));
    return li;
  }

  /* ---------- a collapsible group of rows (rows built on first open) ---------- */
  function renderGroupWith(title, gloss, rows, startOpen, rowFn){
    return renderGroupCore(title, gloss, rows, startOpen, rowFn);
  }
  function renderGroup(title, gloss, rows, startOpen, showCites){
    return renderGroupCore(title, gloss, rows, startOpen,
      function(r){ return renderRow(r, showCites); });
  }
  function renderGroupCore(title, gloss, rows, startOpen, rowFn){
    var wrap = el('div', 'cite-group');
    var head = el('a', 'cite-group-head');
    head.href = '#';
    var arrow = el('span', null, startOpen ? '▾ ' : '▸ ');
    head.appendChild(arrow);
    head.appendChild(el('span', 'cite-group-label', title));
    head.appendChild(el('span', 'cite-group-count', ' (' + fmt(rows.length) + ')'));
    if (gloss) head.title = gloss;  // description as a tooltip, not inline
    wrap.appendChild(head);

    var listWrap = el('div', 'cite-group-body');
    listWrap.style.display = startOpen ? '' : 'none';
    var built = false;
    function build(){
      if (built) return;
      built = true;
      var ul = el('ul', 'cite-rows');
      for (var i = 0; i < rows.length; i++) ul.appendChild(rowFn(rows[i]));
      listWrap.appendChild(ul);
    }
    if (startOpen) build();
    head.addEventListener('click', function(ev){
      ev.preventDefault();
      var open = listWrap.style.display === 'none';
      if (open) build();
      listWrap.style.display = open ? '' : 'none';
      arrow.textContent = open ? '▾ ' : '▸ ';
    });
    wrap.appendChild(listWrap);
    return wrap;
  }

  /* ---------- the split bar ---------- */
  function renderSplitBar(nDetailed, nPassing, nUnjudged){
    var total = nDetailed + nPassing + nUnjudged;
    var bar = el('div', 'cite-splitbar');
    var segs = [
      ['cite-seg-detailed', nDetailed],
      ['cite-seg-passing', nPassing],
      ['cite-seg-unjudged', nUnjudged]
    ];
    for (var i = 0; i < segs.length; i++){
      if (!segs[i][1]) continue;
      var s = el('div', 'cite-seg ' + segs[i][0]);
      s.style.width = (100 * segs[i][1] / total).toFixed(2) + '%';
      bar.appendChild(s);
    }
    return bar;
  }

  /* ---------- the whole view for one paper ---------- */
  /* indexRow is authoritative for the Scholar figure: a gscholar.json
     refresh reaches index.json on every merge run, while a paper's own
     counts.gscholar is rewritten only when that paper is reprocessed. */
  function renderView(mount, key, data, indexRow){
    mount.innerHTML = '';
    var counts = data.counts;
    var gscholar = (indexRow && indexRow.gscholar != null) ? indexRow.gscholar : counts.gscholar;
    var all = data.citations;
    /* COMMIT papers = citing works with Saman Amarasinghe among the
       authors (entry.commit, set at build time); everything else is
       external impact. */
    var external = [], commitPapers = [];
    for (var i = 0; i < all.length; i++){
      (all[i].commit ? commitPapers : external).push(all[i]);
    }


    /* Headline: just the displayed count — max(verified, Google Scholar). */
    var display = displayCount({ verified: counts.works, gscholar: gscholar });
    var head = el('div', 'cite-head');
    head.appendChild(el('span', 'cite-head-count', fmt(display) + ' citations'));
    mount.appendChild(head);

    /* Top-level split over external works. */
    var state = { centrality: gPanel.centrality };
    var extDetailed = external.filter(function(c){ return c.split === 'detailed'; });
    var extPassing  = external.filter(function(c){ return c.split === 'passing'; });
    var extUnjudged = external.filter(function(c){ return !c.split; });

    mount.appendChild(renderSplitBar(extDetailed.length, extPassing.length, extUnjudged.length));
    var legend = el('div', 'cite-legend');
    function leg(cls, label, n){
      var s = el('span', 'cite-legend-item');
      s.appendChild(el('span', 'cite-key ' + cls, ''));
      s.appendChild(document.createTextNode(label + ' ' + fmt(n)));
      return s;
    }
    if (extDetailed.length) legend.appendChild(leg('cite-seg-detailed', 'Detailed engagement', extDetailed.length));
    if (extPassing.length) legend.appendChild(leg('cite-seg-passing', 'Passing mention', extPassing.length));
    if (extUnjudged.length) legend.appendChild(leg('cite-seg-unjudged', 'Not yet analyzed', extUnjudged.length));
    mount.appendChild(legend);

    /* Centrality filter and sort modes (apply to the judged list below). */
    state.sort = gPanel.sort;
    state.expanded = false;  // groups collapsed by default; headers always shown
    var judgedExt = extDetailed.concat(extPassing);
    var centCounts = { core: 0, engaged: 0, peripheral: 0 };
    judgedExt.forEach(function(c){ if (centCounts[c.centrality] !== undefined) centCounts[c.centrality]++; });
    var filterRow = el('div', 'cite-filter');
    filterRow.appendChild(el('span', 'cite-filter-label', 'How central is this paper to the citing work? '));
    var btns = [];
    var CENT_TIPS = {
      all: 'All judged citations',
      core: 'The citing work would be fundamentally different without this paper',
      engaged: "Engages the paper's specifics, short of depending on it",
      peripheral: 'A swap-out-able mention or list membership'
    };
    function mkBtn(value, label){
      var b = el('button', 'type-toggle-btn' + (value === state.centrality ? ' active' : ''), label);
      b.type = 'button';
      if (CENT_TIPS[value]) b.title = CENT_TIPS[value];
      b.addEventListener('click', function(){
        state.centrality = value;
        for (var j = 0; j < btns.length; j++){
          btns[j].el.className = 'type-toggle-btn' + (btns[j].value === value ? ' active' : '');
        }
        drawList();
        trackSafe('citations-centrality-filter', { key: key, value: value });
      });
      btns.push({ value: value, el: b });
      return b;
    }
    var tg = el('span', 'type-toggle');
    tg.appendChild(mkBtn('all', 'All'));
    tg.appendChild(mkBtn('core', 'Core ' + fmt(centCounts.core)));
    tg.appendChild(mkBtn('engaged', 'Engaged ' + fmt(centCounts.engaged)));
    tg.appendChild(mkBtn('peripheral', 'Peripheral ' + fmt(centCounts.peripheral)));
    filterRow.appendChild(tg);
    mount.appendChild(filterRow);

    /* Sort modes + headers toggle. */
    var sortRow = el('div', 'cite-filter');
    sortRow.appendChild(el('span', 'cite-filter-label', 'Sort by '));
    var sortBtns = [];
    var SORT_TIPS = {
      impact: 'Order citations by what they do: building on the paper ranks above running it, above borrowing its idea, above citing it in a list',
      recency: 'Newest citing works first, grouped by year',
      popularity: 'Most-cited citing works first, grouped by their own citation counts'
    };
    function mkSortBtn(value, label){
      var b = el('button', 'type-toggle-btn' + (value === state.sort ? ' active' : ''), label);
      b.type = 'button';
      if (SORT_TIPS[value]) b.title = SORT_TIPS[value];
      b.addEventListener('click', function(){
        state.sort = value;
        for (var j = 0; j < sortBtns.length; j++){
          sortBtns[j].el.className = 'type-toggle-btn' + (sortBtns[j].value === value ? ' active' : '');
        }
        drawList();
        trackSafe('citations-sort', { key: key, value: value });
      });
      sortBtns.push({ value: value, el: b });
      return b;
    }
    var stg = el('span', 'type-toggle');
    stg.appendChild(mkSortBtn('impact', 'Impact'));
    stg.appendChild(mkSortBtn('recency', 'Recency'));
    stg.appendChild(mkSortBtn('popularity', 'Popularity'));
    sortRow.appendChild(stg);
    var expBtn = el('button', 'type-toggle-btn cite-hdr-toggle', 'Expand all');
    expBtn.type = 'button';
    expBtn.title = 'Open or close every group below';
    expBtn.setAttribute('aria-pressed', 'false');
    expBtn.addEventListener('click', function(){
      state.expanded = !state.expanded;
      expBtn.className = 'type-toggle-btn cite-hdr-toggle' + (state.expanded ? ' active' : '');
      expBtn.setAttribute('aria-pressed', state.expanded ? 'true' : 'false');
      expBtn.textContent = state.expanded ? 'Collapse all' : 'Expand all';
      drawList();
      trackSafe('citations-expand-groups', { key: key, on: state.expanded });
    });
    sortRow.appendChild(el('span', null, ' '));
    sortRow.appendChild(expBtn);
    mount.appendChild(sortRow);

    /* The judged list, in the chosen order. */
    var groupsMount = el('div', 'cite-groups');
    mount.appendChild(groupsMount);
    var FN_RANK = {};
    FUNCTIONS.forEach(function(f, i){ FN_RANK[f.key] = i; });
    function sortRows(rows){
      var sorted = rows.slice();
      if (state.sort === 'impact'){
        sorted.sort(function(a, b){
          return (FN_RANK[a.function] - FN_RANK[b.function]) ||
                 ((b.year || 0) - (a.year || 0));
        });
      } else if (state.sort === 'recency'){
        sorted.sort(function(a, b){ return (b.year || -1) - (a.year || -1); });
      } else {
        sorted.sort(function(a, b){
          return ((b.cited_by != null ? b.cited_by : -1) -
                  (a.cited_by != null ? a.cited_by : -1)) ||
                 ((b.year || 0) - (a.year || 0));
        });
      }
      return sorted;
    }
    var commitJudged = commitPapers.filter(function(c){ return c.split; });
    var commitUnjudged = commitPapers.filter(function(c){ return !c.split; });
    function drawList(){
      groupsMount.innerHTML = '';
      /* Impact keeps COMMIT papers apart (external-impact story);
         Recency and Popularity incorporate them, chip-marked. */
      var rows = (state.sort === 'impact') ? judgedExt : judgedExt.concat(commitJudged);
      if (state.centrality !== 'all'){
        rows = rows.filter(function(c){ return c.centrality === state.centrality; });
      }
      rows = rows.filter(rowMatchesGlobal);
      var showCites = state.sort === 'popularity';
      /* Always grouped with headers — categories / years / count buckets;
         the Expand all / Collapse all button opens or closes every group. */
      if (state.sort === 'impact'){
        for (var g = 0; g < FUNCTIONS.length; g++){
          var f = FUNCTIONS[g];
          var grows = rows.filter(function(c){ return c.function === f.key; });
          if (grows.length) groupsMount.appendChild(renderGroup(f.label, f.gloss, grows, state.expanded));
        }
      } else {
        var headerOf = (state.sort === 'recency')
          ? function(c){ return c.year ? String(c.year) : 'no year'; }
          : function(c){ return countBucket(c.cited_by); };
        var sorted = sortRows(rows);
        var order = [], byHeader = {};
        for (var i = 0; i < sorted.length; i++){
          var h = headerOf(sorted[i]);
          if (!byHeader[h]){ byHeader[h] = []; order.push(h); }
          byHeader[h].push(sorted[i]);
        }
        for (var j = 0; j < order.length; j++){
          groupsMount.appendChild(renderGroup(order[j], null, byHeader[order[j]], state.expanded, showCites));
        }
      }
      var unjudged = ((state.sort === 'impact')
        ? extUnjudged : extUnjudged.concat(commitUnjudged)).filter(rowMatchesGlobal);
      if (state.centrality === 'all' && unjudged.length){
        groupsMount.appendChild(renderGroup('Not yet analyzed',
          'no usable evidence yet: title-only records, or citation snippets that never reach this paper',
          unjudged, state.expanded));
      }
      var commitShown = commitPapers.filter(rowMatchesGlobal);
      if (state.sort === 'impact' && state.centrality === 'all' && commitShown.length){
        groupsMount.appendChild(renderGroup('COMMIT papers',
          'the group\'s own citing papers — Saman Amarasinghe is an author; reported apart from external impact',
          commitShown, state.expanded));
      }
    }
    drawList();

    panels.push({ el: mount, sync: function(){
      state.sort = gPanel.sort;
      state.centrality = gPanel.centrality;
      for (var pj = 0; pj < btns.length; pj++)
        btns[pj].el.className = 'type-toggle-btn' + (btns[pj].value === state.centrality ? ' active' : '');
      for (var pk = 0; pk < sortBtns.length; pk++)
        sortBtns[pk].el.className = 'type-toggle-btn' + (sortBtns[pk].value === state.sort ? ' active' : '');
      drawList();
    } });

  }

  /* ---------- toggle wiring, pub-summary pattern ---------- */

  /* Expand-all support: every toggle registers here so "Show citations"
     can open or close the whole page; defaultOpen makes items rendered
     later (filter changes) follow the global state, like summaries do. */
  var instances = [];
  var panels = [];      // loaded panel controllers, for the page-level tools
  var defaultOpen = false;
  var dataCache = {};   // key -> per-paper JSON, kept for cross-paper analysis

  /* Per-paper files load lazily even under expand-all; this small queue
     keeps that progressive (a few fetches in flight, page never blocked). */
  var fetchQueue = [], fetchActive = 0, FETCH_CONCURRENCY = 4;
  function pumpQueue(){
    while (fetchActive < FETCH_CONCURRENCY && fetchQueue.length){
      var job = fetchQueue.shift();
      fetchActive++;
      job().then(
        function(){ fetchActive--; pumpQueue(); },
        function(){ fetchActive--; pumpQueue(); }
      );
    }
  }

  function attachToggle(metaEl, bodyParent, key, indexRow){
    var display = displayCount(indexRow);
    var div = el('div', 'pub-summary cite-view');   // reuses .open show/hide
    var toggle = el('a', 'pub-action pub-summary-toggle cite-toggle');
    toggle.href = '#';
    var setArrow = function(open){
      toggle.textContent = 'Citations (' + fmt(display) + ') ' + (open ? '▾' : '▸');
    };
    setArrow(false);
    var loaded = false;
    function load(){
      if (loaded) return;
      loaded = true;
      div.appendChild(el('div', 'cite-loading', 'Loading…'));
      fetchQueue.push(function(){
        return fetch(DATA_BASE + encodeURIComponent(key) + '.json')
          .then(function(r){ if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
          .then(function(data){ dataCache[key] = data; renderView(div, key, data, indexRow); })
          .catch(function(e){
            loaded = false;
            div.innerHTML = '';
            div.appendChild(el('div', 'cite-loading', 'Could not load citation data (' + e.message + ').'));
          });
      });
      pumpQueue();
    }
    function setOpen(open){
      var isOpen = div.className.indexOf('open') !== -1;
      if (open === isOpen) return;
      div.className = 'pub-summary cite-view' + (open ? ' open' : '');
      setArrow(open);
      if (open) load();
    }
    toggle.addEventListener('click', function(ev){
      ev.preventDefault();
      var willOpen = div.className.indexOf('open') === -1;
      setOpen(willOpen);
      if (willOpen) trackSafe('citations-view', { key: key });
    });
    metaEl.appendChild(document.createTextNode(' '));
    metaEl.appendChild(toggle);
    bodyParent.appendChild(div);
    instances.push({ el: div, setOpen: setOpen });
    if (defaultOpen) setOpen(true);
  }

  function setAllOpen(open){
    instances = instances.filter(function(inst){
      return document.contains(inst.el);
    });
    for (var i = 0; i < instances.length; i++) instances[i].setOpen(open);
  }

  /* Page-level tools: patch the global panel state and resync every
     loaded panel (open or not — they redraw in place). */
  function setGlobalPanels(patch){
    if (patch.sort !== undefined) gPanel.sort = patch.sort;
    if (patch.centrality !== undefined) gPanel.centrality = patch.centrality;
    if (patch.categories !== undefined) gPanel.categories = patch.categories;
    if (patch.search !== undefined) gPanel.search = String(patch.search || '').toLowerCase().trim();
    panels = panels.filter(function(pn){ return document.contains(pn.el); });
    for (var i = 0; i < panels.length; i++) panels[i].sync();
  }

  /* Fetch (through the progressive queue) the data files for a set of
     papers without opening their panels; resolves when all settle. */
  function ensureData(list){
    var jobs = [];
    for (var i = 0; i < list.length; i++){
      (function(key){
        if (dataCache[key]) return;
        jobs.push(new Promise(function(resolve){
          fetchQueue.push(function(){
            return fetch(DATA_BASE + encodeURIComponent(key) + '.json')
              .then(function(r){ if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
              .then(function(data){ dataCache[key] = data; })
              .catch(function(){})
              .then(resolve);
          });
        }));
      })(list[i].key !== undefined ? list[i].key : list[i]);
    }
    pumpQueue();
    return Promise.all(jobs);
  }

  /* Works citing more than one of the given papers, matched by DOI or
     normalized title over whatever files are cached. */
  function crossCiters(keys){
    var byId = {};
    for (var i = 0; i < keys.length; i++){
      var d = dataCache[keys[i]];
      if (!d) continue;
      for (var j = 0; j < d.citations.length; j++){
        var c = d.citations[j];
        if (!c.title || c.title === 'Untitled') continue; // unauditable records
        var id = c.doi || c.title.toLowerCase().replace(/[^a-z0-9]+/g, '');
        if (!id) continue;
        if (!byId[id]) byId[id] = { work: c, papers: [] };
        if (byId[id].papers.indexOf(keys[i]) === -1) byId[id].papers.push(keys[i]);
        if ((c.cited_by || 0) > (byId[id].work.cited_by || 0)) byId[id].work = c;
      }
    }
    var out = [];
    for (var id2 in byId){ if (byId[id2].papers.length >= 2) out.push(byId[id2]); }
    out.sort(function(a, b){
      return (b.papers.length - a.papers.length) ||
             ((b.work.cited_by || 0) - (a.work.cited_by || 0));
    });
    return out;
  }


  /* ==================== Repositories panel (impact view) ====================
     Same grammar as the citations panel; data from data/repos/ per
     data/repos/SCHEMA.md. Unified relationship taxonomy shared with
     citations; groups with no rows do not render. */
  var REPO_BASE = DATA_BASE.replace('citations', 'repos');
  var REPO_GROUPS = [
    { key: 'own',       label: 'Artifact & own repository',
      gloss: "the paper's archival artifact first, then its implementation repository" },
    { key: 'builds-on', label: 'Builds on it',
      gloss: 'derivative works and forks of the artifact' },
    { key: 'uses',      label: 'Uses the system',
      gloss: 'repositories that import or depend on the artifact' },
    { key: 'benchmarks', label: 'Uses its benchmarks',
      gloss: "repositories carrying the paper's workload files" },
    { key: 'adopts',    label: 'Adopts the idea',
      gloss: 'repositories of citing works that reimplement the idea without the code' }
  ];
  function repoStarBucket(n){
    if (n == null) return 'stars unknown';
    if (n >= 1000) return '1,000+ stars';
    if (n >= 100) return '100\u2013999 stars';
    if (n >= 10) return '10\u201399 stars';
    return 'under 10 stars';
  }
  function renderRepoRow(r){
    var li = el('li', 'cite-row' + (r.paperOnly ? ' repo-paper-only' : ''));
    var t = el('span', 'cite-row-title');
    var label = r.name || r.paper || r.url;
    if (r.url && !r.gone){
      var a = el('a', null, label); a.href = r.url; a.target = '_blank'; a.rel = 'noopener';
      t.appendChild(a);
    } else {
      t.appendChild(document.createTextNode(label));
    }
    li.appendChild(t);
    if (r.desc) li.appendChild(el('span', 'cite-row-meta', ' \u2014 ' + r.desc + (/[.!?]$/.test(r.desc) ? '' : '.')));
    if (r.paperOnly) li.appendChild(el('span', 'cite-row-meta', ' \u2014 no repository located.'));
    if (r.badges && r.badges.length) li.appendChild(el('span', 'cite-row-meta', ' \u2014 ' + r.badges.join('; ') + '.'));
    if (r.artifact) li.appendChild(el('span', 'cite-chip', 'artifact'));
    if (r.sdv) li.appendChild(el('span', 'cite-chip', String(r.sdv).replace(/_/g, ' ')));
    if (r.stars != null) li.appendChild(el('span', 'cite-chip', fmt(r.stars) + ' \u2605'));
    if (r.active) li.appendChild(el('span', 'cite-chip', 'active ' + r.active));
    if (r.archived) li.appendChild(el('span', 'cite-chip', 'archived'));
    if (r.gone) li.appendChild(el('span', 'cite-chip', 'unavailable'));
    if (r.evidence) li.title = r.evidence;
    return li;
  }
  function renderRepoPanel(mount, data){
    mount.innerHTML = '';
    var repos = data.repos || [];
    mount.appendChild(el('div', 'cite-head')).appendChild(
      el('span', 'cite-head-count', fmt(repos.length) + (repos.length === 1 ? ' repository' : ' repositories')));
    var tier = { own: 0, using: 0, adopts: 0 };
    repos.forEach(function(r){
      if (r.group === 'own') tier.own++;
      else if (r.group === 'adopts') tier.adopts++;
      else tier.using++;
    });
    var nTiers = (tier.own ? 1 : 0) + (tier.using ? 1 : 0) + (tier.adopts ? 1 : 0);
    if (nTiers > 1){
      var bar = el('div', 'cite-splitbar');
      [['cite-seg-detailed', tier.own], ['cite-seg-passing', tier.using],
       ['cite-seg-unjudged', tier.adopts]].forEach(function(seg){
        if (!seg[1]) return;
        var sd = el('div', 'cite-seg ' + seg[0]);
        sd.style.width = (100 * seg[1] / repos.length).toFixed(2) + '%';
        bar.appendChild(sd);
      });
      mount.appendChild(bar);
      var legend = el('div', 'cite-legend');
      [['cite-seg-detailed', 'Own', tier.own],
       ['cite-seg-passing', 'Builds on or uses it', tier.using],
       ['cite-seg-unjudged', 'Adopts the idea', tier.adopts]].forEach(function(l){
        if (!l[2]) return;
        var sp = el('span', 'cite-legend-item');
        sp.appendChild(el('span', 'cite-key ' + l[0], ''));
        sp.appendChild(document.createTextNode(l[1] + ' ' + fmt(l[2])));
        legend.appendChild(sp);
      });
      mount.appendChild(legend);
    }
    var state = { sort: 'impact', expanded: repos.length <= 6 };
    var sortRow = el('div', 'cite-filter');
    sortRow.appendChild(el('span', 'cite-filter-label', 'Sort by '));
    var tg = el('span', 'type-toggle'), btns = [];
    var TIPS = {
      impact: 'Group by relationship: the artifact and own repository, then the unified categories shared with citations',
      recency: 'Most recently active first, grouped by year',
      popularity: "Most-starred first, grouped by magnitude \u2014 stars are the repo world's citation count"
    };
    ['impact', 'recency', 'popularity'].forEach(function(v){
      var b = el('button', 'type-toggle-btn' + (v === state.sort ? ' active' : ''),
                 v.charAt(0).toUpperCase() + v.slice(1));
      b.type = 'button'; b.title = TIPS[v];
      b.addEventListener('click', function(){
        state.sort = v;
        btns.forEach(function(x){ x.el.className = 'type-toggle-btn' + (x.v === v ? ' active' : ''); });
        draw();
      });
      btns.push({ v: v, el: b }); tg.appendChild(b);
    });
    sortRow.appendChild(tg);
    var expBtn = el('button', 'type-toggle-btn cite-hdr-toggle' + (state.expanded ? ' active' : ''),
                    state.expanded ? 'Collapse all' : 'Expand all');
    expBtn.type = 'button'; expBtn.title = 'Open or close every group below';
    expBtn.addEventListener('click', function(){
      state.expanded = !state.expanded;
      expBtn.className = 'type-toggle-btn cite-hdr-toggle' + (state.expanded ? ' active' : '');
      expBtn.textContent = state.expanded ? 'Collapse all' : 'Expand all';
      draw();
    });
    sortRow.appendChild(el('span', null, ' '));
    sortRow.appendChild(expBtn);
    mount.appendChild(sortRow);
    var groupsMount = el('div', 'cite-groups');
    mount.appendChild(groupsMount);
    function draw(){
      groupsMount.innerHTML = '';
      if (state.sort === 'impact'){
        REPO_GROUPS.forEach(function(g){
          var rows = repos.filter(function(r){ return r.group === g.key; });
          if (rows.length) groupsMount.appendChild(
            renderGroupWith(g.label, g.gloss, rows, state.expanded, renderRepoRow));
        });
      } else {
        var sorted = repos.slice(), headerOf;
        if (state.sort === 'popularity'){
          sorted.sort(function(a, b){
            return ((b.stars != null ? b.stars : -1) - (a.stars != null ? a.stars : -1)); });
          headerOf = function(r){ return repoStarBucket(r.stars); };
        } else {
          sorted.sort(function(a, b){ return (b.active || 0) - (a.active || 0); });
          headerOf = function(r){ return r.active ? String(r.active) : 'no activity data'; };
        }
        var order = [], byH = {};
        sorted.forEach(function(r){
          var h = headerOf(r);
          if (!byH[h]){ byH[h] = []; order.push(h); }
          byH[h].push(r);
        });
        order.forEach(function(h){
          groupsMount.appendChild(renderGroupWith(h, null, byH[h], state.expanded, renderRepoRow));
        });
      }
    }
    draw();
  }
  var repoInstances = [];
  var repoDefaultOpen = false;
  var repoDataCache = {};
  function attachRepoToggle(metaEl, bodyParent, key, indexRow){
    var div = el('div', 'pub-summary cite-view');
    var toggle = el('a', 'pub-action pub-summary-toggle cite-toggle');
    toggle.href = '#';
    var n = indexRow.repos;
    var setArrow = function(open){
      toggle.textContent = 'Repositories (' + fmt(n) + ') ' + (open ? '\u25be' : '\u25b8');
    };
    setArrow(false);
    var loaded = false;
    function load(){
      if (loaded) return;
      loaded = true;
      div.appendChild(el('div', 'cite-loading', 'Loading\u2026'));
      fetchQueue.push(function(){
        return fetch(REPO_BASE + 'papers/' + encodeURIComponent(key) + '.json')
          .then(function(r){ if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
          .then(function(data){ repoDataCache[key] = data; renderRepoPanel(div, data); })
          .catch(function(e){
            loaded = false;
            div.innerHTML = '';
            div.appendChild(el('div', 'cite-loading', 'Could not load repository data (' + e.message + ').'));
          });
      });
      pumpQueue();
    }
    function setOpen(open){
      var isOpen = div.className.indexOf('open') !== -1;
      if (open === isOpen) return;
      div.className = 'pub-summary cite-view' + (open ? ' open' : '');
      setArrow(open);
      if (open) load();
    }
    toggle.addEventListener('click', function(ev){
      ev.preventDefault();
      var willOpen = div.className.indexOf('open') === -1;
      setOpen(willOpen);
      if (willOpen) trackSafe('repos-view', { key: key });
    });
    metaEl.appendChild(document.createTextNode(' '));
    metaEl.appendChild(toggle);
    bodyParent.appendChild(div);
    repoInstances.push({ el: div, setOpen: setOpen });
    if (repoDefaultOpen) setOpen(true);
  }
  function setAllReposOpen(open){
    repoInstances = repoInstances.filter(function(i){ return document.contains(i.el); });
    for (var i = 0; i < repoInstances.length; i++) repoInstances[i].setOpen(open);
  }

  return {
    attachToggle: attachToggle,
    attachRepoToggle: attachRepoToggle,
    setAllReposOpen: setAllReposOpen,
    setRepoDefaultOpen: function(v){ repoDefaultOpen = !!v; },
    loadRepoIndex: function(){
      return fetch(REPO_BASE + 'index.json', { cache: 'no-store' })
        .then(function(r){ if (!r.ok) throw new Error('no repos index'); return r.json(); });
    },
    countBucket: countBucket,
    displayCount: displayCount,
    impactScore: impactScore,
    WEIGHTS: WEIGHTS,
    FUNCTIONS: FUNCTIONS,
    setGlobalPanels: setGlobalPanels,
    ensureData: ensureData,
    crossCiters: crossCiters,
    setAllOpen: setAllOpen,
    setDefaultOpen: function(v){ defaultOpen = !!v; },
    setDataBase: function(p){ DATA_BASE = p; },
    loadIndex: function(){
      // no-store: a stale cached index must never outlive a data refresh
      return fetch(DATA_BASE + 'index.json', { cache: 'no-store' })
        .then(function(r){ if (!r.ok) throw new Error('no citations index'); return r.json(); });
    }
  };
})();
