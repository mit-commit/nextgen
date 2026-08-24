#!/usr/bin/env python3
"""Harvest citing-work metadata for every data/idmap.json entry with an
OpenAlex or Semantic Scholar id.

Two independent passes over harvest/citations/<bibtexKey>.json:

  --pass openalex   Pages OpenAlex `works?filter=cites:<id>` (cursor
                     pagination) for every entry with an openalex id and
                     writes the file fresh:

                         {"counts": {"openalex": <n>, "s2": 0},
                          "citing": [{"title", "year", "doi", "openalex",
                                      "s2": null, "venue", "authors",
                                      "isInfluential": null, "intents": null,
                                      "contexts": null}, ...]}

                     Skips a bibtexKey whose file already exists -- this
                     pass never touches a file the s2 pass has enriched.

  --pass s2          For every entry with an s2 id, pages Semantic Scholar
                     `/paper/<id>/citations` (offset pagination; fields
                     include isInfluential, intents, contexts) and merges
                     the results into the *existing* file by DOI, filling in
                     `s2`, `isInfluential`, `intents`, `contexts` on matched
                     records and appending s2-only records otherwise.
                     Requires the openalex pass to have written the file
                     first. Completion per bibtexKey is tracked in
                     harvest/citations/.s2_state.json, separately from the
                     file's existence, so a merge that fails partway (e.g. a
                     429 exhausts retries) is retried whole on the next run
                     instead of being silently marked done.

No PDFs are fetched -- metadata only.

Reads OPENALEX_API_KEY / S2_API_KEY from the environment on every request
(not just at startup), so a long-running `--pass s2` process picks up a key
added to its own environment without a restart -- though note this is a
process-level os.environ read: exporting the key in a *different* shell has
no effect on an already-running process; restart it to pick up a key set
elsewhere. Without a key, both APIs are polled at 1 request/second with
429/5xx backoff.

Stdlib only.

    python3 harvest/citations/harvest_citations.py --pass openalex
    python3 harvest/citations/harvest_citations.py --pass s2
    python3 harvest/citations/harvest_citations.py --report
    python3 harvest/citations/harvest_citations.py --pass openalex --limit 5
"""

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
IDMAP = os.path.join(ROOT, "data", "idmap.json")
OUTDIR = HERE
CACHE = os.path.join(HERE, "cache")

MAILTO = "samana@mit.edu"

OPENALEX_PAGE = 200
S2_PAGE = 100
MAX_PAGES = 200  # sanity cap: 40k openalex / 20k s2 citations per paper


def openalex_key():
    return os.environ.get("OPENALEX_API_KEY", "").strip()


def s2_key():
    return os.environ.get("S2_API_KEY", "").strip()


# ------------------------------------------------------------------- fetching


