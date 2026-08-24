#!/usr/bin/env python3
"""Backfill `cited_by` (the citing work's own citation count) onto every
citing record in harvest/citations/<bibtexKey>.json.

Sources, in order:
  1. OpenAlex `cited_by_count`, batch-fetched 50 ids per request via
     `works?filter=openalex_id:W..|W..` for records with an OpenAlex id.
  2. The same, via `filter=doi:..|..` for records with a DOI but no
     OpenAlex id.
  3. Semantic Scholar `citationCount` via POST /graph/v1/paper/batch
     (500 ids per request) for records with only an S2 id.
Records with no id, and ids neither service resolves, get `cited_by: null`.

Idempotent: records that already carry a non-null `cited_by` are skipped
unless --refresh. Dry-run by default; --write to modify the files.
Feeds the citation view's popularity sort (data/citations/SCHEMA.md).
"""
import argparse
import glob
import json
import os
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harvest_citations import Fetcher, MAILTO, s2_key  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


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


def fetch_openalex(fetcher, attr, values, verbose):
    """attr is 'openalex_id' or 'doi'; returns {value_lower: count}."""
    out = {}
    batches = list(chunks(sorted(values), 50))
    for i, batch in enumerate(batches):
        url = "https://api.openalex.org/works?" + urllib.parse.urlencode({
            "filter": "%s:%s" % (attr, "|".join(batch)),
            "per-page": 50,
            "select": "id,doi,cited_by_count",
            "mailto": MAILTO,
        })
        body = fetcher.get(url) or {}
        for w in body.get("results", []):
            n = w.get("cited_by_count")
            if w.get("id"):
                out[w["id"].rsplit("/", 1)[-1].lower()] = n
            if w.get("doi"):
                out[norm_doi(w["doi"])] = n
        if verbose and (i + 1) % 20 == 0:
            print("  openalex %s: %d/%d batches" % (attr, i + 1, len(batches)))
    return out


def fetch_s2_batch(ids, verbose):
    """POST batches of 500; returns {s2_id: count}. Rate-limited like GETs."""
    out = {}
    key = s2_key()
    interval = 0.2 if key else 1.0
    batches = list(chunks(sorted(ids), 500))
    for i, batch in enumerate(batches):
        url = ("https://api.semanticscholar.org/graph/v1/paper/batch"
               "?fields=paperId,citationCount")
        payload = json.dumps({"ids": batch}).encode()
        headers = {
            "User-Agent": "commit-nextgen-citations/1.0 "
            "(https://github.com/mit-commit/nextgen; mailto:%s)" % MAILTO,
            "Content-Type": "application/json",
        }
        if key:
            headers["x-api-key"] = key
        for attempt in range(5):
            time.sleep(interval)
            try:
                req = urllib.request.Request(url, data=payload, headers=headers)
                with urllib.request.urlopen(req, timeout=60) as resp:
                    rows = json.loads(resp.read().decode("utf-8", "replace"))
                for r in rows:
                    if r and r.get("paperId"):
                        out[r["paperId"]] = r.get("citationCount")
                break
            except urllib.error.HTTPError as err:
                if err.code == 429 and attempt < 4:
                    delay = float(err.headers.get("Retry-After") or 0) or (2 ** attempt * 2)
                    if verbose:
                        print("  s2 batch 429, sleeping %.1fs" % delay)
                    time.sleep(min(delay, 60))
                    continue
                print("  s2 batch failed: HTTP %s" % err.code, file=sys.stderr)
                break
            except Exception as err:
                if attempt < 4:
                    time.sleep(2 ** attempt * 2)
                    continue
                print("  s2 batch failed: %s" % err, file=sys.stderr)
                break
        if verbose:
            print("  s2 batch %d/%d" % (i + 1, len(batches)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--refresh", action="store_true",
                    help="re-fetch even records that already have cited_by")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    files = {}
    need_oa, need_doi, need_s2 = set(), set(), set()
    for path in sorted(glob.glob(os.path.join(HERE, "*.json"))):
        try:
            d = json.load(open(path))
        except Exception:
            continue
        if not isinstance(d, dict) or "citing" not in d:
            continue
        files[path] = d
        for c in d["citing"]:
            if not args.refresh and c.get("cited_by") is not None:
                continue
            if c.get("openalex"):
                need_oa.add(c["openalex"])
            elif c.get("doi"):
                need_doi.add(norm_doi(c["doi"]))
            elif c.get("s2"):
                need_s2.add(c["s2"])
    print("files: %d | to resolve: openalex %d, doi-only %d, s2-only %d"
          % (len(files), len(need_oa), len(need_doi), len(need_s2)))

    fetcher = Fetcher(verbose=args.verbose)
    counts = {}
    counts.update(fetch_openalex(fetcher, "openalex_id", need_oa, args.verbose))
    counts.update(fetch_openalex(fetcher, "doi", need_doi, args.verbose))
    s2counts = fetch_s2_batch(need_s2, args.verbose)

    stats = {"set": 0, "null": 0, "kept": 0}
    for path, d in files.items():
        changed = False
        for c in d["citing"]:
            if not args.refresh and c.get("cited_by") is not None:
                stats["kept"] += 1
                continue
            val = None
            if c.get("openalex"):
                val = counts.get(c["openalex"].lower())
            if val is None and c.get("doi"):
                val = counts.get(norm_doi(c["doi"]))
            if val is None and c.get("s2"):
                val = s2counts.get(c["s2"])
            if c.get("cited_by") != val:
                changed = True
            c["cited_by"] = val
            stats["set" if val is not None else "null"] += 1
        if args.write and changed:
            tmp = path + ".tmp"
            with open(tmp, "w") as fh:
                json.dump(d, fh, indent=1)
                fh.write("\n")
            os.replace(tmp, path)

    print("cited_by set: %d, null: %d, already had: %d" %
          (stats["set"], stats["null"], stats["kept"]))
    print("fetcher: %(cache)d cache hits, %(net)d network, %(retry)d retries,"
          " %(fail)d failures" % fetcher.stats)
    if not args.write:
        print("dry run — no files written (use --write)")


if __name__ == "__main__":
    main()
