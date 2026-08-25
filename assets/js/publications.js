/* Publications page controller — ES5, dynamic counts, compact UI */
// Data source: data/publications.json; edit that file to add publications.
/* === BibTeX generation (local, ES5) === */
// --- Safe URL localizer shim (works even if pubs.js isn't loaded) ---
// var localizeURL = (window.PUBS && typeof PUBS.localizeAssetURL === 'function')
//   ? function(u){ try { return PUBS.localizeAssetURL(u); } catch (e) { return u || ''; } }
//     : function(u){ return u || ''; };

// Localize commit links to site-relative (papers/... presentations/...)
var localizeURL = (window.PUBS && typeof PUBS.localizeAssetURL === 'function')
  ? function(u){ try { return PUBS.localizeAssetURL(u||''); } catch(e){ return u||''; } }
  : function(u){
      u = u || '';
      // handle https://commit.csail.mit.edu/(papers|presentations)/...
      // and https://groups.csail.mit.edu/commit/(papers|presentations)/...
      var m = u.match(/^https?:\/\/[^/]+\/(?:commit\/)?(papers|presentations)\/(.+)$/i);
      if (m) return (m[1].toLowerCase() + '/' + m[2]);
      return u;
    };


function bibtexKeyOf(it){
  if (it.bibtexKey) return it.bibtexKey;
  var t = (it.title || 'untitled').toLowerCase().replace(/[^a-z0-9]+/g, '');
  return t.slice(0,24) + (it.year ? it.year : '');
}
function escBib(s){
  if (!s) return '';
  return String(s).replace(/[\n\r]+/g,' ').replace(/\s+/g,' ');
}
function firstDefined(){
  for (var i=0;i<arguments.length;i++){ var v=arguments[i]; if (v!==undefined && v!==null && v!=='') return v; }
  return '';
}
function venueOf(it){ return firstDefined(it.journal, it.booktitle, it.series, it.type, it.publisher); }
function locationOf(it){ return firstDefined(it.location, it.address); }
function titleOf(it){ return it.title || 'Untitled'; }

// Normalize item type for dedupe (fallback 'misc')
function normalizeType(t){
  return String(t || 'misc').replace(/\s+/g, ' ').trim().toLowerCase();
}

/* ===== Title & Author normalization ===== */

// Normalize title for dedup (case/space insensitive)
function normalizeTitle(s){
  return String(s || '').replace(/\s+/g, ' ').trim().toLowerCase();
}

// Turn "Last, First [Middle]" into "First [Middle] Last"
function normalizeAuthorName(name){
  var t = String(name || '').trim();
  if (!t) return '';
  // If there's a comma, treat as "Last, First…"
  var comma = t.indexOf(',');
  if (comma >= 0){
    var last  = t.slice(0, comma).trim();
    var first = t.slice(comma + 1).trim();
    if (first) return first + ' ' + last;
    return last;
  }
  return t; // already "First Last"
}

// Tokenize authors string safely.
// Prefer " and " separators (BibTeX); if none, pair up "Last, First" by commas.
function _tokenizeAuthors(raw){
  var s = String(raw || '').trim();
  if (!s) return [];

  // If it contains ' and ', split on that (common BibTeX style)
  if (/\band\b/i.test(s)){
    return s.split(/\s+\band\b\s+/i).map(function(x){ return x.trim(); }).filter(Boolean);
  }

  // Fallback: try to pair "Last, First, Last, First, ..." by commas
  var parts = s.split(/\s*,\s*/);
  var out = [], i;
  for (i = 0; i < parts.length; i += 2){
    if (i + 1 < parts.length) out.push(parts[i] + ', ' + parts[i+1]);
    else out.push(parts[i]); // odd tail, keep as-is
  }
  return out;
}

// Public: list of normalized author display names ("First Last")
function listNormalizedAuthorsFromString(s){
  var toks = _tokenizeAuthors(s);
  var out = [], i, n;
  for (i = 0; i < toks.length; i++){
    n = normalizeAuthorName(toks[i]);
    if (n) out.push(n);
  }
  return out;
}

// Convenience: from item
function listNormalizedAuthors(it){
  var a = firstDefined(it.author0, it.authors, it.author);
  return listNormalizedAuthorsFromString(a);
}

// First author (normalized)
function firstAuthorOf(it){
  var arr = listNormalizedAuthors(it);
  return arr.length ? arr[0] : '';
}

// First author's first name
function firstAuthorFirstName(it){
    var n = firstAuthorOf(it);
  if (!n) return '';
    var parts = n.split(/\s+/);
  return parts[0];
}

// First author's last name
function firstAuthorLastName(it){

    var n = firstAuthorOf(it);

  if (!n) return '';
    var parts = n.split(/\s+/);

  return parts[parts.length - 1];
}


// Human-friendly labels for itemType keys
var TYPE_LABELS = {
  inproceedings: 'Conference Pub',
  article: 'Journal Article',
  mastersthesis: 'M.Eng. Thesis',
  phdthesis: 'PhD Thesis',
  techreport: 'Tech Report',
  book: 'Book',
  incollection: 'Book Chapter',
    misc: 'Other',
    'sciencethesis': "SM Thesis",
    sbthesis: "SB Thesis",
};
function typeLabel(k){
  k = (k || 'misc').toLowerCase().trim();
  return TYPE_LABELS[k] || (k.charAt(0).toUpperCase() + k.slice(1));
}

var MONTH_ABBR = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

function monthNum(s){
  if(!s) return 0;
  var str = String(s).trim();
  if (!str) return 0;
  var digitMatch = str.match(/^(\d{1,2})$/);
  if (digitMatch) {
    var num = parseInt(digitMatch[1], 10);
    if (num >= 1 && num <= 12) return num;
  }
  var m = str.slice(0,3).toLowerCase();
  var map = {jan:1,feb:2,mar:3,apr:4,may:5,jun:6,jul:7,aug:8,sep:9,oct:10,nov:11,dec:12};
  return map[m] || 0;
}

function monthLabelFromParts(parts){
  if (!parts || !parts.month) return 'Other';
  var base = MONTH_ABBR[parts.month] || '';
  if (!base) return 'Other';
  if (parts.day) return base + ' ' + parts.day;
  return base;
}

function parseMonthDay(it){
  var month = 0;
  var day = 0;
  if (it && it.date) {
    var match = String(it.date).trim().match(/^(\d{4})(?:-(\d{1,2})(?:-(\d{1,2}))?)?/);
    if (match) {
      if (match[2]) {
        var parsedMonth = parseInt(match[2], 10);
        if (parsedMonth >= 1 && parsedMonth <= 12) month = parsedMonth;
      }
      if (match[3]) {
        var parsedDay = parseInt(match[3], 10);
        if (!isNaN(parsedDay)) day = Math.max(0, parsedDay);
      }
    }
  }
  if (!month && it && it.month) {
    month = monthNum(it.month);
  }
  if (!day && it && it.day) {
    var d = parseInt(it.day, 10);
    if (!isNaN(d)) day = Math.max(0, d);
  }
  return { month: month, day: day };
}

function monthDayValue(it){
  var parts = parseMonthDay(it);
  if (!parts.month) return 0;
  return (parts.month * 100) + Math.min(99, Math.max(0, parts.day || 0));
}

function monthLabelOf(it){
  if (!it) return 'Other';
  var parts = parseMonthDay(it);
  if (!parts.month) return 'Other';
  if (it.month && monthNum(it.month) === parts.month) {
    return String(it.month);
  }
  return monthLabelFromParts(parts);
}

  function splitKeywords(s){
    if(!s) return [];
    var parts = s.split(/[,;]+/), out=[], i, p;
    for(i=0;i<parts.length;i++){ p = parts[i].trim(); if(p) out.push(p); }
    return out;
  }

  // Facet tags for an item = its topics (array or comma string) plus its project.
  function tagsOf(it){
    var out = [], i, t;
    if (it && it.topics){
      if (Object.prototype.toString.call(it.topics) === '[object Array]'){
        for (i=0;i<it.topics.length;i++){ t = String(it.topics[i]).trim(); if(t) out.push(t); }
      } else {
        out = splitKeywords(it.topics);
      }
    }
    if (it && it.project){ var pr = String(it.project).trim(); if (pr && out.indexOf(pr) < 0) out.push(pr); }
    return out;
  }

  // Just the topics of an item (array or comma string).
  function topicsOf(it){
    var out = [], i, t;
    if (it && it.topics){
      if (Object.prototype.toString.call(it.topics) === '[object Array]'){
        for (i=0;i<it.topics.length;i++){ t = String(it.topics[i]).trim(); if(t) out.push(t); }
      } else {
        out = splitKeywords(it.topics);
      }
    }
    return out;
  }

  // Just the project of an item, as a one-element list (or empty).
  function projectsOf(it){
    if (it && it.project){ var pr = String(it.project).trim(); if (pr) return [pr]; }
    return [];
  }


