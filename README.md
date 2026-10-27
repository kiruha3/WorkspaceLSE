# АИС ФГБУ Абаканская ЛСЭ

Каталог нового самостоятельного проекта: Django backend и Vue frontend в одном репозитории внутри `E:/VLSE`.

Реализован первый рабочий срез: Django API, PostgreSQL и Vue с персональным входом, редактируемыми ролями, сотрудниками, должностями и специальностями. Репозиторий самостоятельный, ветка `implementation`; удалённого репозитория, push и публикации нет.

Структура: `backend/`, `frontend/`, `infra/`, `docs/`. Исходные проекты `../web-vue`, `../labalse` и `../labalse_front` сохраняются без переноса и удаления.

Согласованный путь сначала проверяется в [локальном кликабельном макете](../web-vue/docs/mockups/expertise-workflow-v1/prototype/index.html). Его действия учебные и не заменяют серверный учёт.

## Что уже работает

- Вход по Django session с CSRF, выход, немедленное применение отзыва прав на следующем запросе.
- Роли с отдельной областью каждого действия; назначение и прекращение роли сотрудника, даты и аудит.
- Сотрудник с несколькими должностями и специальностями; обучение отдельно от полученной квалификации.
- Явное подтверждение специальности по праву; обучение не даёт допуска к назначению на экспертизу. Получение можно подтвердить с основанием без известной даты; дата остаётся пустой, известный срок действия проверяется.
- Создание персонального входа без автоматической выдачи ролей; блокировка входа отдельно от активности сотрудника.
- Добавление и деактивация справочных отделов, должностей, специальностей через API.
- Проверка версии при изменении роли, сотрудника, квалификации и кадровых назначений.

Полный путь экспертизы, файлы, переписка, выдача и серверный отчёт 15.1 ещё не реализованы в новом приложении. Старый калькулятор/данные не считаются уже перенесённым backend. Общая цель остаётся незавершённой.

## Локальный запуск без VM и Docker

Требуются Python 3.13/uv, Node.js/npm и переносимые PostgreSQL 17 binaries в `.runtime/postgresql/{bin,lib,share}`. Использованный Windows runtime: `io.zonky.test.postgres:embedded-postgres-binaries-windows-amd64:17.11.0` из Maven Central; PostgreSQL 17.11. Архив содержит TXZ с указанными каталогами. Рабочие файлы старых проектов не используются.

Из корня проекта:

```powershell
uv sync --directory backend --python 3.13
& ./backend/.venv/Scripts/python.exe infra/local.py db-start
& ./backend/.venv/Scripts/python.exe infra/local.py backend manage.py migrate --noinput
& ./backend/.venv/Scripts/python.exe infra/local.py bootstrap --seed-staff --with-personnel-role
& ./backend/.venv/Scripts/python.exe infra/local.py backend manage.py runserver 127.0.0.1:8000 --noreload
```

В другом терминале, из `frontend/`:

```powershell
npm.cmd ci
npm.cmd run dev
```

Адрес: http://127.0.0.1:5173/; страницы `/people`, `/roles`, `/access`. Только один Vite на `0.0.0.0:5173`, прокси `/api` → Django на 8000. Django и PostgreSQL слушают **только loopback**, БД — порт 55432. Это окружение разработки, не готовая производственная конфигурация. Доступ по внешнему адресу зависит от сетевого маршрута и проброса 5173 на эту машину.

Для входа по адресу другого устройства сохраните разрешённые web-hosts и перезапустите Django: `infra/local.py web-hosts <белый-IP> <локальный-IP>`. Команда запускается тем же Python, что выше. При необходимости разрешения Windows существует `infra/allow-web-5173.ps1` для явного запуска из PowerShell от администратора; он не отключает firewall и не открывает БД.

Логин и случайный пароль настройки записываются в игнорируемый `.runtime/local-login.json`. Подключение к БД — отдельно в `.runtime/postgresql-connection.json`. Не публиковать эти файлы. `--with-personnel-role` явно совмещает администратора доступа и кадровый учёт для проверки; право читать экспертизы из этого не следует. Десять сотрудников предзаполнены без вымышленных логинов и ролей, специальности — `unknown_legacy`, без выдуманных дат получения.

Повторный bootstrap сохраняет изменённые роли, пароль и существующие записи. Он не является командой сброса или восстановления. Для другого начального пользователя: `bootstrap_access --username ... --full-name ...`, пароль через `AIS_BOOTSTRAP_PASSWORD` или интерактивный ввод. Остановить только эту БД: `infra/local.py db-stop`; данные остаются на месте.

## Проверки

```powershell
& ./backend/.venv/Scripts/python.exe infra/local.py backend -m pytest
& ./backend/.venv/Scripts/python.exe infra/local.py backend manage.py check
& ./backend/.venv/Scripts/python.exe infra/local.py backend manage.py makemigrations --check --dry-run
```

Из `frontend/`: `npm.cmd test`, `npm.cmd run typecheck`, `npm.cmd run build`. Backend tests используют отдельную тестовую PostgreSQL БД, включая сценарий настоящего HTTP-входа, создания роли, назначения и повторного чтения.

Спецификации: [система](docs/specification.md), [доступ](docs/access-control.md), [начальный состав и таблицы](docs/initial-data-and-tables.md), [применимые паттерны](docs/reference-patterns.md).
