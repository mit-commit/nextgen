#!/usr/bin/env python3
"""Build harvest/authors/authors.json: every author across publications.json.

Four steps:

  1. Parse `author0` on every publication ("Last, First and Last, First" or a
     bare "First Last" for a single author) into one record per appearance,
     keeping the paper's own author order and the file's paper order.
  2. Dedupe appearances into people on an *exact* normalized name (Unicode
     NFC, whitespace collapsed) only. Nothing beyond that is merged
     automatically -- an initial ("J. Won") and a full given name
     ("Jaeyeon Won"), or an accented and unaccented spelling, become two
     person records and a flag in review.json for a human.
  3. For every publication data/idmap.json resolved to a real DOI, fetch the
     Crossref and OpenAlex records for that work and match their author lists
     back onto our parsed names (folded last name + first initial) to pick up
     ORCID and affiliation.
  4. Match each person's name against data/people.xml (current + alumni) to
     flag COMMIT members.

Stdlib only. Writes nothing unless --write is given.

    python3 harvest/authors/authors_build.py             # dry run, fills the cache
    python3 harvest/authors/authors_build.py --write      # write authors.json + review.json
    python3 harvest/authors/authors_build.py --report     # summarize what is on disk
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
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
PUBLICATIONS = os.path.join(ROOT, "data", "publications.json")
IDMAP = os.path.join(ROOT, "data", "idmap.json")
PEOPLE = os.path.join(ROOT, "data", "people.xml")
CACHE = os.path.join(HERE, "cache")
AUTHORS_OUT = os.path.join(HERE, "authors.json")
REVIEW_OUT = os.path.join(HERE, "review.json")


# --------------------------------------------------------------- name parsing


def split_author0(author0):
    """"Last, First and Last, First" / bare "First Last" -> ["First Last", ...]."""
    names = []
    for part in (author0 or "").split(" and "):
        part = part.strip()
        if not part:
            continue
        if "," in part:
            last, first = (x.strip() for x in part.split(",", 1))
            names.append(("%s %s" % (first, last)).strip())
        else:
            names.append(part)
    return names


def normalize_name(name):
    """NFC-compose and collapse whitespace. This *is* the dedupe key."""
    text = unicodedata.normalize("NFC", name or "")
    return " ".join(text.split())


def fold(text):
    """Strip accents and casefold, for near-miss/COMMIT matching, never for dedupe."""
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
    """folded last name + first initial -- groups likely-same-person spellings."""
    tokens = name_tokens(name)
    if not tokens:
        return ""
    return "%s|%s" % (tokens[-1], tokens[0][0] if tokens[0] else "")


def slugify(name):
    text = fold(name)
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "person"


# -------------------------------------------------------------- near misses


def is_initial(token):
    return bool(re.match(r"^[a-z]\.?$", token))


def given_compatible(given_a, given_b):
    """True if the shorter given-name token list is an initials-compression of
    the longer one (extra middle tokens on the longer side are ignored)."""
    if not given_a or not given_b:
        return False
    short, long = (given_a, given_b) if len(given_a) <= len(given_b) else (given_b, given_a)
    for s, l in zip(short, long):
        if s == l:
            continue
        if is_initial(s) and l.startswith(s[0]):
            continue
        if is_initial(l) and s.startswith(l[0]):
            continue
        return False
    return True


def classify_pair(a, b):
    """Return a review reason string, or None if a and b are not a near-miss."""
    fa, fb = fold(a), fold(b)
    if fa == fb:
        return "accent or case variant"

    ta, tb = name_tokens(a), name_tokens(b)
    if not ta or not tb or ta[-1] != tb[-1]:
        return None  # different surname -- coarse_key already filtered this out

    if given_compatible(ta[:-1], tb[:-1]):
        return "initial vs full given name"

    return "name variant (same surname, given name differs)"


def find_review_groups(people):
    """people: dict[normalized name] -> person record. Returns review.json list."""
    by_coarse = {}
    for name in people:
        by_coarse.setdefault(coarse_key(name), []).append(name)

    groups = []
    seen_pairs = set()
    for names in by_coarse.values():
        if len(names) < 2:
            continue
        names = sorted(names)
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                a, b = names[i], names[j]
                reason = classify_pair(a, b)
                if not reason or (a, b) in seen_pairs:
                    continue
                seen_pairs.add((a, b))
                groups.append(
                    {
                        "names": [a, b],
                        "reason": reason,
                        "papers": {a: people[a]["papers"], b: people[b]["papers"]},
                    }
                )
    return groups


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
        path = os.path.join(CACHE, hashlib.sha1(url.encode()).hexdigest() + ".json")
        if os.path.exists(path):
            self.stats["cache"] += 1
            with open(path) as fh:
                return json.load(fh).get("body")

        host = urllib.parse.urlparse(url).netloc
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
                    delay = float(err.headers.get("Retry-After") or 0) or self.interval * (2 ** attempt) * 2
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


def crossref_authors(fetch, doi):
    # Unlike the /works?query=... collection route, /works/{doi} rejects `select`.
    url = "https://api.crossref.org/works/%s?%s" % (
        urllib.parse.quote(doi, safe=""),
        urllib.parse.urlencode({"mailto": fetch.mailto}),
    )
    data = fetch.get(url)
    if not data or data.get("status") != "ok":
        return []
    out = []
    for a in data.get("message", {}).get("author") or []:
        name = " ".join(x for x in (a.get("given"), a.get("family")) if x).strip()
        if not name:
            continue
        orcid = a.get("ORCID") or ""
        orcid = re.sub(r"^https?://orcid\.org/", "", orcid) or None
        affiliation = None
        for aff in a.get("affiliation") or []:
            if aff.get("name"):
                affiliation = aff["name"]
                break
        out.append({"name": name, "orcid": orcid, "affiliation": affiliation})
    return out


def openalex_authors(fetch, doi):
    url = "https://api.openalex.org/works/doi:%s?%s" % (
        urllib.parse.quote(doi, safe="/"),
        urllib.parse.urlencode({"select": "id,authorships", "mailto": fetch.mailto}),
    )
    data = fetch.get(url)
    if not data:
        return []
    out = []
    for a in data.get("authorships") or []:
        author = a.get("author") or {}
        name = a.get("raw_author_name") or author.get("display_name") or ""
        if not name:
            continue
        orcid = author.get("orcid") or ""
        orcid = re.sub(r"^https?://orcid\.org/", "", orcid) or None
        affiliation = None
        raw_aff = a.get("raw_affiliation_strings") or []
        if raw_aff:
            affiliation = raw_aff[0]
        out.append({"name": name, "orcid": orcid, "affiliation": affiliation})
    return out


def match_source_author(our_name, source_authors, used):
    """Best match in source_authors (list of {name,...}) for our_name, by folded
    last name + first initial. `used` tracks indices already claimed on this
    paper so two of our authors don't both grab the same source entry."""
    key = coarse_key(our_name)
    for i, cand in enumerate(source_authors):
        if i in used:
            continue
        if coarse_key(cand["name"]) == key:
            used.add(i)
            return cand
    return None


