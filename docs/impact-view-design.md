# The per-paper impact area — citations and repositories together

**Status: DRAFT, awaiting human review — this is a taste decision.** A mock
of the recommended option runs on the StreamIt paper
(`prototype/impact.html`, §5) with clearly-marked placeholder repository
rows until the tier-2 harvest lands. Nothing here touches the live pages.

Constraint set by the human while this was drafted: per paper, twin
selectors — "Citations (1,361) ▸" and "Repositories (11) ▸" — are
acceptable; what must be seamless is the all-papers surface: one filters
area and one set of page-level behaviors serving both, not two bolted-on
systems.

Reference points: the existing Citations panel (approved through several
rounds of simplification), and the repo presentation of SDVworld-index and
Halide-world — verdict/integration facets, evidence provenance per row,
stars as the practical importance signal, "no silent truncation", and
"a facet with no values does not render". Those two are full index pages;
this stays a lightweight per-paper panel.

## 1. The data being presented

Three repository tiers per paper (2026-08-25 ruling), parallel to citation
categories they echo:

| tier | meaning | citation parallel |
|---|---|---|
| Own repository | the paper's implementation/artifact | — (the paper itself) |
| Repos using it | third-party repos that import/embed/extend the artifact (SDV integration vocabulary: api_user, derivative_work, inherited, fork, …) | `uses-tool` / `extends` |
| Idea descendants | repos of citing works classified extends/adopts-idea at high centrality | `adopts-idea` / `extends` |

Repo rows carry: name/owner (linked), one-line description, integration
type, stars, last-activity year, and evidence (tooltip, like citation
glosses). The same repo may appear under several papers — expected.

## 2. Option A — one "Impact" panel with tabs

One toggle per paper — "Impact (1,361 citations · 11 repos) ▸" — opening a
panel with a [Citations | Repositories] tab bar.

- For: one entry point; the two halves can never visually collide.
- Against: tabs hide one half — a reader scanning with Show-all sees only
  whichever tab is active, and screenshots/prints lose the other half; the
  tab bar is a new UI species on a site that has none; and the combined
  count in the toggle label muddles the two numbers the human has kept
  deliberately plain. Weakest fit with the twin-selector instruction.

## 3. Option B — twin panels, one grammar, one page-level surface (recommended)

Two toggles in the meta line, side by side where Citations sits today:

> Bib &nbsp; Summary ▸ &nbsp; Citations (1,361) ▸ &nbsp; Repositories (11) ▸

The Repositories panel **reuses the citation panel's grammar wholesale**:

1. Headline: "11 repositories".
2. A three-segment tier bar (own / using it / idea descendants) echoing
   the detailed/passing split bar, with the same legend treatment.
3. A sort row in the same button language: **Integration | Stars |
   Recency**, plus the same Expand all / Collapse all. Integration is the
   default and groups rows by tier — Own repository (1), then the
   using-it tier grouped by integration type (Derivative works (3),
   API users (5), Forks (2), …), then Idea descendants (4). Stars and
   Recency regroup into magnitude buckets (1,000+ stars / 100–999 / …)
   and years — the exact analogue of the citation panel's Popularity and
   Recency. Group headers are "Label (N)" with the definition as a
   tooltip, identical to citation groups.
4. Rows: linked repo name — description; stars chip ("2.1k ★"),
   last-active-year chip, and a paper-parallel chip where the repo is the
   located artifact of a citing work already in the Citations panel
   ("artifact of a citing work", tooltip names it). Evidence in the row
   tooltip. Idea descendants without a located repo render as paper-only
   rows, greyed, so the tier's count stays honest.

Page level, one seamless surface: the existing citation-tools grid gains a
**Repositories block** in the same row — an integration-type facet listbox
("Derivative works (12, ★ 4,802)" — repos, then summed stars, mirroring
"(44, cited by 142)") and a minimum-stars slider in the thresholds block
alongside the citation sliders. A **Show repositories** button joins Show
summaries / Show citations, with identical expand-all + lazy-load
semantics (per-paper `data/repos/<bibtexKey>.json`, an `index.json` row
for toggle counts — the citations loading pattern verbatim). The aggregate
overview line extends by one clause: "… and 214 repositories."

- For: honors the twin-selector instruction; zero new UI species — a
  reader who has learned the Citations panel already knows the
  Repositories panel; page-level stays one grid, one button row, one
  overview line; each panel keeps its own appropriate sorts without a
  mode switch contaminating the other.
- Against: two toggles consume more meta-line width (acceptable — the
  line holds Bib/Slides/Code/Summary today); a reader wanting "everything
  about this paper's influence" opens two panels (mitigated by the Show
  buttons opening either across all papers).

## 4. Option C — one unified panel, interleaved tiers

One "Impact" panel where repo tiers render as additional groups inside the
citation group list — Own repository after the use-class citation groups,
Idea descendants beside Adopts the idea — under a single control row.

- For: the tightest expression of "repos parallel the citation categories";
  one toggle.
- Against: the control row breaks — Popularity means citing-work citations
  for one row species and stars for the other; the centrality filter means
  nothing for repos, integration type means nothing for citations, so
  every control needs per-species exceptions; counts stop being one
  number ("Builds on it (35)" of what?). The parallelism reads better as
  two panels sharing one grammar than as one panel with two grammars.

## 5. The mock

`prototype/impact.html` renders the StreamIt paper (`thies:cc:2002`) with
its real Citations panel and an Option-B Repositories panel:

    cd ~/workspace/nextgen && python3 -m http.server 8000
    open http://localhost:8000/prototype/impact.html

The own-repo row (`bthies/streamit`) is real per the ruling; the tier-2
rows are **placeholders marked [PLACEHOLDER]** until the
`repo-ecosystems` harvest lands, with shapes matching the SDV integration
vocabulary; the tier-3 rows use citing works actually classified
extends/adopts-idea for StreamIt (Sponge, Flextream, STR2RTS), with
repo fields left as placeholder or paper-only. Sorts, grouping, chips,
tooltips, and Expand/Collapse all function against the mock data
(`prototype/impact-mock.js`).

## 6. The Summary's three registers

Per the human (during this draft): the combined Summary reads as one flow
with three registers — (a) what the paper is (the hand-written text),
(b) how the literature received it (the reception, already merged), and
(c) a natural sentence accommodating the repositories: the own repo and,
where the ecosystem warrants it, its software afterlife ("The compiler and
benchmark suite live on in bthies/streamit, and …"). Storage follows the
established pattern — a third regenerable field alongside reception, never
touching hand-written prose — and the sentence is written to flow from the
reception's close the way reception flows from the summary. The mock
includes a hand-written specimen for StreamIt; scaling the prose waits, per
the standing queue ruling, on the human's critique of the 9 pilot
summaries.

## 7. Recommendation

Option B. It is the only option that satisfies both halves of the
constraint — twin per-paper selectors, one seamless page surface — and it
adds no new interface vocabulary: the Repositories panel is the Citations
panel with tiers for categories and stars for citations. Data contract
follows the citations pattern (`data/repos/SCHEMA.md`, an index for
counts, per-paper files, lazy load, versioned assets) once repo-verify and
repo-ecosystems produce the inputs.
