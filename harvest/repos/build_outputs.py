#!/usr/bin/env python3
"""Step 1c of the repos lane: join candidates + verdicts into mentions.json,
then write search-plan.json for the papers that came up empty.

Nothing here searches GitHub -- the plan is keyword candidates only.
"""
import json, os, re
from collections import OrderedDict, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
R = lambda *p: os.path.join(ROOT, *p)

STOP = set("""The This That These Those We Our In On For And Or But With Without By Of To From At As It Its Is Are Was Were Be Been Being Has Have Had Do Does Did Can Could Will Would Should May Might Must All Any Each Such Then Than When While Where Which Who Whom Whose What How Why Not No Nor Both Either Neither Also However Thus Hence Therefore Moreover Furthermore Finally First Second Third Figure Table Section Appendix Abstract Introduction Conclusion Related Work Results Evaluation Experiments Method Methods Approach System Systems Design Implementation Performance Analysis Compiler Compilers Language Languages Program Programs Programming Code Codes Data Memory Cache Thread Threads Parallel Sparse Dense Tensor Tensors Matrix Kernel Kernels GPU GPUs CPU CPUs FPGA API APIs DSL DSLs IR SIMD MIT CSAIL PhD MEng SM ACM IEEE USENIX University Institute Technology Massachusetts Cambridge Science Computer Electrical Engineering Laboratory Artificial Intelligence Machine Learning Deep Neural Network Networks Model Models Training Inference United States January February March April May June July August September October November December Monday""".split())
VENUES = set("""PLDI OOPSLA ASPLOS ISCA MICRO CGO CC POPL ICFP SC PPoPP LCTES SIGPLAN SIGARCH MLSys NeurIPS ICML ICLR HPCA IISWC ISPASS FCCM FPGA DAC ICS PACT SPAA EuroSys SOSP OSDI ATC NSDI USENIX ECOOP ESEC FSE ICSE ISMM VLDB SIGMOD WWW HotOS HPEC ARITH ISFP xSIG""".split())


def surnames(author0):
    out = []
    for chunk in re.split(r"\s+and\s+", author0 or ""):
        chunk = chunk.strip().rstrip(",.")
        if not chunk:
            continue
        if "," in chunk:
            last, _, first = chunk.partition(",")
        else:
            parts = chunk.split()
            last, first = (parts[-1], " ".join(parts[:-1])) if parts else ("", "")
        last = re.sub(r"[^A-Za-z\-']", "", last).strip()
        first = re.sub(r"[^A-Za-z\-' ]", "", first).strip()
        if last:
            out.append((last, first))
    return out


def usernames(last, first):
    l, f = last.lower().replace("'", "").replace("-", ""), first.lower().split(" ")[0] if first else ""
    f = re.sub(r"[^a-z]", "", f)
    cands = [l]
    if f:
        cands += [f + l, f[0] + l, l + f[0], f + "-" + l, f + "_" + l]
    return cands


def software_names(entry):
    """Candidate tool names: the "Name: subtitle" head, acronyms, CamelCase."""
    names = []
    title = re.sub(r"<[^>]+>", " ", str(entry.get("title") or ""))
    head = title.split(":")[0].strip()
    if head and len(head.split()) <= 3 and head.lower() not in ("a", "the"):
        names.append(head if len(head.split()) == 1 else head.replace(" ", ""))
    if entry.get("project"):
        names.append(str(entry["project"]))
    blob = " ".join(str(entry.get(k) or "") for k in ("title", "shorttitle", "abstract", "summary"))
    blob = re.sub(r"<[^>]+>", " ", blob)
    for m in re.finditer(r"\(([A-Z][A-Za-z0-9+\-]{1,14})\)", blob):          # "... (UCF)"
        names.append(m.group(1))
    for m in re.finditer(r"\b([A-Z][A-Za-z0-9]*(?:[A-Z][a-z0-9]+|[0-9])[A-Za-z0-9+\-]*)\b", blob):
        names.append(m.group(1))                                             # CamelCase
    for m in re.finditer(r"\b([A-Z]{2,10})\b", blob):                         # acronyms
        names.append(m.group(1))
    for m in re.finditer(r"\b([A-Z][A-Za-z0-9]{2,})\b(?=[ ,]+(?:is|compiler|framework|language|library|system|tool|DSL|runtime|generates|extends|supports))", blob):
        names.append(m.group(1))
    seen, out = set(), []
    for n in names:
        n = n.strip()
        if len(n) < 3 or n in STOP or n.upper() in VENUES:
            continue
        if n.lower() in seen:
            continue
        seen.add(n.lower())
        out.append(n)
    return out[:12]


