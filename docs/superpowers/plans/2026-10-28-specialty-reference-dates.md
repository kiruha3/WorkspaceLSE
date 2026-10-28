# Specialty reference dates implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline. Steps use checkbox syntax.

**Goal:** Учёт полученной специальности без обязательного подтверждения, со справочными датами.
**Architecture:** Существующая модель/права, явный статус, nullable metadata PATCH и общий eligibility без временных ограничений; текущая карточка Vue.
**Tech Stack:** Existing Django/PostgreSQL/Vue3/TypeScript, no dependencies.
**Spec:** docs/superpowers/specs/2026-10-28-specialty-reference-dates-design.md

## Global Constraints

Стажёра не назначать; unknown_legacy не переводить автоматически. Без миграций/массовых правок/новыхgrants/PHP/Googlewrites/push/merge/worktree. Даты и основание необязательны, но невозможная пара дат400. Старые assignmentsnapshots/472реальные/8demo/файлы/996reportcells сохраняются. Ранее подтверждённый автономный inline режим и один finalreview. Не повторять отклонённое удаление .superpowers.

## Review Focus

- PATCH с одним полем проверяет итоговую пару дат, не стирает пропущенные поля и не меняет статус.
- Только training.manage не позволяет создать/изменить qualified, а только qualify позволяет добавить полученную без training.manage.
- Неполные старые даты не становятся обязательными и не влияют на candidate/assignment; снимок старого назначения неизменен после правки.
- Открытый metadata editor не считает исходный basis/даты несохранённой правкой;403/409 сохраняют ввод и ФИО.
- Create/change квалификации не раскрывают чужих сотрудников и не делают historicalunknown полученной автоматически.

### Task 1: Specialty status and reference-date pipeline

**Files:** backend/apps/personnel/{serializers.py,api.py,services.py}, backend/config/urls.py, backend/apps/accounts/{catalog.py,serializers.py}, backend/tests/{test_specialty_reference_dates.py,test_qualifications.py,test_personnel_api.py,test_expert_assignments.py}, frontend/src/modules/people/{EmployeePanel.vue,EmployeePanel.test.ts}, docs/verification/specialty-reference-dates-2026-10-28.md, current specification/access-control amendment.
**Interfaces:** eligibility signature unchanged; POSTspecialties accepts qualified_at/statusqualified/basisoptional; POSTqualify basisoptional; PATCHspecialty {expected_version,training_started_at?,qualified_at?,valid_until?,basis?}->SpecialtyOutput unchanged. No DTO/schema change. Metadata audit employee.specialty.update.

- [x] RED backend test_specialty_reference_dates: createqualified withouttrainingright/dates/basis201, missingqualifiedright403, blank/omittedbasisqualify200, infofuture/expired dateseligible+actualassignment200, training/unknown/inactive remain400, PATCH metadata200/version+audit/snapshotpreserved, omittedfields retained/clearNone, badmergedpair400/stale409/forbidden403/extras400/noorphan. Run newfile serial, expected400/404/eligibilityfalse. Implement minimal backend and update only old tests whose expected date/basis policy intentionally changed; run newfile+test_personnel_api/test_qualifications/test_expert_assignments, expectedallgreen.
- [x] RED Vue directqualifiedcreate/nullbasis/noextra confirmation, trainingonlycantselectqualified, qualifyonlycancreate+readoptions, editexistingdates/clear/statusunchanged/unsavedname/dirtyinitial/403409. Update existing mandatorybasis test to positive and keep other metadata tests. Implement UI/copy and permission title, run EmployeePanel tests then fullfrontend/typecheck/build, expectedgreen.
- [x] Commit verified implementation; one fresh finalreview on BASErange/spec/ledger. Important fixes oneRED→GREENpass, no rereview/minorpolish. Fullbackend serial +frontend/check/drift/diff expectedgreen. Do not rerun unchanged819/307 baseline before implementation.
- [x] Live readonly checkpoint/existingforms/noqualificationwrites/newgrants, restart oneDjango, realbrowser optionalfields/choices/screenshot, compare alloldbusiness/files/996cells+records, document boundaries and currentpolicy amendment. Commit; task-done newfile+personnel_api+qualifications+expert_assignments, closeplan/fullgoalactive.

## Закрытие среза

Реализация3c4d79b, исправление83c7a0f, протоколfbb581c. После одного независимого ревью и одного RED→GREEN прохода: backend840/840, frontend312/312, typecheck/build/check/drift/diff успешны. Закрывающий task-done45/45,30.30s. Liveформы/HTTP и перезапуск проверены, квалификации/права/работы не изменены. Две параллельные правки словаря владельцем явно сопоставлены, не откатывались; файлы13 и996ячеек+происхождение прежние. Полный протокол: docs/verification/specialty-reference-dates-2026-10-28.md.

Ветка implementation остаётся локально безpush/merge; outputs/ и ранее запрещённое к удалению .superpowers не тронуты. Общая цель остаётся активной. Следующий срез — утверждённые комплекты выдачи4/6 и счёт для платной работы с явным учётом платности, без угадывания по категории/сумме.
