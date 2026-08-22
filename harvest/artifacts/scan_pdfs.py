#!/usr/bin/env python3
"""Route 4: scan papers/*.pdf for artifact-related text.

For every bibtexKey with a local papers/ PDF (from data/publications.json),
extract text page by page and record any line containing one of the target
phrases, plus any zenodo/doi.org/10.5281 URLs found nearby.

Writes harvest/artifacts/raw/pdf_hits.json.
"""
import json
import re

from pypdf import PdfReader

ROOT = "/Users/saman/workspace/nextgen"

PHRASES = [
    "artifact evaluation",
    "artifact evaluated",
    "artifacts evaluated",
    "artifacts available",
    "artifact available",
    "results reproduced",
    "results replicated",
    "zenodo.org",
    "doi.org/10.5281",
    "10.5281/zenodo",
    "artifact appendix",
    "artifact doi",
]
URL_RE = re.compile(
    r"(https?://(?:dx\.)?doi\.org/10\.5281/zenodo\.[^\s\"'<>,)]+"
    r"|https?://zenodo\.org/(?:record|records|badge)/[^\s\"'<>,)]+"
    r"|10\.5281/zenodo\.[0-9]+"
    r"|https?://[^\s\"'<>,)]*figshare\.com[^\s\"'<>,)]*"
    r"|https?://github\.com/[^\s\"'<>,)]+)",
    re.I,
)


def main():
    pubs = json.load(open(f"{ROOT}/data/publications.json"))
    results = {}
    n_scanned = 0
    n_err = 0
    for p in pubs:
        key = p.get("bibtexKey")
        url = p.get("url") or ""
        if not url.startswith("papers/") or not url.lower().endswith(".pdf"):
            continue
        path = f"{ROOT}/{url}"
        n_scanned += 1
        try:
            reader = PdfReader(path)
        except Exception as e:
            n_err += 1
            continue
        hits = []
        for pageno, page in enumerate(reader.pages, start=1):
            try:
                text = page.extract_text() or ""
            except Exception:
                continue
            lower = text.lower()
            for phrase in PHRASES:
                idx = lower.find(phrase)
                if idx == -1:
                    continue
                start = max(0, idx - 120)
                end = min(len(text), idx + 200)
                context = " ".join(text[start:end].split())
                hits.append({"page": pageno, "phrase": phrase, "context": context})
            for m in URL_RE.finditer(text):
                start = max(0, m.start() - 100)
                end = min(len(text), m.end() + 100)
                context = " ".join(text[start:end].split())
                hits.append({"page": pageno, "url": m.group(0), "context": context})
        if hits:
            results[key] = {"pdf": url, "hits": hits}
        if n_scanned % 50 == 0:
            print(f"scanned {n_scanned} pdfs, {len(results)} with hits so far")
    with open(f"{ROOT}/harvest/artifacts/raw/pdf_hits.json", "w") as f:
        json.dump(results, f, indent=1)
    print(f"done. scanned={n_scanned} errors={n_err} with_hits={len(results)}")


if __name__ == "__main__":
    main()
