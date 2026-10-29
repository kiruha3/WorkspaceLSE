# Three-state table sorting

**Goal:** Click a data-column heading to cycle ascending, descending and original order in all existing tables.

**Architecture:** A shared Vue `SortableTable` owns local sorting or emits controlled server ordering for paginated registries. Django validates a per-endpoint allowlist and sorts the complete visible, filtered result before pagination; comparison uses the same public values displayed to this user. Empty values stay last, equal values keep their original order. Action-only columns stay static. Report totals remain pinned and report exports keep the official form layout.

**Constraints:** Preserve permissions, filters, selection checkboxes, edits, return links and pagination. No schema changes, writes to business records, new dependencies or push.

- [x] Test natural comparisons, stable empty-value handling and three-state headers.
- [x] Build the shared frontend component and server sorting/pagination helper.
- [x] Connect all paginated registries; persist the expertise ordering in its URL and export.
- [x] Connect local detail/history/comparison/report tables without reordering source arrays.
- [x] Test sorting across page boundaries, filtering/scopes and invalid keys.
- [x] Run existing tests and build; check the UI and save a local commit.

Sorting by computed display values requires evaluating the scoped selection on sorted requests. Unsorted requests keep the existing lazy database pagination. Monitor this path as the registry grows; avoid serializing inaccessible data or fetching the entire selection in the browser.
