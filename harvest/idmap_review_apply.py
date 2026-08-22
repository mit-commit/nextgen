#!/usr/bin/env python3
"""Apply the human-reviewed verdicts for data/idmap-review.json.

Reads ACCEPT (key -> doi) and NOTE (key -> one-line note) tables baked into
this script (produced by manual venue+year+author comparison against
Crossref, see harvest/idmap_review_fetch.py output). For each ACCEPT:
resolves openalex/s2 ids for the doi, writes a data/idmap.json entry with
match: "fuzzy_reviewed", kind: "doi", and removes the key from
data/idmap-review.json. For each NOTE: leaves the row in
data/idmap-review.json but adds a "note" field.

Stdlib only. Writes nothing unless --write is given.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import idmap_build as ib  # noqa: E402
import idmap_review_fetch as rf  # noqa: E402

IDMAP = os.path.join(ROOT, "data", "idmap.json")
REVIEW = os.path.join(ROOT, "data", "idmap-review.json")
PUBLICATIONS = os.path.join(ROOT, "data", "publications.json")

# key -> accepted DOI. venue+year+authors all confirmed against publications.json.
ACCEPT = {
    "ansel:gecco:2011": "10.1145/2001576.2001805",
    "ansel:xrds:2010": "10.1145/1836543.1836554",
    "bernstein-kjolstad:2016": "10.1145/2930661",
    "hall:computer:1996": "10.1109/2.546613",
    "lee:micro:2002": "10.1109/micro.2002.1176243",
    "sheldon:lcpc:2001": "10.1007/3-540-35767-x_17",
    "stephenson:pldi:2000": "10.1145/349299.349317",
    "thies:bmc:2007": "10.1186/1471-2105-8-s5-s3",
    "ugcf-isca21": "10.1109/isca52012.2021.00041",
    "wilson:sigplan:1994": "10.1145/193209.193217",
    "witchel:micro:2001": "10.1109/micro.2001.991111",
    "zhao:cgo:2007": "10.1109/cgo.2007.12",
}

# key -> one-line note for a genuinely unclear row, left in idmap-review.json.
NOTE = {
    "Zaharia:CIDR:2017": "no candidate matches title/venue/year; CIDR papers "
        "typically carry no DOI at all.",
    "agarwal:suif:1997": "no candidate matches; SUIF workshop paper likely "
        "has no DOI.",
    "amarasinghe:gomactech:2003": "cand[0] title nearly matches but venue "
        "(ASIAN/PEPM 2002) and year disagree with GOMACTech 2003 -- looks "
        "like a talk reusing an earlier paper's title, not the same DOI.",
    "amarasinghe:hotchips:1995": "no candidate matches; wrong Hot Chips "
        "years, unrelated authors.",
    "amarasinghe:siam:1995": "cand[0] is a similar-titled 1994 book chapter "
        "with an overlapping but different author list (Lim, not Tseng); "
        "not a confident match.",
    "bruening:fddo:2000": "no candidate matches title/authors.",
    "bruening:fddo:2001": "no candidate matches title/authors.",
    "chuvpilo:hpca-np:2002": "no candidate matches; unrelated HPCA papers.",
    "hall:dtj:1998": "shares claimed_doi 10.1109/2.546613 with "
        "hall:computer:1996 (now accepted there); Crossref record is the "
        "Computer/1996 article, not this Digital Technical Journal reprint "
        "-- likely same_work_as hall:computer:1996, no distinct DOI found.",
    "hall:siam:1995": "no real candidate; only SIAM proceedings front-matter "
        "noise.",
    "ishibe:xsig:2026": "cand[0] (NetBlocks, PLDI) shares two authors but "
        "different title/venue/full author list -- a related but distinct "
        "paper.",
    "ithemal-icml": "cand[0] (BHive, IISWC'19) is a companion benchmark "
        "paper by an overlapping team, not this ICML paper -- different "
        "title/venue.",
    "jaeyeon:mlsys:2023": "cand[0] (WACO) is a different paper by the same "
        "group (3 of 5 authors overlap) -- title doesn't match.",
    "kiriansky:security:2002": "no real candidate; only USENIX Security "
        "issue-front-matter noise.",
    "kjolstad:2018:workspace": "cand[0] is the CGO'19 published version "
        "(adds Willow Ahrens as author) -- venue/year genuinely differ from "
        "this arXiv preprint entry; assigning the CGO DOI here would "
        "conflate preprint and camera-ready.",
    "kotkar:hci4cid:2008": "no candidate matches.",
    "kotkar:wisard:2008": "no real candidate; only WISARD workshop-front-"
        "matter noise.",
    "kuo:pphec:2005": "no candidate matches title/authors.",
    "levison:dyd:2001": "no candidate matches; unrelated workshop papers.",
    "lugato:avancees:2018": "no candidate matches; AVANCEES is a French "
        "outreach venue, likely uncatalogued in Crossref. Candidates are "
        "all differently-titled TACO papers.",
    "olszewski:wodet:2011": "all 3 candidates are the same earlier 'Kendo' "
        "paper (ASPLOS'09) by the same authors -- title/venue/year don't "
        "match this WoDet 2011 paper.",
    "puppin:ijpp:2005": "shares claimed_doi 10.1109/MICRO.2002.1176243 with "
        "lee:micro:2002 (now accepted there); Crossref record is the MICRO "
        "2002 paper, not this JILP 2005 journal venue -- likely an extended "
        "journal version with no DOI of its own, possibly same_work_as "
        "lee:micro:2002.",
    "puppin:mteac:2001": "no candidate matches; unrelated Tullsen SMT "
        "papers.",
    "rabbah:hpec:2005": "cand[0] ('Cache aware optimization...', LCTES'05) "
        "overlaps on 3 of 5 authors but title/venue differ from this HPEC "
        "2005 paper -- a related but distinct paper.",
    "thies:asploswaci:2004": "no candidate matches; all 3 are unrelated "
        "ASPLOS'16 WACI session notices.",
    "thies:recombposter:2006": "shares claimed_doi with thies:bmc:2007 (now "
        "accepted there); Crossref record is the BMC Bioinformatics 2007 "
        "paper, not this RECOMB 2006 poster -- likely a poster preview of "
        "that paper with no DOI of its own.",
    "thies:www:2002": "no candidate matches; unrelated WWW'02 papers.",
    "tiramisu-auto": "cand[0] (Deep Learning Model for Loop Interchange) is "
        "a different paper by an overlapping team -- title doesn't match.",
    "vemal-neurips": "no candidate matches; NeurIPS proceedings papers "
        "generally carry no Crossref DOI.",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--mailto", default="samana@mit.edu")
    args = ap.parse_args()

    with open(IDMAP) as fh:
        idmap = json.load(fh)
    with open(REVIEW) as fh:
        review = json.load(fh)
    with open(PUBLICATIONS) as fh:
        pubs = {p["bibtexKey"]: p for p in json.load(fh)}

    missing = [k for k in ACCEPT if k not in review]
    missing += [k for k in NOTE if k not in review]
    if missing:
        print("!! not in review file:", missing, file=sys.stderr)
        return 1
    overlap = set(ACCEPT) & set(NOTE)
    if overlap:
        print("!! keys in both ACCEPT and NOTE:", overlap, file=sys.stderr)
        return 1
    all_41 = set(ACCEPT) | set(NOTE)
    unhandled = set(review) - all_41
    if unhandled:
        print("!! review keys neither accepted nor noted:", unhandled,
              file=sys.stderr)
        return 1

    existing_dois = {rec["doi"].lower() for rec in idmap.values() if rec.get("doi")}
    dup = [k for k, doi in ACCEPT.items() if doi.lower() in existing_dois]
    if dup:
        print("!! accepted doi already present in idmap.json:", dup,
              file=sys.stderr)
        return 1

    class FetchAdapter:
        """Adapts the module-level cached fetch() to idmap_build's fetch.get() calls."""
        mailto = args.mailto

        @staticmethod
        def get(url):
            return rf.fetch(url)

    fetch = FetchAdapter()

    for key, doi in sorted(ACCEPT.items()):
        pub = pubs[key]
        openalex = ib.openalex_by_doi(fetch, doi)
        s2 = ib.s2_by_doi(fetch, doi)
        idmap[key] = {
            "doi": doi,
            "openalex": openalex,
            "s2": s2,
            "title": pub.get("title") or "",
            "year": pub.get("year"),
            "match": "fuzzy_reviewed",
            "kind": "doi",
        }
        del review[key]
        print("accept  %-28s doi=%s openalex=%s s2=%s" % (key, doi, openalex, s2))

    for key, note in NOTE.items():
        review[key]["note"] = note
        print("note    %-28s %s" % (key, note[:70]))

    if not args.write:
        print("\ndry run -- nothing written. Pass --write to commit.")
        return 0

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
