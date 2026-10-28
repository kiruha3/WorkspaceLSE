# Historical Report Correction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline. Steps use checkbox syntax.

**Goal:** Уточнять старые закрытые работы в карточке с аудитом, одинаковыми фактами для календаря/15.1 и без фиктивных событий производства.
**Architecture:** current typed HistoricalWork + append-only HistoricalCorrection and current HistoricalUnresolvedAllocation; existing result validation/scopes/command idempotency. Registry oneSELECT gains historical reasons/allocations. Vue separate focused editor.
**Tech Stack:** existing Django/PostgreSQL/Vue3/TypeScript/Vitest; additive migration only.
**Spec:** docs/superpowers/specs/2026-10-28-historical-report-correction-design.md

## Global Constraints

Номер/состояние/отдел/люди/поступление/issued_on/raw/facts неизменны. Google только чтение, PHP не меняется. Без новых прав/аккаунтов/live grants/пакетов/push/merge/worktree. implementation. Additive migration послеbackup; максимум2syntheticdemo,реальные472не меняются.

## Review Focus

- Новая причина без изменения старых scalar-полей всё равно блокирует будущую синхронизацию источника.
- Невыданные исторические сведения отличаются от нативного комплекта; даже черновик блокирует ретроспективную правку.
- Own работает только для подтверждённого исторического участника и не расширяет нативные назначения/корректировки.
- Возврат не превращается в СНДЗ, пустые даты/числа/специальность не становятся выдуманными; потерянный ответ сохраняет исходный ключ.
- Смена роли/версии/карточки во время редактирования не создаёт дублей и не отправляет старый пакет по новому id; конкурентный источник/активация сериализуются material-lock.

### Task 1: Historical correction vertical slice

**Files:** backend/apps/expertises/models.py +migrations/0008_historical_report_corrections.py; new historical_reports.py,historical_report_api.py,historical_report_serializers.py; api.py/serializers.py/history.py/urls.py; imports/updates.py; reports/registry.py. Tests/test_historical_report_correction.py, test_historical_report_concurrency.py, existing report/import tests. Frontend api/types.ts, new modules/expertises/HistoryReportEditor.vue,HistoryReportEditor.test.ts,HistoryReportDetails.vue; ExpertisePage.vue, HistoricalFacts.vue; reports heading/tests. docs/verification/historical-report-correction-2026-10-28.md.

**Interfaces:** POST /expertises/id/history-report/ as spec; GET same path options (result catalogue+specialties). HistoricalWork output gains report_details and corrections[{id,number,actor,created_at,reason,before,after}]; allowed_actions adds existing expertise.closed.correct only when eligible. Service correct_historical_report(actor,expertise_id,data,key,payload)->{id,expertise_id}. can_correct_historical_report(user,work,scopes=None)->bool. Before/after contain human-readable reference snapshots, typed scalar values, source row id. Registry uses historical typed reasons if no accepted native closure. Imports update_preview blocks corrections.exists().

- [x] Backend RED API/result/return, unknown counts, report/date/calendar literal deltas, immutable source/identity/people, oneSQL, own/department/institution/revoke, strict payload/balance/category/date/reference/document scope, stale version/replay and rollback, native/package blocker, source-update blocker; expected404 or missing models/fields. Run `backend/.venv/Scripts/python.exe infra/local.py backend -m pytest tests/test_historical_report_correction.py -q`.
- [x] Implement models/additive migration and service/strict serializers/API/context/output/registry/import guard. Same tests +test_form151_reasons.py +test_journal_updates.py →green. Add concurrency test material wait/source winner stale409 →green. No simultaneous DB pytest.
- [x] Vue RED both forms/current facts/history, explicit null/zero, authoritative action, payload/idempotency, frozen uncertain edits/retry,409 accept version,403 draft, late route response, full cause. Implement focused components; profile tests then full frontend/build →green.
- [x] Fullbackend/frontend/check/migration/diff; one fresh whole-slice review and one Important fix pass RED→GREEN/full suites if needed. No unresolved Important.
- [ ] Backup/pre-migration old-field hashes, migrate and verify only new unknown defaults/empty tables, unchanged real/source/roles/native. Seed2 syntheticdemo under already authorized demo.expert2, no rights changes. Browser allowed/denied roles, result+return corrections/history/reload, report/download and804cell QA. Real472 metrics403/4/8/388 unchanged. Localcommit/task-done (same backend command +concurrency +reportreasons+journalupdates); next remaining workflow gaps, full goal active.
