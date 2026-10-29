# Document Picker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Выбирать сохранённые документы по названию и добавлять новые рядом, без ввода кодов.
**Architecture:** Read-only поиск через существующие права документов; общий Vue-компонент поверх BasisDocumentForm и текущих команд родителей.
**Tech Stack:** Django/DRF, Vue 3/TypeScript, pytest/Vitest.
**Spec:** docs/superpowers/specs/2026-10-29-document-picker-design.md

## Global Constraints

Не менять обязательность документов, статусы экспертиз, правила завершения, роли, существующие файлы и рабочие записи. Без новых таблиц и миграций. Без push. Сохранить две прежние правки напоминаний отдельно.

## Review Focus

- Область own/departments и документ, доступный через связь: нельзя показывать чужое название или неправильный count.
- Запоздалый поиск/GET выбранного документа: не заменяет более новый выбор или вид.
- Выбранный ранее документ отсутствует на странице поиска: выбор и название сохраняются.
- Новый документ с выбранным файлом: переход к поиску требует предупреждения; повтор после сетевой ошибки не создаёт дубль.
- Историческая активация требует файл итога, обычное завершение не требует: UI не должен смешать эти политики.

## Task 1: Read-only поиск и общий компонент

**Files:** backend/apps/documents/api.py, search.py; backend/tests/test_document_search.py; frontend/src/shared/DocumentPicker.vue, DocumentPicker.test.ts.
**Interfaces:** GET /documents/?search=...&kind=resolution,decision&page=N → Page<BasisDocument>. DocumentPicker: v-model ID, v-model:mode existing/new; selected(document|null), changed; expose persist():Promise<BasisDocument>, dirty, uploadConflict. Props departmentId, kindOptions (для создания), kinds (фильтр выбора), requireFile, heading, name, busy/inputLocked, document.

- [x] Тесты GET прав, фильтров, имён файлов, пагинации и отсутствия записей; RED подтверждён (405).
- [x] Добавить GET, используя can_document и существующую пагинацию; 4 теста — PASS.
- [x] Тесты общего компонента: выбор/очистка/страницы, новый документ, предупреждение при уходе, поздние ответы, права, сохранение и uploadConflict; RED подтверждён.
- [x] Реализовать компонент; 11 целевых тестов — PASS, включая две регрессии из ревью.

## Task 2: Интеграция и показ

**Files:** HistoryActivation.vue, ResultPanel.vue, CaseDetailsPanel.vue, ClassificationPanel.vue, TimingPanel.vue, ReportPlanEditor.vue, LetterAttachments.vue, IssueDocumentPicker.vue и соответствующие тесты. Финальная инвентаризация выявила ещё ручной код приложения письма; выдача уже имела специальный поиск, там выровнены кнопки без замены её контекстного API.
**Interfaces:** Родители сохраняют прежние payload/версию/idempotency; новый picker заменяет выбор ID и подготовку файла, не бизнес-команду.

- [x] Добавить интеграционные тесты поиска основания и итога вместо UUID, выбрать сохранённый документ и проверить прежний payload; RED на текущих формах.
- [x] Заменить поля, переиспользовать persist/dirty/uploadConflict; обновить существующие тесты под реальные действия нового UI без ослабления проверок. Приложения писем и кнопки выдачи: 4 RED → 59 PASS в двух существующих наборах.
- [x] Полный backend: 1106 PASS; финальный frontend после писем/выдачи: 456 PASS, build/TypeScript и Django checks — PASS.
- [x] Независимое read-only ревью; обе важные находки исправлены RED→GREEN.
- [x] Перезапустить только Django при необходимости; показать форму на №482 в браузере без POST рабочих данных, сохранить скриншот и инструкцию. Подготовлен локальный scoped commit без push.
