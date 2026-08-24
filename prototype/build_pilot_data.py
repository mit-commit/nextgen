#!/usr/bin/env python3
"""Build data/citations/<key>.json for the pilot papers from the taxonomy output.

Reference implementation of data/citations/SCHEMA.md. The corpus-wide merge
script (classify-corpus task) must emit the same shape from its staging
records; this script covers the 8 pilot papers, whose judgments live in
harvest/taxonomy/pilot-classifications.json instead.

Applies the human dedup ruling: fold same-work records by normalized title,
keep the highest-evidence sibling. Excludes self-version records entirely.

Usage: python3 prototype/build_pilot_data.py [--keys k1,k2,...] [--write]
Dry-run by default (prints counts); --write writes data/citations/ files and
refreshes the pilot rows of data/citations/index.json.
"""
import argparse
import hashlib
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EVIDENCE_RANK = {"fulltext": 4, "abstract+contexts": 3, "contexts": 2,
                 "abstract": 1, "title_only": 0}

# Top-level split: which FUNCTION values count as detailed engagement vs
# passing mention. Documented (and reviewable) in data/citations/SCHEMA.md.
DETAILED = {"extends", "uses-tool", "adopts-idea", "uses-benchmark",
            "baseline", "positions", "surveys", "supports-claim",
            "detailed-citation"}
PASSING = {"exemplifies", "passing-citation"}
FUNCTION_ORDER = ["extends", "uses-tool", "adopts-idea", "uses-benchmark",
                  "baseline", "positions", "surveys", "supports-claim",
                  "exemplifies", "detailed-citation", "passing-citation",
                  "unknown", "unclassified"]


def slug_for(citing):
    doi = citing.get("doi")
    if doi:
        return re.sub(r"[^a-z0-9._-]", "_", doi.lower())
    oa = citing.get("openalex")
    if oa:
        return "oa-" + oa.rsplit("/", 1)[-1]
    s2 = citing.get("s2")
    if s2:
        return "s2-" + s2[:16]
    h = hashlib.sha1((citing.get("title") or "").encode("utf-8")).hexdigest()[:16]
    return "noid-" + h


def norm_title(t):
    return re.sub(r"[^a-z0-9]+", "", (t or "").lower())


def is_saman(name):
    """True iff this author name is Saman Amarasinghe (drives the COMMIT-papers
    separation; see SCHEMA.md). Handles 'Saman', 'Saman P.', and 'S.' forms,
    including glued PDF-extraction artifacts, while excluding other
    Amarasinghes (Gayashan, Yasith, ...)."""
    n = re.sub(r"[^a-z]+", " ", (name or "").lower()).strip()
    if "amarasinghe" not in n:
        return False
    return "saman" in n or bool(re.search(r"(^| )s (p )?amarasinghe", n))


def authors_short(names):
    names = [n for n in (names or []) if n]
    if not names:
        return None
    if len(names) > 3:
        return ", ".join(names[:3]) + " et al."
    return ", ".join(names)


def link_for(citing):
    if citing.get("doi"):
        return "https://doi.org/" + citing["doi"]
    if citing.get("openalex"):
        oa = citing["openalex"]
        return oa if oa.startswith("http") else "https://openalex.org/" + oa
    if citing.get("s2"):
        return "https://www.semanticscholar.org/paper/" + citing["s2"]
    return None


def split_of(function):
    if function in DETAILED:
        return "detailed"
    if function in PASSING:
        return "passing"
    return None  # unknown / unclassified


