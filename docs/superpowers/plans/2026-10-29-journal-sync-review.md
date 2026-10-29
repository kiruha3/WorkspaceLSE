# Journal Sync Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the owner source/file buttons and a review list with explicit per-field acceptance before updating actual registrations.

**Architecture:** Add a read-only review projection and one atomic orchestration command around existing selections, create-only application, and historical source updates. Keep old endpoints unchanged. Add a Vue review page and source actions in the expertise register.

**Tech Stack:** Existing Django/DRF/PostgreSQL, Vue 3/TypeScript/Pinia/Vitest; no new dependencies.

**Spec:** `docs/superpowers/specs/2026-10-29-journal-sync-review-design.md`

## Global Constraints

- No Google/PHP writes, schema reset, demo data, pushes, or new server duplicates.
- No real expertise changes during development or acceptance; live checks are read-only.
- Preserve all existing routes, permissions, source files, historical numbers and unrelated outputs/.superpowers contents.
- Exact links only; unsupported native/manual workflow cases stay visible with reasons, not silently overwritten.
- Nothing is selected initially; all selected changes apply atomically and replay idempotently.

## Review Focus

1. Source-only changes must not revert a manual edit in another field.
2. New specialty/executor links must be real existing references and reviewed before application.
3. A stale row in a mixed create/update packet must roll back every mutation.
4. A lost response must freeze the selected fields and reuse the same key and packet.
5. Switching source/page must not display or apply a late response for the old batch.

### Task 1: Reviewed atomic source updates

**Files:** create `backend/apps/imports/review.py`, `backend/apps/imports/review_api.py`, `backend/tests/test_journal_review.py`; modify `backend/apps/imports/updates.py`, `backend/apps/imports/urls.py`.

**Interfaces:** GET `/imports/<batch>/review/` returns summary plus changed/new/invalid rows with proposals, hashes, version anchors and labelled differences; POST `/imports/<batch>/review/` consumes explicitly selected rows and accepted_fields and returns created_count/updated_count plus applications. Existing full updates omit accepted_fields and retain all old guards.

- [ ] Write tests for nonmutating preview, null-to-known specialty, exact executor matching and ambiguous names.
- [ ] Observe RED against missing review endpoint.
- [ ] Implement proposal generation and optional selective updates behind the new review command.
- [ ] Add tests for manual conflict selection, preservation of unrelated edits, stale/mixed atomicity, no-selection validation, permissions and idempotent replay; observe RED before each new behavior.
- [ ] Run `backend/.venv/Scripts/python.exe infra/local.py backend -m pytest tests/test_journal_review.py tests/test_journal_updates.py tests/test_journal_application.py -q` on a fresh test DB; expected all pass.
- [ ] Commit only task files and its spec/plan; preserve unrelated outputs.

### Task 2: Source buttons and owner-operated review page

**Files:** create `frontend/src/modules/imports/JournalSyncActions.vue`, `frontend/src/modules/imports/JournalReviewPage.vue`, associated tests and review types/helpers; modify `frontend/src/modules/expertises/ExpertisesPage.vue`, `frontend/src/router.ts`.

**Interfaces:** source creation uses existing Google/file preview APIs with action-derived audit reason; created batch opens `/imports/<id>/review`. Page consumes Task 1 schema; confirmed POST contains only selected row anchors and fields, no arbitrary values.

- [ ] Write real-component tests: direct Google/file actions, permissions, review before write, no default selection, explicit conflicts, choosing only nonconflicting fields, frozen retry and stale responses.
- [ ] Observe RED for missing controls/page; implement minimal components and route.
- [ ] Run frontend `npm test`, `npm run typecheck`, `npm run build`; expected all exit 0 (existing chunk-size warning may remain).
- [ ] Run full backend suite once after backend completion, independently of frontend tests; no concurrent DB pytest.
- [ ] Commit task files, record checks and perform one fresh final review.

### Task 3: Runtime handoff

**Files:** update this plan checkboxes and `docs/verification/journal-sync-review-2026-10-29.md`.

- [ ] Reuse Vite; restart only existing Django process if needed to load changed code. No migrations are planned.
- [ ] Check live preview read-only; verify actual count remains 478 and specialty fields for 470–472 remain unchanged until the owner applies them.
- [ ] Provide direct review link and explain source/file buttons, acceptance and conflict handling. Do not click application on real data.
- [ ] Preserve owner-denied .superpowers cleanup; no push or merge.
