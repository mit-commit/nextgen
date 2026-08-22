#!/usr/bin/env python3
"""Build harvest/authors/enriched.json: OpenAlex author profiles for every
person in harvest/authors/authors.json.

Resolution order, per person (never on name alone):

  1. ORCID first -- if authors.json already carries an ORCID, look up
     https://api.openalex.org/authors?filter=orcid:... directly.
  2. Otherwise, shared-work match: take every one of the person's papers
     that has an OpenAlex work id (from data/idmap.json, or -- if none of
     their papers are in idmap -- discovered by title search), fetch that
     work's authorship list, and find the *single* authorship whose folded
     last name + first initial matches the person. If two+ of the person's
     papers point at different OpenAlex author ids, or a work has two+
     authorships matching the same coarse key, that is ambiguous and is
     never auto-resolved.

For a resolved OpenAlex author id: works_count, summary_stats.h_index, and
current/last-known affiliation come from the author entity. Any homepage
comes from the *public* ORCID record's researcher-urls, when an ORCID is
known (from authors.json or discovered via the OpenAlex author entity).

Ambiguous or unresolved people are never guessed -- they are appended to
harvest/authors/review.json (tagged "openalex_ambiguous" /
"openalex_unresolved" / "openalex_search_unavailable" -- the last for people
whose only path was the title-search fallback and that request itself
failed, e.g. OpenAlex's search-endpoint quota exhausted; rerun to retarget
just those) and still get a stub row in enriched.json.

Stdlib only.

    python3 harvest/authors/enrich_openalex.py             # dry run, fills the cache
    python3 harvest/authors/enrich_openalex.py --write      # write enriched.json + review.json
    python3 harvest/authors/enrich_openalex.py --report     # summarize what is on disk
"""

import argparse
import hashlib
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
ROOT = os.path.dirname(os.path.dirname(HERE))
PUBLICATIONS = os.path.join(ROOT, "data", "publications.json")
IDMAP = os.path.join(ROOT, "data", "idmap.json")
AUTHORS_IN = os.path.join(HERE, "authors.json")
CACHE = os.path.join(HERE, "cache")
ENRICHED_OUT = os.path.join(HERE, "enriched.json")
REVIEW_OUT = os.path.join(HERE, "review.json")


# ------------------------------------------------------------------ name util
# (same folding rules as authors_build.py, duplicated to keep this script
# standalone)


def fold(text):
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(text.casefold().split())


NAME_SUFFIXES = {"jr", "jr.", "sr", "sr.", "ii", "iii", "iv"}


def name_tokens(name):
    tokens = fold(name).split()
    while len(tokens) > 1 and tokens[-1] in NAME_SUFFIXES:
        tokens.pop()
    return tokens


def coarse_key(name):
    tokens = name_tokens(name)
    if not tokens:
        return ""
    return "%s|%s" % (tokens[-1], tokens[0][0] if tokens[0] else "")


def norm_title(title):
    text = fold(title)
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


# ------------------------------------------------------------------- fetching


class Fetcher:
    """Cached, per-host rate-limited GET with 429/5xx backoff. Shares the
    authors/cache directory with authors_build.py -- keys are sha1(url)."""

    def __init__(self, mailto, intervals, retries=4, verbose=False, openalex_api_key=None):
        self.mailto = mailto
        self.openalex_api_key = openalex_api_key
        self.intervals = intervals  # {host: seconds}
        self.retries = retries
        self.verbose = verbose
        self.last = {}
        self.stats = {"cache": 0, "net": 0, "retry": 0, "fail": 0}
        os.makedirs(CACHE, exist_ok=True)

    def _wait(self, host):
        interval = self.intervals.get(host, 1.0)
        gap = time.time() - self.last.get(host, 0.0)
        if gap < interval:
            time.sleep(interval - gap)
        self.last[host] = time.time()

    def get(self, url):
        host = urllib.parse.urlparse(url).netloc
        if host == "api.openalex.org" and self.openalex_api_key:
            url += "&api_key=" + urllib.parse.quote(self.openalex_api_key)
        path = os.path.join(CACHE, hashlib.sha1(url.encode()).hexdigest() + ".json")
        if os.path.exists(path):
            self.stats["cache"] += 1
            with open(path) as fh:
                return json.load(fh).get("body")

        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "commit-nextgen-authors/1.0 "
                "(https://github.com/mit-commit/nextgen; mailto:%s)" % self.mailto,
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
                    delay = float(err.headers.get("Retry-After") or 0) or self.intervals.get(host, 1.0) * (2 ** attempt) * 2
                    if self.verbose:
                        print("    %s on %s, sleeping %.1fs" % (err.code, host, delay), file=sys.stderr)
                    time.sleep(min(delay, 60))
                    continue
                self.stats["fail"] += 1
                if self.verbose:
                    print("    HTTP %s %s" % (err.code, url), file=sys.stderr)
                return None
            except Exception as err:
                if attempt < self.retries:
                    self.stats["retry"] += 1
                    time.sleep(self.intervals.get(host, 1.0) * (2 ** attempt) * 2)
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


