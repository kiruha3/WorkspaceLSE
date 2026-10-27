# Приёмка регистрация и назначение Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Реальная вертикаль поступление с основанием → материал → ручная регистрация → назначение/перепоручение → сохраняемая рабочая карточка, включая комиссию и комплекс по специальностям.

**Architecture:** Продолжить `E:/VLSE/ais-lse` на существующих Django/PostgreSQL/Vue. Команды в предметных services, DTO/HTTP отдельно, текущий policy и независимая qualification_eligibility. Минимальное хранение документа-основания входит в вертикаль; последующие письма/выдача/15.1 не подменяются фиктивными кнопками.

**Tech Stack:** Python 3.13, Django 5.2, DRF, psycopg/PostgreSQL 17; Vue 3/TypeScript/Vite/Pinia/Router.

**Spec:** `docs/specification.md` §§4–6, 8–11; `docs/access-control.md`; уточнение владельца 28.10 о подтверждённой квалификации без даты с обязательным основанием. Предыдущая вертикаль: `docs/superpowers/plans/2026-10-27-identity-personnel.md`, commit `6f14d40`.

## Global Constraints

- Исходные PHP, старый Vue, Excel/Google и старая VM не меняются. Только локальные коммиты, без push.
- Первоначальный отдел выбирается явно; автоматического распределения и автоинкремента номера нет. Делопроизводитель вручную закрепляет номер, начальник назначает эксперта по отдельному праву.
- Минимальное основание — постановление/определение, фото/копия или заявленное наличие бумажного оригинала. Бумажный оригинал не требует выдуманного электронного файла; скан можно добавить позднее.
- Одна комиссия — один номер. Комплекс — по одному номеру на специальность, не на участника. `primary/repeated/additional`, комиссионность и комплекс — независимы.
- `training` и `unknown_legacy` не допускают новых назначений. Подтверждённая квалификация с основанием может иметь неизвестную дату получения; известный срок проверяется. Должность начальника не обходит правило.
- Перепоручение оставляет номер, закрывает прежнее назначение и открывает новое атомарно. Текущий список у получателя, бывший исполнитель — в истории.
- Номер в скобках — исторический, не источник текущей категории. Категории: 1 уголовное, 2 гражданское, 3 арбитражное, 4 КоАП, 5 КУСП, 6 исследование/по заявлению.
- `in_progress/suspended/completed/without_execution` — канонические состояния работы. Отсутствие назначения — отдельный признак, не новое самовольное итоговое состояние.
- Веб — `0.0.0.0:5173`, Django/БД loopback. Один Vite, без лишних постоянных Node/worker процессов.

## Review Focus

- Два параллельных запроса номера или повтор после потерянного ответа: один результат, конфликт с другим payload, без двойного номера/аудита.
- Общий материал отдела 3/4: право видеть одну работу не выдаёт изменение другой или список всех её исполнителей/закрытых документов.
- Квалификация/сотрудник изменены после загрузки вариантов: команда назначения повторно проверяет фактические сведения под блокировкой.
- Перепоручение комиссии: только добавленные участники получают новые назначения, история сохранена, число регистраций не растёт.
- Успех загрузки файла не означает успешную регистрацию; при сбое команды исходные данные/подготовленные файлы не исчезают и UI не заявляет создание экспертизы.

---

### Task 1: Поступление материал и документ-основание

**Files:**
- Create: `backend/apps/intake/{models,serializers,services,api,urls}.py`.
- Create: `backend/apps/documents/{models,serializers,services,api,urls}.py`.
- Modify: `backend/config/{settings,urls}.py`, `backend/apps/accounts/catalog.py`, bootstrap templates only for newly created roles.
- Test: `backend/tests/test_receipts.py`, `backend/tests/test_basis_documents.py`.

**Interfaces:**
- Consumes: `require/can/effective_scope`, `audit`, `VersionConflict`; versioned strict serializers.
- Produces: `Receipt`, `Material`, `Document`, `FileVersion`; stable UUID relationships, FK/unique constraints. `Receipt` has received_at, sender label/organization reference when known, material, basis document, accepted state, version.
- Produces: `create_receipt(*, actor, data) -> Receipt`, `accept_receipt(*, actor, receipt_id, expected_version) -> Receipt`.
- Produces: `POST/GET /receipts/`, `GET /receipts/{id}/`, `POST /receipts/{id}/register/`; `POST /documents/` for paper basis metadata and `POST /documents/{id}/versions/` multipart upload, authorized preview/download.
- Produces: `receipts.view/create/accept/amend` in catalog; don't silently add these to already customized roles.

