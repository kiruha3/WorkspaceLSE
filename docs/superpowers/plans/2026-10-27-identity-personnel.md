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

- [x] Step 1: Тесты входа, активного аккаунта, session logout/CSRF, объединения ролей и раздельных областей. Проверить training=false и qualified=true только для своей специальности, роль начальника не меняет результат.
- [x] Step 2: Запустить тесты и увидеть отсутствие `/me/`, policy и квалификационных операций. Ошибка окружения не считается RED поведения.
- [x] Step 3: Создать модели, миграции, policy и сессионные endpoints. Собственная User создаётся до миграций; actor employee и role grants отдельны.
- [x] Step 4: Запустить всю backend suite и миграции на PostgreSQL; зафиксировать фактическую среду и не называть SQLite интеграционной проверкой.
- [x] Step 5: Локальный commit файлов задачи, без push.

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

- [x] Step 1: API-тесты реального сохранения роли, отказов без права, разных областей, конфликта версии, неправильного permission/scope и отсутствия частичного сохранения; отзыв права при открытой session.
- [x] Step 2: Запустить и увидеть 404/невыполненные API-ожидания, затем реализовать serializers/services/views.
- [x] Step 3: Тесты нескольких специальностей и должностей, явного qualify и запрета самовыдачи допуска; конфликта duplicate, деактивации вместо удаления. Реализовать кадровые API.
- [x] Step 4: Команда bootstrap принимает логин/ФИО и секрет из environment или безопасного ввода, создаёт лишь явно выбранный доступ; справочники/шаблоны идемпотентны. Реальные имена из журнала не означают автоматическую выдачу логинов и подтверждение допусков.
- [x] Step 5: Вся backend suite GREEN, local commit без push.

### Task 3: Vue вход роли сотрудники и проверка с настоящим API

**Files:**
- Create: `frontend/{package.json,index.html,vite.config.ts,tsconfig.json}`.
- Create: `frontend/src/api/{client,types}.ts`, `stores/session.ts`, `router.ts`, `App.vue`.
- Create: `frontend/src/modules/{LoginPage,HomePage,RolesPage,PeoplePage}.vue`, `shared/ui`, `shared/styles`.
- Test: `frontend/src/api/client.test.ts`, `frontend/src/modules/RolesPage.test.ts`, `PeoplePage.test.ts`.

**Interfaces:**
- Consumes: endpoints Task 1/2, error `{code,message,field_errors}` и permission scope.
- Produces: login shell, roles with grouped permission editor and scope, staff qualifications/training, clear save/error states.

- [x] Step 1: Тест клиента: CSRF login, JSON-ошибка не выдаётся за успех, поздняя загрузка не затирает актуальную.
- [x] Step 2: Тест формы: редактор групп прав сохраняет область/версию и сохраняет введённое при 409; список сотрудников не размножается из-за двух специальностей.
- [x] Step 3: Реализовать единый клиент, страницы и shared UI в зелёной палитре; один dev server с proxy на Django. Не переносить произвольный переключатель роли из макета.
- [x] Step 4: Полная frontend suite, typecheck, build; backend suite повторно. Пройти реальные HTTP-команды входа, создания роли, назначения сотруднику и повторного чтения.
- [x] Step 5: Обновить README/прогресс и локально зафиксировать. Перед переходом к экспертизам сделать независимое ревью этого среза. Весь исходный goal остаётся active.

## Фактическая проверка 28.10.2026

- PostgreSQL 17.11 локально, `127.0.0.1:55432`; миграции применены. Docker и старая VM не требуются.
- Полная backend suite: **50 passed**; включает настоящие HTTP login/CSRF/role-create/assignment/read-back. Django check без замечаний, незаписанных миграций нет.
- Полная frontend suite: **34 passed**; typecheck и production build успешны.
- Живой браузер: вход, 11 сотрудников (10 из исходного списка + настройка), отдельная карточка с двумя специальностями, полноширинный редактор роли. Данные реальных сотрудников через UI-проверки не менялись.
- По запросу владельца веб слушает `0.0.0.0:5173`; Django/БД loopback. Проверены LAN login и CSRF с разрешённым внешним Origin. Владелец подтвердил доступность своего сетевого маршрута; отдельная интернет-проверка извне не выполнялась.
- Ветка `implementation`, только локальные коммиты, push и merge не выполнялись. Исходные PHP/старый Vue/Excel сохранены.

Независимое ревью: 6 Important исправлены в одном TDD-проходе: справочник для отделовых прав, PATCH только изменённых полей, смешанные области роли, отдельный минимальный каталог администратора, проверка итогового срока квалификации, независимая версия метаданных сотрудника при создании аккаунта. В финальной визуальной проверке дополнительно исправлена карточка роли ниже длинного списка.

Отложенное Minor: ввод основания при изменении самих прав роли; audit уже содержит автора, время и before/after, а назначения/прекращения ролей требуют основания. Не считать этот пункт исчезнувшим из общего ТЗ.

### Зафиксированные решения и границы

1. Собственная модульная Django/Vue-модель, а не перенос всей OCR/ML-платформы DD/DA; иначе появятся ненужные зависимости и нагрузка.
2. Project-local PostgreSQL без сброса старой БД; для промышленной эксплуатации ещё нужны отдельные deployment/backup-проверки.
3. Команды персонального входа/блокировки и кадровых назначений включены сразу, иначе первый срез нельзя было бы использовать без прямого вмешательства в БД.
4. Реальные специальности из журнала остаются `unknown_legacy` до подтверждения. По явному уточнению владельца дата получения может быть неизвестна, если ответственный подтвердил факт с основанием. Известные ограничения срока действуют.
5. `Employee.version` относится к ФИО/активности, а аккаунт и другие дочерние сущности меняются отдельно; поля аккаунта не входят в кадровый DTO. Это устраняет ложные конфликты черновиков без снятия защиты реального конкурентного изменения ФИО.
6. Администратору доступа предоставлен минимальный каталог идентичностей, а не неявное право читать все кадровые сведения. Локальное совмещение с кадровой ролью задано явно.
7. Специальное кадровое право допускает подтверждение собственной квалификации; обычного самообслуживания для этого нет. Если потребуется независимый согласующий, это отдельное правило владельца, а не уже реализованная проверка.
8. Экспертизы/документы/письма/выдача/импорт/15.1, все справочники/алиасы/слияние/настройки таблиц остаются обязательными дальнейшими этапами. Сброс пароля, прекращение всех сессий и экран истории аудита также ещё не сделаны.
9. Ревьюер не повторял suites/браузер; ведущий агент выполнил эти проверки. Результат первого среза не доказывает готовность всей исходной системы или промышленной эксплуатации; общая цель остаётся active.
