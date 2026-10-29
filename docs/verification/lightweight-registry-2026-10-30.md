# Lightweight full expertise registry — verification

Rollback checkpoint: `3693c19`.

The main registry now reads `/api/v1/expertises/registry/`: a complete filtered collection with `count` and `results`, without pagination. Existing paginated `/expertises/` and full `/expertises/{id}/` contracts remain available. The row projection preserves every displayed column, including current and historical executors, commission/complex flags and demo markers. It excludes workflow histories, documents and per-command detail calculations.

## Read-only measurement on the local dataset

Measured as setup using an authenticated in-process GET; no business records or sessions were written. These are raw JSON sizes and local server timings, not a network latency guarantee.

| Response | Rows | JSON bytes | SQL queries | Server time |
| --- | ---: | ---: | ---: | ---: |
| New complete lightweight registry | 483 | 355,031 | 7 | 106 ms |
| Existing full paginated response | 25 | 174,636 | 141 | 245 ms |

The matching first 25 lightweight rows occupy 18,329 bytes: approximately **9.5 times smaller** than the previous page response.

## Checks

- 518 frontend tests passed, including complete 41-row rendering, no page parameters, filter/ordering/return links, incomplete-response rejection and retry.
- 54 backend tests passed across the lightweight contract, scopes, bounded query count, all visible fields, calendar filtering, prior sorting/registration and Excel export.
- Production build passed; the existing large bundle warning remains.
- Browser: all 483 links are rendered, no pagination controls, approximately 7,854 table DOM elements. Keyboard End reaches the final row; the column header stays pinned.
- Opening the last work loads its full card with all seven workflow tabs. The return link keeps registry ordering.

Virtualization was not added for this trial: the current 483-row list remains a complete ordinary table with a bounded scroll area and sticky headings. All rows remain searchable by the browser. Reassess rendering and memory for substantially larger datasets or slower client devices.

No database migrations, business-data changes, PHP changes or push.
