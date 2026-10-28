# Delay Count Option Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Select all/primary delay-reason counting consistently in the live report and Excel.
**Architecture:** Optional validated request parameter threads through the existing pure calculator, explanations and existing fingerprint. Vue stores a draft option separately from the returned report.
**Tech Stack:** Existing Django/DRF/PostgreSQL, Vue3/TypeScript, pytest/Vitest; no new dependencies.
**Spec:** docs/superpowers/specs/2026-10-28-delay-count-option-design.md

## Global Constraints

- Default `all`, alternative `primary`; registry only. Preserve journal, all other facts/cells/provenance and permissions.
- No database migrations or live fact changes. No push/new worktree; preserve unrelated plan drafts and outputs.
- Unknown is not zero; failed/stale responses are not downloads. One DB pytest at a time.

## Review Focus

Explicit journal parameter, duplicate/blank/unknown policy, missing primary, policy-bearing export URL and late response after switch all have tests in task1. Reviewer additionally checks default consistency between API/UI/calculator and no accidental raw journal policy advertisement.

### Task 1: Selected policy through report and download

**Files:** backend/apps/reports/{api,calculation,registry,column_rules}.py; frontend/src/modules/reports/{ReportsPage.vue,reports.test.ts}; backend/tests/test_form151_timing.py.
**Interfaces:** calculate/calculate_registry gain optional `delay_reason_policy`; explanations(mode,*,delay_reason_policy=None) takes the effective policy. Public API accepts only `all|primary`, defaultall; report response retains `delay_reason_policy`. No change to timing facts API default policy.

- [x] Write API regression with accepted >30-day conclusion, reasons complexity+workload and primary complexity. Assert all G107=1/I107=1, primary G107=1/I107=0, different fingerprints, no other cell/provenance changes, no extra SELECT, matching explanations, XLSX I107=0, old-revision/mode mismatch409. Missing primary has unknown G/I. Invalid choices/duplicates/journal400.
- [x] Write Vue regression for defaultall, primary query parameter, server result label, invalidation/late-response suppression on option change, journal hides and omits parameter. Run tests, observe expected RED.
- [x] Implement narrow parameter threading, rulesv3 and registryv7, frontend selector/help/result label/watch. No changes to data storage.
- [x] Run targeted backend timing/API/rules/registry tests and reports Vue tests: expect all pass.
- [x] Commit only this slice, excluding unfinished annual-plan drafts.
- [x] Fresh final review of BASE..HEAD, fix Important/Critical in one TDD pass, defer Minor.
- [x] Run full backend and frontend suites, typecheck/build, Django check/migration drift, diff check. Expect green; existing large bundle warning documented.
- [x] Restart existing Django only (no extra process), browser verify both options and actual Excel URL/download, capture screenshot. No live data edits.
- [x] task-done with targeted backend command, verification record and final handoff. Retain ignored workspace because deletion previously denied; do not retry.
