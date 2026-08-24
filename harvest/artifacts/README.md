# artifacts lane

Finds artifact-evaluation badges and artifact download links for the
publications in `data/idmap.json` / `data/publications.json`. Output:
`found.json` (confirmed) and `review.json` (uncertain), each keyed by
bibtexKey with `{doi, badges[], artifact_doi, artifact_url, source[],
evidence[]}`.

## Pipeline

1. `metadata_scan.py` -- routes 1+2. For every DOI'd entry in `data/idmap.json`
   (151 of them), queries Crossref (`relation`/`assertion`/`link`), OpenAlex
   (`locations`/`best_oa_location`), and DataCite (search for records whose
   `relatedIdentifiers` mention the paper's DOI). Writes
   `raw/metadata_hits.json` -- every entry that produced *any* keyword-ish
   signal, unfiltered.
2. `scan_pdfs.py` -- route 4. For every publication with a local
   `papers/**.pdf` (309 of them), extracts text page by page with pypdf and
   records every line containing "artifact evaluation", "zenodo.org",
   "doi.org/10.5281", "artifact appendix", the ACM badge phrases, etc., plus
   any zenodo/figshare/github URL found on the page. Writes
   `raw/pdf_hits.json`, unfiltered.
3. `merge.py` -- reads both raw files and applies the precision rules below
   to produce `found.json`/`review.json`. Rerun this alone (no network) after
   editing the rules; it's cheap.

Route 3 (ACM DL landing-page badge HTML, for the 87 `10.1145` DOIs) was tried
once and returned **HTTP 403** on the very first request
(`dl.acm.org/doi/10.1145/3579990.3580020`), then a connection failure on
retry with a different UA. Per instructions ("fetch gently, 1 req/2s, stop on
any 403/challenge") this route was not pursued further -- it is not a rate
issue, ACM DL is blocking non-browser clients outright. **Badge names are
therefore unavailable this pass** except in the rare case a paper's own PDF
text spells one out (checked in step 2; none did -- badges are rendered as
images next to the title on ACM DL, not as text in the paper PDF). Anyone
picking this up with real browser access (e.g. claude-in-chrome, logged into
an institutional proxy) could revisit route 3 to fill in `badges[]` for the
10 confirmed + 6 review papers below, all ACM-published.

## Precision rules (why so few of 353 PDFs' "artifact" mentions became hits)

- **DataCite**: a search hit only means some DataCite-registered record's
  `relatedIdentifiers` mentions our DOI. Manually auditing all 20 raw hits
  found 18 were noise -- other papers citing ours (`relationType: Cites` /
  `References`) or an arXiv mirror of the same paper (`IsVersionOf`,
  `resourceTypeGeneral: Text`/`Preprint`). Only `resourceTypeGeneral` in
  `{Software, Dataset}` reliably isolates an actual deposited artifact; that
  filter alone correctly isolates the one real hit (`tiramisu-li`,
  `IsDescribedBy` + `Software`, zenodo.org/record/7584641).
- **PDF scan**: a bare `github.com` URL on the same page as the word
  "artifact" was checked against all 41 papers that had one -- zero were the
  paper's own artifact page (all were bibliography citations to unrelated
  tools/baselines, esp. in theses). Those are dropped rather than pushed to
  review. A `zenodo.org`/`10.5281`/`figshare` URL is a much stronger signal,
  but still needs the surrounding sentence checked -- papers routinely cite
  *other* work's Zenodo-archived software in their own bibliography (e.g.
  citing "Shapely" or a baseline compiler). `merge.py` only promotes a
  Zenodo/FigShare hit to `found.json` if the surrounding text either (a) uses
  self-referential language ("the artifact", "our artifact", "reproduction
  package", "artifact appendix", "created zenodo ... our artifacts", etc.) or
  (b) the sentence shares >=3 of the paper's own distinctive title words (or
  >=2 with >=80% title-word coverage -- a plain 2-word overlap on generic
  terms like "high"/"performance" or "finite"/"elements" produced false
  positives during tuning and is excluded).

## Results (last run 2026-08-22)

- 151 DOI'd entries checked via Crossref/OpenAlex/DataCite; 309 local PDFs
  scanned.
- **10 confirmed artifacts** (`found.json`), all with a Zenodo (or in one
  case DataCite-confirmed Zenodo) artifact DOI/URL and an evidence quote
  showing it's self-referential. Zero had recoverable badge names (route 3
  blocked -- see above).