def oa_id(full_id):
    """https://openalex.org/A123 -> A123"""
    if not full_id:
        return None
    return full_id.rsplit("/", 1)[-1]


# ----------------------------------------------------------- OpenAlex lookups


def openalex_author_by_orcid(fetch, orcid):
    """Direct-ID lookup (authors/orcid:<orcid>), not the filter-search form --
    OpenAlex treats external-id lookups and filtered list search as separate
    request classes with separate quota, and only the latter is metered by
    the daily USD-credit budget that the citations/artifacts lanes' heavy
    search-endpoint usage exhausts; this form keeps working through that."""
    url = "https://api.openalex.org/authors/orcid:%s?%s" % (
        urllib.parse.quote(orcid, safe=""),
        urllib.parse.urlencode({"mailto": fetch.mailto}),
    )
    return fetch.get(url)


def openalex_author_entity(fetch, author_id):
    url = "https://api.openalex.org/authors/%s?%s" % (
        author_id,
        urllib.parse.urlencode({"mailto": fetch.mailto}),
    )
    return fetch.get(url)


def openalex_work_authorships(fetch, work_id):
    url = "https://api.openalex.org/works/%s?%s" % (
        work_id,
        urllib.parse.urlencode({"select": "id,title,authorships", "mailto": fetch.mailto}),
    )
    return fetch.get(url)


FETCH_FAILED = object()  # sentinel: distinguishes "the search request itself failed" (retry
# later) from "the request succeeded and no candidate title matched" (genuinely no match)


def openalex_search_work(fetch, title):
    url = "https://api.openalex.org/works?%s" % urllib.parse.urlencode(
        {
            "search": title,
            "per-page": 5,
            "select": "id,title,authorships",
            "mailto": fetch.mailto,
        }
    )
    data = fetch.get(url)
    if data is None:
        return FETCH_FAILED
    target = norm_title(title)
    for cand in data.get("results") or []:
        if norm_title(cand.get("title") or "") == target:
            return cand
    return None


def orcid_homepage(fetch, orcid):
    url = "https://pub.orcid.org/v3.0/%s/person" % urllib.parse.quote(orcid, safe="")
    data = fetch.get(url)
    if not data:
        return None
    urls = (data.get("researcher-urls") or {}).get("researcher-url") or []
    for entry in urls:
        value = ((entry.get("url") or {}).get("value") or "").strip()
        if value:
            return value
    return None


def match_authorship(name, authorships):
    """Return the single authorship whose coarse key matches `name`, or None
    if zero or more than one match (ambiguous on this work)."""
    key = coarse_key(name)
    matches = []
    for a in authorships or []:
        author = a.get("author") or {}
        raw = a.get("raw_author_name") or author.get("display_name") or ""
        if coarse_key(raw) == key:
            matches.append(a)
    if len(matches) == 1:
        return matches[0]
    return None


STOPWORDS = {
    "the", "of", "and", "at", "for", "de", "la", "der", "van",
    "university", "institute", "college", "laboratory", "lab", "school",
    "department", "center", "centre", "national", "research", "technology",
    "technological", "polytechnic", "csail",
}


