#!/usr/bin/env python3
"""Extend the OpenAlex abstract harvest from the 8 pilot papers to every
citing work across harvest/citations/*.json (task `abstracts-all`).

Same output shape and convention as harvest_abstracts.py (one file per key
under harvest/fulltext/abstracts/<bibtexKey>.json, keyed by slug), but
batch-fetched 100 ids per request (`works?filter=openalex_id:W..|W..`, then
`filter=doi:..|..` for doi-only records) rather than one work per request --
at corpus scale (21,563 non-pilot citing works) the one-by-one approach
would take hours; this takes minutes. Records with neither id get
status "no_id" and are not queried. Idempotent: a slug already present in
the output file (any status) is skipped unless --refresh.

Stdlib only.

    python3 harvest/fulltext/harvest_abstracts_all.py
    python3 harvest/fulltext/harvest_abstracts_all.py --key waingold:computer:1997
"""
import argparse
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
CITATIONS_DIR = os.path.join(ROOT, "harvest", "citations")
OUT_DIR = os.path.join(HERE, "abstracts")

sys.path.insert(0, HERE)
from harvest_abstracts import invert_abstract  # noqa: E402

sys.path.insert(0, os.path.join(ROOT, "harvest", "citations"))
from harvest_citations import Fetcher, MAILTO  # noqa: E402


def chunks(seq, n):
    seq = list(seq)
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def norm_doi(doi):
    d = (doi or "").strip().lower()
    for p in ("https://doi.org/", "http://doi.org/", "doi:"):
        if d.startswith(p):
            d = d[len(p):]
    return d


def slug_for(citing):
    doi = citing.get("doi")
    if doi:
        import re
        return re.sub(r"[^a-z0-9._-]", "_", doi.lower())
    oa = citing.get("openalex")
    if oa:
        return "oa-" + oa.rsplit("/", 1)[-1]
    s2 = citing.get("s2")
    if s2:
        return "s2-" + s2[:16]
    import hashlib
    h = hashlib.sha1((citing.get("title") or "").encode("utf-8")).hexdigest()[:16]
    return "noid-" + h


def fetch_openalex_batch(fetcher, attr, values, verbose):
    """attr is 'openalex_id' or 'doi'; returns {value_lower: work dict}."""
    out = {}
    batches = list(chunks(sorted(values), 100))
    for i, batch in enumerate(batches):
        import urllib.parse
        url = "https://api.openalex.org/works?" + urllib.parse.urlencode({
            "filter": "%s:%s" % (attr, "|".join(batch)),
            "per-page": 100,
            "select": "id,doi,title,abstract_inverted_index",
            "mailto": MAILTO,
        })
        body = fetcher.get(url) or {}
        for w in body.get("results", []):
            if w.get("id"):
                out[w["id"].rsplit("/", 1)[-1].lower()] = w
            if w.get("doi"):
                out[norm_doi(w["doi"])] = w
        if verbose and (i + 1) % 10 == 0:
            print("  openalex %s: %d/%d batches" % (attr, i + 1, len(batches)), flush=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", action="append", help="restrict to this key (repeatable)")
    ap.add_argument("--refresh", action="store_true",
                    help="re-fetch even slugs already in the output file")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)

    citations_files = sorted(glob.glob(os.path.join(CITATIONS_DIR, "*.json")))
    per_key = {}
    for path in citations_files:
        key = os.path.basename(path)[:-5]
        if key.startswith("."):
            continue
        if args.key and key not in args.key:
            continue
        d = json.load(open(path))
        per_key[key] = d.get("citing") or []

    existing = {}
    for key in per_key:
        out_path = os.path.join(OUT_DIR, key + ".json")
        existing[key] = json.load(open(out_path)) if os.path.exists(out_path) else {}

    need_oa, need_doi = set(), set()
    for key, citing in per_key.items():
        for c in citing:
            slug = slug_for(c)
            if not args.refresh and slug in existing[key]:
                continue
            if c.get("openalex"):
                need_oa.add(c["openalex"])
            elif c.get("doi"):
                need_doi.add(norm_doi(c["doi"]))

    print("%d papers, %d citing works total; to fetch: openalex %d, doi-only %d"
          % (len(per_key), sum(len(v) for v in per_key.values()), len(need_oa), len(need_doi)))

    fetcher = Fetcher(verbose=args.verbose)
    works = {}
    works.update(fetch_openalex_batch(fetcher, "openalex_id", need_oa, args.verbose))
    works.update(fetch_openalex_batch(fetcher, "doi", need_doi, args.verbose))

    total_with_abstract = 0
    for key, citing in per_key.items():
        changed = False
        for c in citing:
            slug = slug_for(c)
            if not args.refresh and slug in existing[key]:
                continue
            doi = c.get("doi")
            oa = c.get("openalex")
            work = None
            if oa:
                work = works.get(oa.lower())
            if work is None and doi:
                work = works.get(norm_doi(doi))
            if not doi and not oa:
                existing[key][slug] = {
                    "doi": doi, "openalex": oa, "title": c.get("title"),
                    "abstract": None, "status": "no_id",
                }
            elif not work:
                existing[key][slug] = {
                    "doi": doi, "openalex": oa, "title": c.get("title"),
                    "abstract": None, "status": "openalex_lookup_failed",
                }
            else:
                abstract = invert_abstract(work.get("abstract_inverted_index"))
                existing[key][slug] = {
                    "doi": doi,
                    "openalex": oa or (work.get("id") or "").rsplit("/", 1)[-1],
                    "title": work.get("title") or c.get("title"),
                    "abstract": abstract,
                    "status": "ok" if abstract else "no_abstract",
                }
            changed = True
        if changed:
            out_path = os.path.join(OUT_DIR, key + ".json")
            tmp = out_path + ".tmp"
            with open(tmp, "w") as fh:
                json.dump(existing[key], fh, indent=1, sort_keys=True, ensure_ascii=False)
                fh.write("\n")
            os.replace(tmp, out_path)
            with_abstract = sum(1 for v in existing[key].values() if v.get("status") == "ok")
            total_with_abstract += with_abstract
            print("[%s] wrote %d entries, %d with an abstract" % (key, len(existing[key]), with_abstract))

    print("\nfetcher: %(cache)d cache hits, %(net)d network, %(retry)d retries, "
          "%(fail)d failures" % fetcher.stats)


if __name__ == "__main__":
    main()
