# Registry Form151 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox syntax.

**Goal:** Рабочая БД с новыми и историческими работами питает веб/Excel15.1, без учебных материалов, подмены неизвестных фактов и потери трассировки.

**Architecture:** Material.is_demo отличает учебные данные. registry.py строит ReportRecord(facts, raw={}, source_row=workUUID), общая calculation.py с явным mode сохраняет journal-правила и использует typed registry-даты. API разделяет права и fingerprint, Vue переключает режимы и скачивает только успешный Excel-ответ.

**Tech Stack:** существующие Django/DRF/PostgreSQL, Vue3/TS/Vitest, ZIP/XML exporter. Без новых пакетов.

**Spec:** docs/superpowers/specs/2026-10-28-form151-registry-design.md

## Global Constraints

Сохраняем 472 исходных работы/номера/отделы/связи и raw/facts. Не менять Google/PHP/права. Новое поле — только учебная классификация Material с defaultFalse. Читающий расчёт не создаёт события/документы/назначения. Без push/merge и нового worktree. Нет автоматической классификации по тексту/аккаунту.

## Review Focus

- Принятая редакция отличается от последнего черновика; последнее исправление закрытия меняет расчёт, черновик не меняет.
- Возврат без даты решения, но с датой выдачи, не должен стать закрытым по догадке; только snapshot сохраняет историческое правило.
- Учебный флаг действует на весь материал/комплекс, а не по названию, и не скрывает реальные записи с похожим текстом.
- Нет доступа к полному реестру по одним department/own правам или по праву чтения источника.
- Смена данных/режима/периода снимает старую выгрузку;409/403 не скачиваются как Excel. UUID трассируются в карточки и не выдаются за строки листа.

### Task 1: Live registry report and explicit training data

**Files:** intake models/serializers/services/migration; expertises serializer; reports registry.py/api.py/calculation.py; frontend api/client.ts, api/types.ts, modules/reports/ReportsPage.vue, intake/IntakePage.vue, cards/lists training label; tests test_form151_registry.py, test_demo_material.py and Vue report/intake/client tests.

**Interfaces:** Material.is_demo: bool=False; ReceiptCreate.is_demo optionalbool; MaterialOutput.is_demo bool. calculate(..., mode='journal'|'registry'); registry.calculate_registry(year,month,opening_balances_complete)->report with records UUID→reference, source.type registry/name/row_count/excluded_demo_count/data_revision. API source=registry, no batch_id; expected_revision optional SHA256; journal remains default and requires batch_id. ApiClient.download(path, signal?)->{blob,filename}, throws ApiError on error response.

- [x] RED backend: explicit training creation persisted/read/audited, normal names don't imply training; patching receipt cannot reclassify registered data silently. Registry uses live historical field rather than original source, latest accepted closure not draft, native arrival/open stock, partial questions stay unknown, issuance not returndecision, demo excluded. Institution permissions/run/download independent from imports; repeat/invalidparams400, stale revision409, GET has no domain writes, XLSX matches preview.
- [x] Implement minimal field/migration and adapter/mode/API after RED. Preserve literal source calculator tests and original template; focused GREEN.
- [x] RED Vue: default registry works without import grant; snapshot bookmark retains source mode; provenance links real UUIDs; changing mode invalidates old result; binary download errors visible/no save; training checkbox only sends true explicitly. Implement GREEN.
- [x] Full backend pytest, frontend test/build, Django check/migration drift, diffcheck. Expected allpass. One final independent whole-slice review; one importantfixpass with RED→GREEN/full suite if needed.
- [x] Back up DB, apply field migration; verify/mark only six exact prior demo materials with audit, not 472 real works. Run registry report on live472 and compare explained differences with source, verify count/traces and zero source mutation. Browser calculate+download same revision, inspect/render affected Excel ranges using artifact tool. Leave one Vite bound0.0.0.0:5173 and owned Django. No extra persistent Node services.
- [ ] Local commit/evidence, task-done, next explicit outstanding report/workflow requirements, goal stays active.
