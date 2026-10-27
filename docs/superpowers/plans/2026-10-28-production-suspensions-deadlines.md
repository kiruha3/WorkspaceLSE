# Производство приостановки и сроки Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Реальная работа эксперта с приостановками/возобновлением и документированными сроками, наглядным календарным счётчиком и историей в существующем Vue.

**Architecture:** Модуль `expertises/production.py` с предметными командами и отдельной чистой арифметикой; те же policy/audit/expected_version/execute_once. Независимый frontend исполняется параллельно по точным DTO, backend — inline; одно независимое ревью всей вертикали в конце.

**Tech Stack:** существующие Python 3.13/Django 5.2/DRF/PostgreSQL 17; Vue/TS/Vite/Pinia. Без новых зависимостей/worker/VM.

**Spec:** `docs/superpowers/specs/2026-10-28-production-design.md`, `docs/specification.md` §5.3/8, `docs/access-control.md`. Предыдущий завершённый срез `5455b8f`; подтверждение: `docs/verification-intake-registration.md`.

## Global Constraints

- Ветка implementation в самостоятельном ais-lse; исходные PHP, web-vue, журнал/Google и старую VM не менять. Без push/merge.
- Действия по текущим правам и отдельной работе. Нельзя приостановить соседний номер общего материала только из-за общей связи.
- Канонические in_progress/suspended/completed/without_execution; не вводить новые состояния вместо результата.
- Все фактические даты в Asia/Krasnoyarsk; unknown не равен нулю. Календарный счётчик не является юридическим/рабочим сроком.
- Короткие команды синхронны, один Vite 0.0.0.0:5173. Django/PG loopback; DB suites только последовательно, дождаться terminal handle перед новым pytest.
- Не расширять реальные роли/квалификации автоматически; demo.* — явно учебные профили. Старые данные и файлы сохраняются.

## Review Focus

- Повтор suspend после последующего resume должен вернуть прежнее событие и свежую карточку, не перевести состояние обратно.
- Два разных concurrent ключа с одинаковой версией дают один успех/409, а не два интервала; конфликт дат не оставляет аудит/команду успеха.
- Поздно внесённое старое согласование не вытесняет более позднее фактическое; запрос не становится согласованием.
- Чтение общей карточки не раскрывает документ срока после отзыва documents.view и не открывает соседнюю работу.
- 409/сетевой сбой и явное обновление карточки не сбрасывают идентичную пару попытка/ключ и не стирают введённую причину/подготовленный документ.

---

### Task 1: Интервалы производства и календарный счётчик

**Files:**
- Create `backend/apps/expertises/{production,production_api,production_serializers}.py`.
- Modify `models.py`, `serializers.py`, `api.py`, `urls.py` в expertises; migration.
- Test `backend/tests/test_production.py`, `test_production_concurrency.py`.

**Interfaces:**
- Consumes `require_work`, expected_version/check_version, execute_once, audit, current work/receipt/assignments.
- Produces Suspension(id,expertise,suspended_on,resumed_on?,reason,resume_reason,actor,resumed_by?,created_at,resumed_recorded_at?), unique open interval, ordered dates.
- Produces `suspend_work(*,actor,expertise_id,data,key,payload)` / `resume_work(...)` -> `{id,expertise_id}` receipt; pure `calculate_days(received_at,intervals,as_of)` -> `{calendar_days,paused_days,active_calendar_days}`.
- POST suspend/resume -> `{event:{id},expertise:ExpertiseDTO}`. POST body in design. Own authority uses active assignee only; replay rechecks action. Detail/list add `production:{as_of,method:'calendar_inclusive_pause_half_open_v1',calendar_days:number|null,paused_days:number|null,active_calendar_days:number|null,initial_due_on:null,agreed_due_on:null,current_due_on:null,last_requested_due_on:null,overdue_calendar_days:null}` and `suspensions:[]` / `deadline_events:[]` until Task2.
- Suspension DTO `{id,suspended_on,resumed_on:null|string,reason,resume_reason,created_at,resumed_recorded_at:null|string,actor:{id,full_name},resumed_by:null|{id,full_name}}`.
- `allowed_actions` appends expertise.suspend for in_progress, resume for suspended, deadline.record once Task2 implemented. Registry validates `state`, `calendar_days_min/max` nonnegative max365000; filters before pagination, includes boundaries, reversed range400.

- [ ] Step 1: Tests state transitions/version/audit and same-key replay after later resume; own/department/institution actions remain independent; sibling unaffected; invalid early/future/backward dates don't persist command result. `calculate_days(2026-10-01,[(03,06),(08,None)],2026-10-10)` = calendar10/paused6/active4; same-day closed pause0; no intervals10/0/10. Closed-without-ending unknown counts. Registry state/calendar range matches count/detail and reversed400. Concurrent connections same-version one success/409.
- [ ] Step 2: Run focused tests, expected missing API/model RED, not environment failure.
- [ ] Step 3: Implement lock-first validation/DB interval constraints and idempotency; replays don't mutate work. Prefetch intervals for lists; date filtering stays PostgreSQL-scoped before pagination. Keep current allowed-actions tests valid for profiles lacking new rights.
- [ ] Step 4: Full backend suite, migration/check clean; expected all passing.
- [ ] Step 5: Commit `feat: track production suspensions and calendar history`.