def repo_name_forms(names):
    """github-ish spellings of a tool name: Taco -> taco, SySTeC -> systec, ..."""
    out = []
    for n in names[:6]:
        low = n.lower()
        kebab = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "-", n).lower()
        for v in (low, kebab, low + ".jl", low + "-artifact", low + "-lang"):
            if v not in out:
                out.append(v)
    return out[:20]


def repair(urls, repairs):
    """Swap layout-mangled URLs for the resolvable form repair.py found, then
    merge duplicates that collapse onto the same target."""
    merged = OrderedDict()
    for u in urls:
        u = dict(u)
        fixed = repairs.get(u["url"])
        if fixed:
            u["raw_in_pdf"] = u["url"]
            u["url"] = fixed
            u["sources"] = sorted(set(u["sources"]) | {"repaired"})
        prev = merged.get(u["url"])
        if prev is None:
            merged[u["url"]] = u
        else:
            prev["sources"] = sorted(set(prev["sources"]) | set(u["sources"]))
            if not prev.get("context_line"):
                prev["context_line"] = u.get("context_line")
            if prev.get("raw_in_pdf") and not u.get("raw_in_pdf"):
                prev.pop("raw_in_pdf")
    return list(merged.values())


# Sibling files (slides, preprints) that no publications.json entry points at.
# Attributed by hand -- same work, different file -- so step 2 knows where the
# hits belong. Kept out of mentions.json, which stays strictly one-PDF-per-entry.
SIBLING_OF = {
    "papers/2014/bosboom-oopsla14-commensal-slides.pdf": ("bosboom:oopsla:2014", "slides for the OOPSLA'14 commensal-parallelism paper"),
    "papers/2019/oopsla19-paper34.pdf": ("shajii:oopsla:2019", "submission-numbered copy of the Seq OOPSLA'19 paper"),
    "papers/2020/mueller-transpositions-arxiv.pdf": ("mueller_sparse_2020", "arXiv version of the SPAA'20 transpositions paper"),
    "papers/2023/Finch_CGO_2023.pdf": ("looplets-cgo23", "preprint of the CGO'23 Looplets paper"),
    "papers/2024/Willow-Finch-Arxiv.pdf": ("ahrens_finch_2025", "arXiv version of the Finch paper"),
}


def _norm(u):
    u = re.sub(r"^https?://(?:www\.)?", "", u.strip()).rstrip("/")
    return u


