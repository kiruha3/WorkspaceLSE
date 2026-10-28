# Cross-role acceptance implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline. Steps use checkbox syntax.

**Goal:** Воспроизводимый непрерывный HTTP-путь и настоящая проверка рабочих мест в изолированной БД, без рабочих записей/второго Vite.
**Architecture:** Existing Django API + compiled Vue served by a test-only WSGI wrapper; fresh named PostgreSQL and separate media. Shared identity fixtures, not prepared business entities.
**Tech Stack:** Existing Python/Django/PostgreSQL/Vue, standard-library WSGI/urllib; no dependencies.
**Spec:** docs/superpowers/specs/2026-10-28-cross-role-acceptance-design.md

## Global Constraints

Keep implementation checkout/outputs/.superpowers. NoPHP/Googlewrites/push/merge/newworktree/livegrants/livebusinesswrites/schema migrations. Fresh `ais_lse_acceptance_*` only, no overwrite/reset/delete. Separate media. Only127.0.0.1:8001 temporaryserver; no secondVite/Node; stop own server after QA, preserve DB/files. OneDBpytest, fresh seeded DB/no reuse-db. Live67tables/13files/472real8demo/996cells+records+plan unchanged. Unknown issuance policies/Office/sources/relations/production/officialreport remain overall goal, no guessed policies.

## Review Focus

- Runtime path/config/name substitutions never reach ais_lse or real media; existing state/database is refused rather than overwritten.
- SPA fallback never masks API/assets404 or serves paths outside the exact dist root; no stale/unbuilt frontend claimed tested.
- Every business step really traverses authenticated HTTP/public API, no ORM shortcut for work/result/check/issuance and no self-derived expected report totals.
- All browser claims distinguish UI actions from pre-arranged HTTP facts; scopes/role combos and missing-policy blockers remain visible, no blanket all-role claim from one session.
- Cleanup stops only the confirmed created server; fake records are only in the named isolated DB, and live hashes/report remain equal after tests/QA.

### Task 1: Isolated acceptance runtime and identity fixtures

**Files:** infra/acceptance.py; infra/acceptance_static.py; backend/tests/test_acceptance_runtime.py; backend/tests/full_workflow_support.py.
**Interfaces:** `checked_database_name(value:str)->str` requires ais_lse_acceptance_ prefix and safe identifier; `runtime_env(config:dict,state:dict)->dict` selects isolated name/loopback/csrf/noGoogle; CLI `prepare` writes fresh `.runtime/cross-role-acceptance/state.json` and `serve` reads it; `spa_application(api,root:Path)->WSGI` delegates API, confines assets, supplies index. `create_people(password:str)->dict` creates explicit test personas/departments/specialties/catalogs only, returns IDs/usernames; used both CLI and Task2. State records database/media/people/password, never stdout. Existing state refusal.

- [x] Write unit RED tests: invalid/liveDB name rejected before connection, runtimeenv keeps input config unchanged/no journal source, API404 not index, deep SPA200, asset200 MIME, missingasset404, encoded/traversal outside-root never disclosed, missingindex expliciterror, existingstate not overwritten. Run `infra/local.py backend -m pytest tests/test_acceptance_runtime.py -o addopts= -q`; expected missingmodule/entrypoint. Implement minimal wrapper/guard/CLI/fixture identities. GREEN same tests; CLI prepare/serve with state guarded and no secrets. Commit; task-done same test command.

### Task 2: Continuous HTTP scenario and browser acceptance

**Files:** backend/tests/test_http_full_workflow.py; backend/tests/full_workflow_support.py; docs/verification/cross-role-acceptance-2026-10-28.md; README.md; observed product/UI defects only after specific RED.
**Interfaces:** consumes Task1 create_people/state and same app APIs. `WorkflowSession(base,username,password)` uses independent cookiejar/CSRF; `.request(path,method='GET',body=None,key=None,files=None)->(status,body)` supports JSON/multipart/raw XLSX. `run_journey(base,people,password)->dict` returns work/package/letter IDs and independent expected cell checks, never creates business facts by ORM. RealHTTP fixture live_server and real isolated server consume same helper.

- [x] Add fresh transaction HTTP tests: full path spec with literal Q4/R2/S1/T1, category1 paidinvoice blocker, public creation/upload/result/completion/check/issue/replay, separate role denials, currentassignee transfer and head-own actions; is_demo exclusion. Initial pass allowed for existing behavior, record honestly. Any unexpected fail: investigate and individual RED→GREEN product fix, not weaken assertions. Run serial `infra/local.py backend -m pytest tests/test_http_full_workflow.py tests/test_acceptance_runtime.py -o addopts= -q`, expected allgreen. Build realfrontend; prepare isolated environment, launch one confirmed temporaryserver, run journey there, inspect actual Vue with each role and selected full-path UI commands/screenshots. Record actual UI/HTTP distinction and limits. Stop only own server; preserve artifacts and verify livecheckpoint. Commit/task-done same focused command.

## Final gate

- [ ] Fresh whole-range reviewer/spec/ledger/ReviewFocus, regrade, one Important RED→GREEN fix pass, defer minors. Fullbackend once/freshDB +frontend/typecheck/build/check/drift/diff. Original live data unchanged, isolatedserver stopped, docs/claims/rulings accurate. Keep branch/no push; overall goal active.
