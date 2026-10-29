# Storage Settings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Настройки корня документов по годам в веб-интерфейсе администратора.
**Architecture:** Аддитивная настройка в documents, отдельная read-only проверка пути,
существующие роли/аудит/идемпотентность. Vue-страница и общий указатель настроек.
**Tech Stack:** Django/DRF/PostgreSQL, Vue 3/TypeScript, pytest/Vitest; без зависимостей.
**Spec:** `docs/superpowers/specs/2026-10-29-storage-settings-design.md`.

## Global Constraints

- Только чтение папки после явного действия. Пример UNC не подключать.
- Никакой очистки рабочих данных, перемещения файлов, автоматической привязки.
- Право `documents.storage.manage` только institution, без автоматической выдачи.
- Существующие незакоммиченные изменения мягкого завершения сохраняются.
- Работать в текущей feature-ветке без нового worktree/сервера Vite; не push/merge.

## Review Focus

- Сохранение пути не выполняет сетевой или файловый запрос.
- Зависший SMB заканчивается timeout без зависшего фонового процесса.
- Отзыв роли закрывает GET/PUT/check и убирает путь из интерфейса.
- Конфликт версии и повтор запроса не перезаписывают чужое изменение.
- Изменение пути/года сбрасывает прежний результат проверки.

## Task 1: Настройка и проверка на Django

**Files:** documents/models.py, новая миграция, storage_settings.py, storage_probe.py,
documents/urls.py, accounts/catalog.py, accounts/views.py, tests/test_storage_settings.py.
**Interfaces:** GET/PUT /document-storage/<year>/ и POST /document-storage/check/ из spec.

- [x] Написать RED API tests: пустой GET, два года, replay/stale/audit rollback,
  permission/revocation, отсутствие IO при save, валидация пути.
- [x] Воспроизвести RED, реализовать модель/команды/право/маршруты.
- [x] Написать и выполнить RED проверки настоящего временного каталога,
  отсутствующей папки и timeout дочернего процесса; реализовать bounded probe.
- [x] Прогнать профильные tests и Django check/drift.

## Task 2: Настройки во Vue и проверка

**Files:** новый modules/settings/StorageSettingsPage.vue и SettingsPage.vue,
api/storage.ts, router.ts, App.vue, тесты и инструкция README.
**Interfaces:** Контракты Task 1, existing institutionPermission/session/client/dirty guard.

- [x] RED UI tests: нет запроса без права, сохранить не проверяет,
  check отдельно, ввод сбрасывает результат, конфликт/повтор, отзыв роли.
- [x] Реализовать страницы/навигацию, контролируемые ошибки/загрузку.
- [x] Полный frontend/backend, build, check/drift/diff; независимое итоговое ревью.
- [x] Резервная копия и аддитивная миграция перед перезапуском только Django.
  Рабочие данные и пример UNC не изменять; общий Vite переиспользовать.
- [x] Документировать фактическую готовность; локальный commit без push.
