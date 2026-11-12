# Django Admin Implementation Plan

> Исполнение: последовательно в текущем стенде; пользователь поручил подключение существующей админки. Спецификация: `docs/superpowers/specs/2026-11-09-django-admin-design.md`.

**Цель:** рабочий `/admin/` с поиском, аудитом и сохранением доменных команд.

**Архитектура:** собственный AdminSite, стандартные Django templates/messages/staticfiles, адаптер справочников и UserAdmin; прочие модели только для просмотра.

**Стек:** существующие Django 5.2, PostgreSQL, Vite, pytest-django. Новые зависимости не нужны.

## Задачи

- [x] Написать и запустить падающие интеграционные тесты `backend/tests/test_django_admin.py`: доступ, поиск, запрещённые POST, команды справочников, устаревшая версия, аудит учёток и команда доступа.
- [x] Подключить настройки и маршрут в `backend/config/settings.py`, `backend/config/urls.py`; реализовать панель в `backend/config/admin.py`, общий просмотр в `backend/apps/common/admin.py`, адаптеры в `backend/apps/accounts/admin.py`, `backend/apps/references/admin.py`, шаблон в `backend/templates/admin/ais_change_form.html`.
- [x] Реализовать `backend/apps/accounts/management/commands/django_admin_access.py`; не менять пароль, роли АИС или начальный bootstrap.
- [x] Добавить `/admin` и `/static` в `frontend/vite.config.ts`, проверить фактический ответ прокси и CSS.
- [x] Пройти целевые и общие тесты backend/frontend; `manage.py check`, `makemigrations --check --dry-run`; применить штатные миграции Django admin и включить setup на текущем стенде.
- [x] Дополнить `docs/RUNNING.md`: локальная и сетевая ссылка, обновление, выдача доступа, назначение и ограничения служебной панели.

## Особые проверки

Нет повышения прав при bootstrap; Django-superuser не обходит роли API; нельзя POST-ом изменить завершённую работу или историю; старая форма справочника не затирает новое значение; пароли и хеши не попадают в аудит; административные ресурсы действительно доступны на порту 5173.
