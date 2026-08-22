#!/usr/bin/env python3
"""Merge metadata_hits.json (Crossref/OpenAlex/DataCite, routes 1+2) and
pdf_hits.json (route 4) into found.json (confirmed artifact) / review.json
(uncertain) keyed by bibtexKey.

Route 3 (ACM DL landing-page badge HTML) returned 403 on the first request and
was not pursued further per instructions ("stop on any 403/challenge") -- see
README.md in this directory. So badge *names* are unavailable this pass;
badges[] is populated only when a paper's own text literally names one
("Artifacts Available", "Artifact Appendix", etc. found near an artifact URL).

Precision notes (see README.md "What the raw signal looked like" for the full
manual audit this logic is based on):

- DataCite: a search-API hit only means some DataCite-registered record's
  relatedIdentifiers mentions our DOI -- most hits are OTHER papers citing
  ours (relationType "Cites"/"References") or an arXiv mirror of the same
  paper (relationType "IsVersionOf", resourceTypeGeneral "Text"/"Preprint").
  Neither is an artifact. Only resourceTypeGeneral in {Software, Dataset}
  reliably isolates an actual deposited artifact.
- PDF scan: a bare github.com URL on the same page as the word "artifact"
  turned out, on manual audit, to correlate with nothing -- these are almost
  always citations to unrelated tools/baselines, especially in theses'
  bibliographies. github-only hits are dropped rather than pushed to review,
  since zero of 41 manually-spot-checked cases were the paper's own artifact
  landing page. A zenodo.org / 10.5281 / figshare URL is a much stronger
  signal (Zenodo/FigShare are archival deposit targets, not generic
  citations) -- but even those need the surrounding sentence checked, since a
  paper's bibliography often cites *other* papers' Zenodo-hosted artifacts
  too (e.g. a cited software package's own archival DOI).
"""
import json
import re

ROOT = "/Users/saman/workspace/nextgen"

ARTIFACT_RESOURCE_TYPES = {"Software", "Dataset"}

SELF_REF_PATTERNS = [
    r"\bthe artifact\b", r"\bour artifact", r"\bartifacts? for the\b",
    r"\bartifact code ?base\b", r"\breproduction package\b",
    r"\bavailable as an artifact\b", r"\bcreated zenodo\b",
    r"\bartifacts? evaluat", r"\bartifacts? availab",
    r"\bopenly available in zenodo\b",
]
SELF_REF_RE = re.compile("|".join(SELF_REF_PATTERNS), re.I)

BADGE_PHRASES = {
    "artifacts available": "Artifacts Available",
    "artifact available": "Artifacts Available",
    "artifacts evaluated": "Artifacts Evaluated",
    "artifact evaluated": "Artifacts Evaluated",
    "results reproduced": "Results Reproduced",
    "results replicated": "Results Replicated",
}

STOPWORDS = {
    "a", "an", "the", "of", "for", "and", "with", "in", "on", "to", "is",
    "high-performance", "language", "compiler", "programming",
}


def title_words(title):
    words = re.findall(r"[a-z0-9]+", title.lower())
    return {w for w in words if len(w) > 3 and w not in STOPWORDS}


def title_overlap(title, context):
    """True if enough of the paper's own distinctive title words show up in
    the sentence around a Zenodo/FigShare URL to conclude it's citing itself
    (as opposed to 2 generic domain words like "high"/"performance" or
    "finite"/"elements" coincidentally matching a citation to someone else's
    work -- both were false positives before this ratio+count combo)."""
    tw = title_words(title)
    if not tw:
        return False
    cw = set(re.findall(r"[a-z0-9]+", context.lower()))
    n = len(tw & cw)
    ratio = n / len(tw)
    return n >= 3 or (n >= 2 and ratio >= 0.8)


def clean_url(url):
    return url.rstrip(".,;)")


def zenodo_urls(hits):
    return [
        {**h, "url": clean_url(h["url"])}
        for h in hits if "url" in h and re.search(r"zenodo|10\.5281|10\.6084|figshare", h["url"], re.I)
    ]


def pick_artifact_doi(url):
    m = re.search(r"10\.5281/zenodo\.[0-9]+|10\.6084/m9\.figshare\.[0-9.v]+", url, re.I)
    return m.group(0).rstrip(".") if m else None


