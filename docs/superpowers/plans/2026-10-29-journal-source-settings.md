# Journal Source Settings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Редактировать источник Google-журнала через сайт исключительно по праву роли.
**Architecture:** Singleton-настройка БД с fallback на окружение; версионная идемпотентная команда и аудит. Отдельная Vue-форма и ссылки, закрытые тем же правом.
**Tech Stack:** Existing Django/DRF/PostgreSQL, Vue3/TypeScript, pytest/Vitest; без зависимостей.
**Spec:** docs/superpowers/specs/2026-10-29-journal-source-settings-design.md

## Global Constraints

- В текущем checkout без worktree, push, удаления `.superpowers` и изменений `outputs/`.
- Google — только чтение при явной проверке; сохранение настройки без сети и без переноса экспертиз.
- Право `imports.source.manage`, область `institution`; никаких обходов без активной роли.
- Не менять старые снимки, экспертизы, PHP и прежний контракт GET источника.
- Каждый backend-прогон — свежая тестовая БД; одновременно только один pytest.

## Review Focus

- Отзыв права при повторе сохранённой команды не должен возвращать успешный кеш вместо403.
- Настройка без источника и одновременно два первых сохранения не должны обходить версию0.
- Смена gid вручную должна определять настоящий лист, а не скрытая старая часть ссылки.
- Потеря ответа и уход со страницы не должны создавать вторую настройку или терять пакет повтора.
- Управление источником без права запускать импорт не должно запускать импорт или показывать его кнопки.

### Task 1: Серверная настройка и право

**Files:** backend/apps/imports/{models.py,source_settings.py,api.py,services.py,urls.py,migrations/0004_journalsourcesettings.py}; backend/apps/accounts/{catalog.py,views.py}; backend/tests/test_google_source_settings.py.
**Interfaces:** Consumes: configured_google_source(), execute_once(), require(), audit(), check_version(). Produces: active_google_source(), source_settings_data(), save_source_settings(actor,data,key), GET/PUT `/imports/google-source/settings/`, supported module `journal_source_settings`.

- [ ] Step1: Write tests for fallback GET, saved effective source without restart, no business writes/network, missing/invalid scope/role, revoked role replay, invalid URL/gid/unknown fields, stale version, idempotency and old-source preview rejection. Assert exact status403/400/409 and record/event counts.
- [ ] Step2: Run `backend/.venv/Scripts/python.exe infra/local.py backend -m pytest tests/test_google_source_settings.py`; Expected: RED endpoint404/405 before implementation.
- [ ] Step3: Implement the singleton model, additive migration, URL normalization, atomic versioned command, permission catalogue entry, API and active-source read path; preserve old GET response.
- [ ] Step4: Run `backend/.venv/Scripts/python.exe infra/local.py backend -m pytest tests/test_google_source_settings.py tests/test_google_journal_source.py tests/test_google_journal_preview.py`; Expected: all GREEN.
- [ ] Step5: Commit only Task1 files and update ledger.

### Task 2: Форма, видимость и запуск

**Files:** frontend/src/modules/imports/{GoogleSourceSettingsPage.vue,GoogleSourceSettingsPage.test.ts,GooglePreview.vue,JournalSyncActions.vue,JournalSyncActions.test.ts}; frontend/src/api/imports.ts; frontend/src/router.ts; docs/verification/journal-source-settings-2026-10-29.md.
**Interfaces:** Consumes: Task1 contract and `journal_source_settings`; produces `/imports/source-settings` gated by `imports.source.manage`, links in registry and Google-source block.

- [ ] Step1: Write component tests: no right/capability means no form/read/action; link visible only to manager; URL gid parsing, explicit gid, correct versioned body, no import, lost reply frozen key/body,409 preserves inputs, role revocation prevents save.
- [ ] Step2: Run `npm --prefix frontend test -- src/modules/imports/GoogleSourceSettingsPage.test.ts src/modules/imports/JournalSyncActions.test.ts`; Expected: RED missing form/links.
- [ ] Step3: Implement dedicated settings form, route/module gates and role-only links; read current effective source on every explicit refresh.
- [ ] Step4: Run `npm --prefix frontend test` and `npm --prefix frontend run build`; Expected: all GREEN, build exit0 (existing chunk-size warning allowed). Run full backend `backend/.venv/Scripts/python.exe infra/local.py backend -m pytest`; Expected: all GREEN.
- [ ] Step5: Apply only additive migration to local runtime, restart the single Django process, grant only new permission to setup under prior all-rights authorization; verify GET settings/current source and catalogue without changing link or business records. Commit task and verification evidence.

## Final Review

One independent read-only review of this feature range, not earlier journal work. Fix only Critical/Important findings with RED→GREEN; preserve ledger and leave commits local.
