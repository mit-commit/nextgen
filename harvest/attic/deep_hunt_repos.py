#!/usr/bin/env python3
"""own-repo-deep-hunt (round-7 queue task 1): find a confirmed own-group repo
(or confirmed absence) for every paper, going deeper than repos-search step 2
did -- that pass only checked GUESSED (owner, repo-name) pairs and one
software-name search per paper. This pass instead:

  (a) enumerates every repo in every known group org/account -- a full
      listing, not a name-guess check -- plus discovers new orgs/accounts
      from org member lists and from contributors on repos we already know
      are own-group;
  (b) builds a person -> GitHub-login map: surname-matched from already-
      verified own_group owners, plus a GitHub user-name search (`in:name`)
      for every author without one, profile-verified;
  (c) for each mapped login, lists ALL their public repos (not just
      guessed names);
  (d) candidate-matches every paper (title/topics/date) against the full
      repo pool assembled by (a)+(c), folding in candidates.json's 165
      medium-confidence rows repos-search already found but didn't verify.

Auto-accepts nothing -- writes harvest/repos/deephunt.json, evidence per
row, for a Batch model judgment pass (curate/verify_repos.py-style) to
merge into verified.json.

Subcommands (run in order, each resumable/cached under harvest/repos/_ghcache/):
    python3 curate/deep_hunt_repos.py orgs
    python3 curate/deep_hunt_repos.py authormap
    python3 curate/deep_hunt_repos.py repolist
    python3 curate/deep_hunt_repos.py match
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "harvest", "repos"))
from search_github import Client, norm  # noqa: E402

REPOS_DIR = os.path.join(ROOT, "harvest", "repos")
AUTHORS_DIR = os.path.join(ROOT, "harvest", "authors")
PUBLICATIONS = os.path.join(ROOT, "data", "publications.json")

ORGS_OUT = os.path.join(REPOS_DIR, "deephunt_orgs.json")
AUTHORMAP_OUT = os.path.join(REPOS_DIR, "deephunt_authormap.json")
REPOLIST_OUT = os.path.join(REPOS_DIR, "deephunt_repolist.json")
MATCH_OUT = os.path.join(REPOS_DIR, "deephunt.json")
VERIFIED = os.path.join(REPOS_DIR, "verified.json")
CANDIDATES = os.path.join(REPOS_DIR, "candidates.json")
MENTIONS = os.path.join(REPOS_DIR, "mentions.json")
SEARCH_PLAN = os.path.join(REPOS_DIR, "search-plan.json")

# Seed group orgs -- from the queue's named orgs plus every owner already
# confirmed own_group in verified.json that GitHub reports as an
# Organization (checked live, not guessed).
SEED_ORGS = [
    "BuildIt-lang", "GraphIt-DSL", "exaloop", "mit-commit", "tensor-compiler",
    "DynamoRIO", "halide", "weld-project", "finch-tensor", "ithemal",
    "Tiramisu-Compiler", "revec", "dmtcp", "psg-mit", "simit-lang",
    "petabricks",
]

# Personal accounts already confirmed as own-group repo owners (from
# verified.json) or otherwise known -- full-listed too, since prior search
# only checked guessed repo names against them, never a full listing.
SEED_USERS = [
    "bthies", "willow-ahrens", "radha-patel", "rrnewton", "katsumiok",
    "nullplay", "jansel", "jbosboom", "ychen306", "stevenraphael",
    "manya-bansal", "talnish", "rnk",
]


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def load(path, default=None):
    if os.path.exists(path):
        with open(path) as fh:
            return json.load(fh)
    return default if default is not None else {}


def atomic_write(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(obj, fh, indent=1, sort_keys=True, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, path)


# --------------------------------------------------------------- (a) orgs


def paginate_repos(client, kind, login):
    """kind: 'orgs' or 'users'. Returns list of repo dicts (owner repos only,
    forks included -- a fork can still be the thesis's own modified copy)."""
    out = []
    page = 1
    while True:
        path = "/%s/%s/repos?per_page=100&page=%d&sort=created" % (kind, login, page)
        data = client.get(path)
        if not data:
            break
        out.extend(data)
        if len(data) < 100:
            break
        page += 1
    return out


def slim_repo(r):
    return {
        "full_name": r.get("full_name"),
        "owner": (r.get("owner") or {}).get("login"),
        "owner_type": (r.get("owner") or {}).get("type"),
        "name": r.get("name"),
        "description": r.get("description"),
        "created_at": r.get("created_at"),
        "pushed_at": r.get("pushed_at"),
        "topics": r.get("topics") or [],
        "stars": r.get("stargazers_count"),
        "fork": r.get("fork"),
        "archived": r.get("archived"),
        "html_url": r.get("html_url"),
    }


def cmd_orgs(args):
    client = Client(verbose=args.verbose)
    existing = load(ORGS_OUT, {})

    accounts = list(dict.fromkeys(SEED_ORGS + SEED_USERS))
    if args.discover:
        # New orgs/accounts surfaced by public members of orgs we already
        # know, plus contributors on repos already confirmed own_group.
        discovered = set()
        for org in SEED_ORGS:
            members = client.get("/orgs/%s/members?per_page=100" % org)
            for m in members or []:
                discovered.add(m.get("login"))
        verified = load(VERIFIED, {})
        for rows in verified.values():
            for row in rows:
                if not row.get("own_group"):
                    continue
                url = row.get("url") or ""
                m = re.match(r"https?://github\.com/([^/]+)/([^/]+)/?$", url)
                if not m:
                    continue
                owner, repo = m.group(1), m.group(2)
                contributors = client.get("/repos/%s/%s/contributors?per_page=100" % (owner, repo))
                for c in contributors or []:
                    if isinstance(c, dict) and c.get("login"):
                        discovered.add(c["login"])
        discovered -= set(a.lower() for a in accounts)
        discovered = sorted(d for d in discovered if d)
        log("discovered %d candidate accounts from members/contributors" % len(discovered))
        atomic_write(os.path.join(REPOS_DIR, "deephunt_discovered.json"), discovered)
        accounts = list(dict.fromkeys(accounts + discovered))

    seed_set = {a.lower() for a in accounts if a not in (args.discover and discovered or [])}
    for i, login in enumerate(accounts, 1):
        if login in existing and not args.refresh:
            continue
        info = client.get("/users/%s" % login)
        if not info:
            existing[login] = {"error": "not_found"}
            continue
        kind = "orgs" if info.get("type") == "Organization" else "users"
        # Full repo listing only for real orgs and the explicit seed accounts
        # -- a discovered contributor's repos aren't used for matching (only
        # their profile name, for the author map), so fetching/storing
        # thousands of unrelated repos for hundreds of incidental
        # contributors is pure waste.
        is_discovered_only = login not in seed_set and kind == "users"
        repos = [] if is_discovered_only else paginate_repos(client, kind, login)
        existing[login] = {
            "type": info.get("type"),
            "name": info.get("name"),
            "bio": info.get("bio"),
            "company": info.get("company"),
            "public_repos": info.get("public_repos"),
            "repos": [slim_repo(r) for r in repos],
        }
        if args.verbose or i % 5 == 0:
            log("[%d/%d] %s (%s) -> %d repos  core=%d search=%d cache=%d" % (
                i, len(accounts), login, info.get("type"), len(repos),
                client.stats["core"], client.stats["search"], client.stats["cache"]))
        if i % 5 == 0:
            atomic_write(ORGS_OUT, existing)

    atomic_write(ORGS_OUT, existing)
    total_repos = sum(len(v.get("repos", [])) for v in existing.values() if isinstance(v, dict))
    log("done: %d accounts, %d total repos listed" % (len(existing), total_repos))


# ------------------------------------------------------------ (b) authormap


def surname_variants(name):
    parts = [p for p in re.split(r"\s+", name.strip()) if p]
    if not parts:
        return None, None
    return parts[0], parts[-1]


def fold(s):
    return norm(s)


def cmd_authormap(args):
    client = Client(verbose=args.verbose)
    authors = load(os.path.join(AUTHORS_DIR, "authors.json"), [])
    verified = load(VERIFIED, {})
    existing = load(AUTHORMAP_OUT, [])
    by_person = {r["person_id"]: r for r in existing}

    # Pass 1: surname-match against owners already confirmed own_group in
    # verified.json -- these are REAL, live-confirmed GitHub accounts, no
    # guessing. (bthies -> "Bill Thies", willow-ahrens -> "Willow Ahrens", etc.)
    owner_logins = set()
    for rows in verified.values():
        for row in rows:
            if not row.get("own_group"):
                continue
            m = re.match(r"https?://github\.com/([^/]+)/", row.get("url") or "")
            if m:
                owner_logins.add(m.group(1))

    owner_info = {}
    for login in owner_logins:
        info = client.get("/users/%s" % login)
        if info and info.get("type") == "User":
            owner_info[login] = info

    for person in authors:
        pid = person["person_id"]
        if pid in by_person and not args.refresh:
            continue
        first, last = surname_variants(person["name"])
        if not last:
            continue
        last_f = fold(last)
        first_f = fold(first) if first else ""
        matched = None
        for login, info in owner_info.items():
            name_f = fold(info.get("name") or "")
            login_f = fold(login)
            if last_f and last_f in name_f and (not first_f or first_f[0] == (name_f.replace(last_f, "")[:1] or "")):
                matched = (login, "surname_match_verified_owner", info.get("name"))
                break
            if login_f.endswith(last_f) and 0 < len(login_f) - len(last_f) <= 2:
                matched = (login, "fuzzy_login_verified_owner", info.get("name"))
                break
        if matched:
            by_person[pid] = {
                "person_id": pid, "name": person["name"], "github_login": matched[0],
                "method": matched[1], "profile_name": matched[2], "confidence": "high",
            }

    atomic_write(AUTHORMAP_OUT, list(by_person.values()))
    log("pass 1 (verified-owner surname match): %d mapped" % len(by_person))

    # Pass 1.5: exact profile-name match against every User account the
    # `orgs --discover` step pulled in as a contributor to a repo we already
    # know is own-group -- these are real people who worked on our own
    # systems, so an exact display-name match is very high-precision (no
    # guessing, no username search noise).
    discovered = load(ORGS_OUT, {})
    by_exact_name = {}
    for login, info in discovered.items():
        if not isinstance(info, dict) or info.get("type") != "User":
            continue
        name = info.get("name")
        if name:
            by_exact_name.setdefault(fold(name), []).append((login, name))
    added_15 = 0
    for person in authors:
        pid = person["person_id"]
        if pid in by_person and not args.refresh:
            continue
        cands = by_exact_name.get(fold(person["name"]))
        if cands and len(cands) == 1:
            login, name = cands[0]
            by_person[pid] = {
                "person_id": pid, "name": person["name"], "github_login": login,
                "method": "exact_profile_name_from_discovered_contributor",
                "profile_name": name, "confidence": "high",
            }
            added_15 += 1
    atomic_write(AUTHORMAP_OUT, list(by_person.values()))
    log("pass 1.5 (exact name match on discovered contributors): +%d mapped (%d total)" % (
        added_15, len(by_person)))

    # Pass 2: GitHub user search by full name for everyone still unmapped.
    unmapped = [p for p in authors if p["person_id"] not in by_person]
    log("pass 2: searching GitHub for %d unmapped authors" % len(unmapped))
    for i, person in enumerate(unmapped, 1):
        if args.limit and i > args.limit:
            break
        name = person["name"]
        q = '"%s" in:name type:user' % name
        data = client.get("/search/users?" + urllib.parse.urlencode({"q": q, "per_page": 5}), is_search=True)
        items = (data or {}).get("items") or []
        best = None
        for item in items:
            login = item.get("login")
            info = client.get("/users/%s" % login)
            if not info:
                continue
            name_f = fold(info.get("name") or "")
            target_f = fold(name)
            if not name_f:
                continue
            if name_f == target_f:
                best = (login, "exact_name_search", info.get("name"), "high")
                break
            first, last = surname_variants(name)
            if last and fold(last) in name_f and (not first or fold(first)[:1] == name_f.replace(fold(last), "")[:1] or fold(first) in name_f):
                if best is None:
                    best = (login, "fuzzy_name_search", info.get("name"), "medium")
        if best:
            by_person[person["person_id"]] = {
                "person_id": person["person_id"], "name": name, "github_login": best[0],
                "method": best[1], "profile_name": best[2], "confidence": best[3],
            }
        if args.verbose or i % 20 == 0:
            log("[%d/%d] %s -> %s  core=%d search=%d cache=%d" % (
                i, len(unmapped), name, best[0] if best else "none",
                client.stats["core"], client.stats["search"], client.stats["cache"]))
        if i % 20 == 0:
            atomic_write(AUTHORMAP_OUT, list(by_person.values()))

    atomic_write(AUTHORMAP_OUT, list(by_person.values()))
    log("done: %d/%d authors mapped to a GitHub login" % (len(by_person), len(authors)))


# ------------------------------------------------------------ (c) repolist


def cmd_repolist(args):
    client = Client(verbose=args.verbose)
    authormap = load(AUTHORMAP_OUT, [])
    existing = load(REPOLIST_OUT, {})
    logins = sorted({r["github_login"] for r in authormap if r.get("github_login")})
    for i, login in enumerate(logins, 1):
        if login in existing and not args.refresh:
            continue
        repos = paginate_repos(client, "users", login)
        existing[login] = [slim_repo(r) for r in repos]
        if args.verbose or i % 20 == 0:
            log("[%d/%d] %s -> %d repos  core=%d cache=%d" % (
                i, len(logins), login, len(repos), client.stats["core"], client.stats["cache"]))
        if i % 20 == 0:
            atomic_write(REPOLIST_OUT, existing)
    atomic_write(REPOLIST_OUT, existing)
    log("done: %d accounts listed" % len(existing))


# --------------------------------------------------------------- (d) match


STOPWORDS = {"a", "an", "the", "of", "for", "and", "or", "with", "on", "in", "to",
             "towards", "toward", "via", "using", "based", "system", "language",
             "compiler", "compilers", "optimization", "optimizing", "programming"}

# This site's own meta repos -- never a legitimate "own repo" for any paper.
EXCLUDE_REPOS = {"mit-commit/nextgen", "mit-commit/commit-website", "mit-commit/commit-wiki"}


def keywords(text):
    return {w for w in re.split(r"[^a-z0-9]+", (text or "").lower()) if len(w) >= 4 and w not in STOPWORDS}


def score_candidate(repo, pub, author_name=None):
    evidence = []
    score = 0
    title_kw = keywords(pub.get("title"))
    name_kw = keywords(repo.get("name")) | keywords(repo.get("description"))
    overlap = title_kw & name_kw
    if overlap:
        score += min(3, len(overlap))
        evidence.append("repo name/description shares keyword(s) %s with the paper title" % sorted(overlap))
    elif author_name:
        # Date proximity and "it's their own account" are supporting
        # signals, not evidence on their own -- an author's unrelated
        # hobby repo from the right year is not a paper candidate. Require
        # a real title/description keyword hit to even consider a
        # personal-account repo further.
        return 0, []

    year = pub.get("year")
    try:
        year = int(year)
    except (TypeError, ValueError):
        year = None
    created = repo.get("created_at")
    if year and created:
        created_year = int(created[:4])
        if abs(created_year - year) <= 1:
            score += 2
            evidence.append("created within 1y of publication (%s vs %s)" % (created_year, year))
        elif abs(created_year - year) <= 3:
            score += 1
            evidence.append("created within 3y of publication (%s vs %s)" % (created_year, year))

    if author_name:
        evidence.append("from %s's own GitHub account" % author_name)
        score += 1

    if repo.get("fork"):
        evidence.append("note: this is a fork")
    return score, evidence


def cmd_match(args):
    pubs = {p["bibtexKey"]: p for p in load(PUBLICATIONS, [])}
    authors = load(os.path.join(AUTHORS_DIR, "authors.json"), [])
    authormap = {r["person_id"]: r for r in load(AUTHORMAP_OUT, [])}
    repolist = load(REPOLIST_OUT, {})
    orgs = load(ORGS_OUT, {})
    candidates = load(CANDIDATES, {})
    verified = load(VERIFIED, {})

    already_own = {k for k, rows in verified.items() if any(r.get("own_group") for r in rows)}

    # paper -> list of (person_id, name) from authors.json
    paper_authors = {}
    for person in authors:
        for key in person.get("papers") or []:
            paper_authors.setdefault(key, []).append(person)

    out = {}
    all_org_repos = []
    for login, info in orgs.items():
        # Only real group orgs, not the (much larger, much noisier) pool of
        # individual GitHub accounts `orgs --discover` pulled in as
        # contributors -- those feed the author map instead, where an exact
        # profile-name match keeps precision high.
        if isinstance(info, dict) and info.get("type") == "Organization" and info.get("repos"):
            all_org_repos.extend(info["repos"])

    for key, pub in pubs.items():
        if key in already_own:
            continue
        pool = []
        # (c) authors' own repos
        for person in paper_authors.get(key, []):
            am = authormap.get(person["person_id"])
            if not am or not am.get("github_login"):
                continue
            for repo in repolist.get(am["github_login"], []):
                if repo.get("full_name") in EXCLUDE_REPOS:
                    continue
                s, ev = score_candidate(repo, pub, author_name=person["name"])
                if s > 0:
                    pool.append((s, repo, ev, am["confidence"]))
        # (a) org repos -- only worth considering if name/description overlaps
        for repo in all_org_repos:
            if repo.get("full_name") in EXCLUDE_REPOS:
                continue
            s, ev = score_candidate(repo, pub)
            if s >= 2 and (keywords(repo.get("name")) | keywords(repo.get("description"))) & keywords(pub.get("title")):
                pool.append((s, repo, ev, "high"))

        pool.sort(key=lambda t: t[0], reverse=True)
        rows = []
        seen = set()
        for s, repo, ev, conf in pool[:5]:
            fn = repo.get("full_name")
            if fn in seen:
                continue
            seen.add(fn)
            rows.append({
                "repo": fn, "url": repo.get("html_url"), "score": s,
                "confidence": "high" if s >= 4 else ("medium" if s >= 2 else "low"),
                "evidence": ev, "stars": repo.get("stars"),
                "created_at": repo.get("created_at"), "description": repo.get("description"),
                "source": "deep-hunt",
            })
        # fold in the existing medium-confidence candidate.json row the
        # earlier search-and-verify pass rejected -- it's evidence the
        # model already saw and didn't confirm, kept here for the deeper
        # batch pass to re-weigh alongside the new deep-hunt evidence.
        for row in candidates.get(key) or []:
            if row.get("confidence") == "medium" and row.get("repo") not in seen:
                r = dict(row)
                r["source"] = "prior-search-medium"
                rows.append(r)
                seen.add(row.get("repo"))
        if rows:
            out[key] = rows

    atomic_write(MATCH_OUT, out)
    log("done: %d repo-less papers got >=1 new candidate (of %d repo-less)" % (
        len(out), len(pubs) - len(already_own)))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("orgs")
    p.add_argument("--discover", action="store_true")
    p.add_argument("--refresh", action="store_true")
    p.add_argument("-v", "--verbose", action="store_true")
    p.set_defaults(func=cmd_orgs)

    p = sub.add_parser("authormap")
    p.add_argument("--refresh", action="store_true")
    p.add_argument("--limit", type=int)
    p.add_argument("-v", "--verbose", action="store_true")
    p.set_defaults(func=cmd_authormap)

    p = sub.add_parser("repolist")
    p.add_argument("--refresh", action="store_true")
    p.add_argument("-v", "--verbose", action="store_true")
    p.set_defaults(func=cmd_repolist)

    p = sub.add_parser("match")
    p.add_argument("-v", "--verbose", action="store_true")
    p.set_defaults(func=cmd_match)

    args = ap.parse_args()
    if not os.environ.get("GITHUB_TOKEN"):
        sys.exit("GITHUB_TOKEN not set")
    args.func(args)


if __name__ == "__main__":
    main()
