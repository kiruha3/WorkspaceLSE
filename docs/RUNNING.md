# Развёртывание и запуск АИС

Инструкция для текущего проекта Django + Vue 3 + PostgreSQL, опубликованного в `kiruha3/WorkspaceLSE`, ветка `implementation`. Основной проверенный вариант — Windows x64, без виртуальной машины и Docker. Команды выполняются в PowerShell из корня клонированного репозитория, если явно не указано другое.

Это запуск существующего окружения разработки для просмотра и проверки. Постоянная служба, автоматический старт после перезагрузки, HTTPS и промышленный веб-сервер в этом варианте не настроены. Не следует считать запуск `runserver`/Vite готовым промышленным развёртыванием.

## 1. Установить инструменты и получить код

Нужны:

- [Git](https://git-scm.com/downloads).
- [uv](https://docs.astral.sh/uv/getting-started/installation/) для Python и зависимостей.
- [Node.js](https://nodejs.org/en/download) с npm. Здесь проверен Node.js **22.20.0**; Python — **3.13.12**, PostgreSQL — **17.11**. Проект ограничивает Python веткой **3.13**, а JS-зависимости фиксируются `package-lock.json`.
- Windows `tar.exe` для распаковки PostgreSQL.

```powershell
git clone --branch implementation https://github.com/kiruha3/WorkspaceLSE.git
Set-Location WorkspaceLSE
uv python install 3.13
uv sync --directory backend --python 3.13 --locked
npm.cmd --prefix frontend ci
```

Если репозиторий приватный, для `git clone` войдите в GitHub через Git Credential Manager или используйте свой SSH-доступ. Общего пароля GitHub в проекте нет.

`uv sync` создаёт `backend/.venv/`. Системный PHP, старые проекты и прежняя виртуальная машина новой АИС не нужны.

## 2. Подготовить PostgreSQL для нового локального окружения

`infra/local.py` ожидает переносимые бинарные файлы в `.runtime/postgresql/`, с вложенными каталогами `bin`, `lib`, `share`. Сам скрипт PostgreSQL не скачивает.

Для **свежего клона**, где ещё нет этого runtime, можно распаковать тот же пакет, который использовался здесь: Maven Central, `io.zonky.test.postgres:embedded-postgres-binaries-windows-amd64:17.11.0`. Java для извлечения архива не нужна.

```powershell
New-Item -ItemType Directory -Path .runtime/pg-install -Force | Out-Null
New-Item -ItemType Directory -Path .runtime/postgresql -Force | Out-Null
Invoke-WebRequest -Uri 'https://repo.maven.apache.org/maven2/io/zonky/test/postgres/embedded-postgres-binaries-windows-amd64/17.11.0/embedded-postgres-binaries-windows-amd64-17.11.0.jar' -OutFile .runtime/pg-install/postgresql.jar
tar -xf .runtime/pg-install/postgresql.jar -C .runtime/pg-install postgres-windows-x86_64.txz
tar -xf .runtime/pg-install/postgres-windows-x86_64.txz -C .runtime/postgresql
Test-Path .runtime/postgresql/bin/postgres.exe
& ./.runtime/postgresql/bin/postgres.exe --version
```

`Test-Path` должен вернуть `True`. Если получился лишний вложенный каталог, исправьте расположение: исполняемый файл должен находиться именно в `.runtime/postgresql/bin/postgres.exe`. Существующий `.runtime/postgresql-data/` не трогайте и не заменяйте. На уже работающей машине этот шаг пропускается.

Первый запуск:

```powershell
& ./backend/.venv/Scripts/python.exe infra/local.py db-start
& ./backend/.venv/Scripts/python.exe infra/local.py db-status
```

Создаются отдельный кластер `.runtime/postgresql-data/`, база `ais_lse` и файл подключения `.runtime/postgresql-connection.json` со случайными паролем и Django secret. Адрес PostgreSQL — `127.0.0.1:55432`. Существующие внешние базы этот сценарий не использует. Занятый порт нужно сначала диагностировать, а не освобождать остановкой неизвестного сервиса.

## 3. Создать таблицы, справочники и первый вход

```powershell
& ./backend/.venv/Scripts/python.exe infra/local.py backend manage.py migrate --noinput
& ./backend/.venv/Scripts/python.exe infra/local.py backend manage.py seed_result_catalogs
& ./backend/.venv/Scripts/python.exe infra/local.py backend manage.py seed_issue_catalogs
& ./backend/.venv/Scripts/python.exe infra/local.py backend manage.py seed_correspondence_catalogs
& ./backend/.venv/Scripts/python.exe infra/local.py bootstrap --seed-staff --with-personnel-role
& ./backend/.venv/Scripts/python.exe infra/local.py backend manage.py check
```

`bootstrap` создаёт пользователя `setup`, начальные роли, отделы, должности и специальности. `--seed-staff` дополнительно создаёт десять сотрудников начального состава без персональных логинов и без выдуманного подтверждения квалификаций. Если эти сотрудники не нужны, уберите только `--seed-staff`. Демо-экспертизы эти команды не создают.

Пароль первого входа хранится **только локально**:

```powershell
Get-Content .runtime/local-login.json
```

Это новый случайный пароль, а не пароль с прежнего компьютера. Повторный `bootstrap` не сбрасывает пароль и уже отредактированные роли. После ручной смены пароля сохранённый первоначальный пароль может быть неактуален.

Важно: `setup` первоначально получает управление доступом и кадровый учёт, а **не автоматическое право видеть все экспертизы**. На исходной машине расширенные права уже назначены в её БД; свежая БД эти назначения не наследует.

## 4. Запустить бэкенд и фронтенд

Первое окно PowerShell, корень проекта:

```powershell
& ./backend/.venv/Scripts/python.exe infra/local.py backend manage.py runserver 127.0.0.1:8000 --noreload
```

Второе окно PowerShell, тот же корень:

```powershell
npm.cmd --prefix frontend run dev
```

Открыть [http://127.0.0.1:5173/](http://127.0.0.1:5173/) и войти через `setup` с локальным паролем. Vite проксирует `/api` в Django на `8000`; отдельный адрес API во фронтенде указывать не нужно. При обращении к защищённому API без входа `401/403` не означает поломку сервера.

Запускайте **по одному** Django и Vite. Порт Vite фиксирован: при занятом `5173` он завершится с ошибкой, а не незаметно уйдёт на другой порт.

## 5. Настроить роли и данные

Войдите как `setup`:

1. `/roles` — создайте нужные роли и выберите разрешения с подходящей областью: свои записи, отделы или всё учреждение. Для владельца, которому нужен полный доступ, можно создать отдельную роль с поддерживаемыми действиями в области «Учреждение».
2. `/access` — найдите сотрудника `setup` и назначьте ему созданную роль. Само создание роли никому её не назначает.
3. `/people` — проверьте сотрудников, отделы, должности, полученные специальности и обучение. Обучение не даёт допуска к назначению экспертиз. Неподтверждённый исторический статус не заменяется автоматически полученной специальностью.

Для основных сценариев нужны, в частности:

| Сценарий | Разрешения |
|---|---|
| Видеть реестр | `expertise.view` |
| Скачать реестр Excel | `expertise.view` + `expertise.export` |
| Читать и проверять Google/Excel | `imports.preview` + `imports.results.view` |
| Выбрать ссылку Google-источника | `imports.source.manage`, область «Учреждение» |
| Сопоставлять и применять перенос | `imports.reconcile` + `imports.apply` |
| Подтвердить продолжение исторической работы | `imports.history.activate` |
| Рассчитать и выгрузить 15.1 | `reports.form151.run` + `reports.form151.download` |
| Редактировать годовой план | `reports.plans.manage` |

Права действуют и на сервере. Если кнопка отсутствует или API отвечает `403`, сначала проверьте активное назначение роли и область действия на `/access`.

### Google или файл

На `/imports/source-settings` укажите свою ссылку Google-таблицы, `gid` и название листа, затем сохраните. Google используется **только для чтения**. Текущий способ чтения требует, чтобы источник был доступен серверу без интерактивного входа в Google; вход пользователя в Google в его браузере сам по себе доступа Django не даёт.

На `/expertises` нажмите «Обновить из таблицы» либо «Загрузить Excel/CSV». Сначала сохраняется снимок и показывается перечень изменений; запись в рабочие экспертизы — отдельное подтверждение. При первом переносе сопоставьте сотрудников/специальности и устраните блокирующие замечания. «Принять все» только выставляет доступные галочки: лишние можно снять до окончательного применения. Автоматического фонового обновления таблицы нет.

### Выгрузка

На `/expertises` примените фильтры и нажмите «Скачать Excel». Выгружаются **все доступные записи по фильтру**, не одна текущая страница. Первый лист повторяет исходный журнал: 28 колонок A–AB. [Описание соответствия полей](api-journal-export.md).

На `/reports` отдельно рассчитывается 15.1 и скачивается исходный отчётный бланк. Табличная выгрузка реестра не является отчётом 15.1 или полной резервной копией приложения.

## 6. Доступ с другого компьютера / по белому IP

Сама программа Vite уже запускается с `--host 0.0.0.0`. Для разрешённого адреса, например `192.168.1.50`, выполните:

```powershell
& ./backend/.venv/Scripts/python.exe infra/local.py web-hosts 192.168.1.50
```

Для белого IP подставьте реальный адрес этой машины; можно передать несколько адресов через пробел. После этого перезапустите **только Django**, чтобы применились разрешённые источники CSRF. Открывать нужно `http://ВАШ-IP:5173/`; API и БД остаются на loopback. Прокси Vite передаёт API на `127.0.0.1:8000`.

Если мешает Windows Firewall, существует узкое правило для этого web-порта. Запускается отдельно из PowerShell **от администратора**, только если требуется:

```powershell
./infra/allow-web-5173.ps1
```

При наличии роутера/NAT требуется проброс TCP `5173` на эту машину. `--host` не создаёт проброс, белый IP и HTTPS автоматически. Порты PostgreSQL и Django наружу открывать для этого сценария не требуется.

## 7. Что перенести, чтобы получить текущую рабочую базу

Клон Git содержит исходный код и пустой бланк 15.1. Он **не содержит 478 текущих экспертиз**, приложенные файлы, настроенные роли пользователей или их пароли.

Для полного переноса нужны отдельно:

- согласованный дамп PostgreSQL, включая пользователей приложения, роли, историю и журналы;
- каталог `media/` с загруженными документами;
- при необходимости локальные настройки адресов; секреты и параметры подключения на новом сервере задаются отдельно.

Дамп восстанавливают в **новую пустую целевую базу**, проверяют совместимость схемы, затем выполняют необходимые миграции. Нельзя поверх рабочей базы запускать команды удаления или `pg_restore --clean` из случайной инструкции. Папка `.runtime/postgresql-data/` не копируется «на горячую» как замена согласованному дампу.

Если нужен только перенос данных журнала, используйте импорт Google/Excel из предыдущего раздела. Документы, полная история событий и настройки доступа в 28 колонок не помещаются.

## 8. Повторный запуск, обновление и остановка

**Повторный запуск**: `db-start`, затем Django и Vite из раздела 4. Установку PostgreSQL и первичное наполнение каждый раз повторять не нужно.

**Обновление существующей установки**: сохраните резервную копию БД и `media/`, остановите Django/Vite, проверьте `git status`, затем:

```powershell
git pull --ff-only origin implementation
uv sync --directory backend --python 3.13 --locked
npm.cmd --prefix frontend ci
& ./backend/.venv/Scripts/python.exe infra/local.py backend manage.py migrate --noinput
& ./backend/.venv/Scripts/python.exe infra/local.py backend manage.py check
npm.cmd --prefix frontend run build
```

При локальных изменениях или отказе `--ff-only` сначала разберитесь с расхождением; не используйте `reset --hard`. После обновления запустите серверы снова. `build` проверяет TypeScript и собирает `frontend/dist`; сам по себе он не запускает web-сервер и не создаёт промышленную конфигурацию.

**Остановка**: `Ctrl+C` в каждом из двух окон, затем при необходимости:

```powershell
& ./backend/.venv/Scripts/python.exe infra/local.py db-stop
```

База при этом сохраняется. Не удаляйте `.runtime/`, чтобы «перезапустить» проект: там находятся данные и настройки.

## 9. Проверки и частые проблемы

```powershell
& ./backend/.venv/Scripts/python.exe infra/local.py backend manage.py check
& ./backend/.venv/Scripts/python.exe infra/local.py backend manage.py makemigrations --check --dry-run
& ./backend/.venv/Scripts/python.exe infra/local.py backend -m pytest --create-db
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run build
```

Backend-тесты создают отдельную **тестовую** PostgreSQL-базу; локальный пользователь, созданный `db-start`, имеет нужные права. Обычный запуск тестов использует штатное хеширование паролей и может занимать заметно больше времени. На внешнем PostgreSQL нужны заранее согласованные права на тестовую БД. Эти команды не являются командами импорта или сброса рабочих данных.

| Симптом | Что проверить |
|---|---|
| Нет `postgres.exe` | Структуру `.runtime/postgresql/bin`, раздел 2 |
| Нет настроек подключения / connection refused | Сначала `db-start`, затем `db-status`; запускать команды из корня |
| Нет таблиц | `migrate --noinput` через `infra/local.py backend` |
| Фронт открылся, API недоступен | Django должен работать на `127.0.0.1:8000` |
| Пустой реестр / нет нужных кнопок | Фактические данные в новой БД и права роли, а не только логин |
| CSRF при доступе с другого устройства | `web-hosts` с фактическим адресом и перезапуск Django |
| `5173` уже занят | Используйте существующий Vite либо остановите именно свой прежний запуск |
| Google-источник не читается | Ссылка, `gid`, доступ таблицы серверу; альтернативно загрузите Excel/CSV |
| `.env` не влияет на настройки | Django сам не загружает `.env`: локально параметры передаёт `infra/local.py` |

Для самостоятельного использования уже установленного PostgreSQL вместо local-runtime потребуются переменные процесса `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD`, `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` и запуск `manage.py` напрямую из `backend/`. Нельзя смешивать этот способ с `infra/local.py backend`: local-runtime подставляет собственные параметры подключения и всегда включает `DJANGO_DEBUG=1`. Промышленный профиль для такого запуска нужно готовить и проверять отдельно.