### Task 2: Исходный запрошенный и согласованный сроки

**Files:**
- Modify expertises models/production/serializers/api and documents models/serializers/policies, intake/services; migrations.
- Test `backend/tests/test_deadline_events.py` and `test_http_production.py`.

**Interfaces:**
- Consumes Task1 command conventions and fresh work DTO.
- Produces DeadlineEvent id/work/kind(initial|request|agreement)/recorded_on/due_on/reason/document?/actor/created_at, immutable append history.
- `record_deadline(*,actor,expertise_id,data,key,payload)` returns stable event ID. POST `/expertises/{id}/deadline-events/` -> same command wrapper. `allowed_actions` can include expertise.deadline.record in open states, only when granted.
- Deadline DTO `{id,kind,recorded_on,due_on,reason,created_at,actor:{id,full_name},document:DocumentLink}`; production initial/agreed/current/last_requested_due_on and overdue_calendar_days computed from latest factual-date event, tie created_at/id. Request never affects current. Original initial may stay null.
- Extend Document.kind with deadline_agreement/deadline_request; original basis accepts resolution/decision only. Agreement accepts deadline_agreement or resolution/decision, paper_original or persisted uploaded_copy; request doc optional but readable/persisted when linked. Shared document read through allowed deadline link, never write authority or unrelated links.

- [ ] Step 1: RED tests initial/request/agreement independent; unknown initial remains null; agreement required actual document, request kind rejected as proof; all dates bounded as design, due_on future allowed; older fact doesn't override; paper no invented file; pending copy invalid; unrelated doc403, own expert can read clerk-linked agreement only with documents.view; revoked rights redacts and denies download; metadata document cannot replace receipt basis. HTTP separate clerk/expert sessions suspend→request→agreement→resume and reload true data.
- [ ] Step 2: Run focused RED; implement append-only records transactionally, lock evidence/document and work, context policy; requests do not close correspondence/control.
- [ ] Step 3: Full backend suite and migrations check, expected green. Keep all receipt/number/upload replay regressions.
- [ ] Step 4: Commit `feat: record requested and agreed expertise deadlines`.

### Task 3: Рабочий блок производства Vue и проверка разных ролей

**Files:**
- Create `frontend/src/modules/expertises/{ProductionPanel,ProductionPanel.test}.vue/ts` (test extension .test.ts), shared document form generalized only if needed.
- Modify ExpertisePage, ExpertisesPage, api/types, test fixtures, shared document preview labels and related tests; preserve existing UI and guards.
- Update README and tracked verification record; add focused HTTP verification to Task2 file.

**Interfaces:**
- Consumes Task1/2 DTOs and APIs; `newCommandKey()` supports ordinary HTTP IP origins.
- Produce actual forms gated by allowed_actions; server confirmation only, `updated` event passes new ExpertiseDTO and cancels stale card requests without resetting active drafts. No fictional completion/issue button.
- Agreement document uses actual paper metadata or staged upload with stable identity; preserve document/file/reason on 403/409/lost response. Explicit reload of identical data retains key; changed payload changes key. Include state/calendar filters in URL and return link.

- [ ] Step 1: Component RED tests for rights, pause/resume, request versus effective deadline, required evidence upload and persisted preview, retained drafts on conflicts, stable replay through unchanged reload and payload-edits reset, race with old GET after successful mutation; filters restored. Existing full frontend suite remains green.
- [ ] Step 2: Implement consistent green full-width card panel/history, method/as_of shown; generic document creation must not relabel agreement as original постановление. No hard-coded role switcher or direct date mutations.
- [ ] Step 3: Full frontend tests/typecheck/build and full serialized backend suite. Browser own demo expert2 card pause→request/agreement→resume; head without expert authority no self-service bypass, clerk allowed by institution grant. Demo files labelled not real court data.
- [ ] Step 4: Commit `feat: connect production history and deadline forms in Vue`, one fresh whole-slice review, one TDD fix pass for Important/Critical, preserve minor/rulings in tracked verification record. Keep branch and servers; no push. Entire goal remains active.

## Further required goal work

Results/SNDZ/Q-R-S-T and completion; general documents/correspondence/control; materials and full issue packages; import real workbook/Google with preview and reconciliation; report15.1 sections1–6 from reproducible facts and official template; role-wide E2E/restore/deployment and pending account/audit/catalog expansion. This plan is a further vertical, not a substitute for that end state.
