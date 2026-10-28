# Construction flag implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline. Steps use checkbox syntax.

**Goal:** Флаг «Самовольное строение» при регистрации/редактировании16.1/16.2, необязательные доказательства, корректная графа3214-р.
**Architecture:** Reuse WorkCaseDetails.decree3214, existing registration/case command locks and revisions; only a relaxed check constraint, no new fact column.
**Tech Stack:** Existing Django/PostgreSQL/Vue/pytest/Vitest, no dependencies.
**Spec:** docs/superpowers/specs/2026-10-28-construction-flag-design.md

## Global Constraints

Existing implementation checkout/no push/merge/newworktree; preserve outputs/.superpowers. No PHP/Google writes/invented real facts. One DBpytest/fresh DB/no reuse-db. User explicitly approved only reports.plans.manage for setup: already granted via dedicated role/API, plan294 unchanged. No other grants. Backup before one constraint-only migration, preserve current rows. Pending issuance tests remain pending, not falsely counted passed.

## Review Focus

- A lost registration or case-save response cannot duplicate the flag revision or silently change the captured flag.
- Switching16.1→another specialty must not send a stale true; old registration clients omitting the field still work.
- Existing optional evidence and inaccessible documents remain protected; existing legacytrue on another specialty is not counted or silently deleted.
- Report period/result gates remain unchanged; nullable unmarked construction is not interpreted as a new mandatory questionnaire.
- Live schema rollout changes no business rows/grants/files and restarts only the existing Django, not another Node/Vite.

### Task 1: Registration, editing and report

**Files:** backend/apps/expertises/{services,serializers,case_details,case_serializers,models}.py; migrations/0012*; backend/apps/reports/{calculation,column_rules}.py; tests/test_construction_flag.py and superseded case expectations; frontend/src/modules/intake/ReceiptPage.vue; modules/expertises/CaseDetailsPanel.vue; corresponding SFC tests and references/catalogs.ts.
**Interfaces:** registration optionaldecree3214 bool, existing case-details bool|null/document/basis unchanged; reportP counts eligibleflagtrue only. No new route/role/duplicatefield.

- [ ] Write API/SFC/calculation RED: true/false/omission/retry registration; flagwithoutfile saves/toggles/history; foreignspecialty reject atomically; otherlegacytrue notcounted; reportP literal1for16.1/16.2true and0forfalse/null/others. Run backend `-m pytest tests/test_construction_flag.py -o addopts= -q` and frontend `npm.cmd test -- --run src/modules/intake/ReceiptPage.test.ts src/modules/expertises/CaseDetailsPanel.test.ts`; expected missing input/checkbox and oldmandatory evidence failures.
- [ ] Minimal implementation and generated constraint migration; update only superseded oldpolicy assertions, preserve evidence validation/retry/rights. Same focusedtests plus test_case_details/test_registration/report tests green. Commit/task-done focusedbackendcommand. Fullfrontend/typecheck/build and fullbackend must run before final claim.

### Task 2: Verification and local rollout

**Files:** docs/verification/construction-flag-2026-10-28.md; runtime-only backup/checkpoint/QA; docs/API wording.
**Interfaces:** consumes Task1schema/DTO/UI, existing local/acceptance runtime. Real records read-only, fakepositive only isolatedDB.

- [ ] One fresh whole-range review/spec/ledger/ReviewFocus, regrade/fixImportant RED→GREEN inonepass/no rereview. Fullsuite outputs read; preserve deferredminors. Backup+constraintmigration+alloldrow/filecomparison, restartown8000only; realbrowser flag visible/register/edit oneligible example and hiddenelsewhere, optional docs, planeditverified separatelywithoutchanging294. Docs/claims exact, keepbranch/no push; overallgoalactive.

## Self-review

Flagregistration/edit/report+compatibility ownedTask1; backup/runtime/browser/reviewer ownedTask2. Same canonicalbool/route signatures, no two competingflags. Scope does not claim the partial-value-reporting improvement or approvedissuepacks implemented.
