# State assignment plans implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline. Steps use checkbox syntax.

**Goal:** Версионированные годовые планы по специальностям для обоих источников15.1.
**Architecture:** Three models in installed reports app, strict annual command, one coherent work+plan SELECT, pure injected projection, Vue editor with existing recovery helpers.
**Tech Stack:** Existing Django/PostgreSQL/Vue3/TypeScript/Vitest, no dependencies/services.
**Spec:** docs/superpowers/specs/2026-10-28-state-assignment-plans-design.md

## Global Constraints

Owner autonomous inline/in-place, no push/merge/worktree. Google read-only/PHP untouched. Preserve472real/8demo works, all old facts/source/access/documents/files. No new grants. Only live new plan2026total294+one systemrevision via migration; no invented specialty allocation or other year plan. New snapshot/dump before schema migration. Prior denied scratch deletion not retried. Existing deferred minors untouched. Preserve delay_reason_policy all|primary/defaultall and export parameter; registryv8/rulesv4/journalv2.

## Review Focus

- Empty registry must still receive a plan in the same oneSELECT; JSON transport must preserve dates/UUID/accepted-result precedence and stable order.
- Missing, explicitzero, partial sum and unmapped positive/null rows cannot produce invented zeros or multiply parent rows.
- New annual concurrent creation, stale edits and replay after rights/doc revocation must leave one profile/revision and no orphan blank year.
- Year switch and nested-document conflicts must preserve draft/path/key without applying late old-year replies or recreating files.
- Journal source is immutable but plan is not: preview/download must detect plan/rules changes rather than silently serving different figures.

### Task 1: Annual plan to report pipeline

**Files:** new backend/apps/reports/models.py,migrations/0001_initial.py,plans.py,plan_serializers.py,plan_api.py,plan_snapshot.py; modify config/settings.py,config/urls.py,accounts/catalog.py,reports/api.py/calculation.py/registry.py/column_rules.py; new tests/test_report_plans.py,test_report_plan_concurrency.py,test_form151_plans.py; existing tests/test_form151*.py/historical tests for intentional injected plan contract; frontend api/types.ts, new modules/reports/ReportPlansPage.vue+test, ReportsPage.vue/reports.test.ts,router.ts,shared/AppSidebar.vue(or actual navigation file),HomePage.vue; docs/verification/state-assignment-plans-2026-10-28.md.

**Interfaces:** save_plan(actor,year,data,key,payload)->receipt; plan_output(plan|None,user,year)->DTO with choices/version0 for unknown; plan_query(year)->values(payload) QuerySet, read_plan_snapshot(year)->dict|None; coherent_snapshot(work_queryset,fields,year)->(list[dict],plan|None), oneSQL; plan_cells(snapshot)->physical row→count|None + gaps; calculate(...,plan_snapshot=None), calculate_registry(...)->plan_summary+data_revision. New reports.plans.manage institution. Pure calculate has no DB access/default294. Both API modes include expected_revision in new download URL, journal source type preserved.

- [ ] RED tests/test_report_plans: unknown GET createsnothing; seed2026=294/no lines/systemactorNone; expected0create2027 then versioned edit, history/audit/basis, nullablecount vs0; duplicate/1001rows/negative/fractional/out-of-range/year/bodyextra/knownsum>total/basis absent/copy withoutfile fail atomically; active+retained refs; current scope/replay/doc revocation; saved document link remains restricted without document rights. Run `pytest tests/test_report_plans.py -o addopts= -q`, expected missing route/model failures.
- [ ] Implement models/migration/permission/strict command/options+outputs. Add samekey/differentkey/expected0create concurrency; one row/revision and stale409, no orphan. Implement coherent snapshots/pure plan projection and API fingerprints. RED handfixture2027total10+2/3/5 -> D10=2,D57=8,D58=3,D59=5,D107=10, missing16.2 -> parentNone, zero/unmapped/empty registry/accepted priority/oneSELECT; journal without injected plan unknown, injected prior294 retains660; real HTTP downloads both modes stale409 afterplanedit and literalD cells. Run new three testfiles, expected initial failures then green. Existing registry facts/provenance unaffected; update only intentional pure-plan assumptions.
- [ ] RED Vue ReportPlansPage: institutionreadonly/unknown0/default2026/lines/balance/fullpayload, stable newyear/path/body/lostreply, refreshedversion409withoutlosingdraft,403, actualFileupload+doc409reconcile, dirty and late year-route; reportplan source/link/rules/removedhardcode. Implement reuse shared helpers, explicit new permission only; run all frontend tests/typecheck/build, expected green.
- [ ] Commit verified snapshot; one fresh final review on this range with spec/ledger, Important one RED→GREEN fix pass, no rereview/minor fixes. Full backend serial +fullfrontend/check/drift/diff. Tests all named above must exist/run and expected outputs inspected.
- [ ] Backup/checkpoint then additive reports0001 live seedonly; all prior tables/files/grants/corefacts equal. Actualbrowser planread/roledenied/newactionvisible without grant; journal+registry planmetadata consistent, actualnewdownload, oldURLs409, all996oldcells+provenance equal, ArtifactTool996/9sheets/0errors andsection6render. Document limitations/remaining role grant acceptance; commit/task-done focusedthreefiles+oldregistry/columnrules/history, closeplan. Keep full goal active.
