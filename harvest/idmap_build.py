#!/usr/bin/env python3
"""Build data/idmap.json: bibtexKey -> {doi, openalex, s2, title, year, match}.

Three hops, in order:

  1. Crossref. If the publication already carries a `doi`, that DOI is verified
     against Crossref metadata. If it does not, the DOI is searched for with
     `query.bibliographic`. Either way the DOI is accepted only when the title
     Crossref returns matches the title we hold, after normalization.
  2. OpenAlex, keyed by the accepted DOI.
  3. Semantic Scholar, keyed by the accepted DOI.

Theses and technical reports usually have no DOI at all. Those are recorded as
`kind: no_doi` and are not failures. Everything else that fails to resolve goes
to data/idmap-review.json with the top three Crossref candidates, for a human.

Stdlib only. Writes nothing unless --write is given.

    python3 harvest/idmap_build.py                  # dry run, fills the cache
    python3 harvest/idmap_build.py --write          # write the two data files
    python3 harvest/idmap_build.py --report         # summarize what is on disk
"""

import argparse
import hashlib
import html
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PUBLICATIONS = os.path.join(ROOT, "data", "publications.json")
IDMAP = os.path.join(ROOT, "data", "idmap.json")
REVIEW = os.path.join(ROOT, "data", "idmap-review.json")
CACHE = os.path.join(HERE, "idmap_cache")

# Item types that legitimately have no DOI. A thesis that *does* turn out to
# have one still resolves normally; this only decides how a miss is recorded.
NO_DOI_KINDS = {
    "mastersthesis",
    "phdthesis",
    "sciencethesis",
    "sbthesis",
    "techreport",
    "misc",
}

# Supplementary-material DOIs minted alongside the real one: ACM hangs /mm1,
# /vid, /app on the article DOI. Accepting one silently maps a paper to its
# video.
SUPPLEMENTARY_RE = re.compile(
    r"/(?:mm|vid|video|suppl?|supplement|app|appendix|data|dataset|code|software)"
    r"[0-9]*$",
    re.I,
)

# A prefix match on a short title is a coincidence, not a match.
MIN_PREFIX_CHARS = 25

ARXIV_RE = re.compile(r"arxiv\.org/(?:abs|pdf)/([0-9]{4}\.[0-9]{4,5})", re.I)
ARXIV_KEY_RE = re.compile(r"^arxiv:([0-9]{4}\.[0-9]{4,5})$", re.I)


def arxiv_doi(entry):
    """arXiv preprints carry a derivable DOI even when the entry omits it."""
    for pattern, field in (
        (ARXIV_RE, entry.get("url") or ""),
        (ARXIV_KEY_RE, entry.get("bibtexKey") or ""),
    ):
        found = pattern.search(str(field))
        if found:
            return "10.48550/arXiv." + found.group(1)
    return None


# ---------------------------------------------------------------- normalizing

_TAG_RE = re.compile(r"<[^>]+>")
_NONALNUM_RE = re.compile(r"[^0-9a-z]+")


def normalize(title):
    """Lowercase, strip markup and punctuation, collapse whitespace."""
    if not title:
        return ""
    text = html.unescape(str(title))
    text = _TAG_RE.sub(" ", text)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    text = _NONALNUM_RE.sub(" ", text)
    return " ".join(text.split())


def compact(title):
    """normalize() with the spaces taken out too.

    "multi-stage" and "multistage" are the same word to a reader and different
    strings to normalize(), which turns the hyphen into a space. Comparing the
    space-free forms makes hyphenation and spacing differences disappear.
    """
    return normalize(title).replace(" ", "")


def title_match(ours, theirs):
    """Return 'exact', 'fuzzy', or None."""
    a, b = normalize(ours), normalize(theirs)
    if not a or not b:
        return None
    ca, cb = a.replace(" ", ""), b.replace(" ", "")
    if a == b or ca == cb:
        return "exact"
    short, long = (ca, cb) if len(ca) <= len(cb) else (cb, ca)
    if len(short) >= MIN_PREFIX_CHARS and long.startswith(short):
        return "fuzzy"
    return None


def is_supplementary(doi, crossref_type=None):
    if crossref_type == "component":
        return True
    return bool(SUPPLEMENTARY_RE.search(doi or ""))


# ------------------------------------------------------------------- fetching