# Common abbreviations for institutions that recur throughout this (MIT
# compiler-research) corpus -- maps an abbreviation token to the non-stopword
# token(s) its spelled-out name reduces to, so "MIT" and "Massachusetts
# Institute of Technology" are recognized as the same place.
ALIASES = {
    "mit": {"massachusetts"},
    "csail": {"massachusetts"},
    "cmu": {"carnegie", "mellon"},
    "gatech": {"georgia"},
    "ucb": {"california", "berkeley"},
    "berkeley": {"california", "berkeley"},
    "uw": {"washington"},
    "umd": {"maryland"},
    "utexas": {"texas"},
    "ucsd": {"california", "diego"},
    "ucla": {"california", "angeles"},
}


def affiliation_tokens(text):
    tokens = {t for t in norm_title(text).split() if t and t not in STOPWORDS}
    expanded = set(tokens)
    for t in tokens:
        expanded |= ALIASES.get(t, set())
    return expanded


def affiliation_conflicts(known, resolved):
    """True if two non-empty affiliation strings share no meaningful token --
    a cheap smell test for OpenAlex author-cluster contamination (common
    names get merged with unrelated people; see e.g. the "Moscow Institute
    of Thermal Technology" vs MIT collision) that a bare name+affiliation
    lookup would otherwise silently accept."""
    if not known or not resolved:
        return False
    a, b = affiliation_tokens(known), affiliation_tokens(resolved)
    if not a or not b:
        return False
    return a.isdisjoint(b)


def author_affiliation(entity):
    """OpenAlex's `last_known_institutions` is unreliable for common/ambiguous
    names -- it is known to mis-rank e.g. "Moscow Institute of Thermal
    Technology" (a real ROR institution that also uses the acronym "MIT")
    above the real Massachusetts Institute of Technology. Score every
    affiliation instead by (most recent year, years attached) -- recency
    first so a recent job change wins, years-attached only as a tiebreak
    among institutions tied on recency (which is what actually separates
    the real MIT from the noise entries above) -- far more robust than the
    API's own "last known" pick. Falls back to last_known_institutions only
    when the author has no affiliations history at all."""
    affiliations = entity.get("affiliations") or []
    scored = [
        (max(a.get("years") or [0]), len(a.get("years") or []), a["institution"]["display_name"])
        for a in affiliations
        if a.get("institution")
    ]
    if scored:
        scored.sort()
        return scored[-1][2]
    last_known = entity.get("last_known_institutions") or []
    if last_known:
        return last_known[0].get("display_name")
    return None


# ------------------------------------------------------------------------ main


def load_inputs():
    with open(AUTHORS_IN) as fh:
        authors = json.load(fh)
    with open(IDMAP) as fh:
        idmap = json.load(fh)
    with open(PUBLICATIONS) as fh:
        pubs = json.load(fh)
    title_by_key = {p["bibtexKey"]: p.get("title") for p in pubs if p.get("bibtexKey")}
    return authors, idmap, title_by_key


