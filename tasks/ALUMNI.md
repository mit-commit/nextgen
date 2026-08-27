# Alumni page + alumni/author roster — worker spec (Fable)

His instruction, 2026-08-27. Four deliverables now:

1. Add each alum's **current position** under their name on the People page,
   smaller font.
2. **Clean up the role vocabulary** — "Graduate Student" is not a degree, and
   visitors are recorded under many different names.
3. **Merge his UROP roster in** — every UROP student belongs in the alumni
   list; add the ones missing.
4. Build the **alumni + authors spreadsheet** for his own use.

## Privacy boundary — read before collecting anything

`mit-commit/nextgen` and `mit-commit/commit-website` are **public repos**.
Email addresses must not be committed to either. A public file of academics'
addresses is a spam list with a citation. The UROP export he supplied is an
internal administrative record and carries MIT addresses, phone numbers and
home addresses — it is **especially** not for the repo.

- Full spreadsheet and the UROP source stay in `~/workspace/alumni-roster/`,
  gitignored. Never `git add` them.
- The website gets **name, role, years, current position**. Never an email,
  phone, or address.
- Emails otherwise come only from what a person published themselves — a
  faculty page, their own site, an address on their own paper. **Never
  construct one from a pattern**; a guessed address reaches a stranger and
  proves nothing. Blank is the correct answer. Record a source per address.
- No scraper aggregators, leak databases or people-search sites.
- `alum.mit.edu` is behind his login: leave blank, list who is missing.

## Deliverable 1 — current position

Source of alumni: `people.html` in `mit-commit/commit-website` plus any
`data/people*.json` it reads — read the page, do not assume.

Find each person's current position, one line ("Principal Engineer, NVIDIA").
Preference order, same as the link ruling: active faculty/lab page, then the
LinkedIn headline — **much of this is already recorded in
`harvest/authors/linkedin-results.json` and
`linkedin-results-professional.json`, check there before searching** — then
their own site or an employer staff page.

Identity bar unchanged: employer or education plus timeframe must fit their
time in the group. A wrong title under someone's name is worse than a blank.
Unconfirmed goes on a list for him.

Rendering: under the name, smaller and lighter, using the same `clamp()` step
as the facet rows in `tasks/RESPONSIVE.md`. Blank positions degrade cleanly —
no empty line, no stray separator.

## Deliverable 2 — role vocabulary

Collapse the current free-text roles onto one canonical set:

    PhD · SM · MEng · UROP · Postdoc · Research Staff ·
    Visiting Scholar · Visiting Student

Rules:

- **"Graduate Student" is not a role.** Resolve it from evidence, not
  assumption: `publications.json` records thesis type per person —
  `phd-thesis`, `sm-thesis`, `meng-thesis`. Use it. A person with a PhD
  thesis is `PhD`; with only an SM thesis, `SM`.
- Someone who progressed (SM then PhD in the group) gets the **highest**
  degree completed here, with the full span of years.
- **Visitors**: collapse every variant — visiting student, visiting
  researcher, visiting professor, exchange student, and so on — to
  `Visiting Scholar` for someone who held a faculty or research position
  elsewhere, `Visiting Student` for someone enrolled elsewhere.
- Anything you cannot resolve from evidence goes on a list for him with what
  the page currently says. **Do not guess a degree.** Getting someone's
  qualification wrong on their group's own page is a real error.
- Report the full before → after mapping so he can scan it in one pass.

## Deliverable 3 — merge the UROP roster

He supplied a UROP export; the cleaned version is at
`~/workspace/alumni-roster/urop-roster.csv` — **163 students**, being everyone
with at least one non-cancelled term between 1997 and 2017. Four students
whose every term was cancelled are already excluded; do not re-add them.

- Every one of these belongs in the alumni list. Add whoever is missing, role
  `UROP`, with their year span.
- Match against existing alumni AND against `harvest/authors/authors.json`
  **by person, not by string**: the export writes "Petkov, Darin S." where
  the site writes "Darin Petkov". Someone already listed for a higher role
  (they UROPed, then did an MEng here) keeps the higher role — do not
  duplicate them, and do not demote them.
- The export is also **evidence for the unresolved author identities**: it
  carries real full names, class years, and MIT addresses. Two known uses:
  the corpus spells one author **Alexandro Artola** while the UROP roster
  says **Alejandro Artola** — likely why that sitting found nothing; and
  Darin Petkov, Tsvetomir Petrov and Matthew DeBergalis all appear with
  years. Check the export against the people still marked `no_link` and
  report what it resolves. Do not edit `links.json` — report, and the
  coordinator folds it in through `link-overrides.json`.

## Deliverable 4 — the roster spreadsheet

One row per person: union of `authors.json`, the People page, and the UROP
roster. Same person must not appear twice under different spellings.

| Column | Fill from |
|---|---|
| Name | canonical form from `authors.json`, else the page, else the export |
| Email | published sources only; the MIT address from his own UROP export is legitimate for this private file — mark it as such |
| Email source | so he can judge each one |
| URL to cite | resolved link from `links.json` after overrides; respect `publish:false` and `never_primary` |
| Current job | as in deliverable 1 |
| Role | the canonical role from deliverable 2 |
| Years | span in the group |
| Was alumni? | yes / no |
| Has a paper? | yes / no — present in `authors.json` |
| Connected on LinkedIn? | `1st` / `2nd` / `3rd+` / unknown — **from the `degree` field already recorded** in the two linkedin-results files. Everyone else is `unknown`; do not open LinkedIn, that is a sitting he runs |

Sort: alumni first, then authors, alphabetical by surname within each.
Write `alumni-roster.csv` and `alumni-roster.xlsx` to
`~/workspace/alumni-roster/`, frozen header row, sensible widths.

## Report

How many people, how many have each field filled, the role before→after
mapping, who could not be confirmed, and what the UROP export resolved. State
the gaps plainly — they are what he will act on.
