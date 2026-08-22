#!/usr/bin/env python3
"""Step 1b': rescue dead candidates that are only mangled by PDF text layout.

Two mangles show up: text from the next line glued onto the end of a URL, and a
URL that wrapped mid-path. The `collapse` variant in extract_candidates.py turns
the second into the first, so one trim-back pass fixes both: cut at every
plausible boundary, longest first, and keep the longest prefix that resolves.
"""
import json, os, re, sys
from verify import check, CACHE

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def boundaries(u):
    """Prefixes of u with plausible glued-on text trimmed, longest first.

    Cuts land at seams the typesetter creates, never at a "/" -- dropping a
    whole path segment would turn a broken link into a different, wronger one.
    Prefixes that are merely truncated (nothing to trim) are left for prune().
    """
    m = re.match(r"(https?://([^/]+)/)(.*)", u)
    if not m:
        return []
    head, host, path = m.group(1), m.group(2).lower(), m.group(3)
    want_segs = len([x for x in path.split("/") if x])
    cuts = {len(path)}
    for pat, off in [
        (r"[a-z0-9)][A-Z]", 1),              # camel seam: tacoProc
        (r"(?<=[A-Z][A-Z])(?=[a-z])", 0),    # acronym seam: SPACiSLIP
        (r"[A-Za-z_)][0-9]", 1),             # footnote marker: graphit127
        (r"(?<=[0-9])(?=[A-Za-z])", 0),      # digit/word seam: c0e93b65main
        (r"[.,;:%)\]}]", 0),                 # punctuation and %-escapes
    ]:
        for mm in re.finditer(pat, path):
            cuts.add(mm.start() + off)
    for mm in re.finditer(r"https?://", path[1:]):  # a second URL run together
        cuts.add(mm.start() + 1)

    prefixes = set()
    for c in cuts:
        pre = path[:c]
        prefixes.add(pre)
        tail = re.search(r"[0-9]+$", pre)           # peel a trailing footnote run
        if tail:
            prefixes.update(pre[:i] for i in range(tail.start() + 1, tail.end()))

    out = []
    for pre in sorted(prefixes, key=len, reverse=True):
        cand = (head + pre).rstrip("/.,;:-")
        segs = [x for x in cand[len(head):].split("/") if x]
        if cand != u and len(segs) == want_segs:
            out.append(cand)
    return list(dict.fromkeys(out))


def main():
    cache = json.load(open(CACHE))
    cand = json.load(open(os.path.join(ROOT, "harvest/repos/_candidates.json")))
    urls = sorted({u["url"] for v in cand["pdfs"].values() for u in v["urls"]})
    live = {u for u in urls if isinstance(cache.get(u, {}).get("status"), int) and cache[u]["status"] < 400}
    repairs = {}
    for u in urls:
        if u in live:
            continue
        for c in boundaries(u):
            r = cache.get(c)
            if r is None:
                r = cache[c] = check(c)
            if isinstance(r["status"], int) and r["status"] < 400:
                live.add(c)
                repairs[u] = c
                print(f"  repaired {u}\n        -> {c}", file=sys.stderr)
                break
    json.dump(cache, open(CACHE, "w"), indent=2, sort_keys=True)
    json.dump(repairs, open(os.path.join(ROOT, "harvest/repos/_repairs.json"), "w"), indent=2, sort_keys=True)
    print(f"{len(repairs)} of {len(urls) - len(live)} dead candidates repaired", file=sys.stderr)


if __name__ == "__main__":
    main()
