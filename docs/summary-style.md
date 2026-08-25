# Summary style — voice and assembly of the merged Summary

**Status: codifies the voice approved through the 9-paper pilot phase,
including every point of the human's critique feedback.** This document is
the single style reference for generating and reviewing the regenerable
part of a paper's Summary. If a generated text and this document disagree,
this document wins.

## 1. What a Summary is

One flowing block with three registers, rendered seamlessly:

1. **The paper** — the hand-written summary in `data/publications.json`.
   Scripts never touch it. Ever.
2. **The reception** — how the citing literature received the paper,
   generated into `data/citations/reception.json`, written to continue
   from the summary's final sentence.
3. **The repositories** — at the reception's close, one natural sentence
   accommodating the paper's software afterlife (its verified own repo,
   badged artifact, and — where the data warrants — its ecosystem),
   flowing from the reception the way the reception flows from the
   summary.

Storage keeps the registers separate so regeneration can never overwrite
hand-written prose. Papers with fewer than 3 judged external citations get
no reception at all — a paragraph about two citations is noise.

## 2. Voice (rulings, in force)

- Academic and understated. Declarative, concrete, plain words. Short-to-
  medium sentences. Describe, then connect to predecessors and successors.
- **No superlatives or hype.** Banned outright: seminal, groundbreaking,
  landmark, influential, remarkable, pioneering, state-of-the-art, widely,
  highly, extremely — and any editorializing ("shaped the way a paper's
  should be").
- **Timeless phrasing.** Never anchor to the present: recently, currently,
  today, nowadays, to date, so far, newest, "continues to", "remains",
  "growing", "young". A reception is true whenever it is read.
- **No numeric citation counts in prose.** "Dozens of evaluations" — yes.
  "82 evaluations" — no. Counts live in the UI, not the paragraph.
- **KISS.** His recurring instruction. Trim qualifying clauses; when a
  sentence both overclaims and overexplains, delete rather than repair
  (the panel headline went from "1,483 citations — 1,483 verified and
  analyzed below" to "1,483 citations").

## 3. Truth rules

- **Grounding**: every named system, work, person, venue, or document type
  must be supported by the evidence pack. No invented facts, no invented
  co-citation patterns, no guessed document types ("theses"), no invented
  chronology ("later work" that predates the paper).
- **Honesty against the citation profile**: if exemplifies/passing
  dominate, do not imply deep engagement — "the deepest engagement comes
  from…" not "the record is dominated by…"; if most citations are
  unjudged, keep claims modest and say so plainly ("much of it unjudged");
  a thin record described honestly reads better than inflated prose.
- **COMMIT papers are not external reception.** Works with Saman among the
  authors (and clearly group-internal works generally) are "within the
  project", never evidence of outside adoption.
- **No writer-facing leakage**: instructions about how to write must never
  surface in the prose ("claims should stay modest", "a reception text can
  say so plainly").

## 4. The seam

The reception's opening continues the summary's final sentence — never
re-introduces the paper, never repeats a genealogy the summary just gave
(if the summary ends naming Tiramisu, the reception does not re-list
Tiramisu). Vary the construction; approved patterns include "Beyond the
project, the citing literature engaged …", "In the wider literature X
stands as …", "The citing literature treats the article mainly as …",
"Later work cites X as …", and the tightest of them, TOPLAS's "The step
was taken up." Do not reuse one opening more than twice in a wave.

## 5. The repository sentence

Where `harvest/repos/verified.json` has an own-group implementation repo
(confidence high/medium) and/or `harvest/artifacts/found.json` a badged
artifact, the reception closes with one natural sentence naming them —
the canonical repo by name ("the compiler lives on in bthies/streamit"),
the artifact by what it is ("an archival artifact accompanies the
paper"), the ecosystem only where tier-2 data exists. No stars, no counts,
no URLs in prose. Nothing verified → no sentence; never guess a repo.

## 6. Shape

- One paragraph, ~60–110 words, for most papers.
- Two paragraphs, ~150–200 words total, for papers with ≥300 judged
  external citations.
- Paragraphs separated by a blank line; no bullets, no headings.

## 7. Process (full-force rollout)

Waves of ~25 papers ordered by citation count descending. Every wave:
evidence pack (summary text, classification stats, top engaged citers,
verified repos, artifact, notable descendants) → Batch API generation →
reviewer pass against THIS document (grounding, seam, honesty, shape,
banned lists) → hand-fix weak texts → merge into `reception.json` → push.
**After wave 1, stop for the human's spot-check of ~10 before waves 2+.**
Pilot receptions are approved prose and are never regenerated by a wave.

## 8. The nine pilot exemplars

The approved corpus. Each entry shows the hand-written summary's final
sentence (the seam anchor) and the approved reception that follows it.

### halide:pldi:2013

*Summary ends:* “…Later systems that build on or use the compiler include OpenTuner, Distributed Halide, and Tiramisu.”

*Reception:*

> The wider citing literature engages the paper along two paths — through the compiler, and through the idea of separating an algorithm from its schedule — and the idea traveled further. TVM carried the compute/schedule separation into deep-learning compilation and became a lineage of its own — a meaningful share of the citations reach Halide only as TVM's ancestor — while T2S-Tensor and HeteroCL adapted the model to spatial hardware and FPGAs, and TACO's scheduling language generalized it to sparse iteration spaces. The compiler itself became shared research infrastructure: the automatic-scheduling literature, from tree-search and beam-search schedulers to Monte-Carlo tuners, treats Halide as its standard substrate, and verification work has targeted both its compiler and its scheduling rewrites.
>
> Beyond research descendants, Halide pipelines run in production imaging systems — synthetic depth-of-field on mobile phones among them — and imaging-DSP toolchains extend the compiler toward their own targets. The remaining citation mass is the signature of an idea that became vocabulary: several hundred works cite the paper as one item in lists of domain-specific compilers, or with a single sentence crediting the origin of the algorithm/schedule separation, without engaging the system itself.

### thies:cc:2002

*Summary ends:* “…A journal version appeared in IJPP 2005, and Thies's PhD thesis gives the most complete treatment.”

*Reception:*

> Beyond the project, the citing literature engaged both halves of the work. The compiler and its programs served as infrastructure across the field: sketching-based synthesis took bit-streaming StreamIt programs as its input domain, and a line of mapping work — partitioning streaming parallelism for multicores, software-pipelined execution on GPUs, Flextream's adaptive compilation, Sponge, and Optimus's synthesis to FPGAs — compiled or scheduled StreamIt programs onto nearly every parallel substrate of its era. Several manycore projects adopted the language outright as their input format.
>
> The paper's most distinctive afterlife belongs to its benchmark suite. Dozens of evaluations across compilers and architectures run on the StreamIt benchmarks — often through the STR2RTS refactoring, itself a paper about the suite — so the workloads outlived the compiler as the streaming community's shared reference set. In the surrounding literature the language appears as the canonical member of lists of streaming languages, alongside the dataflow work it descends from.

### taylor:micro:2002

*Summary ends:* “…The ISSCC 2003 paper presents the circuit-level implementation, the HPCA 2003 paper the operand network, the ISCA 2004 paper the full evaluation; Taylor's PhD thesis is the most complete treatment.”

*Reception:*

> In the wider literature Raw stands as the exemplar of the tiled microprocessor. Much of its influence is routed through descendants — the tiled-microprocessor line that followed it and the commercial many-core designs it led to — so a portion of the citing literature engages Raw's ideas through successor machines rather than the original. The fabricated chip also had a working life of its own: a 1020-node microphone-array beamformer, software-based instruction caching, and stream-algorithm studies used the Raw machine as their platform.
>
> A second, quieter pattern runs through the architecture literature: individual measurements from this paper became standing evidence. The fraction of chip resources consumed by the interconnect and the latencies of the scalar operand network are cited across a long line of network-on-chip papers as the motivating numbers for their designs. Beyond that, the paper appears wherever tiled architectures are enumerated — a fixture of the related-work paragraph that places any spatial architecture in context.

### amarasinghe:ijpp:2005

*Summary ends:* “…Thies's PhD thesis gives the most complete treatment of the language.”

*Reception:*

> The citing literature treats the article mainly as a point of reference for the StreamIt model: streaming systems describe it and set their own designs against it, with StreamPI among those that compare directly, and it appears as a member of the standard list of streaming languages. A smaller number of works reuse its kernels in their evaluations or borrow its design rationale for other domains. Its reception largely mirrors, at smaller scale, that of the conference paper it expands.

### petkov:ipdps:2002

*Summary ends:* “…Implemented in the Nimble Compiler and evaluated on signal-processing benchmarks, it achieves up to a 2x improvement in area efficiency over the best known techniques.”

*Reception:*

> In the citing literature the transformation survives as a name: works reference unroll-and-squash itself, usually in a sentence crediting it as a way to pipeline loops under resource constraints. The high-level-synthesis literature on loop pipelining places it among the transformations it builds past, and signal-processing implementations on FPGAs apply it to their kernels. The record is nearly all differentiation and technique credit rather than reuse of an artifact — the reception of a transformation that entered the compiler vocabulary and is engaged wherever loop pipelining is surveyed.

### thies:toplas:2007

*Summary ends:* “…The retitling — a 'step towards' unifying — keeps the claim deliberately modest: automating the optimal parallelism-storage compromise is framed as a first step.”

*Reception:*

> The step was taken up. The storage-optimization literature treats the affine unified occupancy vector as a formal object to build on: the lattice-based memory-allocation line generalized it explicitly — extended lattice-based allocation subsumes occupancy vectors among its unified inputs — and the intra-array storage-optimization work that followed positions its contributions against this framework. Its ideas also reappear in polyhedral treatments of sparse code generation. The citations are few and concentrated in one community, but almost all of them are substantive: this is a paper cited by the people extending its mathematics.

### levison:istas:2002

*Summary ends:* “…The paper is a companion version of the TEK system papers: the WWW 2002 paper describes the same system in full technical detail, and the Development by Design workshop paper of 2001 is the earliest form of the work.”

*Reception:*

> Later work cites TEK as a predecessor system in the line of research on web access under constrained connectivity. The ICT-for-development systems that followed — RuralCafe, COCO, Samvidha, and low-bandwidth search designs among them — describe its asynchronous, email-carried search model and position their own architectures against it, and the paper appears in broader accounts of rural networking and the digital divide as an early example of designing services for intermittent connections. The citation record is small and specific: nearly every citing work is itself a system in the same problem space.

### netblocks-pldi24

*Summary ends:* “…SPAC (FCCM 2026) carries the protocol work into FPGA-based switches using NetBlocks-compatible syntax, a unified Kubernetes DSL (xSIG 2026) drives its generator for inter-container communication, and Brahmakshatriya’s PhD thesis (2025) gives the most complete treatment.”

*Reception:*

> External citations are substantive rather than incidental: work on RPC communication for microservices builds on its staged approach to custom host network stacks, and the staged-programming and network-function literatures name it among the systems that generate specialized packet-processing code. The pattern, at small scale, is descent rather than mention: the works that cite it are the ones building on it.

### Kjolstad:2017:TTG:3155562.3155683

*Summary ends:* “…The same tool suite is presented to a French audience in an AVANCÉES article, and Kjolstad's PhD thesis gives the most complete treatment of the taco system.”

*Reception:*

> Among citing works the tool paper serves as the citation for taco as an artifact, usually alongside the OOPSLA paper that supplies its theory. Its most common substantive role is as the system to measure against: the Capstan accelerator, SMASH, and a sparse tensor algebra compiler in MLIR take taco-generated kernels as their baseline, and SparseCore builds outward from it toward processor specialization for sparse computation. Others run the tool — SparseP, a closeness-centrality-based circuit partitioner for quantum simulations, CATBench as a compiler-autotuning benchmark — and Sparseloop carries its ideas into sparse accelerator modeling. The remainder is list membership among sparse tensor compilers.
