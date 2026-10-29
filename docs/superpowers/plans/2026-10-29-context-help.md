# Context Help Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Убрать справочные абзацы карточки под доступные подсказки «?».
**Architecture:** Общий HelpTip с Teleport и ограничением положения экраном; интеграция только справочного текста, без изменения команд.
**Tech Stack:** Vue 3/TypeScript, Vitest.
**Spec:** docs/superpowers/specs/2026-10-29-context-help-design.md

## Global Constraints

Сохранить фактические сведения и текущие сообщения об ошибках, блокировках и подтверждениях. Не менять права, API, обязательность файлов и рабочие записи. Не трогать две существующие правки напоминаний. Без push.

## Review Focus

- Подсказка доступна мышью, клавиатурой и нажатием; Escape закрывает.
- Перевод указателя на текст не скрывает его; длинный текст помещается в экран.
- Кнопка внутри формы/подписи не отправляет форму и не переключает поле.
- Текущая ошибка или отсутствие файла не исчезают под видом справки.
- Teleport и обработчики очищаются при уходе с вкладки.

## Task 1: Общая подсказка и карточка экспертизы

**Files:** shared/ui/HelpTip.vue и HelpTip.test.ts; модули expertises (без IncompleteExpertises), BasisDocumentForm.vue, BasisPreview.vue, ExpertiseIssueStatus.vue; DocumentBatchUpload.vue и DocumentVersionUpload.vue как формы документов этой же карточки; соответствующие существующие тесты.
**Interfaces:** HelpTip принимает label:string и содержимое через slot; не создаёт команд/сохранений. Родители сохраняют прежние поля и обработчики.

- [x] Написать тесты скрытого начального состояния, hover/focus/tap, перехода к тексту, Escape/outside, положения у края и очистки; RED отсутствующего компонента.
- [x] Реализовать HelpTip; 6 исходных тестов PASS. Дополнительно обнаружен уход фокуса/клик без pointerdown, RED→GREEN после подключения focusin/click.
- [x] Заменить справочные абзацы значками, сохранить текущие значения/ошибки; интеграционный RED подтверждён. Полнота исторических приостановок оставлена видимой как факт.
- [x] Полный frontend после всех исправлений: 465 PASS, 48 файлов; TypeScript/build PASS. Независимое ревью и браузерная проверка без сохранения данных завершены.
- [x] Локальный scoped commit подготовлен; README описывает подсказки. Без push.
