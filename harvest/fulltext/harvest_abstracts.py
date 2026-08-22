#!/usr/bin/env python3
"""Fill the evidence floor for the fulltext lane's 8 pilot papers.

For every citing work in the same population harvest_fulltext.py attempted
(all citing works for the 5 low-cited pilots, the fixed 300-sample for the
3 high-cited ones) that does NOT have cached full text (no sidecar, or a
sidecar whose status isn't "ok"), fetch the OpenAlex work record and invert
its abstract_inverted_index into a plain-text abstract.

Written to harvest/fulltext/abstracts/<bibtexKey>.json, one dict per pilot
paper keyed by the same slug harvest_fulltext.py uses (doi-based, or
oa-/s2-/noid- prefixed), so joining against harvest/fulltext/<key>/ is a
plain lookup by key. This is metadata (title + abstract + venue), not
publisher full text, so unlike harvest/fulltext/<key>/ it is committed.

Stdlib only.

    python3 harvest/fulltext/harvest_abstracts.py
    python3 harvest/fulltext/harvest_abstracts.py --key thies:cc:2002 --limit 20
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from harvest_fulltext import (  # noqa: E402
    PILOT_KEYS,
    CONTACT_EMAIL,
    USER_AGENT,
    load_citing_set,
    slug_for,
)

OUT_DIR = os.path.join(HERE, "abstracts")


_last_request = [0.0]
_MIN_INTERVAL = 0.12


def _throttle():
    wait = _last_request[0] + _MIN_INTERVAL - time.time()
    if wait > 0:
        time.sleep(wait)
    _last_request[0] = time.time()


def openalex_work(openalex_id=None, doi=None):
    if openalex_id:
        oid = openalex_id.rsplit("/", 1)[-1]
        url = "https://api.openalex.org/works/%s?mailto=%s&select=id,title,abstract_inverted_index,primary_location" % (
            oid, CONTACT_EMAIL)
    elif doi:
        url = "https://api.openalex.org/works/https://doi.org/%s?mailto=%s&select=id,title,abstract_inverted_index,primary_location" % (
            doi, CONTACT_EMAIL)
    else:
        return None
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    for attempt in range(4):
        _throttle()
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as err:
            if err.code == 404:
                return None
            if err.code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(1.0 * (attempt + 1))
                continue
            return None
        except Exception:
            if attempt < 3:
                time.sleep(1.0 * (attempt + 1))
                continue
            return None
    return None


def invert_abstract(inverted):
    if not inverted:
        return None
    positions = {}
    maxpos = -1
    for word, idxs in inverted.items():
        for i in idxs:
            positions[i] = word
            maxpos = max(maxpos, i)
    return " ".join(positions.get(i, "") for i in range(maxpos + 1)).strip() or None


def has_fulltext(key, slug):
    sidecar = os.path.join(HERE, key, slug + ".json")
    if not os.path.exists(sidecar):
        return False
    with open(sidecar) as fh:
        return json.load(fh).get("status") == "ok"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", action="append", help="restrict to this pilot key (repeatable)")
    ap.add_argument("--limit", type=int, help="cap citing works per key (debug)")
    args = ap.parse_args()

    keys = args.key if args.key else PILOT_KEYS
    for k in keys:
        if k not in PILOT_KEYS:
            sys.exit("not a pilot key: %s" % k)

    os.makedirs(OUT_DIR, exist_ok=True)

    for key in keys:
        citing = load_citing_set(key)
        if args.limit:
            citing = citing[: args.limit]

        needed = [c for c in citing if not has_fulltext(key, slug_for(c))]
        print("[%s] %d/%d citing works need an abstract" % (key, len(needed), len(citing)), flush=True)

        out_path = os.path.join(OUT_DIR, key + ".json")
        existing = {}
        if os.path.exists(out_path):
            with open(out_path) as fh:
                existing = json.load(fh)

        done = 0
        for c in needed:
            slug = slug_for(c)
            if slug in existing:
                continue
            doi = c.get("doi")
            oa = c.get("openalex")
            if not doi and not oa:
                existing[slug] = {
                    "doi": doi, "openalex": oa, "title": c.get("title"),
                    "abstract": None, "status": "no_id",
                }
            else:
                work = openalex_work(openalex_id=oa, doi=doi)
                if not work:
                    existing[slug] = {
                        "doi": doi, "openalex": oa, "title": c.get("title"),
                        "abstract": None, "status": "openalex_lookup_failed",
                    }
                else:
                    abstract = invert_abstract(work.get("abstract_inverted_index"))
                    existing[slug] = {
                        "doi": doi,
                        "openalex": oa or (work.get("id") or "").rsplit("/", 1)[-1],
                        "title": work.get("title") or c.get("title"),
                        "abstract": abstract,
                        "status": "ok" if abstract else "no_abstract",
                    }
            done += 1
            if done % 50 == 0:
                print("  [%s] %d/%d" % (key, done, len(needed)), flush=True)

        tmp = out_path + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(existing, fh, indent=1, sort_keys=True, ensure_ascii=False)
            fh.write("\n")
        os.replace(tmp, out_path)

        with_abstract = sum(1 for v in existing.values() if v.get("status") == "ok")
        print("[%s] wrote %s: %d entries, %d with an abstract" % (
            key, os.path.relpath(out_path, os.path.dirname(HERE)), len(existing), with_abstract), flush=True)


if __name__ == "__main__":
    main()
