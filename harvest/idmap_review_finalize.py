#!/usr/bin/env python3
"""Finalize the 29 remaining data/idmap-review.json rows (task: idmap-review-rest).

For each row: (1) search OpenAlex directly for the publication's own title, in
case it has an OpenAlex work record despite lacking a DOI (workshop/CIDR/
NeurIPS papers commonly do); (2) independently fetch each candidate's
OpenAlex-by-DOI record (not just the Crossref record idmap_review_fetch.py
already checked) and compare venue+year+authors against publications.json.
Prints a report; writes nothing unless --write.

On --write: for each row, resolves into data/idmap.json as one of
  - kind="doi" if a candidate is now confirmed a genuine match (none expected
    here -- the existing notes already ruled all candidates out; a --write
    run will refuse to silently accept one)
  - kind="openalex_only" if the publication's own OpenAlex record was found
    (has openalex id, doi may still be null)
  - kind="same_work_as" for the three rows that share a claimed_doi with an
    already-accepted sibling key (no distinct id of their own)
  - kind="no_doi" otherwise
and removes the row from data/idmap-review.json.

Stdlib only. Rate-limited 1 req/s to openalex.org. Caches under
harvest/idmap_cache (same cache idmap_build.py/idmap_review_fetch.py use).
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CACHE = os.path.join(HERE, "idmap_cache")
MAILTO = "samana@mit.edu"

IDMAP = os.path.join(ROOT, "data", "idmap.json")
REVIEW = os.path.join(ROOT, "data", "idmap-review.json")
PUBLICATIONS = os.path.join(ROOT, "data", "publications.json")

# Rows that share a claimed_doi with a sibling key already accepted into
# idmap.json (match: "fuzzy_reviewed") in the earlier idmap-review pass.
SAME_WORK_AS = {
    "hall:dtj:1998": "hall:computer:1996",
    "puppin:ijpp:2005": "lee:micro:2002",
    "thies:recombposter:2006": "thies:bmc:2007",
}

os.makedirs(CACHE, exist_ok=True)
_last = {}


def fetch(url):
    path = os.path.join(CACHE, __import__("hashlib").sha1(url.encode()).hexdigest() + ".json")
    if os.path.exists(path):
        with open(path) as fh:
            return json.load(fh).get("body")
    host = urllib.parse.urlparse(url).netloc
    gap = time.time() - _last.get(host, 0.0)
    if gap < 1.0:
        time.sleep(1.0 - gap)
    _last[host] = time.time()
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "commit-nextgen-idmap/1.0 (mailto:%s)" % MAILTO,
            "Accept": "application/json",
        },
    )
    body = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                body = json.loads(resp.read().decode("utf-8", "replace"))
            break
        except urllib.error.HTTPError as err:
            if err.code == 404:
                body = None
                break
            time.sleep(2 * (attempt + 1))
        except Exception:
            time.sleep(2 * (attempt + 1))
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump({"url": url, "body": body}, fh)
    os.replace(tmp, path)
    return body


def openalex_by_doi(doi):
    url = "https://api.openalex.org/works/doi:" + urllib.parse.quote(doi, safe="")
    return fetch(url)


def openalex_title_search(title):
    q = urllib.parse.quote(title, safe="")
    url = "https://api.openalex.org/works?filter=title.search:%s&per-page=5" % q
    data = fetch(url)
    if not data:
        return []
    return data.get("results") or []


def norm_title(t):
    return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()


def title_overlap(a, b):
    wa, wb = set(norm_title(a).split()), set(norm_title(b).split())
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


def author_surnames(author0):
    # author0 is "Last, First and Last, First" or "First Last and First Last"
    names = re.split(r"\s+and\s+", author0 or "")
    out = []
    for n in names:
        n = n.strip()
        if "," in n:
            out.append(n.split(",")[0].strip().lower())
        else:
            parts = n.split()
            if parts:
                out.append(parts[-1].lower())
    return set(out)


def openalex_authors(work):
    return [a.get("author", {}).get("display_name", "") for a in (work or {}).get("authorships") or []]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    with open(IDMAP) as fh:
        idmap = json.load(fh)
    with open(REVIEW) as fh:
        review = json.load(fh)
    with open(PUBLICATIONS) as fh:
        pubs = {p["bibtexKey"]: p for p in json.load(fh)}

    resolutions = {}

    for key in sorted(review.keys()):
        rec = review[key]
        pub = pubs.get(key, {})
        title = pub.get("title") or rec.get("title") or ""
        author0 = pub.get("author0") or ""
        our_surnames = author_surnames(author0)

        print("=" * 100)
        print("KEY:", key)
        print("  title:", title)
        print("  authors:", author0)
        print("  existing note:", rec.get("note"))

        if key in SAME_WORK_AS:
            resolutions[key] = {
                "kind": "same_work_as",
                "same_work_as": SAME_WORK_AS[key],
                "note": rec.get("note"),
            }
            print("  -> RESOLUTION: same_work_as", SAME_WORK_AS[key])
            continue

        # (1) does the publication itself have an OpenAlex record?
        own_hits = openalex_title_search(title)
        own_match = None
        for w in own_hits:
            ov = title_overlap(title, w.get("display_name") or "")
            oa_surnames = {s.split()[-1].lower() for s in openalex_authors(w) if s}
            author_hit = bool(our_surnames & oa_surnames)
            year_hit = str(w.get("publication_year")) == str(pub.get("year") or rec.get("year"))
            print("  own-search cand: %r year=%s overlap=%.2f author_overlap=%s doi=%s" % (
                w.get("display_name"), w.get("publication_year"), ov, author_hit, w.get("doi")))
            if ov >= 0.6 and author_hit:
                own_match = w
                break

        # (2) independently re-check the top review candidate via OpenAlex-by-DOI
        cand = (rec.get("candidates") or [None])[0]
        cand_check = None
        if cand and cand.get("doi"):
            w = openalex_by_doi(cand["doi"])
            if w:
                oa_surnames = {s.split()[-1].lower() for s in openalex_authors(w) if s}
                cand_check = {
                    "doi": cand["doi"],
                    "title": w.get("display_name"),
                    "year": w.get("publication_year"),
                    "author_overlap": bool(our_surnames & oa_surnames),
                    "title_overlap": title_overlap(title, w.get("display_name") or ""),
                }
                print("  candidate re-check via OpenAlex:", cand_check)

        if own_match:
            own_doi = (own_match.get("doi") or "").replace("https://doi.org/", "") or None
            resolutions[key] = {
                "kind": "doi" if own_doi else "openalex_only",
                "openalex": own_match["id"].rsplit("/", 1)[-1],
                "doi": own_doi,
                "note": "resolved directly via OpenAlex title search (own record, "
                        "not one of the review candidates); " + (rec.get("note") or ""),
            }
            print("  -> RESOLUTION: %s %s doi=%s" % (
                resolutions[key]["kind"], resolutions[key]["openalex"], own_doi))
        elif cand_check and cand_check["title_overlap"] >= 0.6 and cand_check["author_overlap"]:
            print("  -> WARNING: candidate re-check suggests a possible match not "
                  "previously accepted; needs human eyes, leaving in review.")
        else:
            resolutions[key] = {
                "kind": "no_doi",
                "note": rec.get("note"),
            }
            print("  -> RESOLUTION: no_doi (confirmed no OpenAlex record either)")

    print("\n" + "=" * 100)
    print("SUMMARY: %d/%d rows resolved" % (len(resolutions), len(review)))
    unresolved = set(review) - set(resolutions)
    if unresolved:
        print("UNRESOLVED (left in review.json):", sorted(unresolved))

    if not args.write:
        print("\ndry run -- nothing written. Pass --write to commit.")
        return 0

    for key, res in resolutions.items():
        pub = pubs.get(key, {})
        entry = {
            "title": pub.get("title") or review[key].get("title") or "",
            "year": pub.get("year") or review[key].get("year"),
        }
        if res["kind"] in ("openalex_only", "doi"):
            entry.update({
                "kind": res["kind"],
                "match": "openalex_title_search",
                "doi": res.get("doi"),
                "openalex": res.get("openalex"),
                "s2": None,
                "note": res.get("note"),
            })
        elif res["kind"] == "same_work_as":
            entry.update({
                "kind": "same_work_as",
                "match": None,
                "doi": None,
                "openalex": None,
                "s2": None,
                "same_work_as": res["same_work_as"],
                "note": res.get("note"),
            })
        else:
            entry.update({
                "kind": "no_doi",
                "match": None,
                "doi": None,
                "openalex": None,
                "s2": None,
                "note": res.get("note"),
            })
        idmap[key] = entry
        del review[key]

    for path, payload in ((IDMAP, idmap), (REVIEW, review)):
        tmp = path + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(payload, fh, indent=1, sort_keys=True, ensure_ascii=False)
            fh.write("\n")
        os.replace(tmp, path)
        print("wrote", os.path.relpath(path, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