def build_paper(key, tax_rows, citing_list):
    citing_by_slug = {slug_for(c): c for c in citing_list}
    records = []
    for r in tax_rows:
        c = citing_by_slug.get(r["slug"], {})
        records.append((r, c))

    # Dedup: group by normalized title, keep the highest-evidence sibling.
    # Records with no title can't be folded — each is its own group by slug.
    groups = {}
    for r, c in records:
        gk = norm_title(r.get("title") or c.get("title")) or "slug:" + r["slug"]
        groups.setdefault(gk, []).append((r, c))

    entries = []
    n_commit = 0
    n_self_groups = 0
    for _, sibs in groups.items():
        flags = sorted(set(f for r, _ in sibs for f in r["flags"]))
        if "self-version" in flags:
            n_self_groups += 1
            continue  # the paper itself, indexed as citing itself
        sibs.sort(key=lambda rc: (
            EVIDENCE_RANK.get(rc[0]["evidence"], 0),
            rc[0]["function"] not in ("unknown", "unclassified"),
            bool(rc[1].get("doi")),
            rc[0]["slug"],
        ), reverse=True)
        r, c = sibs[0]
        # fill bibliographic fields from any sibling if the kept one lacks them
        for _, c2 in sibs[1:]:
            for f in ("doi", "venue", "authors", "openalex", "s2"):
                if not c.get(f) and c2.get(f):
                    c = dict(c)
                    c[f] = c2[f]
        e = {"title": r.get("title") or c.get("title") or "Untitled",
             "function": r["function"],
             "split": split_of(r["function"])}
        cb = [c2.get("cited_by") for _, c2 in sibs if c2.get("cited_by") is not None]
        e["cited_by"] = max(cb) if cb else None
        if any(is_saman(a) for _, c2 in sibs for a in (c2.get("authors") or [])):
            e["commit"] = True
            n_commit += 1
        if r.get("year") or c.get("year"):
            e["year"] = r.get("year") or c.get("year")
        for src, dst in ((c.get("venue"), "venue"),
                        (authors_short(c.get("authors")), "authors"),
                        (link_for(c), "url")):
            if src:
                e[dst] = src
        if r["function"] not in ("unknown", "unclassified"):
            e["centrality"] = r["centrality"]
            e["confidence"] = r["confidence"]
        if r.get("secondary"):
            e["secondary"] = r["secondary"]
        if flags:
            e["flags"] = flags
        e["evidence"] = r["evidence"]
        entries.append(e)

    forder = {f: i for i, f in enumerate(FUNCTION_ORDER)}
    entries.sort(key=lambda e: (forder.get(e["function"], 99),
                                -(e.get("year") or 0), e["title"].lower()))
    judged = sum(1 for e in entries if e["split"] is not None)
    return {
        "schema": 1,
        "key": key,
        "generated": None,  # filled by caller
        "codebook": "0.2",
        "counts": {
            "records_raw": len(tax_rows),
            "works": len(entries),          # deduped, self-version excluded
            "commit": n_commit,             # Saman-authored citing works
            "judged": judged,
            "gscholar": None,               # filled from gscholar.json
        },
        "citations": entries,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keys", default="halide:pldi:2013,netblocks-pldi24")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--generated", default="2026-08-24")
    args = ap.parse_args()
    keys = [k.strip() for k in args.keys.split(",") if k.strip()]

    tax = json.load(open(os.path.join(ROOT, "harvest/taxonomy/pilot-classifications.json")))
    gs_path = os.path.join(ROOT, "data/citations/gscholar.json")
    gscholar = json.load(open(gs_path)) if os.path.exists(gs_path) else {}
    rec_path = os.path.join(ROOT, "data/citations/reception.json")
    reception = json.load(open(rec_path)) if os.path.exists(rec_path) else {}
    out_dir = os.path.join(ROOT, "data/citations")
    index_path = os.path.join(out_dir, "index.json")
    index = (json.load(open(index_path)) if os.path.exists(index_path)
             else {"schema": 1, "generated": None, "papers": {}})

    for key in keys:
        tax_rows = [r for r in tax["rows"] if r["pilot"] == key]
        if not tax_rows:
            raise SystemExit(f"no taxonomy rows for {key}")
        citing = json.load(open(os.path.join(ROOT, f"harvest/citations/{key}.json")))["citing"]
        paper = build_paper(key, tax_rows, citing)
        paper["generated"] = args.generated
        gs = (gscholar.get(key) or {}).get("count")
        paper["counts"]["gscholar"] = gs
        if reception.get(key):
            paper["reception"] = reception[key]
        # External judged function counts: feed the page-level impact score
        # and aggregate overview without loading the per-paper file.
        fn_counts = {}
        cent_counts = {}
        for e in paper["citations"]:
            if e["split"] and not e.get("commit"):
                fn_counts[e["function"]] = fn_counts.get(e["function"], 0) + 1
                c = e.get("centrality")
                if c in ("core", "engaged", "peripheral"):
                    cent_counts[c] = cent_counts.get(c, 0) + 1
        index["papers"][key] = {
            "verified": paper["counts"]["works"],
            "gscholar": gs,
            "functions": fn_counts,
            "centrality": cent_counts,
        }
        c = paper["counts"]
        print(f"{key}: raw={c['records_raw']} works={c['works']} "
              f"commit={c['commit']} judged={c['judged']} gscholar={gs}")
        if args.write:
            with open(os.path.join(out_dir, key + ".json"), "w") as f:
                json.dump(paper, f, indent=1)
                f.write("\n")
    index["generated"] = args.generated
    if args.write:
        os.makedirs(out_dir, exist_ok=True)
        with open(index_path, "w") as f:
            json.dump(index, f, indent=1)
            f.write("\n")
        print("wrote", out_dir)


if __name__ == "__main__":
    main()
