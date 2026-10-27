# Пользователи роли и сотрудники Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Первый реальный срез Django/Vue: персональный вход, редактируемые роли, сотрудники с несколькими специальностями и явным обучением.

**Architecture:** Новый отдельный репозиторий `E:/VLSE/ais-lse`, модульный Django REST API и Vue SPA. PostgreSQL — целевая и интеграционно проверяемая база. Это этап общей цели, не замена полного пути экспертизы и 15.1.

**Tech Stack:** Python 3.13, Django 5.2 LTS, DRF, PostgreSQL 17; Vue 3, TypeScript, Vite, Pinia, Vue Router.

**Spec:** `docs/specification.md`, `docs/access-control.md`, `docs/initial-data-and-tables.md`; применимые паттерны `docs/reference-patterns.md`.

## Global Constraints

- Стажировка — только учёт обучения, без назначения на экспертизы по этой специальности.
- У сотрудника несколько ролей и специальностей; начальник может вести собственные экспертизы.
- Роли не подменяют квалификацию. Область проверяется отдельно для каждого действия.
- Не менять исходные Excel/Google, PHP, E:/DD и старую VM. Никакого push.
- Новый код только в `ais-lse`; исходные пароли и рабочие документы не включаются в Git.
- Успех UI подтверждается сохранением сервером, состояние держится после перезапуска.

## Review Focus

- Отзыв права в открытой сессии: следующий API-запрос должен отказать, даже если кнопка осталась в старой вкладке.
- Просмотр учреждения из одной роли не расширяет изменение отдела из другой; пустой список отделов не означает всё учреждение.
- У одного человека одновременно qualified 18.1 и training 13.1; разные результаты пригодности без размножения сотрудника.
- Устаревший редактор роли не затирает новый набор прав; недопустимый код/область не сохраняется частично.
- Сетевой отказ и поздний ответ списка: форма не сообщает успех, устаревшая выборка не заменяет более свежую.

---

### Task 1: Django модели сессия и policy

**Files:**
- Create: `backend/pyproject.toml`, `backend/config/{settings,urls}.py`, `backend/manage.py`.
- Create: `backend/apps/accounts/{models,catalog,policies,services,views,urls}.py`.
- Create: `backend/apps/personnel/models.py`, `backend/apps/references/models.py`, `backend/apps/audit/models.py`.
- Test: `backend/tests/test_identity.py`, `backend/tests/test_policies.py`, `backend/tests/test_qualifications.py`.

**Interfaces:**
- Produces: `effective_scope(user, action) -> AccessScope(own, departments, institution)`.
- Produces: `can(user, action, employee_id=None, department_ids=()) -> bool`.
- Produces: `qualification_eligibility(employee, specialty, at) -> {eligible, code, message}`.
- Produces: `/api/v1/auth/{csrf,login,logout}/`, `/api/v1/me/` с JSON-ошибками и cookie session.

- [ ] Step 1: Тесты входа, активного аккаунта, session logout/CSRF, объединения ролей и раздельных областей. Проверить training=false и qualified=true только для своей специальности, роль начальника не меняет результат.
- [ ] Step 2: Запустить тесты и увидеть отсутствие `/me/`, policy и квалификационных операций. Ошибка окружения не считается RED поведения.
- [ ] Step 3: Создать модели, миграции, policy и сессионные endpoints. Собственная User создаётся до миграций; actor employee и role grants отдельны.
- [ ] Step 4: Запустить всю backend suite и миграции на PostgreSQL; зафиксировать фактическую среду и не называть SQLite интеграционной проверкой.
- [ ] Step 5: Локальный commit файлов задачи, без push.

### Task 2: Редактор ролей кадровые API и начальное наполнение

**Files:**
- Create: `backend/apps/accounts/{serializers,api}.py`, `backend/apps/personnel/{serializers,services,api,urls}.py`.
- Create: `backend/apps/references/{serializers,api,urls}.py`.
- Create: `backend/apps/accounts/management/commands/bootstrap_access.py`.
- Test: `backend/tests/test_roles_api.py`, `backend/tests/test_personnel_api.py`, `backend/tests/test_bootstrap.py`.

**Interfaces:**
- Consumes: `effective_scope`, `can`, `qualification_eligibility` из Task 1.
- Produces: `/permissions/`, `/roles/`, `/roles/{id}/permissions/`, `/employees/`, `/employees/{id}/roles/`, `/employees/{id}/specialties/`, `/references/{catalog}/`.
- Produces: `expected_version` для изменения роли и атомарный audit, начальные шаблоны без скрытого общего пароля.

- [ ] Step 1: API-тесты реального сохранения роли, отказов без права, разных областей, конфликта версии, неправильного permission/scope и отсутствия частичного сохранения; отзыв права при открытой session.
- [ ] Step 2: Запустить и увидеть 404/невыполненные API-ожидания, затем реализовать serializers/services/views.
- [ ] Step 3: Тесты нескольких специальностей и должностей, явного qualify и запрета самовыдачи допуска; конфликта duplicate, деактивации вместо удаления. Реализовать кадровые API.
- [ ] Step 4: Команда bootstrap принимает логин/ФИО и секрет из environment или безопасного ввода, создаёт лишь явно выбранный доступ; справочники/шаблоны идемпотентны. Реальные имена из журнала не означают автоматическую выдачу логинов и подтверждение допусков.
- [ ] Step 5: Вся backend suite GREEN, local commit без push.

### Task 3: Vue вход роли сотрудники и проверка с настоящим API

**Files:**
- Create: `frontend/{package.json,index.html,vite.config.ts,tsconfig.json}`.
- Create: `frontend/src/api/{client,types}.ts`, `stores/session.ts`, `router.ts`, `App.vue`.
- Create: `frontend/src/modules/{LoginPage,HomePage,RolesPage,PeoplePage}.vue`, `shared/ui`, `shared/styles`.
- Test: `frontend/src/api/client.test.ts`, `frontend/src/modules/RolesPage.test.ts`, `PeoplePage.test.ts`.

**Interfaces:**
- Consumes: endpoints Task 1/2, error `{code,message,field_errors}` и permission scope.
- Produces: login shell, roles with grouped permission editor and scope, staff qualifications/training, clear save/error states.

- [ ] Step 1: Тест клиента: CSRF login, JSON-ошибка не выдаётся за успех, поздняя загрузка не затирает актуальную.
- [ ] Step 2: Тест формы: редактор групп прав сохраняет область/версию и сохраняет введённое при 409; список сотрудников не размножается из-за двух специальностей.
- [ ] Step 3: Реализовать единый клиент, страницы и shared UI в зелёной палитре; один dev server с proxy на Django. Не переносить произвольный переключатель роли из макета.
- [ ] Step 4: Полная frontend suite, typecheck, build; backend suite повторно. Пройти реальные HTTP-команды входа, создания роли, назначения сотруднику и повторного чтения.
- [ ] Step 5: Обновить README/прогресс и локально зафиксировать. Перед переходом к экспертизам сделать независимое ревью этого среза. Весь исходный goal остаётся active.
