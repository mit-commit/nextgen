#!/usr/bin/env python3
"""Step 2 of the repos lane: GitHub code/repo search for the 268 papers with
no live in-paper repo URL (search-plan.json).

For each paper:
  1. Direct existence checks (`GET /repos/{owner}/{repo}`, core API, 5000/hr)
     over (owner, repo) pairs built from search-plan.json's candidate lists
     -- known_owners_same_authors and username_candidates crossed with
     repo_name_candidates -- capped per paper to keep the combinatorics sane.
  2. One GitHub repository-search call per paper (`GET /search/repositories`,
     30/min) on the project/software name, to catch repos that exist under
     an owner/name neither guessed.
  3. For every repo found either way, fetch its README (core API) and check
     whether it mentions the paper's title or an author surname -- this is
     the strongest evidence short of reading the paper, so it always
     upgrades confidence when it hits.

Scores, never auto-accepts: writes the top 3 candidates per paper (by
score) to harvest/repos/candidates.json with the evidence that produced the
score and a confidence tier. Nothing here is a verified repo link -- a
human decides what to promote into data/repos or wherever the site
consumes it.

Resumable: a bibtexKey already in candidates.json is skipped on rerun
unless --refresh. Responses are cached under harvest/repos/_ghcache/
(gitignored) so a rerun after a rate-limit pause is nearly free.

    python3 harvest/repos/search_github.py
    python3 harvest/repos/search_github.py --key Kjolstad:2017:TTG:3155562.3155683
    python3 harvest/repos/search_github.py --refresh
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
PLAN_PATH = os.path.join(HERE, "search-plan.json")
PUBLICATIONS = os.path.join(ROOT, "data", "publications.json")
OUT_PATH = os.path.join(HERE, "candidates.json")
CACHE = os.path.join(HERE, "_ghcache")

API = "https://api.github.com"
MAX_OWNER_REPO_PAIRS = 30   # cap on direct existence checks per paper
UA = "commit-nextgen-repos-search/1.0"


# ---------------------------------------------------------------- http/cache

def _token():
    return os.environ.get("GITHUB_TOKEN", "").strip()


class Client:
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.stats = {"cache": 0, "core": 0, "search": 0, "fail": 0}
        self._last_search = 0.0
        os.makedirs(CACHE, exist_ok=True)

    def _cache_path(self, url):
        return os.path.join(CACHE, hashlib.sha1(url.encode()).hexdigest() + ".json")

    def _headers(self):
        h = {"User-Agent": UA, "Accept": "application/vnd.github+json",
             "X-GitHub-Api-Version": "2022-11-28"}
        token = _token()
        if token:
            h["Authorization"] = "Bearer " + token
        return h

    def get(self, path_or_url, is_search=False):
        url = path_or_url if path_or_url.startswith("http") else API + path_or_url
        cpath = self._cache_path(url)
        if os.path.exists(cpath):
            self.stats["cache"] += 1
            with open(cpath) as fh:
                return json.load(fh).get("body")

        if is_search:
            gap = time.time() - self._last_search
            if gap < 2.1:
                time.sleep(2.1 - gap)
            self._last_search = time.time()

        req = urllib.request.Request(url, headers=self._headers())
        body = None
        for attempt in range(4):
            try:
                self.stats["search" if is_search else "core"] += 1
                with urllib.request.urlopen(req, timeout=30) as resp:
                    body = json.loads(resp.read().decode("utf-8", "replace"))
                break
            except urllib.error.HTTPError as err:
                if err.code == 404:
                    body = None
                    break
                if err.code in (403, 429):
                    reset = err.headers.get("X-RateLimit-Reset")
                    retry_after = err.headers.get("Retry-After")
                    wait = float(retry_after) if retry_after else (
                        max(1.0, float(reset) - time.time()) if reset else 30.0 * (attempt + 1))
                    if self.verbose:
                        print("    %s, sleeping %.0fs" % (err.code, wait), file=sys.stderr)
                    time.sleep(min(wait, 90))
                    continue
                self.stats["fail"] += 1
                return None
            except Exception:
                time.sleep(2 * (attempt + 1))
        else:
            self.stats["fail"] += 1

        with open(cpath + ".tmp", "w") as fh:
            json.dump({"url": url, "body": body}, fh)
        os.replace(cpath + ".tmp", cpath)
        return body


# ------------------------------------------------------------------ scoring

def norm(text):
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


def repo_readme_text(client, full_name):
    data = client.get("/repos/%s/readme" % full_name)
    if not data or not data.get("content"):
        return ""
    import base64
    try:
        return base64.b64decode(data["content"]).decode("utf-8", "replace")
    except Exception:
        return ""


def score_repo(repo, plan, pub, client, do_readme):
    evidence = []
    score = 0
    name_n = norm(repo.get("name"))
    owner_n = norm((repo.get("owner") or {}).get("login"))

    software_names = [norm(s) for s in plan.get("software_name_candidates") or []]
    repo_name_cands = [norm(s) for s in plan.get("repo_name_candidates") or []]
    if name_n in software_names or name_n in repo_name_cands:
        score += 2
        evidence.append("repo name matches a project/software name candidate")
    elif any(c and (c in name_n or name_n in c) for c in software_names + repo_name_cands):
        score += 1
        evidence.append("repo name partially matches a project/software name candidate")

    known_owners = [norm(o) for o in plan.get("known_owners_same_authors") or []]
    lab_orgs = [norm(o) for o in plan.get("lab_org_candidates") or []]
    usernames = [norm(u) for u in plan.get("username_candidates") or []]
    surnames = [norm(s) for s in plan.get("author_surnames") or [] if len(s) >= 4]
    # first-initial+surname (bthies for "Bill Thies") is an extremely common
    # GitHub handle shape the pre-generated username list doesn't fully
    # enumerate -- catch it directly rather than relying on that list alone.
    fuzzy_surname_hit = any(
        owner_n.endswith(s) and 0 < len(owner_n) - len(s) <= 2 for s in surnames)
    if owner_n in known_owners:
        score += 2
        evidence.append("owner is a known same-author org/account")
    elif owner_n in usernames or fuzzy_surname_hit:
        score += 2
        evidence.append("owner matches an author-derived username guess")
    elif owner_n in lab_orgs:
        score += 1
        evidence.append("owner is a lab/org seen elsewhere in the corpus")

    year = pub.get("year")
    created = repo.get("created_at")
    if year and created:
        try:
            created_year = int(created[:4])
            if abs(created_year - int(year)) <= 2:
                score += 1
                evidence.append("created within ~2y of publication (%s vs %s)" % (created_year, year))
        except (ValueError, TypeError):
            pass

    desc_n = norm(repo.get("description"))
    title_n = norm(pub.get("title"))
    if title_n and len(title_n) > 8 and title_n in desc_n:
        score += 2
        evidence.append("repo description contains the paper's title")
    elif any(term and term in desc_n for term in software_names + repo_name_cands):
        score += 1
        evidence.append("repo description mentions the project/software name")

    if do_readme:
        readme = repo_readme_text(client, repo["full_name"])
        readme_n = norm(readme[:20000])
        if title_n and len(title_n) > 8 and title_n in readme_n:
            score += 2
            evidence.append("README contains the paper's title")
        else:
            for surname in surnames:
                if surname in readme_n:
                    score += 1
                    evidence.append("README mentions author surname %r" % surname)
                    break

    return score, evidence


def confidence_for(score):
    if score >= 5:
        return "high"
    if score >= 3:
        return "medium"
    return "low"


# ---------------------------------------------------------------- per-paper

def candidate_pairs(plan):
    owners = list(dict.fromkeys(
        (plan.get("known_owners_same_authors") or [])
        + (plan.get("username_candidates") or [])
        + (plan.get("lab_org_candidates") or [])
    ))
    repos = list(dict.fromkeys(plan.get("repo_name_candidates") or []))
    pairs = []
    for owner in owners:
        for repo in repos:
            pairs.append((owner, repo))
            if len(pairs) >= MAX_OWNER_REPO_PAIRS:
                return pairs
    return pairs


def search_repo_name(client, plan):
    query_terms = plan.get("software_name_candidates") or [plan.get("project")]
    query = next((t for t in query_terms if t), None)
    if not query:
        return []
    q = '"%s" in:name' % query
    data = client.get("/search/repositories?" + urllib.parse.urlencode({"q": q, "per_page": 10}),
                       is_search=True)
    if not data:
        return []
    return data.get("items") or []


def process_paper(key, plan, pub, client):
    seen = {}

    for owner, repo_name in candidate_pairs(plan):
        data = client.get("/repos/%s/%s" % (owner, repo_name))
        if data and data.get("full_name"):
            seen[data["full_name"].lower()] = data

    for repo in search_repo_name(client, plan):
        if repo.get("full_name"):
            seen[repo["full_name"].lower()] = repo

    scored = []
    for repo in seen.values():
        s, ev = score_repo(repo, plan, pub, client, do_readme=True)
        if s <= 0:
            continue
        scored.append({
            "repo": repo["full_name"],
            "url": repo.get("html_url"),
            "score": s,
            "confidence": confidence_for(s),
            "evidence": ev,
            "stars": repo.get("stargazers_count"),
            "created_at": repo.get("created_at"),
            "description": repo.get("description"),
        })
    scored.sort(key=lambda c: (c["score"], c["stars"] or 0), reverse=True)
    return scored[:3]


# ---------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--key", action="append", help="restrict to this bibtexKey (repeatable)")
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()

    if not _token():
        sys.exit("GITHUB_TOKEN not set")

    plans = json.load(open(PLAN_PATH))
    pubs = {p["bibtexKey"]: p for p in json.load(open(PUBLICATIONS))}
    existing = json.load(open(OUT_PATH)) if os.path.exists(OUT_PATH) else {}

    keys = args.key if args.key else sorted(plans)
    if not args.refresh:
        keys = [k for k in keys if k not in existing]
    if args.limit:
        keys = keys[:args.limit]

    client = Client(verbose=args.verbose)
    strong = weak = none = 0
    for i, key in enumerate(keys, 1):
        plan = plans[key]
        pub = pubs.get(key, {})
        candidates = process_paper(key, plan, pub, client)
        existing[key] = candidates
        if candidates and candidates[0]["confidence"] in ("high", "medium"):
            strong += 1
        elif candidates:
            weak += 1
        else:
            none += 1
        if args.verbose or i % 20 == 0 or i == len(keys):
            print("[%d/%d] %s -> %d candidate(s) %s core=%d search=%d cache=%d" % (
                i, len(keys), key, len(candidates),
                [c["confidence"] for c in candidates],
                client.stats["core"], client.stats["search"], client.stats["cache"]),
                flush=True)
        if i % 10 == 0 or i == len(keys):
            tmp = OUT_PATH + ".tmp"
            with open(tmp, "w") as fh:
                json.dump(existing, fh, indent=1, sort_keys=True, ensure_ascii=False)
                fh.write("\n")
            os.replace(tmp, OUT_PATH)

    tmp = OUT_PATH + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(existing, fh, indent=1, sort_keys=True, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, OUT_PATH)

    print("\nprocessed %d papers this run" % len(keys))
    print("strong=%d weak-only=%d none=%d (this run)" % (strong, weak, none))
    all_strong = sum(1 for v in existing.values() if v and v[0]["confidence"] in ("high", "medium"))
    all_weak = sum(1 for v in existing.values() if v and v[0]["confidence"] == "low")
    all_none = sum(1 for v in existing.values() if not v)
    print("totals across %d papers: strong=%d weak-only=%d none=%d" % (
        len(existing), all_strong, all_weak, all_none))


if __name__ == "__main__":
    main()