// Key extractors (for sorting within groups)
function keyFor(it, which){
  if (which==='year')     return it.year ? parseInt(it.year,10) : 0; // numeric
  if (which==='citations') return citeCountOf(it);                   // numeric, -1 = no data
  if (which==='month')    return monthDayValue(it);
  if (which==='type')     return typeLabel(it.itemType || 'misc');   // pretty label
  if (which==='authors')  { var a = listNormalizedAuthors(it); return a.length?a[0]:'zzz'; } // first author
  if (which==='authorFirst') { var f = firstAuthorFirstName(it); return f ? f : 'zzz'; }
  if (which==='authorLast')  { var l = firstAuthorLastName(it); return l ? l : 'zzz'; }
  if (which==='keywords') {
    var ks = tagsOf(it);
    if (ks.length) { ks.sort(function(a,b){ return a.localeCompare(b); }); return ks[0]; }
    return 'zzz';
  }
  return '';
}


function venueOf(it){ return firstDefined(it.journal, it.booktitle, it.series, it.type, it.publisher); }

function cmp(a, b) { return a < b ? -1 : a > b ? 1 : 0; }
function makeSorter(key){
  // returns a function(a,b) for within-year sorting
  if (key === 'title')       return function(a,b){ return cmp((a.title||'').toLowerCase(), (b.title||'').toLowerCase()); };
  if (key === 'venue')       return function(a,b){ return cmp((venueOf(a)||'').toLowerCase(), (venueOf(b)||'').toLowerCase()); };
  if (key === 'firstAuthor') return function(a,b){ return cmp((firstAuthorOf(a)||'').toLowerCase(), (firstAuthorOf(b)||'').toLowerCase()); };
  if (key === 'type')        return function(a,b){ return cmp((a.itemType||'misc').toLowerCase(), (b.itemType||'misc').toLowerCase()); };
  if (key === 'month')       return function(a,b){ return cmp(monthDayValue(b), monthDayValue(a)); };
  return null; // default order (as in data) within year
}



function buildBibtex(it, localizeURLFn){
  if (it.oldbibtex && /^\s*@/m.test(String(it.oldbibtex))) {
    return String(it.oldbibtex);
  }
  var typ = it.itemType || 'misc';
  var key = bibtexKeyOf(it);
  var out = [];
  out.push('@' + typ + '{' + key + ',');

  function pushLine(k, v){ if (v) out.push('  ' + k + ' = {' + v + '},'); }

  var url = localizeURLFn ? localizeURLFn(it.url || '') : (it.url || '');
  var slides = localizeURLFn ? localizeURLFn(it.slides || '') : (it.slides || '');

  pushLine('author',    escBib(firstDefined(it.author0, it.authors, it.author)));
  pushLine('title',     '{' + escBib(titleOf(it)) + '}');
  pushLine('booktitle', escBib(it.booktitle || ''));
  pushLine('journal',   escBib(it.journal || ''));
  pushLine('series',    escBib(it.series || ''));
  pushLine('publisher', escBib(it.publisher || ''));
  pushLine('school',    escBib(it.school || ''));
  pushLine('address',   escBib(locationOf(it)));
  pushLine('location',  escBib(locationOf(it)));
  pushLine('month',     escBib(it.month || ''));
  pushLine('year',      escBib(it.year || ''));
  pushLine('volume',    escBib(it.volume || ''));
  pushLine('number',    escBib(it.issue || it.number || ''));
  pushLine('pages',     escBib(it.pages || ''));
  pushLine('doi',       escBib(it.doi || ''));
  pushLine('keywords',  escBib(tagsOf(it).join(', ')));
  pushLine('url',       escBib(url));
  if (slides) pushLine('note', 'Slides: ' + slides);

  // drop trailing comma
  if (out.length > 1) out[out.length-1] = out[out.length-1].replace(/,+\s*$/, '');
  out.push('}');
  return out.join('\n');
}

function createBibLink(it){
  var a = document.createElement('a');
  a.className = 'pub-action';
  a.textContent = 'BibTeX';
  var bib = buildBibtex(it, localizeURL);
  var blob = new Blob([bib], {type:'text/plain'});
  a.href = URL.createObjectURL(blob);
  a.download = bibtexKeyOf(it) + '.bib';
  a.addEventListener('click', function(){
    var href = a.href;
    setTimeout(function(){ URL.revokeObjectURL(href); }, 1500);
  });
  return a;
}


