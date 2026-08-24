/* Citation view — prototype controller.
   Renders the expandable per-paper citation section described in
   docs/citation-design.md. Data contract: data/citations/SCHEMA.md.
   Written in the publications.js style (ES5, createElement, no deps);
   when this graduates, it becomes assets/js/citations.js unchanged except
   for DATA_BASE. */

var CITATIONS = (function(){
  'use strict';

  var DATA_BASE = '../data/citations/';   // site pages use 'data/citations/'

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
  function trackSafe(name, data){
    try { if (typeof track === 'function') track(name, data); } catch (e) {}
  }

  /* ---------- one citing-work row ---------- */
  function renderRow(c){
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
    if (c.flags && c.flags.indexOf('lineage') !== -1)
      li.appendChild(el('span', 'cite-chip', 'via a successor system'));
    return li;
  }

  /* ---------- a collapsible group of rows (rows built on first open) ---------- */
  function renderGroup(title, gloss, rows, startOpen){
    var wrap = el('div', 'cite-group');
    var head = el('a', 'cite-group-head');
    head.href = '#';
    var arrow = el('span', null, startOpen ? '▾ ' : '▸ ');
    head.appendChild(arrow);
    head.appendChild(el('span', 'cite-group-label', title));
    head.appendChild(el('span', 'cite-group-count', ' ' + fmt(rows.length)));
    if (gloss) head.appendChild(el('span', 'cite-group-gloss', ' — ' + gloss));
    wrap.appendChild(head);

    var listWrap = el('div', 'cite-group-body');
    listWrap.style.display = startOpen ? '' : 'none';
    var built = false;
    function build(){
      if (built) return;
      built = true;
      var ul = el('ul', 'cite-rows');
      for (var i = 0; i < rows.length; i++) ul.appendChild(renderRow(rows[i]));
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
    var external = [], ownGroup = [];
    for (var i = 0; i < all.length; i++){
      ((all[i].flags && all[i].flags.indexOf('own-group') !== -1) ? ownGroup : external).push(all[i]);
    }

    /* Headline: displayed count = max(verified, Google Scholar). */
    var display = Math.max(counts.works, gscholar || 0);
    var head = el('div', 'cite-head');
    head.appendChild(el('span', 'cite-head-count', fmt(display) + ' citations'));
    var src = [fmt(counts.works) + ' verified and analyzed below'];
    if (gscholar) src.push('Google Scholar reports ' + fmt(gscholar));
    head.appendChild(el('span', 'cite-head-src', ' — ' + src.join('; ') + '.'));
    mount.appendChild(head);

    /* Top-level split over external works. */
    var state = { centrality: 'all' };
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
    if (ownGroup.length){
      mount.appendChild(el('div', 'cite-owngroup-note',
        'Counts above are external. ' + fmt(ownGroup.length) +
        ' more citations come from our own group and students; they are listed separately at the bottom.'));
    }

    /* Centrality filter (applies to the judged groups below). */
    var judgedExt = extDetailed.concat(extPassing);
    var centCounts = { core: 0, engaged: 0, peripheral: 0 };
    judgedExt.forEach(function(c){ if (centCounts[c.centrality] !== undefined) centCounts[c.centrality]++; });
    var filterRow = el('div', 'cite-filter');
    filterRow.appendChild(el('span', 'cite-filter-label', 'How central is this paper to the citing work? '));
    var btns = [];
    function mkBtn(value, label){
      var b = el('button', 'type-toggle-btn' + (value === 'all' ? ' active' : ''), label);
      b.type = 'button';
      b.addEventListener('click', function(){
        state.centrality = value;
        for (var j = 0; j < btns.length; j++){
          btns[j].el.className = 'type-toggle-btn' + (btns[j].value === value ? ' active' : '');
        }
        drawGroups();
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

    /* FUNCTION drill-down groups. */
    var groupsMount = el('div', 'cite-groups');
    mount.appendChild(groupsMount);
    function drawGroups(){
      groupsMount.innerHTML = '';
      for (var g = 0; g < FUNCTIONS.length; g++){
        var f = FUNCTIONS[g];
        var rows = judgedExt.filter(function(c){ return c.function === f.key; });
        if (state.centrality !== 'all'){
          rows = rows.filter(function(c){ return c.centrality === state.centrality; });
        }
        if (!rows.length) continue;
        groupsMount.appendChild(renderGroup(f.label, f.gloss, rows, false));
      }
      if (state.centrality === 'all' && extUnjudged.length){
        groupsMount.appendChild(renderGroup('Not yet analyzed',
          'no usable evidence yet: title-only records, or citation snippets that never reach this paper',
          extUnjudged, false));
      }
      if (state.centrality === 'all' && ownGroup.length){
        groupsMount.appendChild(renderGroup('Our own group',
          'author overlap with this paper; reported apart from external impact',
          ownGroup, false));
      }
    }
    drawGroups();

    var foot = el('div', 'cite-foot',
      'Classified with codebook v' + data.codebook + ' (' + data.generated +
      '); duplicates folded, self-citations by the paper itself excluded.');
    mount.appendChild(foot);
  }

  /* ---------- toggle wiring, pub-summary pattern ---------- */
  function attachToggle(metaEl, bodyParent, key, indexRow){
    var display = Math.max(indexRow.verified, indexRow.gscholar || 0);
    var div = el('div', 'pub-summary cite-view');   // reuses .open show/hide
    var toggle = el('a', 'pub-action pub-summary-toggle');
    toggle.href = '#';
    var setArrow = function(open){
      toggle.textContent = 'Citations (' + fmt(display) + ') ' + (open ? '▾' : '▸');
    };
    setArrow(false);
    var loaded = false;
    toggle.addEventListener('click', function(ev){
      ev.preventDefault();
      var willOpen = div.className.indexOf('open') === -1;
      div.className = 'pub-summary cite-view' + (willOpen ? ' open' : '');
      setArrow(willOpen);
      if (willOpen && !loaded){
        loaded = true;
        div.appendChild(el('div', 'cite-loading', 'Loading…'));
        fetch(DATA_BASE + encodeURIComponent(key) + '.json')
          .then(function(r){ if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
          .then(function(data){ renderView(div, key, data, indexRow); })
          .catch(function(e){
            loaded = false;
            div.innerHTML = '';
            div.appendChild(el('div', 'cite-loading', 'Could not load citation data (' + e.message + ').'));
          });
      }
      if (willOpen) trackSafe('citations-view', { key: key });
    });
    metaEl.appendChild(document.createTextNode(' '));
    metaEl.appendChild(toggle);
    bodyParent.appendChild(div);
  }

  return {
    attachToggle: attachToggle,
    setDataBase: function(p){ DATA_BASE = p; },
    loadIndex: function(){
      return fetch(DATA_BASE + 'index.json')
        .then(function(r){ if (!r.ok) throw new Error('no citations index'); return r.json(); });
    }
  };
})();
