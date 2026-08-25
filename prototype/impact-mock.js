/* MOCK ONLY — Option-B Repositories panel for docs/impact-view-design.md.
   Renders with the citation panel's CSS grammar (cite-* classes). All
   tier-2 rows and every star count are placeholders until the
   repo-ecosystems / repo-verify harvests land; placeholder rows say so. */

var IMPACT_MOCK = (function(){
  'use strict';

  /* thies:cc:2002 — own repo real per the 2026-08-25 ruling; the rest
     placeholder. Tier-3 titles are real citing works classified
     extends/adopts-idea for StreamIt; their repo fields are placeholder
     or paper-only. */
  var REPOS = [
    { tier: 'own', name: 'StreamIt artifact (archival)', artifact: true,
      integration: 'own', year: 2002, placeholder: true,
      desc: 'specimen of a badged archival artifact row — real entries come from harvest/artifacts/found.json',
      evidence: 'PLACEHOLDER — papers with ACM/Zenodo artifacts list them here, first' },
    { tier: 'own', name: 'bthies/streamit', url: 'https://github.com/bthies/streamit',
      desc: 'The StreamIt compiler and benchmark suite', integration: 'own',
      stars: 87, year: 2013, placeholder: 'metrics pending harvest',
      evidence: 'canonical repository per human ruling (2026-08-25)' },
    { tier: 'using', name: 'placeholder/streamit-on-gpu', integration: 'derivative_work',
      stars: 412, year: 2021, placeholder: true,
      evidence: 'PLACEHOLDER — shape of a derivative-work row' },
    { tier: 'using', name: 'placeholder/str-benchmark-kit', integration: 'derivative_work',
      stars: 96, year: 2019, placeholder: true,
      evidence: 'PLACEHOLDER — shape of a derivative-work row' },
    { tier: 'using', name: 'placeholder/uses-str-files-a', integration: 'api_user',
      stars: 1450, year: 2024, placeholder: true,
      evidence: 'PLACEHOLDER — shape of an api_user row' },
    { tier: 'using', name: 'placeholder/uses-str-files-b', integration: 'api_user',
      stars: 33, year: 2017, placeholder: true,
      evidence: 'PLACEHOLDER — shape of an api_user row' },
    { tier: 'using', name: 'placeholder/course-materials', integration: 'api_user',
      stars: 8, year: 2015, placeholder: true,
      evidence: 'PLACEHOLDER — shape of an api_user row' },
    { tier: 'using', name: 'placeholder/streamit-fork', integration: 'fork',
      stars: 5, year: 2016, placeholder: true,
      evidence: 'PLACEHOLDER — shape of a fork row (non-canonical)' },
    { tier: 'descendant', name: 'placeholder/str2rts', integration: 'descendant',
      stars: 21, year: 2018, placeholder: true,
      paper: 'STR2RTS: Refactored StreamIT Benchmarks into Statically Analyzable Parallel Benchmarks',
      evidence: 'PLACEHOLDER repo — the citing work is real (extends, core)' },
    { tier: 'descendant', name: null, integration: 'descendant',
      paper: 'Sponge', paperOnly: true, year: 2011,
      evidence: 'citing work classified extends/core; no repository located — paper-only row' },
    { tier: 'descendant', name: null, integration: 'descendant',
      paper: 'Flextream: Adaptive Compilation of Streaming Applications', paperOnly: true, year: 2009,
      evidence: 'citing work classified uses-tool/core; no repository located — paper-only row' }
  ];

  var TIER_LABELS = {
    own: ['Artifact & own repository', 'the paper\'s archival artifact first, then its implementation repository'],
    using: ['Repos using it', 'third-party repositories that import, embed, fork, or derive from the artifact'],
    descendant: ['Idea descendants', 'repositories of citing works classified extends or adopts-idea at high centrality']
  };
  /* Unified relationship taxonomy: same group names as the citations
     panel; the SDV integration term stays as a per-row chip. */
  var UNIFIED_GROUPS = [
    { label: 'Builds on it', types: ['derivative_work', 'fork'],
      gloss: 'derivative works and forks of the artifact' },
    { label: 'Uses the system', types: ['api_user', 'inherited'],
      gloss: 'repositories that import or depend on the artifact' },
    { label: 'Adopts the idea', types: ['descendant'],
      gloss: 'repositories of citing works that reimplement the idea without the code' }
  ];
  var SDV_CHIP = { derivative_work: 'derivative work', api_user: 'API user',
                   fork: 'fork', inherited: 'inherited' };

  function el(tag, cls, txt){
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (txt !== undefined && txt !== null) e.appendChild(document.createTextNode(String(txt)));
    return e;
  }
  function fmt(n){ return Number(n).toLocaleString('en-US'); }
  function starBucket(n){
    if (n == null) return 'stars unknown';
    if (n >= 1000) return '1,000+ stars';
    if (n >= 100) return '100–999 stars';
    if (n >= 10) return '10–99 stars';
    return 'under 10 stars';
  }

  function renderRepoRow(r){
    var li = el('li', 'cite-row' + (r.paperOnly ? ' repo-paper-only' : ''));
    var t = el('span', 'cite-row-title');
    if (r.name && r.url){
      var a = el('a', null, r.name); a.href = r.url; a.target = '_blank'; a.rel = 'noopener';
      t.appendChild(a);
    } else if (r.name){
      t.appendChild(document.createTextNode(r.name));
    } else {
      t.appendChild(document.createTextNode(r.paper));
    }
    li.appendChild(t);
    if (r.name && r.desc) li.appendChild(el('span', 'cite-row-meta', ' — ' + r.desc + '.'));
    if (r.name && r.paper) li.appendChild(el('span', 'cite-row-meta', ' — artifact of "' + r.paper.slice(0, 44) + '…"'));
    if (r.paperOnly) li.appendChild(el('span', 'cite-row-meta', ' — no repository located; shown for the tier\'s honesty.'));
    if (r.stars != null){
      var sc = el('span', 'cite-chip', fmt(r.stars) + ' ★');
      if (r.placeholder) sc.title = 'placeholder value';
      li.appendChild(sc);
    }
    if (r.year) li.appendChild(el('span', 'cite-chip', 'active ' + r.year));
    if (SDV_CHIP[r.integration]) li.appendChild(el('span', 'cite-chip', SDV_CHIP[r.integration]));
    if (r.artifact) li.appendChild(el('span', 'cite-chip', 'artifact'));
    if (r.placeholder === true) li.appendChild(el('span', 'cite-chip repo-placeholder-chip', 'PLACEHOLDER'));
    if (r.evidence) li.title = r.evidence;
    return li;
  }

  function renderGroup(title, gloss, rows, startOpen){
    var wrap = el('div', 'cite-group');
    var head = el('a', 'cite-group-head'); head.href = '#';
    var arrow = el('span', null, startOpen ? '▾ ' : '▸ ');
    head.appendChild(arrow);
    head.appendChild(el('span', 'cite-group-label', title));
    head.appendChild(el('span', 'cite-group-count', ' (' + fmt(rows.length) + ')'));
    if (gloss) head.title = gloss;
    wrap.appendChild(head);
    var body = el('div', 'cite-group-body');
    body.style.display = startOpen ? '' : 'none';
    var ul = el('ul', 'cite-rows');
    for (var i = 0; i < rows.length; i++) ul.appendChild(renderRepoRow(rows[i]));
    body.appendChild(ul);
    head.addEventListener('click', function(ev){
      ev.preventDefault();
      var open = body.style.display === 'none';
      body.style.display = open ? '' : 'none';
      arrow.textContent = open ? '▾ ' : '▸ ';
    });
    wrap.appendChild(body);
    return wrap;
  }

  function renderPanel(mount){
    mount.innerHTML = '';
    var head = el('div', 'cite-head');
    head.appendChild(el('span', 'cite-head-count', fmt(REPOS.length) + ' repositories'));
    mount.appendChild(head);

    /* tier bar, echoing the citations split bar */
    var counts = { own: 0, using: 0, descendant: 0 };
    REPOS.forEach(function(r){ counts[r.tier]++; });
    var bar = el('div', 'cite-splitbar');
    [['cite-seg-detailed', counts.own], ['cite-seg-passing', counts.using],
     ['cite-seg-unjudged', counts.descendant]].forEach(function(seg){
      if (!seg[1]) return;
      var s = el('div', 'cite-seg ' + seg[0]);
      s.style.width = (100 * seg[1] / REPOS.length).toFixed(2) + '%';
      bar.appendChild(s);
    });
    mount.appendChild(bar);
    var legend = el('div', 'cite-legend');
    [['cite-seg-detailed', 'Own', counts.own], ['cite-seg-passing', 'Builds on or uses it', counts.using],
     ['cite-seg-unjudged', 'Adopts the idea', counts.descendant]].forEach(function(l){
      if (!l[2]) return;
      var sp = el('span', 'cite-legend-item');
      sp.appendChild(el('span', 'cite-key ' + l[0], ''));
      sp.appendChild(document.createTextNode(l[1] + ' ' + fmt(l[2])));
      legend.appendChild(sp);
    });
    mount.appendChild(legend);

    /* sort row in the citation panel's language */
    var state = { sort: 'impact', expanded: false };
    var sortRow = el('div', 'cite-filter');
    sortRow.appendChild(el('span', 'cite-filter-label', 'Sort by '));
    var tg = el('span', 'type-toggle');
    var btns = [];
    var TIPS = { impact: 'Group by relationship depth: the artifact and own repo, then integration type, then idea descendants',
                 popularity: 'Most-starred first, grouped by magnitude — stars are the repo world\'s citation count',
                 recency: 'Most recently active first, grouped by year' };
    ['impact', 'recency', 'popularity'].forEach(function(v){
      var b = el('button', 'type-toggle-btn' + (v === state.sort ? ' active' : ''),
                 v.charAt(0).toUpperCase() + v.slice(1));
      b.type = 'button'; b.title = TIPS[v];
      b.addEventListener('click', function(){
        state.sort = v;
        btns.forEach(function(x){ x.el.className = 'type-toggle-btn' + (x.v === v ? ' active' : ''); });
        draw();
      });
      btns.push({ v: v, el: b });
      tg.appendChild(b);
    });
    sortRow.appendChild(tg);
    var expBtn = el('button', 'type-toggle-btn cite-hdr-toggle', 'Expand all');
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
        groupsMount.appendChild(renderGroup(TIER_LABELS.own[0], TIER_LABELS.own[1],
          REPOS.filter(function(r){ return r.tier === 'own'; }), state.expanded));
        UNIFIED_GROUPS.forEach(function(g){
          var rows = REPOS.filter(function(r){ return g.types.indexOf(r.integration) !== -1; });
          if (rows.length) groupsMount.appendChild(renderGroup(g.label, g.gloss, rows, state.expanded));
        });
      } else {
        var sorted = REPOS.slice();
        var headerOf;
        if (state.sort === 'popularity'){
          sorted.sort(function(a, b){ return ((b.stars != null ? b.stars : -1) - (a.stars != null ? a.stars : -1)); });
          headerOf = function(r){ return starBucket(r.stars); };
        } else {
          sorted.sort(function(a, b){ return (b.year || 0) - (a.year || 0); });
          headerOf = function(r){ return r.year ? String(r.year) : 'no activity data'; };
        }
        var order = [], byH = {};
        sorted.forEach(function(r){
          var h = headerOf(r);
          if (!byH[h]){ byH[h] = []; order.push(h); }
          byH[h].push(r);
        });
        order.forEach(function(h){ groupsMount.appendChild(renderGroup(h, null, byH[h], state.expanded)); });
      }
    }
    draw();
  }

  /* Specimen third register for the Summary (hand-written for the mock). */
  var SUMMARY_REPO_SENTENCE = 'The compiler and its benchmark suite live on ' +
    'in the bthies/streamit repository, and the suite circulates further ' +
    'through the community\'s refactorings and forks.';

  return { renderPanel: renderPanel, SUMMARY_REPO_SENTENCE: SUMMARY_REPO_SENTENCE, count: REPOS.length };
})();
