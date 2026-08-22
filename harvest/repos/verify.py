#!/usr/bin/env python3
"""Step 1b of the repos lane: GET every candidate URL once, cache the verdict.

Follows redirects so repo renames land as `final_url`. Cache lives in
harvest/repos/_urlcache.json so re-runs are free.
"""
import json, os, ssl, sys, threading, time, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE = os.path.join(ROOT, "harvest/repos/_urlcache.json")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
CTX = ssl.create_default_context()
lock = threading.Lock()


def check(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,*/*"})
    try:
        with urllib.request.urlopen(req, timeout=25, context=CTX) as r:
            body = r.read(4096)
            return {"status": r.status, "final_url": r.geturl(), "error": None,
                    "renamed": r.geturl().rstrip("/") != url.rstrip("/")}
    except urllib.error.HTTPError as e:
        return {"status": e.code, "final_url": e.url, "error": None,
                "renamed": e.url.rstrip("/") != url.rstrip("/")}
    except Exception as e:
        return {"status": None, "final_url": None, "error": f"{type(e).__name__}: {e}"[:200], "renamed": False}


def main(urls):
    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    todo = [u for u in urls if u not in cache]
    print(f"{len(urls)} unique urls, {len(todo)} to fetch", file=sys.stderr)

    def work(u):
        r = check(u)
        if r["status"] is None and r["error"]:
            time.sleep(1.5)
            r = check(u)
        with lock:
            cache[u] = r
            print(f"  {r['status'] or r['error']:>6} {u}" + (f" -> {r['final_url']}" if r["renamed"] else ""), file=sys.stderr)
        return r

    with ThreadPoolExecutor(max_workers=6) as ex:
        list(ex.map(work, todo))
    with open(CACHE, "w") as fh:
        json.dump(cache, fh, indent=2, sort_keys=True)
    return cache


if __name__ == "__main__":
    cand = json.load(open(os.path.join(ROOT, "harvest/repos/_candidates.json")))
    urls = sorted({u["url"] for v in cand["pdfs"].values() for u in v["urls"]})
    main(urls)