# ------------------------------------------------------------------ people.xml


def load_commit_members():
    tree = ET.parse(PEOPLE)
    names = set()
    for person in tree.getroot().iter("person"):
        name = normalize_name(person.get("name") or "")
        if name:
            names.add(name)
    return names


def is_commit_member(name, member_names, member_fold, member_by_coarse, author_coarse_counts):
    if name in member_names or fold(name) in member_fold:
        return True

    # Beyond an exact match, only trust a surname + first-initial match when
    # it is unambiguous on *both* sides: exactly one candidate in people.xml
    # shares the coarse key, the given names are a genuine initials-relation
    # (not just a shared first letter), and no *other* distinct author in our
    # own data shares that same coarse key -- "J. Kim" alone would pass the
    # first two checks against "Juni C. Kim", but "Jang Kim" and "Jason Kim"
    # also occupy kim|j, so the surname+initial is not reliable evidence here
    # and none of the three should be auto-matched.
    if author_coarse_counts.get(coarse_key(name), 0) > 1:
        return False
    candidates = member_by_coarse.get(coarse_key(name)) or []
    if len(candidates) != 1:
        return False
    tokens = name_tokens(name)
    cand_tokens = name_tokens(candidates[0])
    return given_compatible(tokens[:-1], cand_tokens[:-1])


# ------------------------------------------------------------------------ main


def load_source_data():
    with open(PUBLICATIONS) as fh:
        pubs = json.load(fh)
    with open(IDMAP) as fh:
        idmap = json.load(fh)
    return pubs, idmap


def build_people(pubs):
    """First pass: parse every author0, dedupe exactly, no network."""
    people = {}
    for entry in pubs:
        key = entry.get("bibtexKey")
        for raw in split_author0(entry.get("author0")):
            name = normalize_name(raw)
            if not name:
                continue
            person = people.setdefault(
                name,
                {"name": name, "variants": [], "papers": [], "_raw": set()},
            )
            person["_raw"].add(raw)
            if key and key not in person["papers"]:
                person["papers"].append(key)
    for person in people.values():
        person["variants"] = sorted(v for v in person["_raw"] if v != person["name"])
        del person["_raw"]
    return people


