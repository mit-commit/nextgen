#!/usr/bin/env python3
"""Fetch full text for citing works of the fulltext lane's 8 pilot papers.

Pilot papers (fixed list, resolved from data/publications.json + harvest/citations/):
  Low-cited (ALL citing works fetched):
    netblocks-pldi24, levison:istas:2002, amarasinghe:ijpp:2005,
    thies:toplas:2007, petkov:ipdps:2002
  High-cited (random sample of 300 citing works, seed 42), ranked by
  harvest/citations/<key>.json counts.openalex:
    thies:cc:2002, taylor:micro:2002, halide:pldi:2013

For each sampled citing work, tries free full-text routes in order, stopping
at the first that yields >=2000 chars of extracted text:

    1. openalex   -- OpenAlex work's best_oa_location.pdf_url
    2. arxiv      -- an OpenAlex location whose source is arXiv
    3. unpaywall  -- api.unpaywall.org best_oa_location.url_for_pdf
    4. pmc        -- Europe PMC render endpoint, via OpenAlex ids.pmcid

Text is extracted with pypdf. A citing work whose best extracted text is
under 2000 chars is recorded as a stub (no .txt written). A citing work with
neither a DOI nor an OpenAlex id cannot be looked up via any of these routes
and is recorded as no_id.

Output, per citing work, under harvest/fulltext/<bibtexKey>/:
    <slug>.txt   -- extracted text (only when >=2000 chars)
    <slug>.json  -- sidecar {doi, route, chars, status}

harvest/fulltext/manifest.json is written last, aggregating yield stats per
pilot paper. Idempotent/resumable: a citing work whose sidecar already
exists is skipped on rerun.

Stdlib only.

    python3 harvest/fulltext/harvest_fulltext.py
    python3 harvest/fulltext/harvest_fulltext.py --key thies:cc:2002 --limit 20
"""
import argparse
import hashlib
import io
import json
import os
import random
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CITATIONS_DIR = os.path.join(ROOT, "harvest", "citations")
OUT_DIR = os.path.join(ROOT, "harvest", "fulltext")
CACHE_DIR = os.path.join(OUT_DIR, "cache")
MANIFEST_PATH = os.path.join(OUT_DIR, "manifest.json")
CONTACT_EMAIL = "saman@lcs.mit.edu"
USER_AGENT = f"nextgen-fulltext-harvest/1.0 (mailto:{CONTACT_EMAIL})"
STUB_CHARS = 2000
SAMPLE_SIZE = 300
SAMPLE_SEED = 42

LOW_CITED_KEYS = [
    "netblocks-pldi24",
    "levison:istas:2002",
    "amarasinghe:ijpp:2005",
    "thies:toplas:2007",
    "petkov:ipdps:2002",
]
HIGH_CITED_KEYS = ["thies:cc:2002", "taylor:micro:2002", "halide:pldi:2013"]
PILOT_KEYS = LOW_CITED_KEYS + HIGH_CITED_KEYS

_rate_locks = {"openalex": threading.Lock(), "unpaywall": threading.Lock(), "pmc": threading.Lock()}
_rate_last = {"openalex": 0.0, "unpaywall": 0.0, "pmc": 0.0}
_MIN_INTERVAL = {"openalex": 0.12, "unpaywall": 0.25, "pmc": 0.2}


def _throttle(host):
    lock = _rate_locks[host]
    with lock:
        wait = _rate_last[host] + _MIN_INTERVAL[host] - time.time()
        if wait > 0:
            time.sleep(wait)
        _rate_last[host] = time.time()


def _http_get(url, timeout=20, accept=None):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    if accept:
        req.add_header("Accept", accept)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read(), resp.headers.get("Content-Type", "")


def openalex_work(doi=None, openalex_id=None):
    if doi:
        url = f"https://api.openalex.org/works/https://doi.org/{doi}?mailto={CONTACT_EMAIL}"
    elif openalex_id:
        oid = openalex_id.rsplit("/", 1)[-1]
        url = f"https://api.openalex.org/works/{oid}?mailto={CONTACT_EMAIL}"
    else:
        return None
    _throttle("openalex")
    try:
        data, _ = _http_get(url, accept="application/json")
        return json.loads(data)
    except Exception:
        return None


def unpaywall_lookup(doi):
    if not doi:
        return None
    url = f"https://api.unpaywall.org/v2/{doi}?email={CONTACT_EMAIL}"
    _throttle("unpaywall")
    try:
        data, _ = _http_get(url, accept="application/json")
        return json.loads(data)
    except Exception:
        return None