def prune(urls, cache):
    """Drop dead candidates that are only line-break artifacts of a live one.

    PDF text extraction leaves three signatures: trailing junk glued on
    (footnote markers, the next word), a URL truncated at the line break, and a
    hyphen eaten by de-hyphenation. Each is dropped only when a *live* sibling
    from the same PDF explains it; genuinely dead links survive.
    """
    def live(u):
        v = cache.get(u["url"], {})
        return isinstance(v.get("status"), int) and v["status"] < 400

    lives = [u for u in urls if live(u)]
    keep, drop = [], []
    for u in urls:
        # a URL printed with a trailing slash that another candidate continues is
        # the head of a wrapped line, not a link to the owner page
        owner_only = re.match(r"^[^/]+/[^/]+$", _norm(u["url"]))
        if owner_only:
            # "github.com/ARM" next to "github.com/ARM-software/..." is a fragment
            cont = next((o for o in urls if o is not u and _norm(o["url"]).startswith(_norm(u["url"])) and _norm(o["url"]) != _norm(u["url"])), None)
            if cont:
                drop.append({"url": u["url"], "reason": "owner-page fragment of " + cont["url"]})
                continue
        if u["url"].rstrip().endswith("/"):
            head = _norm(u["url"])
            cont = next((o for o in urls if o is not u and _norm(o["url"]).startswith(head + "/")), None)
            if cont:
                drop.append({"url": u["url"], "reason": "line-break fragment of " + cont["url"]})
                continue
        if live(u):
            keep.append(u)
            continue
        d = _norm(u["url"])
        dd = d.replace("-", "").replace("%22", "").replace("%7D", "").replace("%", "")
        reason = None
        for l in lives:
            n = _norm(l["url"])
            if d == n:
                continue
            if d.startswith(n):
                reason = "trailing text glued onto " + l["url"]
            elif n.startswith(d) and (n[len(d)].isalnum() or n[len(d)] == "/") and (d[-1].isalnum() or d[-1] in "-/_."):
                reason = "truncated at a line break; full form " + l["url"]
            elif dd == n.replace("-", ""):
                reason = "hyphen lost to de-hyphenation of " + l["url"]
            elif n in d:
                reason = "run together with " + l["url"]
            if reason:
                break
        if reason is None and "/" not in d:
            # a bare host left behind by a line break, e.g. "git.example.org"
            for other in urls:
                o = _norm(other["url"])
                if other is not u and o != d and o.startswith(d) and "/" in o:
                    reason = "bare host left by a line break; see " + other["url"]
                    break
        if reason is None:
            # glue on a link that is dead either way: keep one copy, the bare one
            for other in urls:
                o = _norm(other["url"])
                if other is not u and o != d and d.startswith(o) and o.count("/") >= 2 and not live(other):
                    reason = "trailing text glued onto " + other["url"] + " (also dead)"
                    break
        if reason:
            drop.append({"url": u["url"], "reason": reason})
        else:
            keep.append(u)
    return keep, drop


