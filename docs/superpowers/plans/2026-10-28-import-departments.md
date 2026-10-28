# Import Department Separation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox syntax.

**Goal:** Перенести реальный журнал с фактическими отделами1/3/4, прежними номерами и связями экспертиз с сотрудниками.

**Architecture:** DepartmentFK работы сохраняет фактический отдел номера, EmployeeOrgAssignment — нынешний отдел человека. Read-only свойство разбирает код регистрации. Импорт использует существующие валидируемые команды; Vue показывает фактический отдел и сохранённое сопоставление.

**Tech Stack:** Существующие Django/DRF, Vue3/TypeScript/Vitest; без зависимостей и миграций.

**Spec:** `docs/superpowers/specs/2026-10-28-import-departments-design.md`

## Global Constraints

- Не менять номера, raw-строки, Google и PHP; текущая implementation, без push/нового worktree.
- DepartmentFK — фактический отдел экспертизы; код номера read-only, отдел1 остаётся1.
- Автоматическое распределение258старых строк по специальностям ОТКЛОНЕНО владельцем, не выполнять.
- Нативную проверку совпадения отдела/номера и сопоставление специальностиM не ослаблять.

## Review Focus

- Старый отдел1 сохраняется даже у сотрудника нынешнего4; неактивный исторический справочник разрешён для истории.
- Собственная историческая работа доступна связанному человеку независимо от его нынешнего отдела, без выдуманного назначения/допуска.
- При сохранении сопоставления строка сразу показывает фактический отдел; читателю не нужен кадровый optionsendpoint.
- Попытка подменить1на3/4 отклоняется и в редакторе, и на сервере.
- Пустая/неверная M не подменяется другой специальностью, исходная строка неизменна.

### Task 1: Transfer factual work departments and explicit employee links

**Files:** backend/apps/imports/reconciliation.py, backend/apps/expertises/{models,serializers,history}.py; frontend/src/api/{types,imports}.ts; modules/imports/{SelectionEditor,ReconciliationPage,ImportRowDetails}.vue; modules/expertises/ExpertisePage.vue; tests below.

**Interfaces:** `Expertise.registration_department_code: str|None`; reconciliation row adds nullable `mapped_department` reference; existing `department`/`department_id` remain factual work departments.

- [x] Write backend RED tests in tests/test_import_departments.py: factual1 with employee4, preservednumber/raw, source1→4rejected, APIcode1, own historical work accessible, no new assignment; factualdepartment filtering.
- [x] Retain original equality/wrong-specialty400 assertions in test_journal_application.py. Run focused RED for attempted false redistribution.
- [x] Implement readonly property/output and mappeddepartment display, preserve numbering/equality validation.
- [x] Write Vue RED tests for oldcode1/reference1/noalternative4 and displayed saved1; implement labels/types and save-state update. Run focused GREEN.
- [x] Run full backend pytest once, frontend tests/typecheck/build, Django check/no migration drift, diffcheck. Expected allpass.
- [x] Prepare one-off exact source/employee mappings, dryrun counts, obtain backup, apply through existing commands and independently verify472actual work records. No specialty-based department mapping. Verify real UI/employee links; restart only owned services.
- [x] Fresh final review of e182edd..current slice, one importantfixpass if needed. Commit locally/no push; record evidence and next real-import step.

Evidence: `docs/verification/real-journal-transfer-2026-10-28.md`. Final backend532/532, frontend224/224; production build and Django checks green. Transfer472/472, repeat verified without duplicates. Next scope is DB-backed reporting/export, not another transfer of these source rows.