(function () {
  'use strict';

  var JSON_PATH = 'data/publications.json';

  // Per-paper citation view (assets/js/citations.js, data/citations/).
  // The index is one small fetch; per-paper data loads only on expand.
  // If citations.js or the index is absent, CITE_INDEX stays null and the
  // page renders exactly as before.
  var CITE_INDEX = null;
  var citeIndexReady = (window.CITATIONS
    ? CITATIONS.loadIndex().then(function(idx){
        CITE_INDEX = (idx && idx.papers) || null;
      })
    : Promise.resolve()
  ).catch(function(){ CITE_INDEX = null; });

  // The paper's displayed citation count — max(verified, Google Scholar) —
  // for the list-level "Citations" sort; -1 when the paper has no data,
  // which sorts it after every counted paper.
  window.citeCountOf = function(it){
    var row = CITE_INDEX && CITE_INDEX[bibtexKeyOf(it)];
    if (!row) return -1;
    return CITATIONS.displayCount(row); // same figure as the per-paper headline
  };

  var state = {
    mode: 'interactive',     // 'noninteractive' | 'interactive'
    years: {},                  // map of selected year -> true
    titleQuery: '',
    keywords: {},               // map of selected keyword -> true
    authors: {},                // map of selected author -> true
    types: {},                  // map of selected itemType -> true
    scroll: {                   // range-controlled scroll positions (0..1)
      keywords: 0,
      authors: 0,
      types: 0
    },
      sortKey: 'none',   // 'none' | 'title' | 'venue' | 'firstAuthor' | 'type' | 'month'
      sortDesc: false,
      sortOrder: ['year','month','type','authorLast'],  // default
      authorSort: 'count',
      kwMode: 'topics',           // 'topics' | 'projects' — Topics & Projects facet mode
      authorQuery: '',            // free-text filter for the authors list
      typeMode: 'type',           // 'type' | 'venue' — how the third facet categorizes
      venueSort: 'name',          // 'name' | 'count' — venue ordering in venue mode
      summaryExpanded: false,     // global default for per-paper summaries
      citationsExpanded: false,   // global default for per-paper citation panels
      minCites: 0,                // paper threshold: displayed citation count
      minImpact: 0                // paper threshold: weighted impact score

  };
  var els = {
    errors: document.getElementById('pubs-errors'),
    results: document.getElementById('pubs-results'),
    count: document.getElementById('pubs-count'),
    filtersInteractive: document.getElementById('filters-interactive'),
    btnClear: document.getElementById('btn-clear'),
    btnToggleSummaries: document.getElementById('btn-toggle-summaries'),
    btnToggleCitations: document.getElementById('btn-toggle-citations'),
    years: document.getElementById('facet-years'),
    title: document.getElementById('facet-title'),
    kwBox: document.getElementById('facet-keywords'),
    kwToggle: document.getElementById('kw-toggle'),
    auBox: document.getElementById('facet-authors'),
      tyBox: document.getElementById('facet-types'),
      authorSort: document.getElementById('author-sort'),
      authorSearch: document.getElementById('author-search'),
      typeToggle: document.getElementById('type-toggle'),
      // els:
      sort1: document.getElementById('sort-1'),
      sort2: document.getElementById('sort-2'),
      sort3: document.getElementById('sort-3'),
      sort4: document.getElementById('sort-4'),
      sortReset: document.getElementById('sort-reset'),
      citeOverview: document.getElementById('cite-overview'),
      citeSort: document.getElementById('cite-global-sort'),
      citeCentrality: document.getElementById('cite-global-centrality'),
      citeSearch: document.getElementById('cite-search'),
      citeCats: document.getElementById('facet-cite-cats'),
      minCites: document.getElementById('cite-min-cites'),
      minCitesLabel: document.getElementById('cite-min-cites-label'),
      minImpact: document.getElementById('cite-min-impact'),
      minImpactLabel: document.getElementById('cite-min-impact-label'),

  };

  var DATA = [];  // raw array
  var ALL_AUTHORS = [];  // unique normalized author names
  var AUTHOR_PUB_COUNTS = {};  // normalized author name -> total publication count
  var AUTHOR_LATEST_YEAR = {};  // normalized author name -> most recent publication year

  /* ---------- Small helpers ---------- */
  function text(s){ return document.createTextNode(s || ''); }
  function firstDefined(){ for(var i=0;i<arguments.length;i++){ var v=arguments[i]; if(v!==undefined&&v!==null&&v!=='') return v; } return ''; }
  function authorsOf(it){ return firstDefined(it.author0, it.authors, it.author); }
  function titleOf(it){ return it.title || 'Untitled'; }
  function venueOf(it){ return firstDefined(it.journal, it.booktitle, it.series, it.type, it.publisher); }
  function locationOf(it){ return firstDefined(it.location, it.address); }
  function splitAuthors(s){
    if(!s) return [];
    var parts = s.split(/\s+and\s+|,/i), out=[], i, p;
    for(i=0;i<parts.length;i++){ p = parts[i].trim(); if(p) out.push(p); }
    return out;
  }
  function splitKeywords(s){
    if(!s) return [];
    var parts = s.split(/[,;]+/), out=[], i, p;
    for(i=0;i<parts.length;i++){ p = parts[i].trim(); if(p) out.push(p); }
    return out;
  }

  // If pubs.js is loaded, reuse its localizer and bib link; else graceful fallback
    //  var localizeURL = (window.PUBS && PUBS.localizeAssetURL) ? function(u){ try{return PUBS.localizeAssetURL(u);}catch(_){return u;} } : function(u){ return u; };
  var makeBibLink = (window.PUBS && PUBS.makeBibDownloadLink) ? PUBS.makeBibDownloadLink : function(){ var a=document.createElement('span'); return a; };

  /* ---------- Build static UI shells (kept; content dynamic) ---------- */

  // Year grid entries and their count badges
  var yearBtnMap = {}; // year -> {btn, badgeNode}

  function buildYearGrid(yearValuesSortedDesc) {
    els.years.innerHTML = '';
    yearBtnMap = {};
    for (var i=0;i<yearValuesSortedDesc.length;i++){
      var y = String(yearValuesSortedDesc[i]);
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'year-btn';
      btn.setAttribute('data-year', y);
      btn.appendChild(text(y));
      // space + badge
      btn.appendChild(text(' '));
      var badge = document.createElement('span');
      badge.className = 'year-badge';
      badge.appendChild(text('0'));
      btn.appendChild(badge);

      btn.onclick = (function(yy){
        return function(){
          state.years[yy] = !state.years[yy];
          applyFilters();
          if (state.years[yy]) track('filter', { facet: 'year', value: String(yy) });
        };
      })(y);

      yearBtnMap[y] = { btn: btn, badge: badge.firstChild };
      els.years.appendChild(btn);
    }
  }

function buildFacetBox(list, mount, facetKey, stateMap, labelFor) {
  mount.innerHTML = '';

  var scrollWrap = document.createElement('div');   // the element that scrolls
  scrollWrap.className = 'facet-scroll';

  var listEl = document.createElement('div');       // tall inner list
  listEl.className = 'facet-items';
  scrollWrap.appendChild(listEl);

  // Build checkboxes
  var itemMap = {}; // value -> { cb, textNode }
  for (var i = 0; i < list.length; i++) {
    var value = list[i];                 // canonical filter value (e.g., itemType key)
    var labelText = labelFor ? labelFor(value) : value;  // pretty label

    var label = document.createElement('label');
    label.className = 'facet-item';

    var cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.value = value;

    var txt = document.createElement('span');
    txt.className = 'facet-text';
    var textNodeValue = document.createTextNode(labelText + ' (0)');
    txt.appendChild(textNodeValue);
    txt.title = labelText; // show full label on hover (handles truncation)

    cb.onchange = (function (val, map, fk) {
      return function () {
        map[val] = !!this.checked;
        applyFilters();
        if (this.checked) track('filter', { facet: fk, value: val });
      };
    })(value, stateMap, facetKey);

    label.appendChild(cb);
    label.appendChild(txt);
    listEl.appendChild(label);

    itemMap[value] = { cb: cb, textNode: textNodeValue, labelText: labelText };
  }

  mount.appendChild(scrollWrap);

  // Stash references for dynamic count updates
  mount._facet = { listEl: listEl, itemMap: itemMap, scrollWrap: scrollWrap, key: facetKey, labelFor: labelFor || null };
}


  function authorNameParts(name) {
    var parts = String(name || '').trim().split(/\s+/).filter(Boolean);
    if (!parts.length) {
      return { first: '', last: '' };
    }
    return {
      first: parts[0].toLowerCase(),
      last: parts[parts.length - 1].toLowerCase()
    };
  }

  function compareAuthors(a, b, mode) {
    if (mode === 'count') {
      var countA = AUTHOR_PUB_COUNTS[a] || 0;
      var countB = AUTHOR_PUB_COUNTS[b] || 0;
      if (countA !== countB) return countB - countA;  // high to low
      // tie-break by last name, then full name, for stable ordering
      return compareAuthors(a, b, 'last');
    }
    if (mode === 'recent') {
      var yearA = AUTHOR_LATEST_YEAR[a] || 0;
      var yearB = AUTHOR_LATEST_YEAR[b] || 0;
      if (yearA !== yearB) return yearB - yearA;  // newest first
      // tie-break by publication count (high to low), then last name
      return compareAuthors(a, b, 'count');
    }

    var ap = authorNameParts(a);
    var bp = authorNameParts(b);
    var primaryA = (mode === 'last') ? ap.last : ap.first;
    var primaryB = (mode === 'last') ? bp.last : bp.first;
    var cmpPrimary = primaryA.localeCompare(primaryB);
    if (cmpPrimary !== 0) return cmpPrimary;

    var fullA = String(a || '').toLowerCase();
    var fullB = String(b || '').toLowerCase();
    var cmpFull = fullA.localeCompare(fullB);
    if (cmpFull !== 0) return cmpFull;
    return 0;
  }

  function sortAuthorValues(values, mode) {
    var arr = values.slice();
    arr.sort(function (a, b) { return compareAuthors(a, b, mode); });
    return arr;
  }

  function rebuildAuthorFacet() {
    if (!els.auBox) return;
    var prevScroll = 0;
    if (els.auBox._facet && els.auBox._facet.scrollWrap) {
      prevScroll = els.auBox._facet.scrollWrap.scrollTop;
    }
    var sorted = sortAuthorValues(ALL_AUTHORS, state.authorSort || 'first');
    var q = (state.authorQuery || '').trim().toLowerCase();
    if (q) {
      sorted = sorted.filter(function (name) {
        return String(name || '').toLowerCase().indexOf(q) !== -1;
      });
    }
    buildFacetBox(sorted, els.auBox, 'authors', state.authors);
    if (els.auBox._facet && els.auBox._facet.scrollWrap) {
      els.auBox._facet.scrollWrap.scrollTop = prevScroll;
    }
  }


  /* ---------- Type / Venue categorization (third facet) ---------- */
  var THESIS_TYPES = { mastersthesis:1, phdthesis:1, sciencethesis:1, sbthesis:1 };

  // Full journal/venue names (lowercased) -> shorthand, for entries lacking a "(ABBR)".
  var VENUE_SHORT_MAP = {
    'acm transactions on graphics': 'TOG',
    'communications of the acm': 'CACM',
    'acm transactions on programming languages and systems': 'TOPLAS',
    'acm transactions on architecture and code optimization': 'TACO',
    'acm transactions on computer systems': 'TOCS',
    'ieee micro': 'IEEE Micro',
    'ieee computer': 'IEEE Computer',
    'ieee transactions on computers': 'IEEE TC',
    'international journal of parallel programming': 'IJPP',
    'journal of instruction-level parallelism': 'JILP'
  };

  function venueRawOf(it){ return firstDefined(it.booktitle, it.journal, it.series); }

  // Best-effort shorthand for a paper's venue; '' when none can be derived.
  function venueShortOf(it){
    if (it.venueShort) return String(it.venueShort).trim();
    var raw = String(venueRawOf(it) || '');
    var m = raw.match(/\(([^()]{1,20})\)\s*$/);   // trailing "(ABBR)"
    if (m) {
      var abbr = m[1].trim();
      if (abbr && /[A-Za-z]/.test(abbr) && !/^\d/.test(abbr)) return abbr;
    }
    var key = raw.toLowerCase().trim();
    if (VENUE_SHORT_MAP[key]) return VENUE_SHORT_MAP[key];
    return '';
  }

  // Canonical category key for the current mode (used by facet values, filtering and counts).
  function categoryKeyOf(it){
    var t = (it.itemType || 'misc').toLowerCase().trim();
    if (state.typeMode !== 'venue') return 'type:' + t;
    // Venue mode: theses and tech reports stay grouped by type.
    if (THESIS_TYPES[t] || t === 'techreport') return 'type:' + t;
    // Conference / journal papers group by shorthand venue when one is derivable.
    if (t === 'inproceedings' || t === 'article') {
      var vs = venueShortOf(it);
      if (vs) return 'venue:' + vs;
    }
    return 'venue:__other__';   // anything without a good venue name
  }

  function categoryLabelOf(key){
    if (key === 'venue:__other__') return 'Other';
    if (key.indexOf('type:') === 0)  return typeLabel(key.slice(5));
    if (key.indexOf('venue:') === 0) return key.slice(6);
    return key;
  }

  // Ordering bucket: theses / tech reports first (0), venues (1), "Other" last (2).
  function categoryBucket(key){
    if (key === 'venue:__other__') return 2;
    return (key.indexOf('type:') === 0) ? 0 : 1;
  }

  function rebuildTypeFacet(){
    if (!els.tyBox) return;
    var counts = {}, i, key;
    for (i = 0; i < DATA.length; i++){ key = categoryKeyOf(DATA[i]); counts[key] = (counts[key] || 0) + 1; }
    var byCount = (state.typeMode === 'venue' && state.venueSort === 'count');
    var vals = Object.keys(counts).sort(function(a, b){
      var ba = categoryBucket(a), bb = categoryBucket(b);
      if (ba !== bb) return ba - bb;
      if (byCount && ba === 1 && counts[a] !== counts[b]) return counts[b] - counts[a];  // venues by # pubs desc
      return categoryLabelOf(a).toLowerCase().localeCompare(categoryLabelOf(b).toLowerCase());
    });
    buildFacetBox(vals, els.tyBox, 'types', state.types, categoryLabelOf);
  }


  /* ---------- Rendering one publication (same look as index) ---------- */
  // Summary text is trusted local JSON containing embedded <a> links.
  function renderSummaryInto(container, summaryText){
    var paras = String(summaryText).split(/\n\n+/), i, p;
    container.innerHTML = '';
    for (i = 0; i < paras.length; i++){
      p = document.createElement('p');
      p.innerHTML = paras[i];
      container.appendChild(p);
    }
    var links = container.getElementsByTagName('a'), j;
    for (j = 0; j < links.length; j++){ links[j].target = '_blank'; links[j].rel = 'noopener'; }
  }

  function renderItem(it){
    var li = document.createElement('li');
    li.className = 'pub-item';

    var localPDF = localizeURL(it.url || '');

    var t = document.createElement('div');
    t.className = 'pub-title';
    if (localPDF) {
      var a = document.createElement('a');
      a.href = localPDF; a.target = '_blank'; a.rel = 'noopener';
      a.appendChild(text(titleOf(it)));
      a.addEventListener('click', function(){ track('paper-view', { key: bibtexKeyOf(it), title: titleOf(it), year: it.year }); });
      t.appendChild(a);
    } else {
      t.appendChild(text(titleOf(it)));
    }
    t.appendChild(text('.'));
    li.appendChild(t);

    var auth = authorsOf(it);
    if (auth){ var al = document.createElement('div'); al.className = 'pub-authors'; al.appendChild(text(auth + '.')); li.appendChild(al); }

    var ven = venueOf(it);
    if (ven){ var vl = document.createElement('div'); vl.className = 'pub-venue'; vl.appendChild(text(ven + '.')); li.appendChild(vl); }

    var meta = document.createElement('div'); meta.className = 'pub-meta';
    var loc = locationOf(it), bits=[];
    if (loc) bits.push(loc + '.');
    if (it.month) bits.push(String(it.month) + ',');
    if (it.year)  bits.push(String(it.year) + '.');
    if (bits.length) meta.appendChild(text(bits.join(' ') + ' '));
    // Bib + Slides
      meta.appendChild(makeBibLink(it));
      var bibA = createBibLink(it);
      bibA.addEventListener('click', function(){ track('bib-download', { key: bibtexKeyOf(it) }); });
      meta.appendChild(bibA);

    var slides = localizeURL(it.slides || '');
    if (slides) { meta.appendChild(text(' ')); var sA=document.createElement('a'); sA.href=slides; sA.target='_blank'; sA.rel='noopener'; sA.className='pub-action'; sA.appendChild(text('Slides')); sA.addEventListener('click', function(){ track('slides-view', { key: bibtexKeyOf(it), title: titleOf(it) }); }); meta.appendChild(sA); }

    // Artifact or source repository, when the paper points to one.
    var code = localizeURL(it.code || '');
    if (code) { meta.appendChild(text(' ')); var cA=document.createElement('a'); cA.href=code; cA.target='_blank'; cA.rel='noopener'; cA.className='pub-action'; cA.appendChild(text('Code')); cA.addEventListener('click', function(){ track('code-view', { key: bibtexKeyOf(it), title: titleOf(it) }); }); meta.appendChild(cA); }

    // Summary toggle (shown only when a summary exists); follows global default.
    var sumDiv = null;
    if (it.summary){
      sumDiv = document.createElement('div');
      sumDiv.className = 'pub-summary' + (state.summaryExpanded ? ' open' : '');
      renderSummaryInto(sumDiv, it.summary);

      var sumToggle = document.createElement('a');
      sumToggle.href = '#';
      sumToggle.className = 'pub-action pub-summary-toggle';
      var setArrow = function(open){ sumToggle.textContent = open ? 'Summary \u25be' : 'Summary \u25b8'; };
      setArrow(state.summaryExpanded);
      (function(item, div, toggle, arrow){
        toggle.addEventListener('click', function(ev){
          ev.preventDefault();
          var willOpen = div.className.indexOf('open') === -1;
          div.className = 'pub-summary' + (willOpen ? ' open' : '');
          arrow(willOpen);
          if (willOpen) track('summary-view', { key: bibtexKeyOf(item), title: titleOf(item) });
        });
      })(it, sumDiv, sumToggle, setArrow);
      meta.appendChild(text(' '));
      meta.appendChild(sumToggle);
    }

    li.appendChild(meta);

    // Citation view toggle (only for papers with a data/citations/ row).
    if (window.CITATIONS && CITE_INDEX){
      var citeRow = CITE_INDEX[bibtexKeyOf(it)];
      if (citeRow) CITATIONS.attachToggle(meta, li, bibtexKeyOf(it), citeRow);
    }

    if (it.price){ var pr=document.createElement('div'); pr.className='pub-price'; pr.appendChild(text(it.price)); li.appendChild(pr); }

    if (sumDiv) li.appendChild(sumDiv);

    return li;
  }


function renderList(mount, items){
  var order = state.sortOrder.slice();                  // e.g. ['none','authors','none','year']
  var active = order.filter(function(k){ return k !== 'none'; });

  // Case 1: no primary (order[0] === 'none') → flat list
  if (!active.length || order[0] === 'none') {
    var flat = items.slice();

    // Apply remaining sort keys (skip initial 'none')
    for (var r = order.length - 1; r >= 0; r--){
      (function(which){
        if (which === 'none') return;
        flat.sort(function(a,b){
          if (which==='year') return (keyFor(b,'year') - keyFor(a,'year')); // year desc
          if (which==='month') return (keyFor(b,'month') - keyFor(a,'month'));
          if (which==='citations') return (keyFor(b,'citations') - keyFor(a,'citations')); // count desc, no-data last
          return cmp(String(keyFor(a,which)).toLowerCase(), String(keyFor(b,which)).toLowerCase());
        });
      })(order[r]);
    }

    var ul = document.createElement('ul'); ul.className = 'pub-list';
    for (var i=0;i<flat.length;i++) ul.appendChild(renderItem(flat[i]));
    mount.innerHTML = '';
    mount.appendChild(ul);
    return;
  }

  // Case 2: group by the first active key
  var primary = active[0];
  var rest = [];
  // take the remaining keys in their original positions, skipping 'none' and the primary
  for (var i=0;i<order.length;i++){
    var k = order[i];
    if (k !== 'none' && k !== primary) rest.push(k);
  }

  var groups = {}; // label -> items
  var groupSortValue = {}; // label -> numeric sort helper
  function add(label, it, sortVal){
    if (!groups[label]) groups[label]=[];
    groups[label].push(it);
    if (sortVal !== undefined) {
      var current = groupSortValue[label];
      if (current === undefined || sortVal > current) groupSortValue[label] = sortVal;
    }
  }

  for (var i2=0;i2<items.length;i2++){
    var it = items[i2];
    if (primary==='year'){
      add(it.year ? String(it.year) : 'Other', it);
    } else if (primary==='month'){
      var label = monthLabelOf(it);
      var sortVal = (label === 'Other') ? 0 : monthDayValue(it);
      add(label, it, sortVal);
    } else if (primary==='type'){
      add(typeLabel(it.itemType || 'misc'), it);
    } else if (primary==='authors'){
      var as = listNormalizedAuthors(it); if (as.length){ for (var a=0;a<as.length;a++) add(as[a], it); } else add('Other', it);
    } else if (primary==='authorFirst'){
      var fn = firstAuthorFirstName(it); add(fn || 'Other', it);
    } else if (primary==='authorLast'){
      var ln = firstAuthorLastName(it); add(ln || 'Other', it);
    } else if (primary==='keywords'){
      var ks = tagsOf(it); if (ks.length){ for (var k2=0;k2<ks.length;k2++) add(ks[k2], it); } else add('Other', it);
    } else if (primary==='citations'){
      // Bucket scheme shared with the per-paper popularity sort.
      var n = keyFor(it, 'citations');
      var bucket = (n < 0)
        ? 'No citation data'
        : (window.CITATIONS ? CITATIONS.countBucket(n) : String(n));
      add(bucket, it, n); // groupSortValue = max count in bucket → rank order
    }
  }

  var headers = Object.keys(groups);
  headers.sort(function(A,B){
    if (primary==='year'){
      if (A==='Other' && B!=='Other') return 1;
      if (B==='Other' && A!=='Other') return -1;
      return (parseInt(B,10)||0) - (parseInt(A,10)||0); // desc
    }
    if (primary==='month'){
      if (A==='Other' && B!=='Other') return 1;
      if (B==='Other' && A!=='Other') return -1;
      var aVal = groupSortValue[A] || 0;
      var bVal = groupSortValue[B] || 0;
      if (aVal !== bVal) return bVal - aVal;
      return A.toLowerCase().localeCompare(B.toLowerCase());
    }
    if (primary==='citations'){
      // Buckets in count order, highest first; "No citation data" last
      // (its groupSortValue is -1, below every real count).
      var aC = groupSortValue[A]; if (aC === undefined) aC = -1;
      var bC = groupSortValue[B]; if (bC === undefined) bC = -1;
      return bC - aC;
    }
    return A.toLowerCase().localeCompare(B.toLowerCase());
  });

  var container = document.createElement('div');
  for (var h=0; h<headers.length; h++){
    var label = headers[h];
    var arr = groups[label].slice();

    // multi-key within group
    for (var r2 = rest.length - 1; r2 >= 0; r2--){
      (function(which){
        arr.sort(function(a,b){
          if (which==='year') return (keyFor(b,'year') - keyFor(a,'year'));
          if (which==='month') return (keyFor(b,'month') - keyFor(a,'month'));
          if (which==='citations') return (keyFor(b,'citations') - keyFor(a,'citations'));
          return cmp(String(keyFor(a,which)).toLowerCase(), String(keyFor(b,which)).toLowerCase());
        });
      })(rest[r2]);
    }
    // Inside a citation bucket the list is ranked by count (stable sort:
    // the remaining keys above become tiebreakers).
    if (primary==='citations'){
      arr.sort(function(a,b){ return keyFor(b,'citations') - keyFor(a,'citations'); });
    }

    var sec = document.createElement('div');
    var h3 = document.createElement('h3'); h3.textContent = label;
    sec.appendChild(h3);
    var ul = document.createElement('ul'); ul.className = 'pub-list';
    for (var j=0;j<arr.length;j++) ul.appendChild(renderItem(arr[j]));
    sec.appendChild(ul);
    container.appendChild(sec);
  }

  mount.innerHTML = '';
  mount.appendChild(container);
}


  /* ---------- Topics & Projects facet ---------- */
  function kwValuesOf(it){
    return (state.kwMode === 'projects') ? projectsOf(it) : topicsOf(it);
  }

  function rebuildKeywordFacet(){
    if (!els.kwBox) return;
    var prev = (els.kwBox._facet && els.kwBox._facet.scrollWrap) ? els.kwBox._facet.scrollWrap.scrollTop : 0;
    var set = {}, i, j;
    for (i=0;i<DATA.length;i++){ var vs = kwValuesOf(DATA[i]); for (j=0;j<vs.length;j++) set[vs[j]] = 1; }
    var vals = Object.keys(set).sort(function(a,b){ return a.localeCompare(b); });
    buildFacetBox(vals, els.kwBox, 'keywords', state.keywords);
    if (els.kwBox._facet && els.kwBox._facet.scrollWrap) els.kwBox._facet.scrollWrap.scrollTop = prev;
  }

  /* ---------- Filtering & Dynamic counts ---------- */

  // Returns items filtered by current state, optionally excluding one facet ("years"|"keywords"|"authors"|"types")
  function filteredItems(excludeFacet){
    var items = DATA.slice();

    // Title
    var q = state.titleQuery.replace(/\s+/g,' ').trim().toLowerCase();
    if (q) {
      items = items.filter(function(it){
        return (it.title||'').toLowerCase().indexOf(q) >= 0;
      });
    }

    // Years
    if (excludeFacet !== 'years') {
      var yKeys = keysSelected(state.years);
      if (yKeys.length){
        items = items.filter(function(it){ return it.year && yKeys.indexOf(String(it.year)) >= 0; });
      }
    }

    // Keywords
    if (excludeFacet !== 'keywords') {
      var kwKeys = keysSelected(state.keywords);
      if (kwKeys.length){
        items = items.filter(function(it){
          var kws = tagsOf(it);
          for (var i=0;i<kws.length;i++) if (kwKeys.indexOf(kws[i]) >= 0) return true;
          return false;
        });
      }
    }

    // Authors
    if (excludeFacet !== 'authors') {
// Authors (OR within facet)
var auKeys = keysSelected(state.authors);
if (auKeys.length){
  items = items.filter(function (it) {
    var as = listNormalizedAuthors(it);   // <-- normalized
    for (var i = 0; i < as.length; i++) if (auKeys.indexOf(as[i]) >= 0) return true;
    return false;
  });
}

    }

    // Types
    if (excludeFacet !== 'types') {
      var tyKeys = keysSelected(state.types);
      if (tyKeys.length){
        items = items.filter(function(it){
          return tyKeys.indexOf(categoryKeyOf(it)) >= 0;
        });
      }
    }

    // Citation thresholds (page-level sliders); papers without data are
    // hidden once a threshold is above zero.
    if (state.minCites > 0){
      items = items.filter(function(it){ return citeCountOf(it) >= state.minCites; });
    }
    if (state.minImpact > 0 && window.CITATIONS){
      items = items.filter(function(it){
        var row = CITE_INDEX && CITE_INDEX[bibtexKeyOf(it)];
        var imp = row ? CITATIONS.impactScore(row) : null;
        return imp != null && imp >= state.minImpact;
      });
    }

    return items;
  }

  function keysSelected(map){
    var out=[], k;
    for (k in map) if (map[k]) out.push(k);
    return out;
  }

  function updateDynamicCounts(){
    // Years (exclude its own selections)
    var itemsY = filteredItems('years'), yCounts = {}, i;
    for (i=0;i<itemsY.length;i++){
      var y = itemsY[i].year ? String(itemsY[i].year) : '';
      if (y) yCounts[y] = (yCounts[y]||0) + 1;
    }
    updateFacetCounts(els.years, 'years', yCounts, state.years);

    // Keywords
    var itemsK = filteredItems('keywords'), kCounts = {}, j;
    for (i=0;i<itemsK.length;i++){
      var kws = kwValuesOf(itemsK[i]);
      for (j=0;j<kws.length;j++) kCounts[kws[j]] = (kCounts[kws[j]]||0) + 1;
    }
    updateFacetCounts(els.kwBox, 'keywords', kCounts, state.keywords);

    // Authors
// Authors dynamic counts
var itemsA = filteredItems('authors'), aCounts = {};
for (i = 0; i < itemsA.length; i++){
  var as = listNormalizedAuthors(itemsA[i]);  // <-- normalized
  for (j = 0; j < as.length; j++) aCounts[as[j]] = (aCounts[as[j]] || 0) + 1;
}
updateFacetCounts(els.auBox, 'authors', aCounts, state.authors);


    // Types
var itemsT = filteredItems('types'), tCounts = {};
for (i = 0; i < itemsT.length; i++){
  var ck = categoryKeyOf(itemsT[i]);
  tCounts[ck] = (tCounts[ck] || 0) + 1;
}
updateFacetCounts(els.tyBox, 'types', tCounts, state.types);

  }

  function updateFacetCounts(mount, facetKey, countsMap, stateMap) {
    var facet = mount._facet;
    if (!facet) return;

    var itemMap = facet.itemMap;
  for (var val in itemMap) {
    var cnt = countsMap[val] || 0;
    var display = facet.labelFor ? facet.labelFor(val) : val;
    itemMap[val].textNode.nodeValue = display + ' (' + cnt + ')';

    var disabled = (cnt === 0) && !stateMap[val];
    itemMap[val].cb.disabled = disabled;
    itemMap[val].cb.parentNode.className = disabled ? 'facet-item disabled' : 'facet-item';
    itemMap[val].cb.checked = !!stateMap[val];
  }
}

  function updatePublicationCount(count){
    if (!els.count) return;
    var label = String(count || 0);
    els.count.textContent = '(' + label + ')';
  }

  updatePublicationCount(0);

  // Aggregate citation overview over the papers currently shown, plus the
  // cross-paper-citers finder. Hidden when the citations index is absent.
  function renderCiteOverview(items){
    var box = els.citeOverview;
    if (!box) return;
    if (!CITE_INDEX || !window.CITATIONS){ box.className = 'cite-overview hidden'; return; }
    var withData = [], totalC = 0, i;
    for (i = 0; i < items.length; i++){
      var row = CITE_INDEX[bibtexKeyOf(items[i])];
      if (!row) continue;
      withData.push({ key: bibtexKeyOf(items[i]), title: items[i].title || '' });
      totalC += CITATIONS.displayCount(row);
    }
    box.innerHTML = '';
    if (!withData.length){ box.className = 'cite-overview hidden'; return; }
    box.className = 'cite-overview';
    var l1 = document.createElement('div'); l1.className = 'cite-overview-line';
    l1.innerHTML = '<b>' + withData.length.toLocaleString('en-US') + '</b> of ' +
      items.length.toLocaleString('en-US') + ' shown papers have <b>' +
      totalC.toLocaleString('en-US') + '</b> total citations.';
    box.appendChild(l1);
  }

  // Paper counts on the page-level citation controls: how many currently
  // shown papers have at least one external judged citation in each
  // category / at each centrality (facet-style, from index.json only).
  function updateCiteToolCounts(items){
    if (!CITE_INDEX || !window.CITATIONS) return;
    var catCounts = {}, centCounts = { core: 0, engaged: 0, peripheral: 0 };
    var seen = {}, withData = 0, i, f;
    for (i = 0; i < items.length; i++){
      var k = bibtexKeyOf(items[i]);
      if (seen[k]) continue;
      seen[k] = 1;
      var row = CITE_INDEX[k];
      if (!row) continue;
      withData++;
      for (f in (row.functions || {})){
        if (row.functions[f] > 0) catCounts[f] = (catCounts[f] || 0) + 1;
      }
      var ce = row.centrality || {};
      for (f in centCounts){ if (ce[f] > 0) centCounts[f]++; }
    }
    if (els.citeCats && els.citeCats._catRefs){
      for (f in els.citeCats._catRefs){
        var ref = els.citeCats._catRefs[f];
        ref.node.nodeValue = ref.label + ' (' + (catCounts[f] || 0) + ')';
      }
    }
    if (els.citeCentrality){
      var bs = els.citeCentrality.querySelectorAll('.type-toggle-btn');
      for (i = 0; i < bs.length; i++){
        var v = bs[i].getAttribute('data-v');
        if (v === 'all') bs[i].textContent = 'All (' + withData + ')';
        else bs[i].textContent = v.charAt(0).toUpperCase() + v.slice(1) +
          ' (' + centCounts[v] + ')';
      }
    }
  }

  function applyFilters(){
    // recompute dynamic counts first (so user sees availability)
    updateDynamicCounts();

    // then produce final result set (include all active facets)
    var items = filteredItems(null);

    updatePublicationCount(items.length);

    // sort by year desc, stable
    items.sort(function(a,b){
      var ay = a.year ? parseInt(a.year,10) : 0;
      var by = b.year ? parseInt(b.year,10) : 0;
      if (ay !== by) return by - ay;
      var am = monthDayValue(a);
      var bm = monthDayValue(b);
      if (am !== bm) return bm - am;
      return 0;
    });

    renderList(els.results, items);

    renderCiteOverview(items);
    updateCiteToolCounts(items);

    // interactive panel visibility
    els.filtersInteractive.className = (state.mode === 'interactive') ? 'filters-interactive' : 'filters-interactive hidden';
  }

  function clearAll(){
    // citation tools
    state.minCites = 0; state.minImpact = 0;
    if (els.minCites){ els.minCites.value = '0'; els.minCitesLabel.textContent = '0'; }
    if (els.minImpact){ els.minImpact.value = '0'; els.minImpactLabel.textContent = 'all papers'; }
    if (els.citeSearch) els.citeSearch.value = '';
    if (els.citeCats){
      var ccbs = els.citeCats.querySelectorAll('input'), ci;
      for (ci = 0; ci < ccbs.length; ci++) ccbs[ci].checked = false;
    }
    if (window.CITATIONS) CITATIONS.setGlobalPanels({ categories: null, search: '' });
    state.years = {};
    state.titleQuery = '';
    state.keywords = {};
    state.authors = {};
    state.types = {};
    state.scroll = { keywords:0, authors:0, types:0 };
    if (els.title) els.title.value = '';
    state.authorQuery = '';
    if (els.authorSearch) els.authorSearch.value = '';
    rebuildAuthorFacet();
    applyFilters();
  }

  // Debounced search event: fires once typing pauses, ignoring short/noisy input.
  var _searchTimer;
  function trackSearch(field, query){
    clearTimeout(_searchTimer);
    _searchTimer = setTimeout(function(){
      var q = (query || '').trim().toLowerCase();
      if (q.length < 2) return;
      if (q.length > 100) q = q.slice(0, 100);
      track('search', { field: field, q: q, results: filteredItems(null).length });
    }, 600);
  }

  /* ---------- Boot ---------- */
  function boot(){
    // Mode toggle
    var radios = document.querySelectorAll('input[name=mode]');
    for (var i=0;i<radios.length;i++){
      radios[i].onchange = function(){ state.mode = this.value; applyFilters(); };
    }

    // Title search
    els.title.oninput = function(){ state.titleQuery = els.title.value || ''; applyFilters(); trackSearch('title', state.titleQuery); };

    // Clear
      els.btnClear.onclick = function(){ clearAll(); };

    // Global show/hide for all visible summaries
    if (els.btnToggleSummaries) {
      els.btnToggleSummaries.onclick = function(){
        state.summaryExpanded = !state.summaryExpanded;
        var open = state.summaryExpanded;
        els.btnToggleSummaries.textContent = open ? 'Hide summaries' : 'Show summaries';
        els.btnToggleSummaries.setAttribute('aria-pressed', open ? 'true' : 'false');
        // :not(.cite-view) / :not(.cite-toggle): the citation panels share
        // the .pub-summary box styling but have their own expand-all below.
        var divs = document.querySelectorAll('.pub-summary:not(.cite-view)'), i;
        for (i = 0; i < divs.length; i++){ divs[i].className = 'pub-summary' + (open ? ' open' : ''); }
        var toggles = document.querySelectorAll('.pub-summary-toggle:not(.cite-toggle)'), j;
        for (j = 0; j < toggles.length; j++){ toggles[j].textContent = open ? 'Summary \u25be' : 'Summary \u25b8'; }
        // Reception prose inside citation panels is a summary too.
        if (window.CITATIONS) CITATIONS.setReceptionVisible(open);
        track('summaries-toggle-all', { expanded: open });
      };
    }

    if (els.btnToggleCitations) {
      els.btnToggleCitations.onclick = function(){
        state.citationsExpanded = !state.citationsExpanded;
        var on = state.citationsExpanded;
        els.btnToggleCitations.textContent = on ? 'Hide citations' : 'Show citations';
        els.btnToggleCitations.setAttribute('aria-pressed', on ? 'true' : 'false');
        if (window.CITATIONS){
          CITATIONS.setDefaultOpen(on);  // items rendered later follow suit
          CITATIONS.setAllOpen(on);      // per-paper files still load lazily
        }
        track('citations-toggle-all', { expanded: on });
      };
    }

    // Page-level citation tools: sort / centrality button groups driving
    // every open panel, the category listbox, the citing-work search, and
    // the two paper-threshold sliders.
    function wireToggleGroup(container, patchKey){
      if (!container) return;
      var bs = container.querySelectorAll('.type-toggle-btn');
      for (var i = 0; i < bs.length; i++){
        bs[i].onclick = function(){
          for (var j = 0; j < bs.length; j++){
            bs[j].className = 'type-toggle-btn' + (bs[j] === this ? ' active' : '');
          }
          if (window.CITATIONS){
            var patch = {}; patch[patchKey] = this.getAttribute('data-v');
            CITATIONS.setGlobalPanels(patch);
          }
          track('citations-global-' + patchKey, { value: this.getAttribute('data-v') });
        };
      }
    }
    wireToggleGroup(els.citeSort, 'sort');
    wireToggleGroup(els.citeCentrality, 'centrality');

    if (els.citeCats && window.CITATIONS){
      (function(){
        var selected = {};
        // Same scrolling shell as the other facet boxes, so the list sits
        // at the standard facet height instead of growing to all 11 rows.
        var scrollWrap = document.createElement('div');
        scrollWrap.className = 'facet-scroll';
        var listEl = document.createElement('div');
        listEl.className = 'facet-items';
        scrollWrap.appendChild(listEl);
        els.citeCats.appendChild(scrollWrap);
        for (var i = 0; i < CITATIONS.FUNCTIONS.length; i++){
          (function(f){
            var label = document.createElement('label'); label.className = 'facet-item';
            var cb = document.createElement('input'); cb.type = 'checkbox'; cb.value = f.key;
            var txt = document.createElement('span'); txt.className = 'facet-text';
            var tn = document.createTextNode(f.label + ' (0)');
            txt.appendChild(tn); txt.title = f.gloss;
            if (!els.citeCats._catRefs) els.citeCats._catRefs = {};
            els.citeCats._catRefs[f.key] = { node: tn, label: f.label };
            cb.onchange = function(){
              selected[f.key] = this.checked;
              var keys = keysSelected(selected);
              CITATIONS.setGlobalPanels({ categories: keys.length ? keys : null });
              if (this.checked) track('citations-category-filter', { value: f.key });
            };
            label.appendChild(cb); label.appendChild(txt);
            listEl.appendChild(label);
          })(CITATIONS.FUNCTIONS[i]);
        }
      })();
    }

    if (els.citeSearch){
      var citeSearchTimer = null;
      els.citeSearch.oninput = function(){
        var q = this.value;
        clearTimeout(citeSearchTimer);
        citeSearchTimer = setTimeout(function(){
          if (window.CITATIONS) CITATIONS.setGlobalPanels({ search: q });
        }, 200);
      };
    }

    // Sliders map quadratically onto [0, max] for fine control at the low end.
    function wireSlider(input, labelEl, maxFn, apply){
      if (!input) return;
      input.oninput = function(){
        var frac = (parseInt(this.value, 10) || 0) / 100;
        var v = Math.round(frac * frac * maxFn());
        labelEl.textContent = v.toLocaleString('en-US');
        apply(v);
        applyFilters();
      };
    }
    function maxCites(){
      var m = 0, k;
      for (k in (CITE_INDEX || {})) m = Math.max(m, CITATIONS.displayCount(CITE_INDEX[k]));
      return m || 1;
    }
    wireSlider(els.minCites, els.minCitesLabel, maxCites, function(v){ state.minCites = v; });

    // The impact slider speaks in tiers, not raw scores: thresholds are
    // quantiles of the corpus impact distribution, labels are plain words.
    var IMPACT_TIERS = [
      { label: 'all papers',            q: null },
      { label: 'top half by impact',    q: 0.50 },
      { label: 'top quarter by impact', q: 0.25 },
      { label: 'top 10% by impact',     q: 0.10 },
      { label: 'top 3% by impact',      q: 0.03 }
    ];
    function impactQuantile(q){
      var vals = [], k, v;
      for (k in (CITE_INDEX || {})){
        v = window.CITATIONS ? CITATIONS.impactScore(CITE_INDEX[k]) : null;
        if (v != null) vals.push(v);
      }
      if (!vals.length) return 0;
      vals.sort(function(a, b){ return b - a; });
      var idx = Math.min(vals.length - 1, Math.max(0, Math.round(vals.length * q) - 1));
      return vals[idx];
    }
    if (els.minImpact){
      els.minImpact.oninput = function(){
        var tier = IMPACT_TIERS[parseInt(this.value, 10) || 0];
        state.minImpact = tier.q == null ? 0 : Math.max(1, impactQuantile(tier.q));
        els.minImpactLabel.textContent = tier.label;
        applyFilters();
      };
    }

    if (els.authorSort) {
      els.authorSort.value = state.authorSort;
      els.authorSort.onchange = function(){
        state.authorSort = this.value || 'first';
        rebuildAuthorFacet();
        applyFilters();
      };
    }

    if (els.authorSearch) {
      els.authorSearch.value = state.authorQuery;
      els.authorSearch.oninput = function(){
        state.authorQuery = this.value || '';
        rebuildAuthorFacet();
        applyFilters();
        trackSearch('author', state.authorQuery);
      };
    }

    if (els.kwToggle) {
      var kwBtns = els.kwToggle.querySelectorAll('.type-toggle-btn');
      var setKwMode = function(sel){
        if (sel === state.kwMode) return;
        state.kwMode = sel;
        state.keywords = {};   // selections differ between Topics and Projects
        for (var k=0;k<kwBtns.length;k++){
          var on = kwBtns[k].getAttribute('data-kwmode') === sel;
          kwBtns[k].className = on ? 'type-toggle-btn active' : 'type-toggle-btn';
          kwBtns[k].setAttribute('aria-pressed', on ? 'true' : 'false');
        }
        rebuildKeywordFacet();
        applyFilters();
      };
      for (var kb=0;kb<kwBtns.length;kb++){
        kwBtns[kb].onclick = (function(btn){ return function(){ setKwMode(btn.getAttribute('data-kwmode')); }; })(kwBtns[kb]);
      }
    }

    if (els.typeToggle) {
      var toggleBtns = els.typeToggle.querySelectorAll('.type-toggle-btn');
      var setMode = function(sel){
        var mode = (sel === 'type') ? 'type' : 'venue';
        var vsort = (sel === 'venue-count') ? 'count' : 'name';
        var modeChanged = (mode !== state.typeMode);
        var sortChanged = (mode === 'venue' && vsort !== state.venueSort);
        if (!modeChanged && !sortChanged) return;
        state.typeMode = mode;
        state.venueSort = vsort;
        for (var k = 0; k < toggleBtns.length; k++){
          var on = toggleBtns[k].getAttribute('data-mode') === sel;
          toggleBtns[k].className = on ? 'type-toggle-btn active' : 'type-toggle-btn';
          toggleBtns[k].setAttribute('aria-pressed', on ? 'true' : 'false');
        }
        if (modeChanged) state.types = {};          // category keys differ between type and venue
        rebuildTypeFacet();
        applyFilters();
      };
      for (var ti = 0; ti < toggleBtns.length; ti++){
        toggleBtns[ti].onclick = function(){ setMode(this.getAttribute('data-mode')); };
      }
    }

function downloadText(filename, text){
  var blob = new Blob([text], {type:'text/plain'});
  var a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  setTimeout(function(){ URL.revokeObjectURL(a.href); document.body.removeChild(a); }, 0);
}

// Ensure the button exists; if not, create it in the filter row
var btnExport = document.getElementById('btn-export-bib') || (function(){
  var row = document.querySelector('.filter-row');
  if (!row) return null;
  var b = document.createElement('button');
  b.id = 'btn-export-bib';
  b.type = 'button';
  b.className = 'btn';
  b.textContent = 'Export .bib';
  row.appendChild(b);
  return b;
})();

if (btnExport) {
  btnExport.onclick = function(){
    track('export-bib', {});
    // Export exactly what’s currently shown
 var items = filteredItems(null);

// Group by year like the UI
var byYear = {};
for (var i=0;i<items.length;i++){
  var y = items[i].year ? String(items[i].year) : 'Other';
  if (!byYear[y]) byYear[y] = [];
  byYear[y].push(items[i]);
}
var years = Object.keys(byYear).sort(function(a,b){
  if (a==='Other' && b!=='Other') return 1;
  if (b==='Other' && a!=='Other') return -1;
  var ai = parseInt(a,10)||0, bi = parseInt(b,10)||0;
  return bi - ai;
});

// Within-year sort same as UI
var sorter = makeSorter(state.sortKey);
var dir = state.sortDesc ? -1 : 1;

var out = [], yi, y;
for (yi=0; yi<years.length; yi++){
  y = years[yi];
  var arr = byYear[y].slice();
  if (sorter) arr.sort(function(a,b){ return dir * sorter(a,b); });

  for (var k=0; k<arr.length; k++){
    out.push(buildBibtex(arr[k], localizeURL));
    if (yi !== years.length-1 || k !== arr.length-1) out.push('\n\n');
  }
}

downloadText('commit-publications.bib', out.join(''));

  };
}

function uniqueOrder(arr){
  // Keep order, remove duplicates except 'none' (allowed multiple),
  // then append any missing real keys to complete 4 slots.
  var seen = {}, out = [], ALL = ['year','keywords','authors','type'], i, k;
  for (i=0;i<arr.length;i++){
    k = arr[i] || 'none';
    if (k === 'none') { out.push('none'); continue; }
    if (!seen[k]) { seen[k]=1; out.push(k); }
  }
  // pad to 4 with 'none'
  while (out.length < 4) out.push('none');
  return out.slice(0,4);
}
function applySortUIToState(){
  state.sortOrder = uniqueOrder([
    (els.sort1 && els.sort1.value) || 'none',
    (els.sort2 && els.sort2.value) || 'none',
    (els.sort3 && els.sort3.value) || 'none',
    (els.sort4 && els.sort4.value) || 'none'
  ]);
}
function refreshSortUI(){
  var so = state.sortOrder;
  if (els.sort1) els.sort1.value = so[0];
  if (els.sort2) els.sort2.value = so[1];
  if (els.sort3) els.sort3.value = so[2];
  if (els.sort4) els.sort4.value = so[3];

  // Disable chosen non-'none' values in other selects to avoid duplicates
  var picks = [so[0], so[1], so[2], so[3]];
  var selects = [els.sort1, els.sort2, els.sort3, els.sort4];
  for (var i=0;i<selects.length;i++){
    var s = selects[i]; if (!s) continue;
    for (var j=0;j<s.options.length;j++){
      var v = s.options[j].value;
      s.options[j].disabled = false;
      if (v !== 'none') {
        // if v is selected elsewhere (not this select), disable it here
        var selectedElsewhere = (v===picks[0] && s!==els.sort1) ||
                                (v===picks[1] && s!==els.sort2) ||
                                (v===picks[2] && s!==els.sort3) ||
                                (v===picks[3] && s!==els.sort4);
        if (selectedElsewhere) s.options[j].disabled = true;
      }
    }
  }
}


function onSortChange(){
  applySortUIToState();
  refreshSortUI();
  applyFilters(); // re-render with new grouping/sort
}

      // hook up
      if (els.sort1) els.sort1.onchange = onSortChange;
      if (els.sort2) els.sort2.onchange = onSortChange;
      if (els.sort3) els.sort3.onchange = onSortChange;
      if (els.sort4) els.sort4.onchange = onSortChange;
if (els.sortReset) els.sortReset.onclick = function(){
  state.sortOrder = ['none','none','none','none']; // <— all none on reset
  refreshSortUI();
  applyFilters();
};

      // initialize UI
      refreshSortUI();


    // Load JSON
    var xhr = new XMLHttpRequest();
    xhr.open('GET', JSON_PATH, true);
    xhr.onreadystatechange = function(){
      if (xhr.readyState !== 4) return;
      if (xhr.status >= 200 && xhr.status < 300){
        try {
            DATA = JSON.parse(xhr.responseText);

	    // --- Dedupe by normalized title ---
// --- Dedupe by normalized (title + type) ---
// Prefer the entry that has a URL (PDF) or DOI; otherwise keep first seen.
(function(){
  var bestByKey = Object.create(null);
  var order = []; // preserve overall order for stable output

  function isBetter(a, b){
    // Return true if a is better than b
    var aHasPdf = !!(a && a.url);
    var bHasPdf = !!(b && b.url);
    if (aHasPdf !== bHasPdf) return aHasPdf;

    var aHasDoi = !!(a && a.doi);
    var bHasDoi = !!(b && b.doi);
    if (aHasDoi !== bHasDoi) return aHasDoi;

    // (optional) prefer one with slides
    var aHasSlides = !!(a && a.slides);
    var bHasSlides = !!(b && b.slides);
    if (aHasSlides !== bHasSlides) return aHasSlides;

    return false; // otherwise don't replace
  }

  for (var i = 0; i < DATA.length; i++){
    var it = DATA[i];
    var key = normalizeTitle(it.title) + '|' + normalizeType(it.itemType);
    if (!bestByKey[key]) {
      bestByKey[key] = it;
      order.push(key);
    } else if (isBetter(it, bestByKey[key])) {
      bestByKey[key] = it;
    }
  }

  var dedup = [];
  for (var j = 0; j < order.length; j++){
    dedup.push(bestByKey[order[j]]);
  }
  DATA = dedup;
})();



          // YEARS: compute global list first (unique, desc)
          var ySet = {}, i;
          for (i=0;i<DATA.length;i++){ if (DATA[i].year) ySet[String(DATA[i].year)] = 1; }
          var years = []; for (var k in ySet) years.push(parseInt(k,10));
          years.sort(function(a,b){ return b-a; });
          buildFacetBox(years.map(String), els.years, 'years', state.years);

            // Facets static lists (values only; counts dynamic)
            var auSet = {};
            for (i=0;i<DATA.length;i++){
		var it = DATA[i], j;
		var aus = listNormalizedAuthors(it);
		var itYear = it.year ? parseInt(it.year, 10) : 0;
		for (j=0;j<aus.length;j++) {
		    var auKey = normalizeAuthorName(aus[j]);
		    auSet[auKey] = 1;
		    AUTHOR_PUB_COUNTS[auKey] = (AUTHOR_PUB_COUNTS[auKey] || 0) + 1;
		    if (itYear > (AUTHOR_LATEST_YEAR[auKey] || 0)) AUTHOR_LATEST_YEAR[auKey] = itYear;
		}
            }
	    // Type / Venue facet (values + labels depend on state.typeMode)
	    rebuildTypeFacet();

          ALL_AUTHORS = Object.keys(auSet);

          rebuildKeywordFacet();
          rebuildAuthorFacet();

          // Wait for the (already in-flight, always-resolving) citations
          // index before first render so toggles appear on the first paint.
          citeIndexReady.then(function(){
            applyFilters(); // initial render and dynamic counts
          });
        } catch (e) {
          els.errors.textContent = 'Failed to parse publications.json: ' + e.message;
        }
      } else {
        els.errors.textContent = 'HTTP ' + xhr.status + ' loading ' + JSON_PATH;
      }
    };
    xhr.send();
  }

  if (document.readyState === 'loading'){ document.addEventListener('DOMContentLoaded', boot); }
  else { boot(); }
})();
