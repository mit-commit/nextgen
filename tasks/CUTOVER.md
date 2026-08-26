# Cutover — worker spec (lane F)

His instruction, 2026-08-26: put Umami analytics on the site, then make the
live site at `mit-commit/commit-website` serve this project's publications
page, with home / projects / people still working. Run it with **minimal
interaction from him** — do not stop to ask questions that the repo can
answer.

Two repos:
- source: `mit-commit/nextgen`, local clone `~/workspace/nextgen`
- target: `mit-commit/commit-website`, local clone `/Users/saman/commit-website`,
  published at https://mit-commit.github.io/commit-website/

## Step 0 — the one thing he supplies

The Umami website ID (and script src) from https://cloud.umami.is. It is in
`tasks/UMAMI.md` if he has already pasted it; if that file is absent, STOP and
ask for it — do not invent an ID, and do not skip analytics silently.

## Step 1 — analytics on every page

Add the Umami snippet immediately before `</head>` on EVERY html page of the
target site (publications, index/home, projects, people, and any other page
present — enumerate them, do not assume the list):

    <script defer src="<script src from his dashboard>" data-website-id="<id>"></script>

Rules: `defer`, no inline config, nothing else added. Umami is cookieless, so
no consent banner is required. Verify by grepping every `*.html` afterwards —
the count of pages with the snippet must equal the count of pages.

## Step 2 — migrate the publications page

Bring the nextgen publications experience onto the live site, replacing the
existing `publications.html`. What has to travel with it:

- `publications.html` and any page it links to
- `assets/js/*` and `assets/css/*` it depends on (`publications.js`,
  `citations.js`, `pubs.js`, `common.js`, and whatever else it imports —
  resolve by reading the page, not by guessing)
- the whole data layer it fetches: `data/publications.json`,
  `data/citations/**`, `data/repos/**`, `data/impact-authors.json`,
  `data/citations/citers.json`, `harvest/authors/links.json` if the page
  reads it at runtime, and every other path fetched by the JS
- `papers/**` PDFs referenced by the page

**Resolve the file list by reading the code**, then confirm empirically: serve
the target repo locally and check the browser console and network log for any
404. A missing lazy-loaded data file will not break first paint — it will
break silently on expand, which is exactly the failure this step must catch.

## Step 3 — home, projects, people keep working

These pages exist on the live site today and must be unchanged in behaviour.
If they share `assets/js/common.js` or `assets/css/style.css` with the
publications page, diff carefully: the nextgen versions of those shared files
may have moved on. Where a shared file has diverged, take the nextgen version
ONLY if home/projects/people still render correctly against it; otherwise
namespace the new styles rather than breaking the old pages. Verify each page
loads with an empty console before and after.

## Step 4 — safety net

Do the work on a branch (`cutover`) in the target repo. Before merging,
record the current `main` SHA in the commit message as the rollback point.
Run the UI harness (`tests/ui/facet_test.py` and
`tests/ui/random_settings_test.py`, copied over or pointed at the target
checkout) against the migrated page and require green. Then merge to `main`
in a single commit and push — GitHub Pages will publish from there.

## Step 5 — verify live

After Pages rebuilds (give it a couple of minutes), fetch the live URLs and
check: publications page renders and its panels expand with real data; home,
projects and people load; the Umami script tag is present on each; no 404s in
the network log. Report the live check results plainly, including anything
that did not work.

## Report

Append to `docs/LANES.md` under a `cutover` row: the file list migrated, the
rollback SHA, harness results, and the live verification. State explicitly
whether the site is live and correct, or what is broken. He wants the outcome
stated, not implied.
