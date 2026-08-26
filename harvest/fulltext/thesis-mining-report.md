# Thesis-mining report (round 9 task 5)

Mines this corpus's own full-text harvest (chased for OTHER, DOI'd papers'
citing works) for reference-list citations to the ~108 no-DOI theses/TRs
that OpenAlex/S2 have nothing to look up for.

## Pipeline

1. **scan** (mechanical, free): 87-107 theses with a usable match
   signature (first-author surname + significant title words), word-
   boundary searched across all 3,681 distinct full-text documents
   already on disk. First pass at a loose bar (3+ title words) produced
   3,508 candidates dominated by common-surname noise (one author's
   surname alone drove 543 hits); tightened to a two-tier bar (4+ title
   words alone, or 2+ with a thesis+MIT+year marker cluster nearby) ->
   **976 candidates across 51 theses**.
2. **verify** (Batch API, $2.01): independent model gate -- genuine
   citation to this specific thesis, or a coincidental surname/title-
   vocabulary collision? **584/976 confirmed (60%)**.
3. **recheck-siblings** (Batch API, $0.81): 25 of the 43 theses with a
   round-2 confirmation turned out to have a same-first-author, near-
   identically-titled PUBLISHED paper already in this corpus (the normal
   thesis -> conference-paper path, e.g. a S.M. thesis and its later
   co-authored ASPLOS paper). The verify step has no way to know a
   sibling exists, so it happily confirmed citations to the PAPER
   (multi-author, no "thesis"/"dissertation" language) as citations to
   the solo-authored THESIS -- **435/584 (75%) of round-1 confirmations
   for those 25 theses were this mistake**. Re-verified with the
   sibling's real title/venue given, asking explicitly which of the two
   a citation is for: **7 re-confirmed as the thesis, 379 reclassified
   to the sibling paper (already has its own real citation data), 49
   neither**.
4. **fold**: confirmed pairs' citing works already have full metadata
   elsewhere in `harvest/citations/` (same doi/openalex/s2/authors/year,
   just a new `contexts` entry) -- appended into a brand-new
   `harvest/citations/<thesisKey>.json` per thesis. **156 citing records
   folded across 29 theses**, 0 pairs had no findable source record.
5. Standard taxonomy classification (`classify_citations.py`, ~$1.13)
   and merge (`merge_taxonomy.py --write`) -- these 29 theses now have
   real `data/citations/<key>.json` files.

## Result

- **29 of ~108 no-DOI theses now have >=1 confirmed citing work** (up
  from 0 -- this source didn't exist for them before).
- **156 (citing-work, thesis) pairs total**, 138 distinct works after
  corpus-wide dedup (a citing work can cite more than one thesis).
- Function distribution across the 138 works: 65 passing-citation, 34
  detailed-citation, 15 uses-tool, 5 surveys, 4 exemplifies, 4
  adopts-idea, 3 uses-benchmark, 2 positions, 1 supports-claim, 1
  extends, 4 unknown.
- Heaviest coverage: `bruening:phd-thesis:2004` (46 citing works --
  DynamoRIO's PhD thesis is directly and explicitly cited as "PhD
  thesis, MIT" across many tool papers, not superseded by a sibling
  paper), `thies:phd-thesis:2009` (13), `karczmarek:sm-thesis:2002` (12),
  `puppin:sm-thesis:2002` (10).

## Honesty note

**This source is our-corpus-only, a lower bound.** It only finds a
citation if the citing work's full text happened to already be in this
corpus's fulltext harvest -- which itself only exists because that
citing work also cites some OTHER, DOI'd corpus paper. A thesis cited
ONLY by works that never cite anything else in this corpus is invisible
to this method. `gscholar.json`'s displayed count (where present) already
supplies a fuller external count for these theses via the site's
`max(verified, gscholar)` rule, which is unchanged by this task.

## Remaining gap

79 of ~108 no-DOI theses still have zero citation data (no scan
candidate cleared the bar, or none survived verify/recheck). The
mechanical bar can be tuned further, but the deeper limitation is
coverage of the fulltext corpus itself, not the mining method.