class Fetcher:
    """Cached, per-host rate-limited GET with 429/5xx backoff."""

    def __init__(self, retries=4, verbose=False):
        self.retries = retries
        self.verbose = verbose
        self.last = {}
        self.stats = {"cache": 0, "net": 0, "retry": 0, "fail": 0}
        os.makedirs(CACHE, exist_ok=True)

    def _interval(self, host):
        if host == "api.openalex.org":
            return 0.15 if openalex_key() else 1.0
        if host == "api.semanticscholar.org":
            return 0.2 if s2_key() else 1.0
        return 1.0

    def _wait(self, host):
        interval = self._interval(host)
        gap = time.time() - self.last.get(host, 0.0)
        if gap < interval:
            time.sleep(interval - gap)
        self.last[host] = time.time()

    def get(self, url, headers=None):
        """Return parsed JSON, or None on 404 / permanent failure."""
        path = os.path.join(CACHE, hashlib.sha1(url.encode()).hexdigest() + ".json")
        if os.path.exists(path):
            self.stats["cache"] += 1
            with open(path) as fh:
                return json.load(fh).get("body")

        host = urllib.parse.urlparse(url).netloc
        req_headers = {
            "User-Agent": "commit-nextgen-citations/1.0 "
            "(https://github.com/mit-commit/nextgen; mailto:%s)" % MAILTO,
            "Accept": "application/json",
        }
        req_headers.update(headers or {})
        req = urllib.request.Request(url, headers=req_headers)

        body = None
        for attempt in range(self.retries + 1):
            self._wait(host)
            try:
                self.stats["net"] += 1
                with urllib.request.urlopen(req, timeout=45) as resp:
                    body = json.loads(resp.read().decode("utf-8", "replace"))
                break
            except urllib.error.HTTPError as err:
                if err.code == 404:
                    body = None
                    break
                if err.code in (429, 500, 502, 503, 504) and attempt < self.retries:
                    self.stats["retry"] += 1
                    delay = float(err.headers.get("Retry-After") or 0) or (
                        self._interval(host) * (2 ** attempt) * 2
                    )
                    if self.verbose:
                        print(
                            "    %s on %s, sleeping %.1fs" % (err.code, host, delay),
                            file=sys.stderr,
                        )
                    time.sleep(min(delay, 60))
                    continue
                self.stats["fail"] += 1
                if self.verbose:
                    print("    HTTP %s %s" % (err.code, url), file=sys.stderr)
                return None
            except Exception as err:  # network hiccup, bad JSON
                if attempt < self.retries:
                    self.stats["retry"] += 1
                    time.sleep(self._interval(host) * (2 ** attempt) * 2)
                    continue
                self.stats["fail"] += 1
                if self.verbose:
                    print("    %s %s" % (type(err).__name__, url), file=sys.stderr)
                return None

        tmp = path + ".tmp"
        with open(tmp, "w") as fh:
            json.dump({"url": url, "body": body}, fh)
        os.replace(tmp, path)
        return body


# -------------------------------------------------------------------- sources

OPENALEX_SELECT = "id,doi,title,publication_year,primary_location,authorships,cited_by_count"
S2_FIELDS = ("title,year,externalIds,venue,authors,isInfluential,intents,"
             "contexts,citationCount")


def openalex_citing(fetch, work_id, verbose=False):
    """Yield citing-work records for one OpenAlex work id."""
    cursor = "*"
    pages = 0
    while cursor and pages < MAX_PAGES:
        params = {
            "filter": "cites:%s" % work_id,
            "per-page": OPENALEX_PAGE,
            "cursor": cursor,
            "select": OPENALEX_SELECT,
            "mailto": MAILTO,
        }
        key = openalex_key()
        if key:
            params["api_key"] = key
        url = "https://api.openalex.org/works?" + urllib.parse.urlencode(params)
        data = fetch.get(url)
        pages += 1
        if not data:
            break
        for item in data.get("results", []) or []:
            yield openalex_record(item)
        cursor = (data.get("meta") or {}).get("next_cursor")
    if pages >= MAX_PAGES and verbose:
        print("    openalex: hit %d-page cap for %s" % (MAX_PAGES, work_id), file=sys.stderr)


def openalex_record(item):
    doi = item.get("doi")
    if doi:
        doi = doi.replace("https://doi.org/", "").lower()
    source = ((item.get("primary_location") or {}).get("source")) or {}
    authors = [
        (a.get("author") or {}).get("display_name")
        for a in item.get("authorships") or []
        if (a.get("author") or {}).get("display_name")
    ]
    oa_id = (item.get("id") or "").rsplit("/", 1)[-1] or None
    return {
        "title": item.get("title"),
        "year": item.get("publication_year"),
        "doi": doi,
        "openalex": oa_id,
        "s2": None,
        "venue": source.get("display_name"),
        "authors": authors,
        "isInfluential": None,
        "intents": None,
        "contexts": None,
        "cited_by": item.get("cited_by_count"),
    }


