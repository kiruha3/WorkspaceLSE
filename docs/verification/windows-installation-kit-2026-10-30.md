# Установка и публикация 30.10.2026

Поручение владельца: опубликовать текущую версию в `master`, дополнить установку с нуля, предусмотреть папку с реальными установщиками и одну команду установки. Выбран перенос журнала через Google-таблицу, без дампа.

## Проверки приложения

- Frontend: **518 тестов / 52 файла**, production build и TypeScript — успешно.
- В двух существующих тестах навигации заменены селекторы прежней сетки и уточнена область основного меню: локальная навигация настроек теперь тоже семантический `nav`.
- Backend: **1133 теста**, отдельная заново созданная тестовая PostgreSQL БД — успешно. Для полного прогона только в тестовом процессе использован MD5PasswordHasher; настройки приложения не менялись.
- Начальная настройка, сброс пароля и настоящий HTTP-вход отдельно проверены штатным хешированием: **16 тестов**, успешно.
- `manage.py check`, `makemigrations --check --dry-run`, `uv lock --check`, `git diff --check` — успешно.
- Сохраняется прежнее предупреждение сборщика о JS-чанке более 500 КБ.

Воспроизведение полного тестового прогона с быстрым тестовым хешером из корня:

```powershell
& ./backend/.venv/Scripts/python.exe infra/local.py backend -c "import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings'); from django.conf import settings; settings.PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher']; import pytest; raise SystemExit(pytest.main(['--create-db']))"
& ./backend/.venv/Scripts/python.exe infra/local.py backend -m pytest --reuse-db tests/test_bootstrap.py tests/test_account_password_reset.py tests/test_http_identity.py
```

Обычный полный запуск без этого ускорения описан в RUNNING.md. Его первый прогон остановлен после части тестов ради уменьшения времени повторного хеширования; результат 1133 относится к завершённому быстрому прогону.

## Установочный набор

- Пять файлов (Git, Python, Node, uv, PostgreSQL), всего **164.7 MiB**; SHA-256 проверены по `installation/packages.json`.
- Синтаксис всех PowerShell-скриптов и не изменяющий окружение `Install.ps1 -CheckOnly` проверены.
- Изолированная папка исходников без `.venv`, `node_modules` и схемы БД прошла `Install.ps1` до сообщения об успешном окончании.
- Для проверки использован отдельный PostgreSQL на **55433**, существующие Django/Vite и рабочий PostgreSQL не останавливались.
- В свежей БД: `setup` с паролем, **11 сотрудников**, **4 способа выдачи**, **0 экспертиз**.
- Тестовый PostgreSQL остановлен; отсутствие слушателя на 55433 проверено.
- Проверка повторной свежей установки поверх действующей базы завершилась ожидаемым отказом до установки пакетов или изменения данных.
- Уже совместимые Git/Node/Python использованы повторно. Установка EXE/MSI в чистую Windows в этой проверке не выполнялась; это не тест отдельной новой ОС.

Локальные логи находятся в игнорируемом `.runtime/`: `release-frontend-tests.log`, `release-backend-fast-tests.log`, `release-auth-default-tests.log`, `installation-download.log`, `installation-smoke.log`, `installation-existing-guard.log`.

Бинарные установщики и готовый ZIP исключены из Git. Скрипт набора берёт исходники через `git archive` и добавляет только пять установочных файлов; рабочие данные и пароли не включаются. Первичное получение Python/npm-библиотек требует Интернета.
