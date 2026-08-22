#!/usr/bin/env python3
"""Step 1a of the repos lane: pull code-host URLs out of every PDF in papers/.

Two sources per PDF:
  * link annotations (/Annots -> /A -> /URI) -- exact, never line-broken
  * page text -- regex over three variants of the text so URLs that the
    typesetter broke across lines (with or without a hyphen) are rejoined

Writes harvest/repos/_candidates.json; verification happens in verify.py.
"""
import json, os, re, sys, warnings
from collections import OrderedDict

warnings.filterwarnings("ignore")
from pypdf import PdfReader
from pypdf.errors import PdfReadError

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HOSTS = (
    r"(?:github\.com|raw\.githubusercontent\.com|gist\.github\.com|bitbucket\.org"
    r"|[a-z0-9-]*(?:gitlab|gitea|forgejo|git)\.[a-z0-9.-]+\.[a-z]{2,})"
)
# the lookbehind keeps "vcgit.hhi..." from being clipped to "git.hhi..."
URL_RE = re.compile(
    r"(?<![\w.@-])(?:https?://)?(?:www\.)?" + HOSTS + r"(?:/[^\s<>\"'\\^{}|`\[\]()]*)?",
    re.I,
)
TRAILING = ".,;:!?'\"\u2019\u201d>)]}*\u00b7\u2022"


def variants(text):
    """raw, de-hyphenated, and newline-collapsed views of the same text."""
    yield "text", text
    yield "dehyphen", re.sub(r"[-\u2010\u2011][ \t]*\n[ \t]*", "", text)
    # collapse a break that falls inside a token (no space either side)
    yield "joined", re.sub(r"(?<=[^\s])\n[ \t]*(?=[^\s])", "", text)
    # last resort: a URL wrapped mid-path with stray spaces around the break.
    # Glues the next line's words on too; repair.py trims those back off.
    yield "collapse", re.sub(r"[ \t]*\n[ \t]*", "", text)


def clean(u):
    u = u.strip().rstrip(TRAILING)
    u = re.sub(r"(?:%[0-9A-Fa-f]{2})+$", "", u)  # %22%7D and friends from BibTeX url fields
    while u.count("(") < u.count(")"):
        u = u[:-1].rstrip(TRAILING)
    if not u.lower().startswith("http"):
        u = "https://" + u
    return u


def context_for(text, url_tail):
    for line in text.splitlines():
        if url_tail in line:
            return " ".join(line.split())[:300]
    return None


def scan(path):
    """-> OrderedDict cleaned_url -> {sources:set, context_line, page}"""
    found = OrderedDict()

    def add(u, src, ctx, page):
        u = clean(u)
        if len(u) < 22:  # nothing shorter than https://github.com/x is useful
            return
        rec = found.setdefault(u, {"sources": set(), "context_line": ctx, "page": page})
        rec["sources"].add(src)
        if rec["context_line"] is None and ctx:
            rec["context_line"] = ctx

    try:
        reader = PdfReader(path, strict=False)
    except Exception as e:
        return found, f"open failed: {type(e).__name__}: {e}"
    err = None
    for pno, page in enumerate(reader.pages, 1):
        # annotations
        try:
            for annot in page.get("/Annots", []) or []:
                try:
                    obj = annot.get_object()
                    uri = (obj.get("/A") or {}).get("/URI")
                except Exception:
                    continue
                if uri and URL_RE.search(str(uri)):
                    m = URL_RE.search(str(uri))
                    add(m.group(0), "annot", None, pno)
        except Exception:
            pass
        # text
        try:
            text = page.extract_text() or ""
        except Exception as e:
            err = f"page {pno} text failed: {type(e).__name__}"
            continue
        if not text:
            continue
        raw = text
        for name, var in variants(text):
            for m in URL_RE.finditer(var):
                u = m.group(0)
                tail = u.split("/")[-1][:20] if "/" in u else u[-20:]
                add(u, name, context_for(raw, tail) or context_for(raw, "ithub"), pno)
    return found, err


def main():
    pubs = json.load(open(os.path.join(ROOT, "data/publications.json")))
    by_path = {}
    for e in pubs:
        for fld in ("url", "pdf"):
            v = e.get(fld)
            if v and v.lower().endswith(".pdf") and not v.startswith("http"):
                by_path.setdefault(v.lstrip("/"), []).append(e["bibtexKey"])

    pdfs = []
    for r, _, fs in os.walk(os.path.join(ROOT, "papers")):
        for f in sorted(fs):
            if f.lower().endswith(".pdf"):
                pdfs.append(os.path.relpath(os.path.join(r, f), ROOT))
    pdfs.sort()

    out = {"pdfs": {}, "errors": {}}
    for i, p in enumerate(pdfs, 1):
        found, err = scan(os.path.join(ROOT, p))
        if err:
            out["errors"][p] = err
        out["pdfs"][p] = {
            "bibtexKeys": by_path.get(p, []),
            "urls": [
                {"url": u, "sources": sorted(v["sources"]), "context_line": v["context_line"], "page": v["page"]}
                for u, v in found.items()
            ],
        }
        print(f"[{i}/{len(pdfs)}] {p}: {len(found)} url(s)" + (f"  !{err}" if err else ""), file=sys.stderr)

    with open(os.path.join(ROOT, "harvest/repos/_candidates.json"), "w") as fh:
        json.dump(out, fh, indent=2)
    n = sum(len(v["urls"]) for v in out["pdfs"].values())
    print(f"\n{n} candidate URLs across {sum(1 for v in out['pdfs'].values() if v['urls'])} PDFs; {len(out['errors'])} read errors", file=sys.stderr)


if __name__ == "__main__":
    main()