- [ ] Step 1: Tests `test_paper_basis_accepts_without_fake_file`, `test_missing_basis_does_not_accept`, `test_uploaded_basis_survives_reload`, `test_denied_file_download`, `test_shared_document_not_copied_per_work`. Assert literal document kind `resolution/decision`, source `paper_original/uploaded_copy`; uploaded_copy requires a persisted file version, not a Boolean.
- [ ] Step 2: Run `infra/local.py backend -m pytest tests/test_receipts.py tests/test_basis_documents.py --tb=short`; expect missing routes/models, not a database/setup error.
- [ ] Step 3: Implement models/migrations/services and real media storage under ignored `media/`. Copy and link are distinct; original is not replaced by preview. File version allocation locks Document and has DB uniqueness `(document, number)`. New staged-file cleanup is limited to files owned by that failed operation; never remove an existing document on transaction failure. No conversion worker needed for PDF/image first preview.
- [ ] Step 4: Run migrations and full backend suite on PostgreSQL. Expected: all pass, no pending migrations. Keep paper record source visible without promising PDF preview when none exists.
- [ ] Step 5: Local commit `feat: add receipts materials and persisted basis documents`.

### Task 2: Ручной номер и атомарная регистрация

**Files:**
- Create: `backend/apps/expertises/{models,numbering,serializers,services,api,urls}.py`.
- Create: `backend/apps/accounts/commands.py` for reusable idempotency receipts, with migration model in accounts.
- Test: `backend/tests/test_registration.py`, `backend/tests/test_registration_concurrency.py`.

**Interfaces:**
- Consumes: accepted Receipt/Material/Document from Task 1; current Department/Specialty references and `expertise.register` policy.
- Produces: `parse_current_number(number: str) -> ParsedNumber(sequence, department_code, category_code, year, normalized)`. New manual format `N/D-C-YY`, anchored entire current number; historical_number separate. Validate chosen Department/code, category, specialty and receipt linkage, not appointment organization as category fallback.
- Produces: `register_expertise(*, actor, receipt_id, data, idempotency_key) -> Expertise` and `/receipts/{id}/expertises/` POST, `/expertises/` GET, `/expertises/{id}/` GET, `/expertises/number-hint/` GET.
- Produces: `Expertise` UUID, material/receipt, normalized unique full current number within institution, parsed year/category/department, specialty, `appointment_nature`, commission flag, optional ComplexGroup, canonical state and version. `ComplexGroup` relates material/works; unique group+specialty, planned specialty has no invented number.
- Produces: `execute_once(*,actor,action,key,payload,operation)` stores canonical payload hash and original command result in the same transaction. Same key/different payload → 409; failed operation doesn't leave a successful command record.

- [ ] Step 1: Tests `test_number_151_1_1_26_category_criminal`, `test_parenthesized_historical_number_is_not_current_category`, `test_same_number_concurrent_one_success_one_conflict`, `test_retry_returns_same_registration`, `test_same_key_different_payload_conflicts`, `test_complex_two_specialties_two_numbers_not_per_person`. Assert category 1/5 remains distinct and both can later be state assignment, not all categories alike.
- [ ] Step 2: Run focused tests; expected RED missing registration behavior.
- [ ] Step 3: Implement services under transaction, DB uniqueness, idempotency uniqueness per actor/action/key; handle concurrent uniqueness races as controlled conflicts, not 500. Hint returns last existing number and is explicitly not reservation. Do not reserve/autoassign the next value.
- [ ] Step 4: Verify focused concurrency tests with independent PostgreSQL connections, then full backend suite. Expected one persisted Expertise for duplicate number, one successful business audit, repeated request same identity. Filter before pagination and detail access.
- [ ] Step 5: Local commit `feat: register expertise with explicit numbers and replay protection`.

### Task 3: Назначение комиссия перепоручение и история

**Files:**
- Modify: `backend/apps/expertises/{models,services,serializers,api,urls}.py`.
- Modify: personnel qualification service only if locking support needed; preserve approved eligibility rule.
- Test: `backend/tests/test_expert_assignments.py`, `backend/tests/test_expertise_scopes.py`.