def s2_citing(fetch, paper_id, verbose=False):
    """Yield citing-work records for one Semantic Scholar paper id."""
    offset = 0
    pages = 0
    while pages < MAX_PAGES:
        params = {"fields": S2_FIELDS, "offset": offset, "limit": S2_PAGE}
        url = "https://api.semanticscholar.org/graph/v1/paper/%s/citations?%s" % (
            paper_id,
            urllib.parse.urlencode(params),
        )
        key = s2_key()
        headers = {"x-api-key": key} if key else {}
        data = fetch.get(url, headers=headers)
        pages += 1
        if not data:
            break
        for edge in data.get("data", []) or []:
            yield s2_record(edge)
        nxt = data.get("next")
        if nxt is None:
            break
        offset = nxt
    if pages >= MAX_PAGES and verbose:
        print("    s2: hit %d-page cap for %s" % (MAX_PAGES, paper_id), file=sys.stderr)


def s2_record(edge):
    cp = edge.get("citingPaper") or {}
    ext = cp.get("externalIds") or {}
    doi = ext.get("DOI")
    if doi:
        doi = doi.lower()
    return {
        "title": cp.get("title"),
        "year": cp.get("year"),
        "doi": doi,
        "openalex": None,
        "s2": cp.get("paperId"),
        "venue": cp.get("venue") or None,
        "authors": [a.get("name") for a in cp.get("authors") or [] if a.get("name")],
        "isInfluential": edge.get("isInfluential"),
        "intents": edge.get("intents") or [],
        "contexts": edge.get("contexts") or [],
        "cited_by": cp.get("citationCount"),
    }


def merge(oa_list, s2_list):
    """Merge two citing-work lists by DOI; unmatched records pass through."""
    merged = []
    by_doi = {}
    for rec in oa_list:
        merged.append(rec)
        if rec.get("doi"):
            by_doi[rec["doi"]] = rec
    for rec in s2_list:
        doi = rec.get("doi")
        target = by_doi.get(doi) if doi else None
        if target is not None:
            target["s2"] = rec["s2"]
            target["isInfluential"] = rec["isInfluential"]
            target["intents"] = rec["intents"]
            target["contexts"] = rec["contexts"]
            if not target.get("venue"):
                target["venue"] = rec.get("venue")
            if not target.get("authors"):
                target["authors"] = rec.get("authors")
            if target.get("cited_by") is None:  # OpenAlex figure preferred
                target["cited_by"] = rec.get("cited_by")
        else:
            merged.append(rec)
            if doi:
                by_doi[doi] = rec
    return merged


# ------------------------------------------------------------------- harvest

S2_STATE = os.path.join(HERE, ".s2_state.json")


def load_idmap():
    with open(IDMAP) as fh:
        return json.load(fh)


def targets(idmap):
    return sorted(k for k, v in idmap.items() if v.get("openalex") or v.get("s2"))


def out_path(key):
    return os.path.join(OUTDIR, key + ".json")


def write_result(key, result):
    path = out_path(key)
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(result, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, path)


def load_s2_state():
    if os.path.exists(S2_STATE):
        with open(S2_STATE) as fh:
            return json.load(fh)
    return {}


def save_s2_state(state):
    tmp = S2_STATE + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(state, fh, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, S2_STATE)


def sort_citing(citing):
    citing.sort(key=lambda r: (-(r.get("year") or 0), r.get("title") or ""))
    return citing


def openalex_pass(limit=0, verbose=False):
    """Write harvest/citations/<key>.json fresh from OpenAlex alone."""
    idmap = load_idmap()
    keys = [k for k in targets(idmap) if idmap[k].get("openalex")]
    if limit:
        keys = keys[:limit]
    fetch = Fetcher(verbose=verbose)

    done = skipped = 0
    for i, key in enumerate(keys, 1):
        if os.path.exists(out_path(key)):
            skipped += 1
            continue
        print("[%d/%d] %s" % (i, len(keys), key))
        fails_before = fetch.stats["fail"]
        oa_list = list(openalex_citing(fetch, idmap[key]["openalex"], verbose))
        if fetch.stats["fail"] > fails_before:
            print("    openalex fetch incomplete -- leaving for retry")
            continue
        result = {
            "counts": {"openalex": len(oa_list), "s2": 0},
            "citing": sort_citing(oa_list),
        }
        write_result(key, result)
        done += 1
        print("    openalex=%d" % len(oa_list))

    print(
        "\nopenalex pass: %d done, %d already-done, %d targets"
        % (done, skipped, len(keys))
    )
    print(
        "fetcher: %d cache hits, %d network, %d retries, %d failures"
        % (fetch.stats["cache"], fetch.stats["net"], fetch.stats["retry"], fetch.stats["fail"])
    )


