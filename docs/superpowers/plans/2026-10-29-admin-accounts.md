# Admin Accounts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Добавить создание сотрудника из учётных записей и административный сброс пароля, сохранив существующую выдачу логина.

**Architecture:** Переиспользовать создание карточки сотрудника и компонент EmployeeAccount. Добавить один серверный обработчик сброса и отдельное разрешение; данные и миграции не менять.

**Tech Stack:** Django, DRF, PostgreSQL; Vue 3, TypeScript, Vitest.

**Spec:** `docs/superpowers/specs/2026-10-29-admin-accounts-design.md`

## Global Constraints

- Область `users.reset_password`: только `institution`.
- Никаких автоматических ролей, смены логина, реактивации и массового изменения существующих учёток.
- Создание сотрудника: существующий `POST /employees/`, право `employees.create`.
- Без саморегистрации, почтовых ссылок, новых зависимостей и миграций.
- Сохранить соседние изменения напоминаний, не включать их в коммит этой функции.

## Review Focus

- Повторный сброс не должен возвращать или аудитировать пароль/хеш.
- Наличие `users.create` не даёт сбрасывать уже существующий пароль.
- Ошибка логина после создания сотрудника не создаёт второго человека.
- Сброс заблокированной учётки не разрешает вход автоматически.
- Переход из незаполненной формы/во время запроса не должен терять контекст команды.

### Task 1: Backend password reset

**Files:** `backend/apps/personnel/api.py`, `serializers.py`; `backend/apps/accounts/catalog.py`, `management/commands/bootstrap_access.py`; `backend/config/urls.py`; новый `backend/tests/test_account_password_reset.py`.

**Interfaces:** `POST /api/v1/employees/{id}/account/reset-password/`, body `{password, reason?}`, результат `{id, username, is_active}`. GET каталога/учётки допускается и по новому праву.

- [x] Написать тесты смены пароля, старого/нового входа и сессии, запрета без права/после отзыва, отсутствующей учётки, слабого пароля, неизменности ролей/активности и отсутствия секретов в аудите; запустить и увидеть RED.
- [x] Реализовать право, сериализатор, транзакционный обработчик с блокировкой строки User, URL и чтение минимального каталога; шаблон для новых установок, без массового обновления ролей.
- [x] Запустить целевые серверные тесты, затем `manage.py check` и проверку отсутствия миграций; ожидается GREEN.

### Task 2: Frontend administration flow

**Files:** `frontend/src/modules/AccessPeoplePage.vue`, `PeoplePage.vue`, `people/EmployeeAccount.vue`, `people/EmployeePanel.vue`, `stores/session.ts`, `api/storage.ts` и соответствующие тесты.

**Interfaces:** Существующее создание сотрудника возвращает Employee; после успеха открыть его персональную учётку. Сброс вызывает endpoint из Task 1; права проверяются и интерфейсом, и сервером.

- [x] Добавить RED-тесты создания сотрудника в `/access`, перехода к существующей выдаче логина без автосоздания учётки, отказа отмены/ошибки сохранения; кнопки создания из карточки `/people`; сброса, скрытия без права, несовпадения паролей и серверной ошибки.
- [x] Реализовать кнопки и формы без дублирования существующего ввода первоначального пароля; включить новое право в навигацию/родительские условия показа.
- [x] Запустить целевые тесты, весь frontend suite и build; ожидается GREEN.
- [x] Запустить весь изолированный backend suite; проверить интерфейс без создания/сброса реальных учёток, получить независимый read-only review; задокументировать результат.
- [x] Закоммитить только файлы этой функции после проверок, без push. Не изменять существующие права без ответа на отдельный вопрос о setup.