class Fetcher:
    """Cached, per-host rate-limited GET with 429/5xx backoff."""

    def __init__(self, mailto, interval=1.0, retries=4, verbose=False):
        self.mailto = mailto
        self.interval = interval
        self.retries = retries
        self.verbose = verbose
        self.last = {}
        self.stats = {"cache": 0, "net": 0, "retry": 0, "fail": 0}
        os.makedirs(CACHE, exist_ok=True)

    def _wait(self, host):
        gap = time.time() - self.last.get(host, 0.0)
        if gap < self.interval:
            time.sleep(self.interval - gap)
        self.last[host] = time.time()

    def get(self, url):
        """Return parsed JSON, or None on 404 / permanent failure."""
        path = os.path.join(
            CACHE, hashlib.sha1(url.encode()).hexdigest() + ".json"
        )
        if os.path.exists(path):
            self.stats["cache"] += 1
            with open(path) as fh:
                return json.load(fh).get("body")

        host = urllib.parse.urlparse(url).netloc
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "commit-nextgen-idmap/1.0 "
                "(https://github.com/mit-commit/nextgen; "
                "mailto:%s)" % self.mailto,
                "Accept": "application/json",
            },
        )

        body = None
        for attempt in range(self.retries + 1):
            self._wait(host)
            try:
                self.stats["net"] += 1
                with urllib.request.urlopen(req, timeout=45) as resp:
                    body = json.loads(resp.read().decode("utf-8", "replace"))
                break
            except urllib.error.HTTPError as err:
                if err.code == 404:
                    body = None
                    break
                if err.code in (429, 500, 502, 503, 504) and attempt < self.retries:
                    self.stats["retry"] += 1
                    delay = float(
                        err.headers.get("Retry-After") or 0
                    ) or self.interval * (2 ** attempt) * 2
                    if self.verbose:
                        print(
                            "    %s on %s, sleeping %.1fs"
                            % (err.code, host, delay),
                            file=sys.stderr,
                        )
                    time.sleep(min(delay, 60))
                    continue
                self.stats["fail"] += 1
                if self.verbose:
                    print("    HTTP %s %s" % (err.code, url), file=sys.stderr)
                return None
            except Exception as err:  # network hiccup, bad JSON
                if attempt < self.retries:
                    self.stats["retry"] += 1
                    time.sleep(self.interval * (2 ** attempt) * 2)
                    continue
                self.stats["fail"] += 1
                if self.verbose:
                    print("    %s %s" % (type(err).__name__, url), file=sys.stderr)
                return None

        tmp = path + ".tmp"
        with open(tmp, "w") as fh:
            json.dump({"url": url, "body": body}, fh)
        os.replace(tmp, path)
        return body


# -------------------------------------------------------------------- sources

CROSSREF_SELECT = "DOI,title,subtitle,issued,type,container-title,author"


def crossref_by_doi(fetch, doi):
    url = "https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="")
    data = fetch.get(url)
    if not data or data.get("status") != "ok":
        return None
    return data.get("message")


def crossref_search(fetch, entry, rows=3):
    """Top `rows` candidates for an entry, best first."""
    bits = [str(entry.get("title") or "")]
    for key in ("author0", "venue", "booktitle", "journal", "year"):
        if entry.get(key):
            bits.append(str(entry[key]))
    query = " ".join(bits)
    url = "https://api.crossref.org/works?" + urllib.parse.urlencode(
        {
            "query.bibliographic": query,
            "rows": rows,
            "select": CROSSREF_SELECT,
            "mailto": fetch.mailto,
        }
    )
    data = fetch.get(url)
    if not data or data.get("status") != "ok":
        return []
    return data.get("message", {}).get("items", []) or []


def cr_title(item):
    """Crossref splits "Foo: a bar" into title=['Foo'], subtitle=['a bar'].

    Comparing against the title alone matches every paper whose name starts
    with the same word, so the subtitle has to be glued back on.
    """
    item = item or {}
    titles = item.get("title") or []
    head = titles[0] if titles else ""
    subs = item.get("subtitle") or []
    sub = subs[0] if subs else ""
    if head and sub:
        return "%s: %s" % (head, sub)
    return head or sub


def cr_year(item):
    issued = (item or {}).get("issued", {}).get("date-parts") or [[]]
    parts = issued[0] if issued else []
    return parts[0] if parts else None


def openalex_work(fetch, doi):
    url = "https://api.openalex.org/works/doi:%s?%s" % (
        urllib.parse.quote(doi, safe="/"),
        urllib.parse.urlencode(
            {"mailto": fetch.mailto, "select": "id,title,publication_year"}
        ),
    )
    data = fetch.get(url)
    return data if (data and data.get("id")) else None


def openalex_by_doi(fetch, doi):
    work = openalex_work(fetch, doi)
    if not work:
        return None
    return work["id"].rsplit("/", 1)[-1]  # https://openalex.org/W123 -> W123


