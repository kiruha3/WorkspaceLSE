# Expertise Reopen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Вернуть случайно завершённую работу в производство отдельным правом.
**Architecture:** Добавочное событие возврата поверх существующих версионированных команд; прежние закрытия остаются историей. Vue использует серверные allowed_actions.
**Tech Stack:** Django, PostgreSQL, DRF, Vue 3, TypeScript, pytest, Vitest.
**Spec:** docs/superpowers/specs/2026-10-29-expertise-reopen-design.md

## Global Constraints

Не менять реальные экспертизы для проверки. Миграция только добавляет таблицу событий; никакого удаления БД, массовой активации, новых зависимостей или push.

## Review Focus

- Историческая неактивированная работа: возврат не выдумывает основание/назначение.
- Повторное завершение: номера закрытий не повторяются, прежние файлы остаются.
- Приостановка: возврат не создаёт фиктивного возобновления.
- Выдача и повторный импорт: старое закрытие не разрешает выдачу/перезапись.
- Потерянный ответ и изменившаяся версия: повтор не откатывает новые данные.

## Task 1: Серверная команда и согласованность фактов

**Files:** accounts/catalog.py; expertises/models.py, reopen.py, results.py, serializers.py, result_api.py, urls.py, api.py; reports/registry.py; imports/updates.py; новая миграция; tests/test_expertise_reopen.py.
**Interfaces:** `reopen_work(actor,expertise_id,data,key,payload)` → `{id,expertise_id}`; API добавляет `reopening_history` с прежними датами, автором, причиной, состоянием.

- [x] Написать тесты разрешений/пустой причины/версии/idempotency, закрытого и открытого состояния, истории, исторической выдачи, повторного завершения, приостановки, отчёта и экспорта. Запустить — ожидается 404 нового API.
- [x] Добавить событие и команду, state-aware latest_closure, независимую нумерацию закрытий, согласованный отчёт и защиту импорта. Создать аддитивную миграцию.
- [x] Запустить целевые тесты и связанные completion/history/report/issuance/import тесты — ожидается PASS.

## Task 2: Интерфейс и проверка

**Files:** frontend/src/modules/expertises/ReopenWork.vue, ReopenWork.test.ts, ExpertisePage.vue; frontend/src/api/types.ts; docs/verification.
**Interfaces:** потребляет `allowed_actions`, `reopening_history`, версионированный POST; emits updated(Expertise).

- [x] Тесты скрытой кнопки без права, причины/подтверждения, ответа сервера, конфликта, повторной отправки, истории; сначала ожидается отсутствие компонента.
- [x] Добавить форму в раздел результата, защиту ухода/двойной отправки и историю; переиспользовать клиент API и newCommandKey.
- [x] Полные backend/frontend тесты, build, check и makemigrations --check; ожидается PASS без новых миграций.
- [x] Независимое read-only ревью; исправить важные находки через RED→GREEN.
- [x] Бэкап, применить миграцию, перезапустить только Django, выдать setup ровно новое право; UI проверить без возврата настоящей работы. Vite также восстановлен после внешней остановки.
- [x] Документировать результаты; локальный scoped commit, без push и без включения прежних двух файлов напоминаний.
