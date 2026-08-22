#!/usr/bin/env python3
"""Fetch Crossref author/venue/year detail for every candidate DOI in
data/idmap-review.json, and print a side-by-side comparison against the
publications.json entry, for a human to judge venue+year+author agreement.

Read-only: writes nothing to data/. Caches Crossref responses in
harvest/idmap_cache (same cache idmap_build.py uses).
"""
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CACHE = os.path.join(HERE, "idmap_cache")
MAILTO = "samana@mit.edu"

os.makedirs(CACHE, exist_ok=True)
_last = {}


def fetch(url):
    path = os.path.join(CACHE, hashlib.sha1(url.encode()).hexdigest() + ".json")
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


def crossref_by_doi(doi):
    url = "https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="")
    data = fetch(url)
    if not data or data.get("status") != "ok":
        return None
    return data.get("message")


def authors_str(item):
    out = []
    for a in (item or {}).get("author") or []:
        given = a.get("given", "")
        family = a.get("family", "")
        out.append((given + " " + family).strip() or a.get("name", ""))
    return "; ".join(out)


def main():
    pubs = json.load(open(os.path.join(ROOT, "data", "publications.json")))
    by_key = {p["bibtexKey"]: p for p in pubs}
    review = json.load(open(os.path.join(ROOT, "data", "idmap-review.json")))

    keys = sys.argv[1:] or sorted(review.keys())
    for key in keys:
        rec = review[key]
        pub = by_key.get(key, {})
        print("=" * 100)
        print("KEY:", key)
        print("  ours: title=%r" % rec.get("title"))
        print("        venue=%r  year=%r  itemType=%r  author0=%r" % (
            pub.get("venue") or pub.get("booktitle") or pub.get("journal"),
            rec.get("year"), rec.get("itemType"), pub.get("author0")))
        if rec.get("claimed_doi"):
            print("        claimed_doi=%r" % rec.get("claimed_doi"))
        for i, cand in enumerate(rec.get("candidates") or []):
            doi = cand.get("doi")
            item = crossref_by_doi(doi) if doi else None
            print("  cand[%d]: doi=%s" % (i, doi))
            print("           title=%r" % cand.get("title"))
            print("           container=%r  year=%r  type=%r" % (
                cand.get("container"), cand.get("year"), cand.get("type")))
            if item:
                print("           crossref authors=%s" % authors_str(item))
            else:
                print("           crossref authors=<no crossref record>")
        print()


if __name__ == "__main__":
    main()