def s2_by_doi(fetch, doi):
    url = "https://api.semanticscholar.org/graph/v1/paper/DOI:%s?fields=paperId" % (
        urllib.parse.quote(doi, safe="/")
    )
    data = fetch.get(url)
    if not data:
        return None
    return data.get("paperId")


# ------------------------------------------------------------------- resolver


def resolve_doi(fetch, entry, verbose=False):
    """Return (doi, match, candidates). doi/match are None when unresolved."""
    title = entry.get("title") or ""
    claimed = (entry.get("doi") or "").strip()
    claimed = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:)", "", claimed, flags=re.I)
    if not claimed:
        claimed = arxiv_doi(entry) or ""

    # 1. Verify the DOI the entry already carries.
    if claimed and not is_supplementary(claimed):
        item = crossref_by_doi(fetch, claimed)
        if item:
            match = title_match(title, cr_title(item))
            if match and not is_supplementary(item.get("DOI"), item.get("type")):
                # Crossref's casing is the registered one; keep it.
                return item.get("DOI") or claimed, match, []
        else:
            # Crossref does not know this DOI. arXiv (10.48550/*), Zenodo and
            # other DataCite registrants never appear there, and their DOIs are
            # perfectly real -- title-check them against OpenAlex instead.
            work = openalex_work(fetch, claimed)
            if work:
                match = title_match(title, work.get("title"))
                if match:
                    return claimed, match, []

    # A thesis or TR shares its title with the paper it became, so a search
    # confidently returns the *paper's* DOI -- which would make the two
    # entries the same work and double-count every citation. Theses only ever
    # get a DOI they explicitly claim.
    if entry.get("itemType") in NO_DOI_KINDS:
        return None, None, []

    # 2. Otherwise search, and take the best title-matching candidate.
    candidates = crossref_search(fetch, entry)
    best = None
    for item in candidates:
        doi = item.get("DOI") or ""
        if not doi or is_supplementary(doi, item.get("type")):
            continue
        match = title_match(title, cr_title(item))
        if match == "exact":
            return doi, "exact", candidates
        if match == "fuzzy" and best is None:
            best = (doi, "fuzzy")
    if best:
        return best[0], best[1], candidates

    # A DOI Crossref will not corroborate is not accepted, even one the entry
    # already claimed. It goes to review with `claimed_doi` set, for a human.
    return None, None, candidates


def candidate_summary(items):
    out = []
    for item in items[:3]:
        out.append(
            {
                "doi": item.get("DOI") or "",
                "title": cr_title(item),
                "year": cr_year(item),
                "type": item.get("type"),
                "container": (item.get("container-title") or [""])[0],
            }
        )
    return out


def dedupe(idmap, review, source):
    """No two bibtexKeys may join to the same work.

    publications.json deliberately points a tech report or thesis at the DOI of
    the paper it became, so a shared DOI is usually intentional rather than a
    mistake. But a citations or artifacts lane joining on DOI would count that
    work twice, so exactly one key per DOI keeps the join ids.

    The published paper wins; the thesis or TR is recorded as `no_doi` with
    `same_work_as` naming the winner, which keeps the relationship without
    double-counting it. When a group has no clear winner -- two papers claiming
    one DOI -- nobody wins and all of them go to review.
    """
    groups = {}
    for key, rec in idmap.items():
        if rec.get("doi"):
            groups.setdefault(rec["doi"].lower(), []).append(key)

    folded = demoted = 0
    for doi, keys in sorted(groups.items()):
        if len(keys) < 2:
            continue
        papers = [k for k in keys
                  if source[k].get("itemType") not in NO_DOI_KINDS]

        if len(papers) == 1:
            winner = papers[0]
            for key in keys:
                if key == winner:
                    continue
                rec = idmap[key]
                rec.update({"doi": None, "openalex": None, "s2": None,
                            "match": None, "kind": "no_doi",
                            "same_work_as": winner})
                folded += 1
            continue

        for key in keys:
            entry = source[key]
            others = ", ".join(k for k in keys if k != key)
            review[key] = {
                "title": entry.get("title") or "",
                "year": entry.get("year"),
                "itemType": entry.get("itemType"),
                "venue": entry.get("venue"),
                "claimed_doi": entry.get("doi"),
                "reason": "doi %s is also claimed by %s, and neither is "
                          "clearly the published version" % (doi, others),
                "candidates": [{"doi": doi, "title": idmap[key]["title"],
                                "year": idmap[key]["year"], "type": None,
                                "container": None}],
            }
            del idmap[key]
            demoted += 1
    return folded, demoted


# ---------------------------------------------------------------------- report