**Interfaces:**
- Consumes: `qualification_eligibility(employee,specialty,at)` and Task 2 Expertise, version/conflict conventions.
- Produces: `ExpertAssignment` with employee, work, start/end, actor/reason and qualification snapshot; stable employee FK, not text list. Historical assignments remain readable.
- Produces: `assign_experts(*,actor,expertise_id,employee_ids,expected_version,reason)`, `reassign_experts(...)`; explicit `/expertises/{id}/assignments/` and `/{id}/reassign/` commands, `/assignment-candidates/` with eligibility reasons.
- Produces: `expertise_scope_queryset(user,action)` and detail `allowed_actions` based on current active assignments and this work's department, not all material siblings.

- [ ] Step 1: Tests `test_training_13_1_does_not_block_qualified_18_1`, `test_head_role_does_not_override_training`, `test_unknown_date_confirmed_basis_allowed`, `test_inactive_or_expired_candidate_rechecked`, `test_commission_one_number_two_qualified_participants`, `test_reassignment_moves_current_list_preserves_history`, `test_institution_view_does_not_expand_department_assign`, `test_shared_material_does_not_expand_other_work_mutation`.
- [ ] Step 2: Focused RED before implementation; assert number/count unchanged by reassignment, old participant absent from current list and present in history. Empty department grant denies.
- [ ] Step 3: Lock work + selected personnel/qualification rows, recheck rights/state/eligibility, create/close assignments atomically with audit and work version. Registration itself does not pick a concrete expert. Department head can be an assigned expert if qualified. Initial commission requires its declared participant set; no silent replacement by a flag or duplicate number per participant.
- [ ] Step 4: Full backend suite + migrations check, including concurrent version conflict and role revocation in an open session. Existing history must remain intact when qualification later changes.
- [ ] Step 5: Local commit `feat: assign and reassign qualified experts with scoped history`.

### Task 4: Vue приёмка регистрация и рабочая карточка

**Files:**
- Create: `frontend/src/modules/intake/{IntakePage,ReceiptPage}.vue` and tests.
- Create: `frontend/src/modules/expertises/{ExpertisesPage,ExpertisePage,AssignmentForm}.vue` and tests.
- Modify: `frontend/src/api/{client,types}.ts`, router/nav/HomePage; lightweight document preview component under `shared/`.
- Test: client multipart and replay behavior, page transitions/forms, real HTTP integration in `backend/tests/test_http_expertise.py`.

**Interfaces:**
- Consumes: Tasks 1–3 endpoints, server `allowed_actions`, field errors and conflicts.
- Produces: `/intake`, `/receipts/:id`, `/expertises`, `/expertises/:id`; filters persist in URL and detail return restores selection/page.

- [ ] Step 1: Tests actual components with transport boundary fixtures: paper original has no invented upload, photo requires successful persistence, manual hint never fills/locks number without action, retry retains same idempotency key, error retains form, commission/complex show distinct numbering and candidate reasons. Multipart client sends FormData without a fabricated JSON Content-Type.
- [ ] Step 2: Run focused RED tests, then implement pages using current green design, full-width detail view and unsaved-form guard. Server confirmation is the only successful registration; failed file/registration combinations remain clearly distinct.
- [ ] Step 3: Full frontend suite/typecheck/build + full backend suite. Real HTTP scenario with separate clerk/head/expert fixture accounts: receipt with paper basis → number → assignment → reload from DB; qualified vs training denial checked through API. No shared automatic role switcher.
- [ ] Step 4: Browser QA in own tab, source data unchanged; verify registration card, current assignee list, documents preview, conflict recovery and department boundaries. Use test/demo identities explicitly labelled, not silently granting roles/qualifications to real staff from the journal.
- [ ] Step 5: Update README/progress, local commit, one independent whole-slice review followed by TDD fixes. The full goal is still active until production/letters/results/issue/import/15.1 and AC01–AC20 are verified.

## После этой вертикали

Следом: приостановки/возобновление/согласованные сроки; версии всех документов, переписка и контроль; результат и комплекты выдачи; импорт реального журнала с предпросмотром и сверкой; Python 15.1 разделов 1–6 со снимком и расшифровкой; проверка всех рабочих мест и восстановления. Не потерять отложенное основание изменения прав роли и оставшиеся account/audit-команды из общего ТЗ.
