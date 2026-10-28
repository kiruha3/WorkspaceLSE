# Historical Journal Updates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox syntax.

**Goal:** Новый снимок исправляет исторические рабочие записи с явным diff, без дублей и потери собственных изменений АИС.
**Architecture:** updates.py строит базу из прежнего ImportSelection/source_facts (as_of первоначального применения) либо before/after последнего ImportApplication; сравнивает её с live. Атомарная команда обновляет только неоперационные исторические поля и новый provenance. Обновления используют отдельный endpoint и UI-компонент, общий протокол ImportApplication.
**Tech Stack:** существующие Django/DRF/PostgreSQL, Vue3/TS/Vitest; без пакетов/миграций.
**Spec:** docs/superpowers/specs/2026-10-28-history-updates-design.md

## Global Constraints

Google только чтение, PHP/документы/ручные изменения/операционный учёт сохраняются. Номер и исторический отдел неизменны; людей не выводить из специальности. Без новых прав/аккаунтов/пакетов/схемы/push/merge/worktree; implementation. Не закрывать468 по предположению.

## Review Focus

- Историческая дата выдачи не равна нативному MaterialIssue; первое — исправление метаданных с аудитом, второе блокирует.
- Поздний черновик/письмо/назначение не исчезает из-за нового снимка; оперативное продолжение блокирует обновление, read-only diff честно объясняет.
- Первоначально будущая дата остаётся неизвестной в базе сравнения и после наступления дня; вычислять baseline на дату первоначального применения, не сегодняшнюю.
- Конкурентное изменение хотя бы одной строки/выбора/источника откатывает весь пакет; общий порядок material→receipt→work→source предотвращает цикл с активацией/выдачей/сопоставлением.
- После потерянного ответа и при смене маршрута нельзя переслать старый пакет в другой снимок или подтвердить новым ключом повторно.

### Task 1: Исторические обновления через сайт и рабочая сверка

**Files:** создать backend/apps/imports/updates.py, update_api.py, tests/test_journal_updates.py; изменить application.py source_facts(as_of), application_data updated_count, reconciliation_api.py preview, urls.py и save_selection freeze уже обеспечен application_item. Frontend api/imports.ts, modules/imports/HistoryUpdates.vue, ReconciliationPage.vue, SelectionEditor.vue, ApplicationResult.vue; tests/historyUpdates.test.ts, reconciliation.test.ts. docs/verification/history-updates-2026-10-28.md.

**Interfaces:** update_preview(row,work)->{eligible,blockers,changes,expected_work_version,expected_source_row_id,previous_selection}; POST /imports/<batch>/updates/ {reason,updates:[{row_id,expected_selection_version,expected_work_version,expected_source_row_id}]} -> {event,application}. Application updated_count and items action updated with before/after/previous_source_row_id. Source_facts(row,*,as_of=None) defaults localdate.

- [x] Backend RED: changed complexity/specialty/completion/people/unknowns; source/number preservation and exact report delta; older source/manual drift/operative/MaterialIssue blocked; historical issued metadata allowed; atomic packet/version/source/choice races; replay/revocation/strict params/read-only preview. Expected missing endpoint/preview before implementation.
- [x] Implement minimal updates/service/API/protocol after RED; run focused pytest journal updates/application/concurrency, legacy registry tests. Expected all green.
- [x] Vue RED: changed-row diff, old mapping draft not auto-confirmed, explicit update selection+reason, actual request versions/key, error retry retains payload, route reset and readonly gating. Implement separate HistoryUpdates panel and preserve new-row creation. Expected frontend tests/build green.
- [x] Full pytest and frontend test/build/check/migration drift/diffcheck; one final whole-slice review and one Important fix pass RED→GREEN/full suite. Expected no unresolved Important. Actual568 backend,236 frontend, build2.10s.
- [x] Backup; current live eligibility check, explicit six mapping confirmations preserving people/composition, apply via API and independently verify before/after/provenance/raw hashes/old IDs/report. Browser diff/packet/protocol and fresh report/download; render changed Excel ranges. No duplicates or native events. Leave one Vite/Django only. Actual6+2 updates: fresh source confirms468 closure and395 specialty, separate backup/checkpoints;472 unchanged on final reconciliation,660 Excel cells verified.
- [ ] Local commits/task-done/evidence; next actual process/report gaps, keep full goal active.