def main():
    pubs = json.load(open(R("data/publications.json")))
    by_key = {e["bibtexKey"]: e for e in pubs}
    cand = json.load(open(R("harvest/repos/_candidates.json")))
    cache = json.load(open(R("harvest/repos/_urlcache.json")))
    repairs = json.load(open(R("harvest/repos/_repairs.json"))) if os.path.exists(R("harvest/repos/_repairs.json")) else {}

    # ---- mentions.json -------------------------------------------------
    mentions = {k: {"urls": []} for k in by_key}
    orphans = {}
    pruned = {}
    for pdf, rec in sorted(cand["pdfs"].items()):
        if not rec["urls"]:
            continue
        keep, drop = prune(repair(rec["urls"], repairs), cache)
        if drop:
            pruned[pdf] = drop
        entries = []
        for u in keep:
            v = cache.get(u["url"], {})
            item = {
                "url": u["url"],
                **({"raw_in_pdf": u["raw_in_pdf"]} if u.get("raw_in_pdf") else {}),
                "status": v.get("status") if v.get("status") is not None else ("error:" + (v.get("error") or "unchecked")),
                "context_line": u["context_line"],
                "source_pdf": pdf,
                "page": u["page"],
                "found_via": u["sources"],
            }
            if v.get("renamed") and v.get("final_url"):
                item["final_url"] = v["final_url"]
            entries.append(item)
        keys = rec["bibtexKeys"]
        if keys:
            for k in keys:
                mentions[k]["urls"].extend(entries)
        else:
            key, why = SIBLING_OF.get(pdf, (None, None))
            orphans[pdf] = {"likely_bibtexKey": key, "why": why, "urls": entries}
    with open(R("harvest/repos/mentions.json"), "w") as fh:
        json.dump(mentions, fh, indent=2, sort_keys=True)
    if pruned:
        with open(R("harvest/repos/mentions-pruned-variants.json"), "w") as fh:
            json.dump(pruned, fh, indent=2, sort_keys=True)
    if orphans:
        with open(R("harvest/repos/mentions-unmapped-pdfs.json"), "w") as fh:
            json.dump(orphans, fh, indent=2, sort_keys=True)

    # ---- who owns what, learned from the papers that did have URLs ------
    def owner_of(url):
        m = re.match(r"https?://(?:www\.)?(?:github\.com|gitlab\.com|bitbucket\.org)/([^/]+)", url, re.I)
        return m.group(1) if m else None

    owner_by_surname = defaultdict(set)
    owner_papers = defaultdict(set)
    for k, rec in mentions.items():
        sn = [x[0].lower() for x in surnames(by_key[k].get("author0"))]
        for u in rec["urls"]:
            owner = owner_of(u.get("final_url") or u["url"]) or owner_of(u["url"])
            if not owner:
                continue
            owner_papers[owner].add(k)
            for x in sn:
                owner_by_surname[x].add(owner)

    # orgs the group itself publishes under: whatever a `code` field points at,
    # plus owners whose name echoes an author of the paper that mentions them
    lab_orgs = set()
    for e in pubs:
        o = owner_of(e.get("code") or "")
        if o:
            lab_orgs.add(o)
    def echoes(owner, last):
        last, o = last.lower(), owner.lower()
        toks = re.split(r"[-_.]", o)
        return last == o or last in toks or (len(last) >= 5 and (o.startswith(last) or o.endswith(last)))

    for owner, keys in owner_papers.items():
        for k in keys:
            if any(echoes(owner, x[0]) for x in surnames(by_key[k].get("author0"))):
                lab_orgs.add(owner)

    # ---- search-plan.json ----------------------------------------------
    plan = {}
    for k, e in sorted(by_key.items()):
        live = [u for u in mentions[k]["urls"] if isinstance(u["status"], int) and u["status"] < 400]
        if live:
            continue
        sn = surnames(e.get("author0"))
        unames, known = [], []
        for last, first in sn:
            unames += usernames(last, first)
            known += [o for o in sorted(owner_by_surname.get(last.lower(), ()))
                      if o in lab_orgs or echoes(o, last)]
        names = software_names(e)
        pdf = e.get("url") if str(e.get("url", "")).endswith(".pdf") else None
        plan[k] = {
            "title": e.get("title"),
            "year": e.get("year"),
            "venue": e.get("venue") or e.get("booktitle") or e.get("journal") or e.get("type"),
            "project": e.get("project"),
            "topics": e.get("topics") or [],
            "author_surnames": [s[0] for s in sn],
            "username_candidates": list(dict.fromkeys(unames))[:24],
            "known_owners_same_authors": list(dict.fromkeys(known))[:12],
            "lab_org_candidates": sorted(lab_orgs),
            "software_name_candidates": names,
            "repo_name_candidates": repo_name_forms(names),
            "code_field_in_publications_json": e.get("code"),
            "dead_urls_in_paper": [u["url"] for u in mentions[k]["urls"]],
            "pdf": pdf,
            "pdf_on_disk": bool(pdf and os.path.exists(R(pdf))),
        }
    with open(R("harvest/repos/search-plan.json"), "w") as fh:
        json.dump(plan, fh, indent=2, sort_keys=True)

    # ---- console summary ------------------------------------------------
    live_keys = [k for k, v in mentions.items() if any(isinstance(u["status"], int) and u["status"] < 400 for u in v["urls"])]
    dead_keys = [k for k, v in mentions.items() if v["urls"] and k not in live_keys]
    print(f"bibtexKeys: {len(mentions)}  live: {len(live_keys)}  only-dead: {len(dead_keys)}  none: {len(plan) - len(dead_keys)}")
    print(f"unmapped PDFs with hits: {len(orphans)}")


if __name__ == "__main__":
    main()
