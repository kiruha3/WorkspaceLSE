# Lightweight expertise registry without pagination

**Approved direction:** Load the complete filtered registry using only table data; load the full expertise separately when its card opens. Consider virtual scrolling only if actual rendering measurements justify it.

**Rollback checkpoint:** `3693c19` (before this implementation).

- [x] Add tests for more than 25 rows, filtering/scopes, natural ordering, bounded database queries and the lightweight contract.
- [x] Add a read-only `/expertises/registry/` collection with `count` and `results`; retain the existing paginated and detail APIs for other consumers.
- [x] Switch the registry UI to a dedicated row type and the full collection. Remove pagination controls and page parameters from new filter/sort actions. Legacy page URLs may still open the full list.
- [x] Keep all displayed columns, return links, filters, three-state sorting, import controls and complete Excel export.
- [x] Run relevant tests and build. Measure the actual response size and browser rendering; inspect scrolling and full-card opening.
- [x] Document measured results, save a local commit and report the result.

No database migrations or business-data updates. No push. Heavy result histories, documents, production facts and per-command permissions stay in the detail response. Table names and historical/current executors retain their existing meaning.