def report():
    if not os.path.exists(IDMAP):
        print("data/idmap.json: not built yet")
        return 1
    with open(IDMAP) as fh:
        idmap = json.load(fh)
    review = {}
    if os.path.exists(REVIEW):
        with open(REVIEW) as fh:
            review = json.load(fh)

    counts = {}
    for rec in idmap.values():
        key = rec.get("match") or rec.get("kind") or "unknown"
        counts[key] = counts.get(key, 0) + 1

    print("data/idmap.json      %d entries" % len(idmap))
    for key in sorted(counts):
        print("  %-12s %d" % (key, counts[key]))
    print("  with openalex  %d" % sum(1 for r in idmap.values() if r.get("openalex")))
    print("  with s2        %d" % sum(1 for r in idmap.values() if r.get("s2")))
    print("data/idmap-review.json  %d entries" % len(review))
    return 0


# ------------------------------------------------------------------------ main


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true",
                    help="write data/idmap.json and data/idmap-review.json "
                         "(default is a dry run)")
    ap.add_argument("--report", action="store_true",
                    help="summarize the files already on disk and exit")
    ap.add_argument("--mailto", default="samana@mit.edu",
                    help="contact address for the Crossref/OpenAlex polite pools")
    ap.add_argument("--sleep", type=float, default=1.0,
                    help="minimum seconds between requests to one host")
    ap.add_argument("--limit", type=int, default=0,
                    help="only process the first N publications")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    if args.report:
        return report()

    with open(PUBLICATIONS) as fh:
        pubs = json.load(fh)
    if args.limit:
        pubs = pubs[: args.limit]

    fetch = Fetcher(args.mailto, interval=args.sleep, verbose=args.verbose)
    idmap, review, source = {}, {}, {}
    started = time.time()

    for n, entry in enumerate(pubs, 1):
        key = entry.get("bibtexKey")
        if not key:
            print("  !! entry %d has no bibtexKey, skipped" % n, file=sys.stderr)
            continue
        if key in idmap or key in review:
            print("  !! duplicate bibtexKey %r, skipped" % key, file=sys.stderr)
            continue

        title = entry.get("title") or ""
        source[key] = entry
        doi, match, candidates = resolve_doi(fetch, entry, args.verbose)

        openalex = s2 = None
        if doi:
            openalex = openalex_by_doi(fetch, doi)
            s2 = s2_by_doi(fetch, doi)

        if doi:
            idmap[key] = {
                "doi": doi,
                "openalex": openalex,
                "s2": s2,
                "title": title,
                "year": entry.get("year"),
                "match": match,
                "kind": "doi",
            }
        elif entry.get("itemType") in NO_DOI_KINDS:
            idmap[key] = {
                "doi": None,
                "openalex": None,
                "s2": None,
                "title": title,
                "year": entry.get("year"),
                "match": None,
                "kind": "no_doi",
            }
        else:
            review[key] = {
                "title": title,
                "year": entry.get("year"),
                "itemType": entry.get("itemType"),
                "venue": entry.get("venue"),
                "claimed_doi": entry.get("doi"),
                "candidates": candidate_summary(candidates),
            }

        if args.verbose or n % 25 == 0 or n == len(pubs):
            print(
                "[%3d/%3d] %5.0fs  resolved=%d review=%d  net=%d cache=%d"
                % (n, len(pubs), time.time() - started,
                   len(idmap), len(review), fetch.stats["net"], fetch.stats["cache"]),
                file=sys.stderr,
            )

    folded, demoted = dedupe(idmap, review, source)
    if folded:
        print("%d thesis/TR entries folded onto the paper's DOI "
              "(same_work_as)" % folded)
    if demoted:
        print("%d entries demoted to review for an ambiguous shared DOI"
              % demoted)

    counts = {}
    for rec in idmap.values():
        k = rec["match"] or rec["kind"]
        counts[k] = counts.get(k, 0) + 1
    print()
    print("publications   %d" % len(pubs))
    for k in sorted(counts):
        print("  %-12s %d" % (k, counts[k]))
    print("  review       %d" % len(review))
    print("  openalex     %d" % sum(1 for r in idmap.values() if r["openalex"]))
    print("  s2           %d" % sum(1 for r in idmap.values() if r["s2"]))
    print("requests: %(net)d net, %(cache)d cached, %(retry)d retried, "
          "%(fail)d failed" % fetch.stats)

    if not args.write:
        print()
        print("dry run — nothing written. Responses are cached, so --write is fast.")
        return 0

    for path, payload in ((IDMAP, idmap), (REVIEW, review)):
        tmp = path + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(payload, fh, indent=1, sort_keys=True, ensure_ascii=False)
            fh.write("\n")
        os.replace(tmp, path)
        print("wrote %s" % os.path.relpath(path, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