def candidate_urls(doi, openalex_id):
    """Yield (route, pdf_url) pairs in priority order."""
    work = openalex_work(doi=doi, openalex_id=openalex_id)

    if work:
        bol = work.get("best_oa_location") or {}
        if bol.get("pdf_url"):
            yield ("openalex", bol["pdf_url"])

        for loc in work.get("locations") or []:
            src = (loc.get("source") or {}) or {}
            name = (src.get("display_name") or "") or ""
            landing = loc.get("landing_page_url") or ""
            if "arxiv" in name.lower() or "arxiv.org" in landing.lower():
                pdf = loc.get("pdf_url")
                if not pdf:
                    arxiv_id = None
                    m = re.search(r"arxiv\.org/(?:abs|pdf)/([\w.\-]+)", landing, re.I)
                    if m:
                        arxiv_id = m.group(1)
                    elif doi and "arxiv" in doi.lower():
                        m2 = re.search(r"arxiv\.(.+)$", doi, re.I)
                        if m2:
                            arxiv_id = m2.group(1)
                    if arxiv_id:
                        if arxiv_id.endswith(".pdf"):
                            arxiv_id = arxiv_id[:-4]
                        pdf = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
                if pdf:
                    yield ("arxiv", pdf)
                    break

    up = unpaywall_lookup(doi)
    if up:
        bol = up.get("best_oa_location") or {}
        if bol.get("url_for_pdf"):
            yield ("unpaywall", bol["url_for_pdf"])
        elif bol.get("url"):
            yield ("unpaywall", bol["url"])

    pmcid = None
    if work:
        pmcid = (work.get("ids") or {}).get("pmcid")
    if not pmcid and up:
        for loc in (up.get("oa_locations") or []):
            u = loc.get("url") or ""
            m = re.search(r"(PMC\d+)", u)
            if m:
                pmcid = m.group(1)
                break
    if pmcid:
        pmcid = pmcid.upper()
        if not pmcid.startswith("PMC"):
            pmcid = "PMC" + pmcid
        yield ("pmc", f"https://europepmc.org/backend/ptpmcrender.fcgi?accid={pmcid}&blobtype=pdf")


def fetch_pdf_text(url):
    data, ctype = _http_get(url, timeout=30)
    if b"%PDF" not in data[:1024] and "pdf" not in ctype.lower():
        raise ValueError(f"not a pdf (content-type={ctype!r})")
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    text = []
    for page in reader.pages:
        try:
            text.append(page.extract_text() or "")
        except Exception:
            continue
    return "\n".join(text).strip()


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


def process_one(key, citing, out_dir):
    slug = slug_for(citing)
    sidecar_path = os.path.join(out_dir, slug + ".json")
    if os.path.exists(sidecar_path):
        with open(sidecar_path) as f:
            return json.load(f)

    doi = citing.get("doi")
    openalex_id = citing.get("openalex")

    result = {"doi": doi, "route": None, "chars": 0, "status": "no_id", "slug": slug}

    if not doi and not openalex_id:
        _write_sidecar(sidecar_path, result)
        return result

    best = None  # (route, chars, text)
    try:
        for route, url in candidate_urls(doi, openalex_id):
            try:
                text = fetch_pdf_text(url)
            except Exception:
                continue
            chars = len(text)
            if best is None or chars > best[1]:
                best = (route, chars, text)
            if chars >= STUB_CHARS:
                break
    except Exception:
        pass

    if best is None:
        result["status"] = "fetch_fail"
        _write_sidecar(sidecar_path, result)
        return result

    route, chars, text = best
    result["route"] = route
    result["chars"] = chars
    if chars >= STUB_CHARS:
        result["status"] = "ok"
        with open(os.path.join(out_dir, slug + ".txt"), "w") as f:
            f.write(text)
    else:
        result["status"] = "stub"
    _write_sidecar(sidecar_path, result)
    return result


def _write_sidecar(path, result):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(result, f, indent=2)
    os.replace(tmp, path)


def load_citing_set(key):
    with open(os.path.join(CITATIONS_DIR, f"{key}.json")) as f:
        d = json.load(f)
    citing = d["citing"]
    if key in HIGH_CITED_KEYS:
        rng = random.Random(SAMPLE_SEED)
        if len(citing) > SAMPLE_SIZE:
            citing = rng.sample(citing, SAMPLE_SIZE)
    return citing


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", action="append", help="restrict to this pilot key (repeatable)")
    ap.add_argument("--limit", type=int, help="cap citing works per key (debug)")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--report", action="store_true", help="only summarize existing output")
    args = ap.parse_args()

    keys = args.key if args.key else PILOT_KEYS
    for k in keys:
        if k not in PILOT_KEYS:
            sys.exit(f"not a pilot key: {k}")

    manifest = {"generated_from": "harvest_fulltext.py", "sample_seed": SAMPLE_SEED, "sample_size": SAMPLE_SIZE, "papers": {}}

    for key in keys:
        out_dir = os.path.join(OUT_DIR, key)
        os.makedirs(out_dir, exist_ok=True)
        citing = load_citing_set(key)
        if args.limit:
            citing = citing[: args.limit]

        results = []
        if args.report:
            for c in citing:
                sc = os.path.join(out_dir, slug_for(c) + ".json")
                if os.path.exists(sc):
                    with open(sc) as f:
                        results.append(json.load(f))
        else:
            print(f"[{key}] attempting {len(citing)} citing works...", flush=True)
            with ThreadPoolExecutor(max_workers=args.workers) as ex:
                futs = {ex.submit(process_one, key, c, out_dir): c for c in citing}
                done = 0
                for fut in as_completed(futs):
                    try:
                        results.append(fut.result())
                    except Exception as e:
                        results.append({"status": "error", "route": None, "chars": 0, "doi": None, "error": str(e)})
                    done += 1
                    if done % 25 == 0 or done == len(citing):
                        print(f"[{key}] {done}/{len(citing)}", flush=True)

        by_route = {}
        landed = 0
        stub = 0
        no_id = 0
        fetch_fail = 0
        for r in results:
            if r["status"] == "ok":
                landed += 1
                by_route[r["route"]] = by_route.get(r["route"], 0) + 1
            elif r["status"] == "stub":
                stub += 1
            elif r["status"] == "no_id":
                no_id += 1
            else:
                fetch_fail += 1

        manifest["papers"][key] = {
            "attempted": len(citing),
            "landed": landed,
            "by_route": by_route,
            "stub": stub,
            "no_id": no_id,
            "fetch_fail": fetch_fail,
        }
        print(f"[{key}] done: {landed}/{len(citing)} landed {by_route}", flush=True)

    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"wrote {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