def enrich(people, pubs, idmap, fetch, verbose=False):
    by_key = {p.get("bibtexKey"): p for p in pubs}
    name_by_key = {}  # bibtexKey -> {normalized name -> person}
    for name, person in people.items():
        for key in person["papers"]:
            name_by_key.setdefault(key, {})[name] = person

    orcids = {name: None for name in people}
    affiliations = {name: [] for name in people}  # (year, affiliation)

    doi_keys = [k for k, rec in idmap.items() if rec.get("doi")]
    for n, key in enumerate(doi_keys, 1):
        doi = idmap[key]["doi"]
        entry = by_key.get(key) or {}
        year = entry.get("year")
        try:
            year = int(str(year)[:4])
        except (TypeError, ValueError):
            year = 0

        cr = crossref_authors(fetch, doi)
        oa = openalex_authors(fetch, doi)
        used_cr, used_oa = set(), set()

        for name, person in (name_by_key.get(key) or {}).items():
            src = match_source_author(name, cr, used_cr)
            if src:
                if src["orcid"] and not orcids[name]:
                    orcids[name] = src["orcid"]
                if src["affiliation"]:
                    affiliations[name].append((year, src["affiliation"]))
            src = match_source_author(name, oa, used_oa)
            if src:
                if src["orcid"] and not orcids[name]:
                    orcids[name] = src["orcid"]
                if src["affiliation"]:
                    affiliations[name].append((year, src["affiliation"]))

        if verbose or n % 25 == 0 or n == len(doi_keys):
            print(
                "  [%3d/%3d] enriched  net=%d cache=%d"
                % (n, len(doi_keys), fetch.stats["net"], fetch.stats["cache"]),
                file=sys.stderr,
            )

    for name, person in people.items():
        person["orcid"] = orcids[name]
        person["latest_affiliation"] = None
        if affiliations[name]:
            affiliations[name].sort(key=lambda t: t[0])
            person["latest_affiliation"] = affiliations[name][-1][1]


def assign_person_ids(people):
    used = {}
    for name in sorted(people):
        base = slugify(name)
        slug = base
        n = 2
        while slug in used:
            slug = "%s-%d" % (base, n)
            n += 1
        used[slug] = name
        people[name]["person_id"] = slug


def report():
    if not os.path.exists(AUTHORS_OUT):
        print("harvest/authors/authors.json: not built yet")
        return 1
    with open(AUTHORS_OUT) as fh:
        authors = json.load(fh)
    review = []
    if os.path.exists(REVIEW_OUT):
        with open(REVIEW_OUT) as fh:
            review = json.load(fh)
    print("distinct authors   %d" % len(authors))
    print("  with orcid       %d" % sum(1 for a in authors if a.get("orcid")))
    print("  commit members   %d" % sum(1 for a in authors if a.get("commit_member")))
    print("review.json        %d flagged pairs" % len(review))
    return 0


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--write", action="store_true", help="write authors.json and review.json")
    ap.add_argument("--report", action="store_true", help="summarize files already on disk and exit")
    ap.add_argument("--mailto", default="saman@lcs.mit.edu", help="contact for Crossref/OpenAlex polite pools")
    ap.add_argument("--sleep", type=float, default=1.0, help="minimum seconds between requests to one host")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    if args.report:
        return report()

    pubs, idmap = load_source_data()
    people = build_people(pubs)
    print("parsed %d appearances into %d distinct (normalized) names" % (
        sum(len(p["papers"]) for p in people.values()), len(people)
    ), file=sys.stderr)

    review = find_review_groups(people)
    print("flagged %d near-miss pairs for review" % len(review), file=sys.stderr)

    fetch = Fetcher(args.mailto, interval=args.sleep, verbose=args.verbose)
    enrich(people, pubs, idmap, fetch, args.verbose)

    member_names = load_commit_members()
    member_fold = {fold(n) for n in member_names}
    member_by_coarse = {}
    for n in member_names:
        member_by_coarse.setdefault(coarse_key(n), []).append(n)
    author_coarse_counts = {}
    for name in people:
        key = coarse_key(name)
        author_coarse_counts[key] = author_coarse_counts.get(key, 0) + 1
    for name, person in people.items():
        person["commit_member"] = is_commit_member(
            name, member_names, member_fold, member_by_coarse, author_coarse_counts
        )

    assign_person_ids(people)

    ordered = sorted(
        people.values(),
        key=lambda p: (name_tokens(p["name"])[-1] if name_tokens(p["name"]) else "", fold(p["name"])),
    )
    out = [
        {
            "person_id": p["person_id"],
            "name": p["name"],
            "variants": p["variants"],
            "papers": p["papers"],
            "orcid": p["orcid"],
            "latest_affiliation": p["latest_affiliation"],
            "commit_member": p["commit_member"],
        }
        for p in ordered
    ]

    print()
    print("publications      %d" % len(pubs))
    print("distinct authors   %d" % len(out))
    print("  with orcid       %d" % sum(1 for a in out if a["orcid"]))
    print("  commit members   %d" % sum(1 for a in out if a["commit_member"]))
    print("  review pairs     %d" % len(review))
    print(
        "requests: %(net)d net, %(cache)d cached, %(retry)d retried, %(fail)d failed"
        % fetch.stats
    )

    if not args.write:
        print()
        print("dry run -- nothing written. Responses are cached, so --write is fast.")
        return 0

    for path, payload in ((AUTHORS_OUT, out), (REVIEW_OUT, review)):
        tmp = path + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(payload, fh, indent=1, ensure_ascii=False)
            fh.write("\n")
        os.replace(tmp, path)
        print("wrote %s" % os.path.relpath(path, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
