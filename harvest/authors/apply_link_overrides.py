#!/usr/bin/env python3
"""Fold harvest/authors/link-overrides.json into harvest/authors/links.json.

The GitHub match audit (harvest/authors/github-match-audit.json) found 17
accounts belonging to different people who share an author's name. This
script applies that finding, plus the links he supplied by hand. It is
idempotent: running it twice changes nothing the second time.

Four actions, matching the rules in link-overrides.json:

  drop      remove every candidate whose `source` starts with "github_" for
            that person. The blog and email were scraped from the wrong
            person's GitHub profile, so they are wrong for the same reason
            the handle is -- 31 candidates across 17 people, not 17.
  hold      keep the candidate but set publish=false, so nothing renders it
            until a second signal turns up.
  never     empty accounts stay but are marked never_primary=true.
  human     links he supplied directly are inserted as the FIRST candidate
            with source="human"; they outrank anything harvested.

"NOT FOUND" in the drop report is normal once the drops have been applied
upstream -- the script only counts a drop when the handle is still present.

Usage:
    python3 harvest/authors/apply_link_overrides.py            # dry run
    python3 harvest/authors/apply_link_overrides.py --write    # apply
"""

import argparse
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
LINKS = HERE / "links.json"
OVERRIDES = HERE / "link-overrides.json"


def gh_handle(candidate):
    url = candidate.get("url") or ""
    if "github.com/" not in url:
        return None
    return url.split("github.com/", 1)[1].rstrip("/").split("/")[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="write links.json in place")
    args = ap.parse_args()

    links = json.loads(LINKS.read_text())
    ov = json.loads(OVERRIDES.read_text())

    drop_by_pid = {d["person_id"]: d["handle"] for d in ov["drop"]}
    hold = {h["handle"] for h in ov["hold_do_not_publish"]}
    never = set(ov["never_primary_empty_accounts"])

    human = ov.get("human_supplied", [])
    human_by_pid = {h["person_id"]: h for h in human}

    removed, held, marked, added, emptied = 0, 0, 0, 0, []
    seen_drop = set()

    for person in links["people"]:
        pid = person.get("person_id")
        cands = person.get("candidates") or []

        if pid in drop_by_pid:
            handles = {gh_handle(c) for c in cands}
            if drop_by_pid[pid] not in handles:
                # already applied, or the data moved under us
                continue
            seen_drop.add(pid)
            kept = [c for c in cands if not str(c.get("source", "")).startswith("github_")]
            removed += len(cands) - len(kept)
            person["candidates"] = cands = kept
            if not cands:
                emptied.append(person.get("name", pid))

        for c in cands:
            h = gh_handle(c)
            if h is None:
                continue
            if h in hold and c.get("publish") is not False:
                c["publish"] = False
                c["hold_reason"] = "github-match-audit: unverified, needs a second signal"
                held += 1
            if h in never and not c.get("never_primary"):
                c["never_primary"] = True
                marked += 1

    # Separate pass: a person can be in both `drop` and `human_supplied`, and
    # the drop branch above short-circuits once its handle is already gone.
    for person in links["people"]:
        h = human_by_pid.get(person.get("person_id"))
        if h is None:
            continue
        cands = person.get("candidates") or []
        url = h["url"].rstrip("/")
        if any((c.get("url") or "").rstrip("/") == url for c in cands):
            continue
        cands.insert(0, {
            "tier": h["tier"],
            "source": "human",
            "url": h["url"],
            "evidence": "supplied by him 2026-08-26",
        })
        person["candidates"] = cands
        added += 1

    unmatched_human = sorted(set(human_by_pid) - {p.get("person_id") for p in links["people"]})
    missing = sorted(set(drop_by_pid) - seen_drop)

    print(f"people with drops applied : {len(seen_drop)} of {len(drop_by_pid)}")
    print(f"candidates removed        : {removed}")
    print(f"candidates held           : {held}")
    print(f"empty accounts marked     : {marked}")
    print(f"links he supplied added   : {added} of {len(human)}")
    if emptied:
        print("left with no link at all  : " + ", ".join(sorted(emptied)))
        print("  (expected -- their only link was a stranger's account; they")
        print("   go to the academic-page hunt or the LinkedIn sittings)")
    if unmatched_human:
        print("HIS LINKS WITH NO MATCHING PERSON: " + ", ".join(unmatched_human))
    if missing:
        print("NOT FOUND (already applied, or person_id changed): " + ", ".join(missing))

    if args.write:
        LINKS.write_text(json.dumps(links, indent=1, ensure_ascii=False) + "\n")
        print(f"\nwrote {LINKS}")
    else:
        print("\ndry run -- pass --write to apply")

    return 0


if __name__ == "__main__":
    sys.exit(main())
