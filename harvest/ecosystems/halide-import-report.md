# Halide-world import for `halide:pldi:2013`

Source: `samanamarasinghe/Halide-world`'s `data/site/halide-index.json` (schema_version 1,
822 repos / 1795 citing
papers indexed corpus-wide). Mapped, not re-judged -- every verdict, star
count, and evidence string here is Halide-world's own.

## Tier-2 (repositories with Halide in them -- ecosystem users)

Imported **567** real code-level rows (verdict
consumer/generator/uses_source -> `uses`, halide_copy_or_fork -> `builds-on`).

Deliberately excluded:
- **2828** `third_party_bundle` rows (Halide arrived only
  inside a vendored third-party dependency -- real signal, but importing all of them
  into one paper's panel would swamp it; available in the source index's `lane_a`/
  `lane_b_classified` pools if a future pass wants a capped, star-sorted subset).
- **67** `prose_only` rows (no real code integration).
- **188** rows with no verdict at all (pre-curation).

**567 rows is a large single-paper ecosystem** -- comparable in scale to
the outside-user hunts the round-7 strategy flagged as needing explicit human
approval before going live (e.g. dynamorio). Recommend the same here: this file is
staged in `harvest/ecosystems/`, not `data/repos/`, until a human has seen the count
and the site-citations lane decides how (or whether) to render all 567 at
once vs. a capped/sorted view.

## Tier-3 (idea-descendants: citing works with their own repo)

**162** rows, from **130**
citing papers linked to the `pldi2013-halide` anchor that published their own artifact repo
(of 1225 citing papers total). A further **237** citing papers only
*mention* another repo without publishing their own -- left out, matching this corpus's
own idea-descendants rule that a bare mention is not a located descendant.

This tier is a much more modest addition (same order of magnitude as this corpus's own
idea-descendants waves) and is reasonable to fold into `data/repos/papers/halide:pldi:2013.json`
directly, gated only on the usual dedup-against-existing-rows step.

## Confirms

Before this import, `data/repos/papers/halide:pldi:2013.json` had 0 rows attributed to
Halide-world -- its only tier-3 rows (8, group `adopts`) came from this corpus's own
generic `curate/build_idea_descendants.py` pass, and it had no tier-2 rows at all. Per
the round-4 spec ("import... do not re-harvest or re-judge... attribute the source"),
this was the gap task `halide-import` asked to close.
