# Expertise card layout implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox syntax for tracking.

**Goal:** Реализовать выбранный владельцем вариант А без изменения данных и бизнес-действий.

**Architecture:** Прежние панели остаются в ExpertisePage, сгруппированные в сохраняемые v-show вкладки. ExpertiseOverview — только чтение существующего Expertise. Локальные стили карточки, без зависимостей и backend edits.

**Tech Stack:** Existing Vue 3, TypeScript, Vue Router, Vitest, Vue Test Utils.

**Spec:** docs/superpowers/specs/2026-10-29-expertise-card-layout-design.md

## Global constraints

- Контрольный коммит 100ee76 создан до обновления; без push/merge/worktree.
- Новые поля и бизнес-команды запрещены; прежние API/allowed_actions/can_edit/dirty guards сохраняются.
- Не менять backend, живые данные, права, .superpowers соседних планов и outputs.
- Сохранять неизвестное отдельно от нуля; старые исполнители/окончания/выдачи не превращать в нативные факты.
- Существующие два RED флага фиксируются отдельно, не исправляются и не скрываются.

## Review focus

- Переключение скрытых панелей не стирает незавершённую форму/команду.
- Нативная работа с датой черновика не показывается как законченная/выданная.
- Переход между UUID не оставляет на экране исходные данные или выбранный раздел.
- Отзыв клиентской доступности раздела не оставляет видимой скрытую по правам панель.
- Узкая ширина и управление вкладками с клавиатуры не лишают доступа к разделам.

### Task 1: Перекомпоновка и проверка

**Files:** Create frontend/src/modules/expertises/ExpertiseOverview.vue and ExpertiseSummary.vue; Modify frontend/src/modules/expertises/ExpertisePage.vue; Test frontend/src/modules/expertises/ExpertisePage.test.ts and new ExpertiseCardLayout.test.ts. Стили scoped в компонентах. Документ проверки docs/verification/expertise-card-layout-2026-10-29.md.

**Interfaces:** Consumes existing Expertise DTO and child component events; produces only local selected tab and readonly summary, no new network payload.

- [x] Написать и увидеть RED: обзор по умолчанию, исторические источники/ноль/null, переключение без записи/потери формы, сброс UUID, сохранение серверных ограничений, отзыв доступности и клавиатура.
- [x] Реализовать Overview и вкладки с v-show; не менять формы и команды.
- [x] Прогнать новый набор и существующие компонентные сценарии. Старые тесты действий открывают соответствующую вкладку перед действием, без изменения ожиданий команд.
- [x] Полный npm test: допустимы только 2 именованных исходных RED. npm run typecheck и npm run build должны вернуть exit0.
- [x] Проверить реальную карточку в браузере без записи, desktop и narrow layout; сохранить снимки. Сверить доступность всех прежних разделов и возврат в реестр.
- [x] Один свежий review; важные замечания исправить RED→GREEN, без повторного review.
- [x] git diff --check, документ фактических результатов и отдельный локальный коммит обновления, без push.
