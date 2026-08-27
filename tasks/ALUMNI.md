# Alumni page + alumni/author roster — worker spec (Fable)

His instruction, 2026-08-27. Two deliverables:

1. The **Alumni section of the People page** currently lists names and
   nothing else. Add each person's current position under their name, in a
   smaller font.
2. A **spreadsheet of everyone** — alumni and paper authors — with contact
   and status columns, for his own use.

## Privacy boundary — read this before collecting anything

`mit-commit/nextgen` and `mit-commit/commit-website` are **public repos**.
Email addresses must not be committed to either one. A public file of
academics' addresses is a spam list with a citation.

- Write the full spreadsheet **locally only**: `~/workspace/alumni-roster/`.
  Do not `git add` it. Add the path to `.gitignore` in the same commit that
  creates any sibling file, so a later session cannot commit it by accident.
- If a committed artifact is wanted for the pipeline, commit a copy with the
  email column removed and say so in the commit message.
- The website itself gets **current position only** — never an email address,
  never a personal phone, never a home city.

Collection rules, which are not negotiable:

- Take addresses only from sources the person published themselves: a faculty
  or lab page, their own website, an address printed on their own paper, a
  public CV. Record where each one came from.
- **Never construct an address from a pattern.** Guessing
  `first.last@company.com` produces wrong addresses that reach strangers, and
  it is not evidence of anything. An empty cell is the correct answer when
  nothing was published.
- Do not use scraper aggregators, leak databases, or people-search sites,
  whatever they claim about their sources.
- The MIT alumni directory (`alum.mit.edu`) is behind his login. Leave those
  cells empty and list who is missing — he can fill them in one sitting if he
  wants to. Do not ask him for credentials.

## Deliverable 1 — the Alumni section

Source of truth for who is an alum: the existing People page in
`mit-commit/commit-website` (`people.html`) plus `data/people*.json` if the
list is data-driven — read the page, do not assume.

For each alum, find their **current position** — title and organisation, one
line, e.g. "Principal Engineer, NVIDIA" or "Associate Professor, EPFL". Order
of preference for the source, which is the same ruling already in force for
author links:

1. an active faculty or lab page
2. their LinkedIn headline — much of this is already recorded in
   `harvest/authors/linkedin-results.json` and
   `linkedin-results-professional.json`; **check there first before searching
   for anything**
3. their own website or a current employer's staff page

Identity bar, unchanged: education or employer plus timeframe must be
consistent with their time in the group. A name match is not enough. If you
cannot confirm the person, leave the line blank and list them for him — a
wrong job title under someone's name is worse than a blank.

Rendering: the position goes under the name in a smaller, lighter font,
consistent with the type scale from `tasks/RESPONSIVE.md` (use the same
`clamp()` step as the facet rows). Blank positions must degrade cleanly — no
empty line, no stray separator. Link the name using the link ruling if the
People page does not already.

## Deliverable 2 — the roster spreadsheet

One row per person, union of: everyone in `harvest/authors/authors.json`
(paper authors, 368 after the merge) and everyone listed as an alum on the
People page. Match the two sets by person, not by string — the same human
must not appear twice because the page writes "Bill Thies" and the data
writes "William Thies".

Columns, exactly these:

| Column | Fill from |
|---|---|
| Name | canonical form from `authors.json`; the People page spelling if only there |
| Email | published sources only, per the rules above; blank if none |
| Email source | where it came from, so he can judge it |
| URL to cite | the resolved link from `links.json` after overrides — faculty page, else LinkedIn, else best active site. Respect `publish:false` and `never_primary` |
| Current job | as in deliverable 1 |
| Was alumni? | yes / no — from the People page list |
| Has a paper? | yes / no — present in `authors.json` |
| Connected on LinkedIn? | `1st` / `2nd` / `3rd+` / unknown — **from the `degree` field already recorded** in the two linkedin-results files. Everyone else is `unknown`; do not open LinkedIn to find out, that is a sitting he runs, not a worker task |

Sort by: alumni first, then authors, alphabetical by surname within each.

Formats: `alumni-roster.csv` and `alumni-roster.xlsx`, both in
`~/workspace/alumni-roster/`. The xlsx gets a frozen header row, sensible
column widths, and no formatting cleverness beyond that.

## Report

A short summary: how many people, how many have each field filled, and the
list of people whose current position could not be confirmed. State plainly
what is missing rather than implying completeness — the gaps are the part he
will act on.
