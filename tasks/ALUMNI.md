# Alumni page + alumni/author roster — worker spec (Fable)

His instruction, 2026-08-27. Four deliverables:

1. Add each alum's **current position** under their name on the People page,
   smaller font.
2. **Clean up the role vocabulary** — "Graduate Student" is not a degree, and
   visitors are recorded under many different names.
3. **Merge in his UROP roster and his thesis list** — everyone who did a UROP
   or a thesis under him belongs in the alumni list, and every thesis belongs
   in the corpus.
4. Build the **alumni + authors spreadsheet** for his own use.

## Privacy boundary — read before collecting anything

`mit-commit/nextgen` and `mit-commit/commit-website` are **public repos**.
Email addresses must not be committed to either. A public file of academics'
addresses is a spam list with a citation. The UROP export is an internal
administrative record carrying MIT addresses, phones and home addresses — it
is **especially** not for the repo.

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

### The UROP addresses are historical — treat them as such

His note, 2026-08-27: those addresses date from the UROP terms themselves
(1997–2017) and most of these people left MIT years ago. **Assume they are
dead until shown otherwise.** MIT keeps some alumni forwarding alive and
retires other accounts; you cannot tell which from the address.

So:

- Two separate columns, never merged: **Email (current)** from a published
  present-day source, and **Email (historical)** from the UROP export, with
  the year it was recorded so he can see how old it is.
- A historical address never fills the current column, and never becomes a
  `mailto:` link on the site or in `links.json`. Under the link ruling a
  `mailto:` is the last resort, and a dead one is worse than none.
- **Do not send test messages to check whether an address still works.** Mail
  from an unknown sender probing old accounts is exactly what it looks like.
- If a current address turns up for someone who also has a historical one,
  keep both; the old one is still useful to him for recognising a person.

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
as the facet rows in `tasks/RESPONSIVE.md`. Blank positions degrade cleanly.

## Deliverable 2 — role vocabulary

Collapse the current free-text roles onto one canonical set:

    PhD · SM · MEng · UROP · Postdoc · Research Staff ·
    Visiting Scholar · Visiting Student

- **"Graduate Student" is not a role.** Resolve it from evidence:
  `harvest/theses/supervised-theses.json` is his own authoritative list and
  names the degree directly for 94 people. `publications.json` thesis types
  corroborate. Use those, never assumption.
- Someone who progressed (SM then PhD here — there are nine) gets the
  **highest** degree completed here, with the full span of years.
- **Visitors**: collapse every variant to `Visiting Scholar` (held a faculty
  or research post elsewhere) or `Visiting Student` (enrolled elsewhere).
- Unresolvable goes on a list for him with what the page says now.
  **Do not guess a degree.** Getting someone's qualification wrong on their
  own group's page is a real error.
- Report the full before → after mapping so he can scan it in one pass.

## Deliverable 3 — merge the theses and the UROPs

**Theses** — `harvest/theses/supervised-theses.json`, in the repo: 103 theses,
94 people, his own list and authoritative.

- Every one of these people belongs in the alumni list at the degree stated.
- Every thesis belongs in `publications.json`. The file names **5 that are
  missing entirely** (Tammy Yap 1999, Tim Garnett 2003, Ben Wagner 2006,
  Ceryen Tan 2009, Kevin Kelly 2010) — add them, with the PDF from MIT
  DSpace where it exists, following the existing thesis-entry conventions.
- It also names **3 title conflicts** between his list and the corpus. The
  Garnett one looks like a misattribution — the corpus has his MEng under
  Iris Baron's thesis title. **Report these; do not pick a title.** For Frank
  and Taylor, check DSpace and report what MIT's own record says.

**UROPs** — `~/workspace/alumni-roster/urop-roster.csv`, placed locally by
him: 163 students with at least one non-cancelled term, 1997–2017. Four
whose every term was cancelled are already excluded; do not re-add them.

- Add whoever is missing, role `UROP`, with their year span.
- Match by person, not by string: the export writes "Petkov, Darin S." where
  the site writes "Darin Petkov". **A thesis outranks a UROP entry for the
  same person** — do not duplicate, do not demote.
- The export is also **evidence for unresolved author identities**: real
  names, class years, MIT addresses. The corpus spells one author
  **Alexandro Artola** while the export says **Alejandro Artola** — likely
  why that sitting found nothing. Check the export against everyone still
  marked `no_link` and report what it resolves. Do not edit `links.json`;
  the coordinator folds it in through `link-overrides.json`.

## Deliverable 4 — the roster spreadsheet

One row per person: union of `authors.json`, the People page, the thesis
list, and the UROP roster. No one appears twice under different spellings.

| Column | Fill from |
|---|---|
| Name | canonical form from `authors.json`, else the page, else the source list |
| Email (current) | published present-day sources only |
| Email (historical) | the UROP export, with the year recorded |
| Email source | so he can judge each one |
| URL to cite | resolved link from `links.json` after overrides; respect `publish:false` and `never_primary` |
| Current job | as in deliverable 1 |
| Role | canonical role from deliverable 2 |
| Years | span in the group |
| Thesis | title and degree if they did one here |
| Was alumni? | yes / no |
| Has a paper? | yes / no — present in `authors.json` |
| Connected on LinkedIn? | `1st` / `2nd` / `3rd+` / unknown — **from the `degree` field already recorded** in the two linkedin-results files. Everyone else is `unknown`; do not open LinkedIn, that is a sitting he runs |

Sort: alumni first, then authors, alphabetical by surname within each.
Write `alumni-roster.csv` and `alumni-roster.xlsx` to
`~/workspace/alumni-roster/`, frozen header row, sensible widths.

## Report

How many people, how many have each field filled, the role before→after
mapping, the thesis additions and title conflicts, who could not be
confirmed, and what the UROP export resolved. State the gaps plainly — they
are what he will act on.
