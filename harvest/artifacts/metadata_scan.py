#!/usr/bin/env python3
"""Route 1 (Crossref relations/assertions) + Route 2 (DataCite + OpenAlex
links to artifact DOIs) for every DOI'd publication in data/idmap.json.

Writes harvest/artifacts/raw/metadata_hits.json: one entry per bibtexKey that
produced any signal, with the raw fragments that triggered it so merge.py can
decide confirmed vs. review.
"""
import json
import re
import time
import urllib.request
import urllib.error

ROOT = "/Users/saman/workspace/nextgen"
UA = "nextgen-artifact-harvest/1.0 (mailto:saman@lcs.mit.edu)"

ARTIFACT_DOI_RE = re.compile(r"10\.5281/[^\s\"'<>]+|10\.6084/[^\s\"'<>]+", re.I)
KEYWORDS = re.compile(r"artifact|zenodo|figshare|supplement|software|dataset|reproduc", re.I)


def fetch_json(url, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8", "replace")), None
    except urllib.error.HTTPError as e:
        return None, f"http {e.code}"
    except Exception as e:
        return None, str(e)


def crossref(doi):
    data, err = fetch_json(f"https://api.crossref.org/works/{doi}")
    if err or not data:
        return {"error": err}
    msg = data.get("message", {})
    relation = msg.get("relation") or {}
    assertion = msg.get("assertion") or []
    link = msg.get("link") or []
    hits = {}
    rel_hits = {}
    for rel_type, entries in relation.items():
        for e in entries:
            rid = e.get("id", "")
            if KEYWORDS.search(rel_type) or ARTIFACT_DOI_RE.search(rid):
                rel_hits.setdefault(rel_type, []).append(e)
    if rel_hits:
        hits["relation"] = rel_hits
    assert_hits = [a for a in assertion if KEYWORDS.search(json.dumps(a))]
    if assert_hits:
        hits["assertion"] = assert_hits
    link_hits = [l for l in link if ARTIFACT_DOI_RE.search(l.get("URL", ""))]
    if link_hits:
        hits["link"] = link_hits
    return hits


def openalex(doi):
    data, err = fetch_json(f"https://api.openalex.org/works/https://doi.org/{doi}")
    if err or not data:
        return {"error": err}
    hits = {}
    locs = data.get("locations") or []
    loc_hits = []
    for l in locs:
        blob = json.dumps(l)
        if "zenodo" in blob.lower() or "figshare" in blob.lower() or ARTIFACT_DOI_RE.search(blob):
            loc_hits.append(l)
    if loc_hits:
        hits["locations"] = loc_hits
    best_oa = data.get("best_oa_location") or {}
    if best_oa and ("zenodo" in json.dumps(best_oa).lower() or "figshare" in json.dumps(best_oa).lower()):
        hits["best_oa_location"] = best_oa
    return hits


def datacite(doi):
    q = f'relatedIdentifiers.relatedIdentifier:"{doi}"'
    url = "https://api.datacite.org/dois?query=" + urllib.parse.quote(q) + "&page[size]=10"
    data, err = fetch_json(url)
    if err or not data:
        return {"error": err}
    items = data.get("data") or []
    if items:
        return {"matches": items}
    return {}


import urllib.parse


def main():
    idmap = json.load(open(f"{ROOT}/data/idmap.json"))
    entries = [(k, v["doi"]) for k, v in idmap.items() if v.get("doi")]
    print(f"{len(entries)} DOI'd entries")
    results = {}
    for i, (key, doi) in enumerate(entries):
        rec = {}
        cr = crossref(doi)
        if cr:
            rec["crossref"] = cr
        time.sleep(0.4)
        oa = openalex(doi)
        if oa:
            rec["openalex"] = oa
        time.sleep(0.4)
        dc = datacite(doi)
        if dc:
            rec["datacite"] = dc
        time.sleep(0.4)
        has_signal = any(
            rec.get(src) and not (set(rec[src].keys()) == {"error"})
            for src in ("crossref", "openalex", "datacite")
        )
        if has_signal:
            results[key] = {"doi": doi, **rec}
            print(f"[{i+1}/{len(entries)}] {key}: SIGNAL")
        elif (i + 1) % 25 == 0:
            print(f"[{i+1}/{len(entries)}] ...")
    with open(f"{ROOT}/harvest/artifacts/raw/metadata_hits.json", "w") as f:
        json.dump(results, f, indent=1)
    print(f"done. {len(results)} bibtexKeys with metadata signal")


if __name__ == "__main__":
    main()
