# repos lane — step 1: in-paper repository discovery

Finds the code-host URLs the papers themselves print, and checks whether they
still resolve. **No GitHub searching happens here** — that is step 2, and the
keyword candidates for it are prepared in `search-plan.json`.

## Outputs

| File | What it holds |
|---|---|
| `mentions.json` | every `bibtexKey` → `{urls: [{url, status, context_line, …}]}`. All 327 entries appear; 268 have an empty list. |
| `mentions-unmapped-pdfs.json` | hits from PDFs in `papers/` that no `publications.json` entry points at (slides, arXiv copies), with the entry they belong to by hand. |
| `mentions-pruned-variants.json` | candidates dropped as PDF-layout artifacts, each with the reason and the URL that explains it. Audit trail — read this before trusting a "no repo" verdict. |
| `search-plan.json` | one record per paper with no live repo URL: author surnames, username guesses, lab orgs seen elsewhere in the corpus, project/software names, plausible repo spellings. Input to step 2. |
| `_candidates.json`, `_urlcache.json`, `_repairs.json` | intermediates. The URL cache makes re-runs free; delete it to re-check liveness. |

`status` is the HTTP status of a GET, or `"error:…"` when the host did not
answer. `final_url` is present only when the request was redirected — that is
how repo renames show up (`willow-ahrens/Finch.jl` → `finch-tensor/Finch.jl`).

## Pipeline

    python3 harvest/repos/extract_candidates.py   # pypdf over all 353 PDFs (~6 min)
    python3 harvest/repos/verify.py               # GET each unique URL, cache the verdict
    python3 harvest/repos/repair.py               # retry layout-mangled URLs, trimmed back
    python3 harvest/repos/build_outputs.py        # join, prune artifacts, write the outputs

## Why the repair/prune steps exist

PDF text extraction mangles URLs in three reproducible ways, and each one
produces a candidate that would otherwise be reported as a dead link:

* **glue** — the next word or a footnote marker runs onto the end
  (`…/tensor-compiler/tacoProc`, `…/graphit127`);
* **wrap** — the URL breaks across lines, so it arrives truncated
  (`https://github.com/tensor-`) or with the break healed wrongly
  (`ARMsoftware/…` for `ARM-software/…`);
* **escapes** — a BibTeX `url` field leaks `%7B%22…%22%7D` around the link.

`extract_candidates.py` reads each page three ways (raw, de-hyphenated,
newline-collapsed) plus the PDF's own link annotations, so the true form is
almost always among the candidates. `repair.py` trims glue back to the longest
prefix that resolves — never at a `/`, since dropping a path segment turns a
broken link into a different, wronger one. `build_outputs.py` then drops any
dead candidate a live sibling explains. What survives as dead is a real dead
link, not a layout artifact.