def resolve_person(person, idmap, title_by_key, fetch, work_cache):
    """Returns (record, [review_entry, ...])."""
    name = person["name"]
    pid = person["person_id"]
    orcid = person.get("orcid")
    known_affiliation = person.get("latest_affiliation")

    record = {
        "person_id": pid,
        "name": name,
        "openalex_id": None,
        "resolution_method": None,
        "resolution_evidence": None,
        "orcid": orcid,
        "affiliation": None,
        "works_count": None,
        "h_index": None,
        "homepage": None,
    }

    entity = None

    # 1. ORCID first.
    if orcid:
        oa = openalex_author_by_orcid(fetch, orcid)
        if oa:
            entity = openalex_author_entity(fetch, oa_id(oa["id"]))
            if entity:
                record["resolution_method"] = "orcid"
                record["resolution_evidence"] = {"orcid": orcid}

    review_entries = []

    # 2. Shared-work match.
    if entity is None:
        anchored_keys = [k for k in person["papers"] if idmap.get(k, {}).get("openalex")]
        candidates = {}  # author_id -> [paper keys]
        per_paper_no_match = []

        def try_work(paper_key, work_id):
            work = work_cache.get(work_id)
            if work is None:
                work = openalex_work_authorships(fetch, work_id) or {}
                work_cache[work_id] = work
            match = match_authorship(name, work.get("authorships"))
            if match:
                aid = oa_id((match.get("author") or {}).get("id"))
                if aid:
                    candidates.setdefault(aid, []).append(paper_key)
                    return True
            per_paper_no_match.append(paper_key)
            return False

        for key in anchored_keys:
            try_work(key, idmap[key]["openalex"])

        search_failed_keys = []
        if not candidates:
            # No idmap-linked paper (or none matched) -- try title search.
            search_keys = person["papers"] if not anchored_keys else []
            for key in search_keys:
                title = idmap.get(key, {}).get("title") or title_by_key.get(key)
                if not title:
                    continue
                work = openalex_search_work(fetch, title)
                if work is FETCH_FAILED:
                    search_failed_keys.append(key)
                    continue
                if not work:
                    continue
                work_cache[work["id"]] = work
                match = match_authorship(name, work.get("authorships"))
                if match:
                    aid = oa_id((match.get("author") or {}).get("id"))
                    if aid:
                        candidates.setdefault(aid, []).append(key)

        if len(candidates) == 1:
            aid, papers = next(iter(candidates.items()))
            entity = openalex_author_entity(fetch, aid)
            if entity:
                record["resolution_method"] = "shared_work"
                record["resolution_evidence"] = {"papers": papers}
        elif len(candidates) > 1:
            review_entries.append({
                "type": "openalex_ambiguous",
                "person_id": pid,
                "name": name,
                "reason": "papers point at different OpenAlex author ids",
                "candidates": {aid: papers for aid, papers in candidates.items()},
            })
        elif search_failed_keys:
            # Title search itself couldn't be reached (e.g. OpenAlex's search-endpoint
            # quota exhausted) -- distinct from a genuine no-match so a later rerun can
            # retarget exactly these people instead of this being mistaken for settled.
            review_entries.append({
                "type": "openalex_search_unavailable",
                "person_id": pid,
                "name": name,
                "reason": "no ORCID and no idmap-anchored paper; the title-search fallback "
                "could not be reached (request failed) -- unresolved, not unresolvable; rerun "
                "enrich_openalex.py once the OpenAlex search endpoint is available again",
                "papers": search_failed_keys,
            })
        else:
            review_entries.append({
                "type": "openalex_unresolved",
                "person_id": pid,
                "name": name,
                "reason": "no ORCID and no shared-work anchor (no OpenAlex-linked paper "
                "matched this person's coarse name on its authorship list)",
                "papers": person["papers"],
            })

    if entity:
        record["openalex_id"] = oa_id(entity.get("id"))
        record["works_count"] = entity.get("works_count")
        record["h_index"] = (entity.get("summary_stats") or {}).get("h_index")
        record["affiliation"] = author_affiliation(entity)
        if affiliation_conflicts(known_affiliation, record["affiliation"]):
            review_entries.append({
                "type": "openalex_affiliation_conflict",
                "person_id": pid,
                "name": name,
                "reason": "OpenAlex-derived affiliation shares no token with the "
                "affiliation already on file (likely author-cluster contamination "
                "on a common name) -- affiliation kept in enriched.json but unverified",
                "known_affiliation": known_affiliation,
                "openalex_affiliation": record["affiliation"],
                "openalex_id": record["openalex_id"],
            })
        discovered_orcid = None
        if entity.get("orcid"):
            discovered_orcid = re.sub(r"^https?://orcid\.org/", "", entity["orcid"])
        if not record["orcid"] and discovered_orcid:
            record["orcid"] = discovered_orcid

    if record["orcid"]:
        record["homepage"] = orcid_homepage(fetch, record["orcid"])

    return record, review_entries


