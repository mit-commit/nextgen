/* Scoring — the single JS home of the ranking formulas (his rulings,
   2026-08-26). The ONLY other copy is the deliberately independent test
   oracle: tests/ui/oracle.py. A formula change edits exactly those two
   files (then bump asset versions and run both harnesses).

   impactOf  — the publications page's Impact sort + slider:
       2e^(-age/5) + [award] 5e^(-awardAge/10) + citations/100
       + repos/1000 + venueBonus - typePenalty
   featuredOf — the home page's Featured list:
       10e^(-age/5) + [award] 20e^(-awardAge/12) + citations/100
       + repos/250   (theses excluded by the caller)
   Award age counts from the AWARD's own year — the latest year in the
   award text >= the paper year (Halide's 2023 Test-of-Time is recent). */
var SCORING = (function () {
  'use strict';

  function yearOf(it, nowY) {
    var y = parseInt(it && it.year, 10);
    return isNaN(y) ? nowY : y;
  }

  function awardYearOf(it, nowY) {
    var py = yearOf(it, nowY);
    var m = String(it.price || '').match(/\b(19|20)\d{2}\b/g) || [];
    var best = py;
    for (var i = 0; i < m.length; i++) {
      var yy = parseInt(m[i], 10);
      if (yy >= py && yy > best) best = yy;
    }
    return best;
  }

  /* Venue bonus (his ruling). Matching quirks: the MICRO conference tag
     is uppercase (IEEE Micro the magazine is not); the HPCA Workshop is
     not HPCA; SIGGRAPH publishes as Transactions on Graphics. */
  function venueBonus(v) {
    v = String(v || '');
    if (/\bPLDI\b/.test(v)) return 2.0;
    if (/\bASPLOS\b|\bOOPSLA\b|\bISCA\b/.test(v)) return 1.0;
    if (v.indexOf('HPCA Workshop') !== -1) return 0.0;
    if (/\bCGO\b|\bMICRO\b|\bPACT\b|\bPPoPP\b|\bPOPL\b|\bSOSP\b|USENIX Security|P?VLDB|\bHPCA\b|Communications of the ACM|\bCACM\b/.test(v)) return 0.5;
    if (/\bTOPLAS\b|Transactions on Programming Languages|\bTACO\b|Architecture and Code Optimization|Transactions on Graphics|SIGGRAPH|\bICML\b|\bICS\b|NeurIPS|MLSys|\bSC\b|Supercomputing/.test(v)) return 0.25;
    return 0.0;
  }

  /* Tiered demotion: PhD -1, SM -2, MEng -3, SB -4; anything that is
     not a conference or journal paper (tech reports, talks, misc) -5. */
  function typePenalty(it) {
    var itype = String(it.itemType || '').toLowerCase();
    if (/thesis/.test(itype)) {
      var tt = String(it.type || '').toLowerCase();
      if (/ph\.?\s*d/.test(tt)) return 1;
      if (/s\.?\s*b/.test(tt)) return 4;
      if (/m\.?\s*eng/.test(tt)) return 3;
      if (/s\.?\s*m/.test(tt)) return 2;
      return 2;
    }
    if (itype !== 'inproceedings' && itype !== 'article') return 5;
    return 0;
  }

  function isThesis(it) {
    return /thesis/.test(String(it.itemType || '').toLowerCase());
  }

  function displayCount(citeRow) {
    if (!citeRow) return 0;
    return Math.max(citeRow.verified || 0, citeRow.gscholar || 0);
  }

  function impactOf(it, citeRow, repoRow, nowY) {
    var age = nowY - yearOf(it, nowY);
    var s = 2 * Math.exp(-age / 5);
    if (it.price) s += 5 * Math.exp(-(nowY - awardYearOf(it, nowY)) / 10);
    s += displayCount(citeRow) / 100;
    if (repoRow) s += (repoRow.repos || 0) / 1000;
    s += venueBonus(it.venue);
    s -= typePenalty(it);
    return s;
  }

  function featuredOf(it, citeRow, repoRow, nowY) {
    var age = nowY - yearOf(it, nowY);
    var s = 10 * Math.exp(-age / 5);
    if (it.price) s += 20 * Math.exp(-(nowY - awardYearOf(it, nowY)) / 12);
    s += displayCount(citeRow) / 100;
    if (repoRow) s += (repoRow.repos || 0) / 250;
    return s;
  }

  return {
    awardYearOf: awardYearOf,
    venueBonus: venueBonus,
    typePenalty: typePenalty,
    isThesis: isThesis,
    displayCount: displayCount,
    impactOf: impactOf,
    featuredOf: featuredOf
  };
})();
