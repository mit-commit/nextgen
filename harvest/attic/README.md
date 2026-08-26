# Attic — closed one-off scripts

Scripts whose task is complete and will not re-run: round-numbered queue
tasks, superseded v1s, and applied migrations. Kept runnable for
archaeology; nothing here is part of the refresh pipeline
(`docs/refresh.md` names the durable set). The `apply_*` scripts that
encode human rulings stay in their original homes (protected), as does
`idmap_review_finalize.py` (refresh.md §1 references its pattern) and
`dedupe_verified_repos.py` (imported by fold_own_inventory here).
