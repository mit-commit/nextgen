# Citation-function taxonomy — pilot draft (v0.1, for human review)

**Status: DRAFT.** Built and applied on the 8-paper pilot corpus only
(task `taxonomy-pilot`). Nothing here scales past the pilot until a human
has reviewed this document. Machine-readable classifications for every
citing work are in `harvest/taxonomy/pilot-classifications.json`.

---

## 1. What this is

For each pilot paper we classified every citing work (where evidence
permits) by **what the citation does** — does the citing work build on
ours, use our system, borrow our idea, compare against us, or just wave
at us in a related-work list? Raw citation counts treat all of these as
equal; they are not. This taxonomy is meant to drive the citation
section of the site: it distinguishes the ~10% of citations that
represent real intellectual descent from the ~60% that are list
membership, and it does so with per-judgment evidence provenance so a
reader (or a later pass) can audit any row.

**Pilot corpus** (8 papers, 4,629 citing-work records, 2,751 judged):

| pilot key | paper | citing records | judged (non-title-only) |
|---|---|---|---|
| `thies:cc:2002` | StreamIt: A Language for Streaming Applications | 1,652 | 1,012 |
| `halide:pldi:2013` | Halide (PLDI'13) | 1,706 | 1,145 |
| `taylor:micro:2002` | The Raw Microprocessor | 1,104 | 463 |
| `amarasinghe:ijpp:2005` | StreamIt/RAW language+machine (IJPP) | 91 | 69 |
| `petkov:ipdps:2002` | Unroll-and-squash | 41 | 32 |
| `thies:toplas:2007` | Affine unified occupancy vectors (TOPLAS) | 20 | 16 |
| `levison:istas:2002` | TEK (low-connectivity search) | 10 | 9 |
| `netblocks-pldi24` | NetBlocks | 5 | 5 |

Evidence per citing work, best-first: cached full text
(`harvest/fulltext/<key>/`, local only), else OpenAlex abstract
(`harvest/fulltext/abstracts/<key>.json`), else Semantic Scholar
citation contexts/intents (`harvest/citations/<key>.json`). Records with
none of these (title only) are **not judged** — they carry
`function: unclassified` in the output rather than a guess.

Method: (a) deep read of a stratified 111-row sample (seeded
`random.Random(42)`, quotas per pilot over influential /
non-influential / abstract-only strata, oversampling multi-context
rows) plus keyword-windowed reads of 15 cached full texts; (b) codebook
drafted from that sample; (c) full classification in 67 rendered
batches, every judgment recording evidence tier, context anchoring,
confidence, and a short justification note; (d) comparison against
Semantic Scholar's `isInfluential`/`intents` (§6).

---

## 2. Dimension 1 — FUNCTION

One primary value per citation. When a citing work does several things
(uses the tool *and* cites it in related work), the **highest-priority
value wins** and the rest go in `secondary`:

> `extends > uses-tool > adopts-idea > uses-benchmark > baseline >
> positions > surveys > supports-claim > exemplifies > mentions`

The order encodes "depth of dependence": building on the artifact
outranks running it, running it outranks borrowing its idea, any use
outranks any form of talking about it.

### 2.1 `extends` — builds on the cited artifact or technique

The citing work **modifies, extends, or incorporates** the cited
artifact/technique; the cited work is the substrate of their
contribution. Decision rule: if removing the cited system would leave
their contribution with nothing to be a contribution *to*, it is
`extends`. Includes formal generalizations of the cited technique.

- **TVM** (`s2-df013a17ab84d540`, OSDI'18, → halide:pldi:2013): "This
  layer *extends Halide's compute/schedule separation concept* by also
  separating target hardware intrinsics from transformation
  primitives" — the entire compiler stack is a Halide descendant, and
  says so five different ways.
- **STR2RTS** (`10.4230_oasics.wcet.2017.1`, → thies:cc:2002):
  "Refactored StreamIT Benchmarks into Statically Analyzable Parallel
  Benchmarks" — the paper's *contribution is a refactoring of the
  StreamIt suite itself*.
- **Distributed Halide** (`10.1145_2851141.2851157`, PPoPP'16, →
  halide:pldi:2013): "Until now, however, Halide has been restricted to
  parallel shared memory execution" — adds distributed-memory
  scheduling primitives to the Halide compiler. (Also `own-group`.)

### 2.2 `uses-tool` — runs the cited artifact as infrastructure

The citing work **employs the cited language/compiler/system** as
working infrastructure, unmodified or lightly configured. Rule vs.
`extends`: if their contribution *includes changing* the artifact →
`extends`; if the artifact is a consumed dependency → `uses-tool`.
Includes toolchains that take the cited language as their input format.

- **Onyx** (`10.1109_jssc.2025.3604724`, JSSC'25, → halide:pldi:2013):
  a 12-nm CGRA accelerator whose applications are *written in Halide
  and lowered through the Halide compiler* onto the chip.
- **CoreVA-MPSoC** (`s2-9bae6481cac22026`, → thies:cc:2002): their
  many-core's compiler *consumes StreamIt programs* as its input
  language across a multi-paper evaluation line.
- **Portrait mode** (`10.1145_3197517.3201329`, SIGGRAPH'18, →
  halide:pldi:2013): "Our code was implemented in Halide, then manually
  scheduled for the CPU" — Google's synthetic depth-of-field pipeline
  shipped on Pixel phones.

### 2.3 `adopts-idea` — imports the concept, not the artifact

The citing work **borrows the cited work's abstraction, formalism, or
design principle** without running its artifact. The classic case
across this corpus is Halide's algorithm/schedule decoupling, adopted
by systems that share no code with Halide. Rule vs. `uses-tool`:
concept in, code out.

- **CoCoNet** (`10.1145_3503222.3507778`, ASPLOS'22, →
  halide:pldi:2013): "Inspired by Halide, CoCoNet includes a scheduling
  language to specify an execution schedule" — for *distributed ML
  communication*, a domain Halide never touched.
- **SPECTRUM** (`10.1145_3400032`, → taylor:micro:2002): "MIT Raw …
  first to use compiler-scheduled flow control" — their software-defined
  many-core builds on Raw's static-scheduling principle, on new silicon.
- **TACO sparse scheduling** (`10.1145_3428226`, → halide:pldi:2013):
  "follows the scheduling language design pioneered by Halide … but
  generalizes those transformations for the first time to sparse
  iteration spaces."

### 2.4 `uses-benchmark` — uses the cited work's benchmarks/workloads

The citing work's **evaluation runs on benchmarks, applications, or
data the cited work introduced**, without using its system otherwise.

- **Cache-Integrated Network Interfaces** (`10.1007_s10766-011-0173-6`,
  → amarasinghe:ijpp:2005): FFT and bitonic-sort kernels "taken from
  the StreamIt suite" drive their CMP network-interface evaluation.
- **Enumo** (`10.1145_3622834`, → halide:pldi:2013): equality-saturation
  theory exploration whose flagship case study is *Halide's rewrite-rule
  grammar*, re-deriving 90% of the handwritten rules.
- **Warp-overlapped tiling** (`10.1145_3410463.3414649`, PACT'20, →
  halide:pldi:2013): six canonical image pipelines from the
  Halide-literature suite are the benchmark set (also compares to
  Halide → secondary `baseline`).

### 2.5 `baseline` — cited system is a compared alternative

The cited system appears **in the experiment section as a comparison
target** — numbers against numbers. Rule vs. `positions`: `baseline`
requires measured comparison, not prose differentiation.

- **Ansor** (`s2-09bda461aa4911d0`, OSDI'20, → halide:pldi:2013): "We
  let search frameworks (i.e., Halide auto-scheduler, FlexTensor,
  AutoTVM, and Ansor) run search … with up to 1,000 measurement trials."
- **StreamPI** (`10.1007_s11227-011-0656-7`, →
  amarasinghe:ijpp:2005): "We compared the performance of StreamPI with
  the StreamIt language and compiler framework."
- **Polyhedral multi-dim streaming** (`10.1145_3330999`, →
  thies:cc:2002): ran the StreamIt compiler head-to-head and reported
  its scaling limits.

### 2.6 `positions` — related-work differentiation

The citing work **describes the cited work's specifics and contrasts
its own contribution** against them. Requires an actual competing
contribution being differentiated — otherwise it's `surveys`,
`exemplifies`, or `mentions`. Includes "we don't compare against X
because…" statements and detailed limitation claims.

- **AutoSA** (`10.1145_3431920.3439292`, FPGA'21, → halide:pldi:2013):
  "the current Halide-based frameworks … only support rectangular
  domains" — a specific technical limitation motivating their polyhedral
  approach.
- **Darkroom** (`10.1145_2601097.2601174`, SIGGRAPH Asia'14, →
  halide:pldi:2013): "Halide's programming and scheduling models are
  more general than Darkroom, but as a result, automatically optimizing
  programs requires an expensive brute-force search."
- **τC** (`10.1016_j.procs.2014.05.099`, → amarasinghe:ijpp:2005):
  "does not define a new programming language (as done by StreamIt)" —
  design-decision contrast against the StreamIt model.

### 2.7 `surveys` — systematic descriptive cataloging

The citing work is a **survey, taxonomy, textbook chapter, or thesis
background section** that describes the cited work as part of a
systematic treatment — descriptive, not competitive.

- **Scheduling Language Chronology** (`10.1145_3743135`, →
  halide:pldi:2013): the field's history organized with Halide as the
  pivot event.
- **FPGA HLS Today** (`10.1145_3530775`, TRETS, → halide:pldi:2013):
  survey covering the whole Halide-HLS / HeteroHalide / T2S family.
- **CPSoC exemplar survey** (`s2-05f53fabc1b7d374`, →
  taylor:micro:2002): systematic per-architecture table row + paragraph
  describing RAW among self-aware SoCs.

### 2.8 `supports-claim` — cites a specific finding as evidence

The citing work **leans on a specific measurement, result, or
established fact** from the cited paper to support a claim of its own.
The distinctive test: a *number or finding* travels, not a system.

- **Deflection-NoC line** (`s2-aa97d9f856e51f27` and siblings, →
  taylor:micro:2002): "interconnect consumes … 36% in MIT RAW [20]" —
  the Raw power-breakdown figure as motivation, repeated across a whole
  family of NoC papers.
- **FlashAttention** (`10.52202_068431-1189`, NeurIPS'22, →
  halide:pldi:2013): cites Halide as evidence that IO-aware algorithms
  matter in memory-bound domains, and as the model for a future
  IO-aware attention compiler.
- **Tiramisu** (`10.1109_cgo.2019.8661197`, CGO'19, →
  halide:pldi:2013): "The use of a scheduling language has been shown
  effective … by multiple compilers including CHiLL, AlphaZ, and
  Halide" — Halide's success as evidence the approach works.

### 2.9 `exemplifies` — canonical example in a list/category

The cited work appears as **one member of a list of examples of a
category** ("DSLs such as Halide, TVM, TACO…"), possibly with a
one-clause gloss. Swap-out-able: replacing it with a peer would not
change the citing paper. This is the single largest judged class in the
corpus (677 rows).

- **BaCO** (`10.1145_3623278.3624770`, → halide:pldi:2013): "Prominent
  examples of this paradigm include Halide [42], TVM [7], TACO [47],
  and RISE & ELEVATE."
- **StreamPU** (`10.1002_cpe.7820`, → thies:cc:2002 and
  amarasinghe:ijpp:2005): member of "many languages dedicated to
  streaming applications [40]–[46]."
- **PL and HCI** (`10.1145_3469279`, CACM, → halide:pldi:2013): "the
  Halide project allows programmers to write in a high-level language,
  delegating the low-level scheduling details" — a success-story example
  in an essay, no engagement with specifics.

### 2.10 `mentions` — residual passing reference

Anything thinner than the above: pointer citations, definitional cites,
origin-credit one-liners, **secondhand citations** (citing Halide only
to say "TVM is based on Halide"), terminology mappings. The second
largest class (701 rows). The "secondhand" pattern is extremely common
for halide:pldi:2013 — 62 rows carry the `lineage` flag, most of them
citing Halide purely as TVM's ancestor.

- **ConCo** (`10.1145_3721145.3735113`, → halide:pldi:2013):
  "TVM extends Halide's scheduling primitives" — Halide cited only to
  describe TVM.
- **Stream Types** (`10.1145_3656434`, POPL, → thies:cc:2002): a
  history-of-streams pointer citation.
- **Scheduling of Iterative Algorithms** (`10.1007_s11265-006-0004-y`,
  → petkov:ipdps:2002): "Improvement by unroll-and-squash has been
  shown in [23]" — names the technique, engages no further.

### 2.11 `unknown` / `unclassified`

- `unknown` (292 rows): evidence exists but is insufficient — e.g. S2
  contexts that never anchor to the cited work (see `polluted-contexts`
  below), or an abstract that doesn't reach the citation's topic.
  Judged as "cannot tell", not silently guessed.
- `unclassified` (1,878 rows): title-only records; not judged at all.

---

## 3. Dimension 2 — CENTRALITY

How load-bearing the citation is for the citing work, judged
independently of (but informed by) function:

| value | definition |
|---|---|
| `core` | the citing work would be fundamentally different without the cited work — substrate, direct successor, the primary evaluation vehicle |
| `engaged` | specific engagement with the work's content (≥1 sentence about its specifics, eval use, detailed differentiation) short of dependency |
| `peripheral` | swap-out-able mention or list membership |
| `unknown` | cannot judge from available evidence |

Guidance used (defaults, overridable by evidence): `extends`/`uses-tool`
→ core; `adopts-idea` → core when the idea pervades the citing work,
else engaged; `uses-benchmark`/`baseline`/`positions` → engaged;
`surveys` → engaged (peripheral for a single table row);
`supports-claim`/`exemplifies`/`mentions` → peripheral.

Worked examples:
- **core**: TVM → Halide (the compiler is built on it); Taylor's own
  "Tiled microprocessors" thesis → Raw; STR2RTS → StreamIt.
- **engaged**: Ansor → Halide (head-to-head baseline); Darte et al.
  "Extended lattice-based memory allocation" → thies:toplas:2007
  (their framework is an explicit generalization of AUOV — a rare
  `extends`+engaged, since AUOV is one of several unified inputs);
  STeP → StreamIt (Table-1 differentiation).
- **peripheral**: BaCO → Halide (paradigm-example list); Stream Types →
  StreamIt (history pointer); "36% in MIT RAW" NoC papers → Raw
  (one number).

---

## 4. Flags, evidence tiers, confidence

**Flags** (multi-valued, per row):

| flag | meaning | count |
|---|---|---|
| `own-group` | author overlap with the pilot paper's authors — self-ecosystem citation, should be reported separately from external impact | 119 |
| `self-version` | the record *is* the pilot paper (or a same-work clone) indexed as citing itself; excluded from impact stats | 3 |
| `lineage` | engages the cited work via a successor/derived system (TVM for Halide, Tilera for Raw) rather than its own content | 62 |
| `polluted-contexts` | the S2 contexts attached to this record do not anchor to the cited work at all | 278 |
| `critical` | explicitly negative stance drives the citing work | 0 in pilot (limitation-driven rows all fit `positions`) |

**Evidence tier** per row (`fulltext` 85 / `abstract+contexts` 211 /
`contexts` 2,137 / `abstract` 318 / `title_only` 1,878) and **context
anchoring** (`named` — contexts name the work or system: 1,737;
`numref` — only bracket references: 510; `none`: 145). Anchoring drives
**confidence** (`high` 1,655 / `medium` 485 / `low` 319): named
contexts → high is possible; numref-only → medium at best unless the
sentence content pins the reference; abstract-only rows get a function
only when lineage is unambiguous (e.g. a CoreVA-MPSoC paper for
StreamIt), at confidence low, else `unknown`.

**Duplicate records.** The citing lists contain many same-work
duplicates (arXiv + DOI + venue clones under different ids). These were
labeled consistently (notes name their siblings) but are *not*
collapsed in `pilot-classifications.json` — each record keeps its own
row. Any counting for display should dedupe first; the notes provide
the pairs.

---

## 5. What the pilot corpus looks like

Function distribution over **judged** rows (self-versions included;
percentages of judged non-unknown rows):

| function | thies:cc:2002 | halide:pldi:2013 | taylor:micro:2002 | small pilots (5) | total |
|---|---|---|---|---|---|
| extends | 44 | 40 | 10 | 5 | 99 |
| uses-tool | 55 | 87 | 22 | 1 | 165 |
| adopts-idea | 36 | 97 | 22 | 6 | 161 |
| uses-benchmark | 85 | 26 | 2 | 3 | 116 |
| baseline | 4 | 23 | 1 | 2 | 30 |
| positions | 126 | 139 | 31 | 42 | 338 |
| surveys | 36 | 19 | 25 | 2 | 82 |
| supports-claim | 6 | 13 | 63 | 8 | 90 |
| exemplifies | 271 | 249 | 132 | 25 | 677 |
| mentions | 248 | 372 | 59 | 22 | 701 |
| **judged** | **911** | **1,065** | **367** | **116** | **2,459** |
| unknown (within judged) | 101 | 80 | 96 | 15 | 292 |
| unclassified (title-only) | 640 | 561 | 641 | 36 | 1,878 |

Centrality over judged rows: core 221 (9%), engaged 472 (19%),
peripheral 1,760 (72%).

Reading of the numbers, per pilot:

- **halide:pldi:2013** has the healthiest "descent" profile: 224 rows
  (21% of judged) are use-class (`extends`+`uses-tool`+`adopts-idea`),
  including an entire compiler genus (TVM/TC/HeteroCL/AKG via
  `lineage`), a hardware ecosystem (AHA/CGRA flows compiling Halide),
  and an auto-scheduling research industry that treats Halide as its
  experimental substrate. Its noise profile is distinctive too: a large
  `mentions` mass exists *because* the idea won — hundreds of papers
  cite it only as "the origin of compute/schedule separation" or
  through TVM.
- **thies:cc:2002** (StreamIt) shows the *benchmark-suite* pattern:
  `uses-benchmark` (85) is far larger than for any other pilot — the
  StreamIt benchmark suite outlived the compiler as the community's
  shared workload set (often via the STR2RTS refactoring, itself an
  `extends`).
- **taylor:micro:2002** (Raw) shows the *number-that-travels* pattern:
  `supports-claim` (63) dominated by two figures (interconnect ≈36–40%
  of chip power; scalar operand network latencies) cited by a decade of
  NoC papers, plus a heavy `exemplifies` mass ("tiled architectures
  e.g. Raw"). Much of its influence is routed through successors
  (Tilera) → `lineage`.
- **petkov:ipdps:2002** and **thies:toplas:2007** are small but almost
  entirely *technique* citations: the ElasticFlow HLS line credits and
  supersedes unroll-and-squash (`positions`, origin-credit), and the
  storage-optimization literature treats AUOV as the formal object to
  generalize (`extends`/`positions` by Darte et al.).
- **levison:istas:2002** (TEK) is cited by the ICTD lineage
  (RuralCafe, Samvidha, COCO) as the predecessor system — nearly all
  `positions` at abstract-only evidence.
- **netblocks-pldi24** is young: 5 records, 2 of them the paper's own
  arXiv/ACM clones (`self-version`), but both real citations are
  substantive (a HotOS'25 position paper *building on* NetBlocks'
  abstractions, and a staged-programming list mention).

**Evidence-tier caveats.** 41% of all records are title-only and
unjudged — these skew old (pre-OpenAlex-abstract era) and toward
non-OA venues, so *the judged sample under-represents 1990s–2000s
citing literature*, most severely for taylor:micro:2002 (58%
unjudged). Judgments at tier `contexts` depend on S2's snippet
extraction: 10% of judged rows are flagged `polluted-contexts`. All
distribution numbers above should be read as "of what we can see", not
of the full citation graph.

---

## 6. Comparison with Semantic Scholar (`isInfluential` / `intents`)

Comparable rows: 2,316 judged rows carry an S2 `isInfluential` verdict;
1,858 carry non-empty `intents`.

### 6.1 `isInfluential` vs. centrality

| my centrality | n | S2 infl=True | rate |
|---|---|---|---|
| core | 203 | 79 | 39% |
| engaged | 444 | 183 | 41% |
| peripheral | 1,666 | 64 | **4%** |

- **Agreement**: the signal is real but coarse. S2's flag is strongly
  *anti-correlated with peripherality* (4% base rate) — as a filter for
  "not a list mention" it works. P(core-or-engaged | infl=True) =
  262/326 = 80%.
- **Disagreement, direction 1 — S2 misses real dependence**:
  P(infl | core) is only 39%. **124 rows we judge `core` carry
  infl=False**, including unambiguous cases: *End-to-end translation
  validation for the Halide language* (`10.1145_3527328` — the whole
  paper verifies Halide's compiler), *Accelerating AI Applications with
  Sparse Matrix Compression in Halide* (`10.1007_s11265-022-01821-z` —
  Halide is in the title), the Halide GPU auto-scheduler
  (`10.1145_3485486`, by Halide's own authors), Onyx
  (`10.1109_jssc.2025.3604724`), and Google's portrait-mode paper.
  S2's flag appears driven by in-text citation frequency/position and
  systematically misses works whose dependence is *total but quietly
  cited* (the system is the substrate, so the paper cites it once and
  moves on).
- **Disagreement, direction 2 — S2 over-fires on incidental cites**:
  64 peripheral rows carry infl=True. Recurring patterns: class-list
  exemplars (*BuildIt* `10.1109_cgo51591.2021.9370333`, warp-level
  primitives `10.1109_cgo.2019.8661187`), Relay's secondhand
  TVM-ancestry cites (`s2-82995a95781ef5b9`), and whole-proceedings /
  garbage records (the ELS 2016 proceedings volume,
  `s2-51a811aeaaf396f6`). For Raw, S2 flagged a Memcached-on-TILEPro64
  power study (`10.1016_j.suscom.2012.01.006`) that engages Tilera, not
  Raw.
- Conclusion for design: **use `isInfluential` as a cheap recall aid,
  never as ground truth** — it misses ~60% of substrate-level
  dependence and its precision at the top is ~80% only after our
  dedup/pollution cleanup.

### 6.2 `intents` vs. function

Mapping used: use-class functions → expect `methodology`;
`adopts-idea` → `methodology|background`; `positions`/`surveys`/
`exemplifies`/`mentions` → `background`; `supports-claim` →
`result|background`. Overall overlap agreement: **71%** (1,319/1,858).

- Where S2 tags `methodology` (n=911), only **34%** of those rows fall
  in our use-class. The bulk are `exemplifies` (213) and `mentions`
  (194): S2 assigns `methodology` to any citation appearing in a
  methods-ish section, including pure list mentions. Conversely, of our
  use-class rows, 72% do get a `methodology` tag — so as a *recall*
  signal for "uses/extends" it is decent, as *precision* it is ~3×
  diluted.
- `intents` has no value at all distinguishing `extends` from
  `uses-benchmark` from `baseline` — the distinctions this corpus's
  story actually needs (STR2RTS vs. StreamPI vs. a list mention are
  three different relationships; S2 renders all three as
  `methodology`).
- `result` intent is nearly absent (28 rows total) and does not align
  with our `supports-claim` (which S2 mostly tags `background`).

---

## 7. Known limitations / open questions for review

1. **Single-annotator labels.** Every judgment is one model pass over
   the rendered evidence; there is no inter-annotator agreement number.
   The 111-row deep-read sample and the per-row notes are the audit
   trail. A human spot-check of, say, 50 rows stratified over
   function × confidence would calibrate error rates before scaling.
2. **`exemplifies` vs. `mentions` boundary** is the fuzziest in
   practice (list-with-gloss vs. bare pointer). If the site only needs
   a coarser "substantive vs. peripheral" cut, these two can be merged
   without loss.
3. **`adopts-idea` centrality** required the most judgment (core when
   pervasive, engaged otherwise); reviewers should check whether the
   TVM-style cases (labeled `extends`) vs. CoCoNet-style cases
   (labeled `adopts-idea`) match their intuition of the boundary.
4. **Duplicates are labeled, not collapsed** (§4). Decide the dedup
   policy (probably: fold by title-normalized key, keep the
   highest-evidence sibling) before computing any public-facing counts.
5. **Coverage bias** (§5): title-only rows are unjudged and skew old;
   any per-decade claims need the abstract-era caveat.
6. **The 5 small pilots show the taxonomy transfers** beyond
   compiler-systems papers (TEK's ICTD lineage classifies cleanly),
   but n is tiny; a non-systems pilot (e.g. a bioinformatics paper)
   would be the right next stress test.

## 8. Reproducibility

- Output: `harvest/taxonomy/pilot-classifications.json` — one row per
  citing-work record: `{pilot, slug, function, centrality, flags[],
  secondary[], confidence, evidence, anchored, note?, title, year,
  s2_isInfluential, s2_intents}`. Slugs are `harvest_fulltext.py`'s
  slug scheme, joining against `harvest/citations/<key>.json` (by DOI /
  OpenAlex / S2 id) and `harvest/fulltext/abstracts/<key>.json`
  (directly).
- All working artifacts (evidence index, stratified sample, 67 rendered
  evidence batches, per-batch label files, reconciliation + comparison
  scripts) live in the session scratchpad; the reconciliation confirmed
  every non-title record carries exactly one label and every label
  matches a manifest row.
