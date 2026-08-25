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

**One relationship taxonomy for both media** (2026-08-25 ruling: two
taxonomies under one sort name is not acceptable). The citation
categories' approved plain-language names are the single group-level
vocabulary; the SDV integration terms survive as row-level chips and
evidence, and the three tiers fall out of the unified categories rather
than being a second scheme:

| unified group | citations mean | repositories mean | tier |
|---|---|---|---|
| Artifact & own repository | — | the paper's badged archival artifact (artifacts lane) first, then its implementation repo | own |
| Builds on it | `extends` | derivative works and forks of the artifact | using it |
| Uses the system | `uses-tool` | API users and inherited/dependency users | using it |
| Uses its benchmarks | `uses-benchmark` | repos carrying the paper's workload files | using it |
| Adopts the idea | `adopts-idea` | repos of citing works classified extends/adopts-idea at high centrality, reimplementing the idea without the code | idea descendants |
| Measures against it, Positions against it, Surveys it, Cites a result as evidence, Names it as an example, Mentions it specifically, Cites it in a list | bibliographic engagement | *no repo values — the group simply does not render in the Repositories panel* | — |

This also lets the page-level **Citation categories facet govern both
panels**: selecting "Builds on it" filters citation rows to `extends` and
repo rows to derivative works/forks — one control, two media.

Repo rows carry: name/owner (linked), one-line description, an SDV
integration chip (api_user / derivative_work / fork / inherited), stars,
last-activity year, and evidence (tooltip, like citation glosses). The
same repo may appear under several papers — expected.

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
3. A sort row with **the same three names as the citations panel** —
   **Impact | Recency | Popularity** (2026-08-25 ruling: one vocabulary,
   each panel interpreting it natively) — plus the same Expand all /
   Collapse all. Impact is the default and groups rows by the unified
   relationship taxonomy: Artifact & own repository first, then Builds on
   it, Uses the system, Uses its benchmarks, Adopts the idea — the same
   names, order, and tooltips as the citations panel, with the SDV
   integration term as a per-row chip. Popularity regroups by stars magnitude (1,000+ stars /
   100–999 / …) — stars being the repo world's citation count — and
   Recency by last-activity year. Group headers are "Label (N)" with the
   definition as a tooltip, identical to citation groups.
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

## 7. Appendix — catching renamed embedded forks (the sketch-frontend lesson)

`asolarlez/sketch-frontend` builds on StreamIt's compiler frontend and IR,
verified directly: its AUTHORS file credits "the MIT StreamIt team"; the
live `sketch.compiler.*` tree carries StreamIt's grammar files
(`StreamItLex.g`, `StreamItParserFE.g`), classes named `StreamItParser`,
and comments like "data-flow analysis for the StreamIt front-end IR" with
StreamIt developers' `@author` tags; older trees and launcher scripts
still invoke the original `streamit.frontend.*` packages. A repo like this
defeats import-signature search the moment the packages are renamed. The
ecosystem harvests should therefore search **beyond import statements**:

1. **Namespace archaeology** — the original package/namespace strings
   survive in scripts, stack traces, generated token files, and old
   directories (`streamit.frontend`, `at.dms.kjc`).
2. **Grammar and IR fingerprints** — distinctive file and class names
   travel through renames (`StreamItLex.g`, `StreamItParserFE`,
   `SIRStream`/`SIRFilter` for StreamIt; equivalent lists per ecosystem).
3. **Provenance files** — AUTHORS/CREDITS/LICENSE naming the origin team,
   and origin-team email domains in `@author` tags (`cag.lcs.mit.edu`).
4. **Comment fingerprints** — prose like "a StreamIt program" inside
   source comments.
5. **The paper-side net** — a citing work classified `uses-tool` or
   `extends` at core centrality should trigger a repo lookup of *its*
   artifact regardless of code signatures; sketch-frontend is found this
   way from "Programming by sketching for bit-streaming programs", already
   StreamIt's top core citing work. Note the queued idea-descendants task
   filters on extends/adopts-idea only — **it should widen to include
   uses-tool at core**, or Sketch-class descendants fall through.

## 8. Recommendation

Option B. It is the only option that satisfies both halves of the
constraint — twin per-paper selectors, one seamless page surface — and it
adds no new interface vocabulary: the Repositories panel is the Citations
panel with tiers for categories and stars for citations. Data contract
follows the citations pattern (`data/repos/SCHEMA.md`, an index for
counts, per-paper files, lazy load, versioned assets) once repo-verify and
repo-ecosystems produce the inputs.