def s2_pass(limit=0, verbose=False):
    """Enrich existing harvest/citations/<key>.json files with S2 metadata."""
    idmap = load_idmap()
    keys = [k for k in targets(idmap) if idmap[k].get("s2")]
    if limit:
        keys = keys[:limit]
    state = load_s2_state()
    fetch = Fetcher(verbose=verbose)

    done = skipped = missing = 0
    for i, key in enumerate(keys, 1):
        if state.get(key):
            skipped += 1
            continue
        path = out_path(key)
        if not os.path.exists(path):
            missing += 1
            print("[%d/%d] %s: no openalex-pass file yet, skipping" % (i, len(keys), key))
            continue

        print("[%d/%d] %s" % (i, len(keys), key))
        fails_before = fetch.stats["fail"]
        s2_list = list(s2_citing(fetch, idmap[key]["s2"], verbose))
        if fetch.stats["fail"] > fails_before:
            print("    s2 fetch incomplete -- leaving for retry")
            continue

        with open(path) as fh:
            existing = json.load(fh)
        existing["counts"]["s2"] = len(s2_list)
        existing["citing"] = sort_citing(merge(existing.get("citing", []), s2_list))
        write_result(key, existing)
        state[key] = True
        save_s2_state(state)
        done += 1
        print("    s2=%d merged_total=%d" % (len(s2_list), len(existing["citing"])))

    print(
        "\ns2 pass: %d done, %d already-enriched, %d awaiting openalex pass, %d targets"
        % (done, skipped, missing, len(keys))
    )
    print(
        "fetcher: %d cache hits, %d network, %d retries, %d failures"
        % (fetch.stats["cache"], fetch.stats["net"], fetch.stats["retry"], fetch.stats["fail"])
    )


# ---------------------------------------------------------------------- report


def report():
    idmap = load_idmap()
    keys = targets(idmap)
    done, missing, zero = 0, [], []
    total_citing = oa_total = s2_total = 0
    for key in keys:
        path = os.path.join(OUTDIR, key + ".json")
        if not os.path.exists(path):
            missing.append(key)
            continue
        with open(path) as fh:
            rec = json.load(fh)
        done += 1
        counts = rec.get("counts", {})
        oa_total += counts.get("openalex", 0)
        s2_total += counts.get("s2", 0)
        total_citing += len(rec.get("citing", []))
        if not counts.get("openalex") and not counts.get("s2"):
            zero.append(key)

    print("papers done: %d/%d" % (done, len(keys)))
    print("total citing works (merged): %d" % total_citing)
    print("openalex citing-work total: %d" % oa_total)
    print("s2 citing-work total: %d" % s2_total)
    print("zero-citation papers: %d" % len(zero))
    for key in zero:
        print("  - %s" % key)
    if missing:
        print("not yet harvested: %d" % len(missing))
        for key in missing:
            print("  - %s" % key)
    return 0


# ------------------------------------------------------------------------ main


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--pass", dest="which_pass", choices=("openalex", "s2"),
                    help="which pass to run")
    ap.add_argument("--report", action="store_true", help="summarize harvest/citations/ and exit")
    ap.add_argument("--limit", type=int, default=0, help="only process the first N targets")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    if args.report:
        return report()
    if not args.which_pass:
        ap.error("--pass openalex|s2 is required (or use --report)")
    if args.which_pass == "openalex":
        openalex_pass(limit=args.limit, verbose=args.verbose)
    else:
        s2_pass(limit=args.limit, verbose=args.verbose)
    return 0


if __name__ == "__main__":
    sys.exit(main())