- **6 review** (`review.json`): a Zenodo/FigShare URL appears in the PDF but
  the context doesn't clearly establish it as *this* paper's own artifact
  (could be a citation to a different work's archive) -- worth a human
  glance, especially `randomwalk-iiswc21`-adjacent `ahrens_autoscheduling_2022`
  (footnote to a Zenodo record right after the paper's own repo link) and
  `gladshtein_mechanised_2024` (a formal-methods/mechanization paper that
  plausibly has its own proof artifact on GitHub, not caught by any route
  here since it wasn't archived on Zenodo/FigShare or described in Crossref).
- Everything else: no positive signal via any of the 3 available routes. Not
  listed in either file -- most of the corpus (pre-2016 papers especially)
  predates the ACM/community norm of archiving artifacts, so true negatives
  are expected to dominate.

Re-run: `python3 metadata_scan.py && python3 scan_pdfs.py && python3 merge.py`
(the two scan scripts hit the network / read every local PDF respectively and
take a few minutes each; `merge.py` alone is near-instant).

## Route 3 revisit (2026-08-24): still blocked

Route 3 (ACM DL badge markup for the 87 `10.1145` DOIs in `data/idmap.json`)
was retried with real browser access -- Playwright, headful Chromium, a
persistent profile (`pip install playwright --break-system-packages &&
playwright install chromium`). Every attempt hit a Cloudflare "Just a
moment..." interstitial on `dl.acm.org`, including:

- A specific paper DOI (`doi.org/10.1145/3519939.3523442` -> dl.acm.org).
- The plain `dl.acm.org` homepage (no DOI, in case the challenge was
  redirect-specific).
- A logged-in-user manual solve attempt: the browser window was left open
  (up to 30 min at a time) for a human to click through the challenge
  directly, twice, including after the user separately confirmed their own
  normal Chrome could load IEEE Xplore fine (ruling out a general
  network/fingerprint problem) -- the ACM DL challenge never cleared.

Conclusion: this isn't a rate-limit or headless-detection issue, dl.acm.org
is blocking this network path/profile outright regardless of browser
automation vs. manual human interaction. **Badge names remain unavailable.**
`found.json` entries now carry a `badges: []` field (schema-ready for a
future successful scrape) but nothing is populated in it, and no
`badge_source` field was added since no data was actually sourced from
`acm_dl`. Anyone revisiting this with a different network path (e.g. an
institutional VPN/proxy, or a residential IP) could try again.

## review.json settlement (2026-08-24)

All 6 `review.json` rows were settled by opening each row's `artifact_url`
(the Zenodo landing page) and comparing its title/authors against the
paper's own title/authors from `data/idmap.json`:

- **2 promoted to `found.json`** as the paper's own artifact (title and
  authors match exactly, and in one case the Zenodo record explicitly
  states it's the artifact for this paper):
  - `ahrens_autoscheduling_2022` -> zenodo.org/record/6366296, "Autoscheduling
    for Sparse Tensor Algebra with an Asymptotic Cost Model (The Artifact)".
  - `gladshtein_mechanised_2024` -> 10.5281/zenodo.10951930, "LGTM: the Logic
    for Graceful Tensor Manipulation", which states outright it's the
    artifact for "Mechanised Hypersafety Proofs about Structured Data".
- **4 settled as citations to a dependency, not the paper's own artifact**
  (moved to `harvest/artifacts/settled_not_own.json` for the audit trail,
  removed from `review.json`): `bansal2025lightweight`,
  `thea:sm-thesis:2025`, `won:phd-thesis:2026`, and `won_continuous_2025` all
  turned out to cite the same two general-purpose libraries in their
  bibliography -- Shapely (geospatial Python) or FInAT (finite elements) --
  not an artifact of their own.
- `review.json` is now empty; each row's `review_resolution` field records
  the reasoning. See `settled_not_own.json` for the 4 dependency citations.

## ACM DL badge ingestion (2026-08-24)

The user separately obtained ACM DL badge markup for all 92 `10.1145` DOIs
(scraped by hand outside this session, after route 3's Cloudflare block
above) and handed it in as `~/Downloads/acm_badges.json` (list of `{key,
doi, status, badges[], links[], title}`). Ingested into `found.json`:

- `badges[]` on each entry is the parsed real ACM badge type strings only
  (`Artifacts Available`, `Artifacts Evaluated & Functional`, `Artifacts
  Evaluated & Reusable`, `Results Reproduced`) with version suffixes like
  `/ v1.1` stripped; `badge_source: "acm_dl"` marks where they came from.
  Non-badge noise in the raw `badges[]` field (artifact titles, the ACM
  badging-policy URL) was dropped rather than kept as a fake badge type.
- `acm_dl_links[]` holds every non-`scholar.google.com` link the page
  surfaced (the raw list mixes the paper's own archived artifact with
  bibliography citations to baseline tools -- it is not filtered to "own
  artifact only"). Where `artifact_doi`/`artifact_url` was empty, it was
  filled from the first Zenodo/DOI link, excluding six links already
  confirmed (via `review.json` settlement, above, or a fresh landing-page
  check) to be citations to a shared dependency rather than the paper's own
  artifact: Shapely (`zenodo.5597138`), FInAT (`zenodo.597531`), TensorFlow
  (`zenodo.16852354`), pandas (`zenodo.3509134`), Mathematical Components
  (`zenodo.7118596`), and the CoRa Tensor Compiler (`zenodo.6326456`).
- 11 papers had a real ACM badge but no prior `found.json` entry (PDF/DataCite
  scan missed them entirely) and were added fresh, sourced purely from
  `acm_dl` with no PDF evidence: `chen:asplos:2021`, `chen:pldi:2022`,
  `chou-pldi20-taco-conversion`, `chou:2018:formats`,
  `chou:2022:dynamic-formats`, `goslp`, `graphit`, `jaeyeon:asplos:2023`,
  `kjolstad:oopsla:2017`, `og-cgo20`, `shajii:oopsla:2019`.
- Two `settled_not_own.json` rows (`bansal2025lightweight`,
  `won_continuous_2025`) had no ACM badge and their only links were more
  dependency citations (confirmed for the new one, `pandas`,
  `zenodo.3509134`) -- left as-is, not promoted.
- `found.json` now has 23 entries; 20 carry at least one real ACM badge.