def from_pdf(pdf_hits, titles):
    found, review = {}, {}
    for key, rec in pdf_hits.items():
        z = zenodo_urls(rec["hits"])
        if not z:
            continue
        title = titles.get(key, "")
        confirmed_hits = []
        ambiguous_hits = []
        for h in z:
            is_self_ref = bool(SELF_REF_RE.search(h["context"]))
            overlaps = title_overlap(title, h["context"])
            (confirmed_hits if (is_self_ref or overlaps) else ambiguous_hits).append(h)
        chosen = confirmed_hits or ambiguous_hits
        urls = [h["url"] for h in chosen]
        artifact_doi = next((pick_artifact_doi(u) for u in urls if pick_artifact_doi(u)), None)
        artifact_url = urls[0]
        badges = sorted({
            BADGE_PHRASES[h["phrase"]]
            for h in rec["hits"] if "phrase" in h and h["phrase"] in BADGE_PHRASES
        })
        evidence = [{"page": h["page"], "match": h["url"], "context": h["context"]} for h in chosen]
        evidence += [
            {"page": h["page"], "match": h["phrase"], "context": h["context"]}
            for h in rec["hits"] if "phrase" in h
        ]
        record = {
            "badges": badges,
            "artifact_doi": artifact_doi,
            "artifact_url": artifact_url,
            "source": ["pdf_scan"],
            "evidence": evidence,
            "pdf": rec["pdf"],
        }
        if confirmed_hits:
            found[key] = record
        else:
            record["review_reason"] = (
                "Zenodo/FigShare URL found in PDF text but the surrounding "
                "sentence doesn't clearly say it's this paper's own artifact "
                "(no title-word overlap, no self-referential phrase) -- may "
                "be a citation to a different work's archived artifact."
            )
            review[key] = record
    return found, review


def from_metadata(meta_hits):
    found = {}
    for key, rec in meta_hits.items():
        dc = rec.get("datacite", {})
        artifact_matches = []
        for m in dc.get("matches", []):
            rtype = m["attributes"].get("types", {}).get("resourceTypeGeneral")
            if rtype in ARTIFACT_RESOURCE_TYPES:
                artifact_matches.append(m)
        if not artifact_matches:
            continue
        doi = artifact_matches[0]["id"]
        url = artifact_matches[0]["attributes"].get("url")
        found[key] = {
            "badges": [],
            "artifact_doi": doi,
            "artifact_url": url,
            "source": ["metadata(datacite)"],
            "evidence": [
                {
                    "source": "datacite",
                    "doi": m["id"],
                    "url": m["attributes"].get("url"),
                    "resourceType": m["attributes"].get("types", {}).get("resourceTypeGeneral"),
                    "relations": [
                        r for r in m["attributes"].get("relatedIdentifiers", [])
                        if r.get("relatedIdentifier", "").lower() == rec["doi"].lower()
                    ],
                }
                for m in artifact_matches
            ],
        }
    return found


def main():
    meta_hits = json.load(open(f"{ROOT}/harvest/artifacts/raw/metadata_hits.json"))
    pdf_hits = json.load(open(f"{ROOT}/harvest/artifacts/raw/pdf_hits.json"))
    idmap = json.load(open(f"{ROOT}/data/idmap.json"))
    titles = {p["bibtexKey"]: p.get("title", "") for p in json.load(open(f"{ROOT}/data/publications.json"))}

    meta_found = from_metadata(meta_hits)
    pdf_found, pdf_review = from_pdf(pdf_hits, titles)

    found = {}
    for key in set(meta_found) | set(pdf_found):
        rec = {"doi": idmap.get(key, {}).get("doi")}
        parts = [r for r in (meta_found.get(key), pdf_found.get(key)) if r]
        rec["badges"] = sorted({b for p in parts for b in p["badges"]})
        rec["artifact_doi"] = next((p["artifact_doi"] for p in parts if p.get("artifact_doi")), None)
        artifact_url = next((p["artifact_url"] for p in parts if p.get("artifact_url")), None)
        if artifact_url and not artifact_url.startswith(("http://", "https://")):
            artifact_url = f"https://doi.org/{artifact_url}"
        rec["artifact_url"] = artifact_url
        rec["source"] = sorted({s for p in parts for s in p["source"]})
        rec["evidence"] = [e for p in parts for e in p["evidence"]]
        if "pdf" in (pdf_found.get(key) or {}):
            rec["pdf"] = pdf_found[key]["pdf"]
        found[key] = rec

    review = {}
    for key, rec in pdf_review.items():
        if key in found:
            continue
        if rec.get("artifact_url") and not rec["artifact_url"].startswith(("http://", "https://")):
            rec["artifact_url"] = f"https://doi.org/{rec['artifact_url']}"
        review[key] = {"doi": idmap.get(key, {}).get("doi"), **rec}

    with open(f"{ROOT}/harvest/artifacts/found.json", "w") as f:
        json.dump(found, f, indent=1, sort_keys=True)
    with open(f"{ROOT}/harvest/artifacts/review.json", "w") as f:
        json.dump(review, f, indent=1, sort_keys=True)

    n_badge = sum(1 for r in found.values() if r["badges"])
    print(f"found.json: {len(found)} confirmed ({n_badge} with badge text)")
    print(f"review.json: {len(review)} uncertain")
    for k in sorted(found):
        print(" found  ", k, "->", found[k]["artifact_doi"] or found[k]["artifact_url"])
    for k in sorted(review):
        print(" review ", k, "->", review[k].get("artifact_doi") or review[k].get("artifact_url"))


if __name__ == "__main__":
    main()