def report():
    if not os.path.exists(ENRICHED_OUT):
        print("harvest/authors/enriched.json: not built yet")
        return 1
    with open(ENRICHED_OUT) as fh:
        enriched = json.load(fh)
    review = []
    if os.path.exists(REVIEW_OUT):
        with open(REVIEW_OUT) as fh:
            review = json.load(fh)
    resolved = [r for r in enriched if r.get("openalex_id")]
    print("people                %d" % len(enriched))
    print("resolved              %d" % len(resolved))
    print("  with affiliation    %d" % sum(1 for r in resolved if r.get("affiliation")))
    print("  with homepage       %d" % sum(1 for r in resolved if r.get("homepage")))
    print("ambiguous (review)    %d" % sum(1 for r in review if r.get("type") == "openalex_ambiguous"))
    print("unresolved (review)   %d" % sum(1 for r in review if r.get("type") == "openalex_unresolved"))
    print("search unavailable    %d" % sum(1 for r in review if r.get("type") == "openalex_search_unavailable"))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--mailto", default="saman@lcs.mit.edu")
    ap.add_argument("--limit", type=int, default=0, help="only process the first N authors (debugging)")
    ap.add_argument(
        "--retries", type=int, default=4,
        help="HTTP retry attempts per request (default 4). Pass 0 to fail fast instead of "
        "backing off -- useful when OpenAlex's search/filter endpoints are returning a "
        "sustained 429 with an hours-long Retry-After (a shared daily USD-credit budget, "
        "seen exhausted by other lanes' heavy search-endpoint usage): with retries>0 each "
        "such call still burns up to retries*60s in backoff before giving up.",
    )
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    if args.report:
        return report()

    authors, idmap, title_by_key = load_inputs()
    if args.limit:
        authors = authors[: args.limit]

    fetch = Fetcher(
        args.mailto,
        intervals={"api.openalex.org": 0.12, "pub.orcid.org": 0.3},
        retries=args.retries,
        verbose=args.verbose,
        openalex_api_key=os.environ.get("OPENALEX_API_KEY", "").strip() or None,
    )

    work_cache = {}
    enriched = []
    new_review = []

    for n, person in enumerate(authors, 1):
        record, entries = resolve_person(person, idmap, title_by_key, fetch, work_cache)
        enriched.append(record)
        new_review.extend(entries)
        if args.verbose or n % 20 == 0 or n == len(authors):
            print(
                "  [%3d/%3d] %-30s net=%d cache=%d fail=%d"
                % (n, len(authors), person["name"][:30], fetch.stats["net"], fetch.stats["cache"], fetch.stats["fail"]),
                file=sys.stderr,
            )

    resolved = [r for r in enriched if r["openalex_id"]]
    print()
    print("people                %d" % len(enriched))
    print("resolved              %d" % len(resolved))
    print("  via orcid           %d" % sum(1 for r in resolved if r["resolution_method"] == "orcid"))
    print("  via shared_work     %d" % sum(1 for r in resolved if r["resolution_method"] == "shared_work"))
    print("  with affiliation    %d" % sum(1 for r in resolved if r["affiliation"]))
    print("  with homepage       %d" % sum(1 for r in resolved if r["homepage"]))
    print("ambiguous             %d" % sum(1 for r in new_review if r["type"] == "openalex_ambiguous"))
    print("unresolved            %d" % sum(1 for r in new_review if r["type"] == "openalex_unresolved"))
    print("search unavailable    %d" % sum(1 for r in new_review if r["type"] == "openalex_search_unavailable"))
    print("affiliation conflict  %d" % sum(1 for r in new_review if r["type"] == "openalex_affiliation_conflict"))
    print(
        "requests: %(net)d net, %(cache)d cached, %(retry)d retried, %(fail)d failed" % fetch.stats
    )

    if not args.write:
        print()
        print("dry run -- nothing written. Responses are cached, so --write is fast.")
        return 0

    existing_review = []
    if os.path.exists(REVIEW_OUT):
        with open(REVIEW_OUT) as fh:
            existing_review = json.load(fh)
    existing_review = [
        r for r in existing_review
        if r.get("type") not in (
            "openalex_ambiguous", "openalex_unresolved",
            "openalex_search_unavailable", "openalex_affiliation_conflict",
        )
    ]
    combined_review = existing_review + new_review

    for path, payload in ((ENRICHED_OUT, enriched), (REVIEW_OUT, combined_review)):
        tmp = path + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(payload, fh, indent=1, ensure_ascii=False)
            fh.write("\n")
        os.replace(tmp, path)
        print("wrote %s" % os.path.relpath(path, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
