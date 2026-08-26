# Applying the GitHub match audit (github-match-audit.json)

The coordinator ran a full manual pass over every author with a GitHub
candidate in `links.json` (198 accounts): 17 wrong, 19 uncertain, 39
zero-repo/unverifiable, 123 look right. This applies the three
actionable buckets to `links.json`.

## (a) 17 wrong matches — dropped

Removed the `github_profile` candidate plus every candidate DERIVED from
that same wrong account (`github_blog`, `github_email` -- a personal
site or contact email scraped from the wrong account's own profile is
equally invalid), then recomputed `best_tier` from what's left.

Albert Ma's `adadima` was already absent from `links.json`'s current
state (it resolves solely to Alexandra Dima there, correctly, via
`surname_match_verified_owner`) -- the collision the human's ruling
addressed must have existed in an earlier/intermediate snapshot; nothing
to change for him specifically. The other 16:

| person | dropped handle | new best_tier |
|---|---|---|
| Anant Agarwal | agarwalanant | permanent-academic |
| John Hennessy | DevJHennessy | permanent-academic |
| Michael Taylor | patternizer | permanent-academic |
| Vivek Sarkar | viveksarkar0 | permanent-academic |
| Rob Schreiber | HerrSchreiber | **none** (no candidates left) |
| Daniel Sanchez | danielSanchezQ | permanent-academic |
| Henry Hoffman(n) | thehen | **none** (no candidates left) |
| Jason Miller | developit | professional (orcid -- itself flagged as a possible mismatch in the academic-page-hunt report, unrelated to this fix) |
| Matthew Brown | muglug | **none** (no candidates left) |
| Matthew Frank | maafrank | **none** (no candidates left) |
| Johnathan Babb | warmace101 | **none** (no candidates left) |
| Dan Campbell | Danny2097 | **none** (no candidates left) |
| William Harrod | wharrod | **none** (no candidates left) |
| Paras Jain | retroportalstudio | email |
| Yang Cao | yiluheihei | professional (orcid) |
| Eric Wong | wsdjeg | **none** (no candidates left) |

8 people now have no link at all and are residue for a future sitting/hunt.

## (b) 19 uncertain matches — flagged do-not-publish, not removed

Added a `flag` field to each candidate (kept, for when a real second
signal shows up later) and excluded it from `best_tier` ranking. Checked
the repo-contributor angle the task asked for: of the 19, 7 have an own
repo traceable through their papers (`harvest/repos/verified.json`) --
`timothy-garnett`/`DynamoRIO/dynamorio`, `jasper-lin` + `steven-hall` +
`jeremy-wong`/`bthies/streamit`, `guoyu-li` + `qianzhou-wang`/
`spac-proj/SPAC`, `ondrej-sykora`/`ithemal/bhive`+`ithemal/Ithemal`.
Fetched each repo's contributor list live (GitHub API) and checked for
the candidate handle: **no match in any of them** (`spac-proj/SPAC`
returned 0 contributors from the API, so those two checks are
inconclusive rather than a confirmed negative; the rest are genuine
negatives). This settles nothing new -- all 19 stay uncertain, exactly
per the task's default. The other 12 have no own repo to check against
at all.

| person | handle | old best_tier | new best_tier |
|---|---|---|---|
| Timothy Garnett | tgarnett | professional | none |
| Walter Lee | leewalter | professional | professional (orcid) |
| Peter Finch | PeterEFinch | professional | none |
| Jasper Lin | jasper241024 | professional | email |
| Guoyu Li | Lester-Li-BUPT | professional | professional (orcid) |
| Steven Hall | hallzy | professional | professional (orcid -- itself flagged as a likely wrong ORCID match in the academic-page-hunt report) |
| Juan C Reyes | cookies4u | permanent-academic | permanent-academic (unaffected) |
| Christopher Rhodes | arreyder | professional | professional (orcid) |
| Ricardo Ruiz | ruizrica | professional | none |
| Mark Stephenson | Mark2000 | permanent-academic | permanent-academic (unaffected) |
| Elijah Taylor | Elijahesegift | professional | none |
| Govinda Shrestha | Govinda010 | professional | none |
| Qianzhou Wang | KingsAlpaca | professional | none |
| Richard Wang | wangleihd | professional | professional (orcid) |
| Amy Williams | csamywilliams | permanent-academic | permanent-academic (unaffected) |
| Jeremy Wong | jermspeaks | professional | personal |
| Min Zhang | MinZHANG-WHU | professional | none |
| Larry Rudolph | curiouslarry-tech | professional | email (his own MIT CSAIL address, from a paper PDF) |
| Ondrej Sykora | osykora | professional | none |

## (c) 39 zero-repo/unverifiable accounts — flagged, never primary

The audit file only kept a 20-item *sample* of this bucket, not the
full 39 (its "wrong" and "uncertain" buckets are exhaustive lists
matching their summary counts exactly; "no_evidence" and
"clearly_right_sample" are not). Re-derived the exhaustive list myself:
fetched `public_repos` for all 178 `github_profile` candidates currently
in `links.json` (post the (a)/(b) fixes above) -- 17 have zero. One
(`curiouslarry-tech`, Larry Rudolph) is already handled under (b). The
other 16 are flagged here the same way as (b): candidate stays, `flag`
added, excluded from `best_tier` ranking.

| person | handle | old best_tier | new best_tier |
|---|---|---|---|
| Ian Bratt | ISBRATT | professional | email |
| Zohreh Davoudi | zdavoudi | permanent-academic | permanent-academic (unaffected) |
| Justin Gottschlich | jgottschlich-intel | permanent-academic | permanent-academic (unaffected) |
| Sid Henderson | sidhenderson | professional | none |
| Jang Kim | jangplayhaven | professional | professional (had another candidate) |
| Pratik Kotkar | pratik-apoha | professional | none |
| Mark Oskin | markoskin | professional | email |
| Diego Puppin | dp-synth | professional | email |
| Arvind Saraf | arvindsaraf | professional | none |
| David Sehr | davidsehr | professional | none |
| Janis Sermulins | janis-debug-hub | professional | none |
| Saad Shakhshir | saads | professional | none |
| Dillon Sharlet | dsharletg | professional | professional (had another candidate) |
| Nathan Shnidman | mitfit | professional | personal |
| Thomas Sterling | tster9306 | professional | none |
| Nesime Tatbul | tatbul | permanent-academic | permanent-academic (unaffected) |

Note: this re-derivation was against the *current* 178, which already
excludes the 16 accounts dropped under (a) -- some of the audit's
original 39 may have been among those 16 and are therefore not double
counted here; that's expected, not a discrepancy to chase.

## Net effect

`links.json` best_tier distribution after all three fixes: 147
permanent-academic (was ~145 before this task, +2 net from candidates
that only mattered once a github fallback was removed), 104 professional
(down from ~136), 18 email, 5 personal, 3 linkedin, 1 memorial, **90
residue** (up from 68) -- honest: dropping bad/unverifiable GitHub
matches surfaces more people who currently have no reliable link, not
fewer. That's the tradeoff the audit exists to make.
