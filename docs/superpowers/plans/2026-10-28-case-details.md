# Case Details Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline. Steps use checkbox syntax.

**Goal:** Настраивать типы органов, заполнять фактические сведения дела и3214 в карточке и получать из них15.1.
**Architecture:** AuthorityType reference +generic catalog UI; WorkCaseDetails1:1 and immutable revisions; shared scoped atomic command; registry oneSELECT with explicit legacy fallback.
**Tech Stack:** existing Django/PostgreSQL/Vue3/TypeScript/Vitest, no new packages.
**Spec:** docs/superpowers/specs/2026-10-28-case-details-design.md

## Global Constraints

implementation in place. Номера/состояния/фактические отделы/люди/даты/исходники/права неизменны. Google read-only, PHP не трогать. Без live grants/push/merge/worktree/дополнительных серверов. Additive migration послеbackup; реальных472не менять. Только существующийявныйdemo и максимум1новыйдемодокумент/1демосправочник дляQA.

## Review Focus

- Явно очищенный тип/3214 не восстанавливаются из истории; пользовательское «нет» не превращается в неизвестное или0 по умолчанию.
- Поздний ответ/неопределённый запрос/409 после потери ответа сохраняют старые path/body/key и позволяют явное восстановление, без дубля документов/редакций.
- Каталоговая деактивация/изменение группы и отзыв прав между запросами/replay не нарушают прошлые ссылки и не открывают запрещённые документы/историю.
- Профиль исторической работы защищён от источника даже при совпадающих старых scalar-значениях; конкурирующая команда победила→409 без частичных данных.
- Тип органа и3214 не меняют категорию номера/дату/закрытие/выдачу; registry остаётся одним согласованным SELECT, новый typed-null не затирает известное нулём.

### Task 1: Case details, manageable authority catalogue and report projection

**Files:** references/models.py, new authority_seeds.py +migrations0005; references/api.py/newcommands.py,newhistory.py; config/urls.py. expertises/models.py +migration0009; new case_details.py/case_serializers.py/case_api.py; api.py/serializers.py/urls.py; imports/updates.py; reports/registry.py/calculation.py/reason_columns.py. Frontend api/types.ts/newreferences.ts, new modules/references/{ReferencesPage.vue,ReferenceEditor.vue,ReferenceHistory.vue,catalogs.ts}, new expertises/{CaseDetailsPanel.vue,CaseDetailsHistory.vue}; ExpertisePage.vue, ReportsPage.vue, router.ts, App.vue, HomePage.vue. Tests backend/tests/test_case_details.py,test_case_details_concurrency.py,test_reference_commands.py, frontend case/catalogue/navigation tests; docs/verification/case-details-2026-10-28.md.

**Interfaces:** WorkCaseDetails(expertise,authority_type,authority_name,official,contact,case_number,case_description,basis_text,inventory,questions_text,decree3214,decree_document,decree_basis,created_by,timestamps); CaseDetailsRevision(details,number,actor,reason,before,after,created_at). `save_case_details(actor,expertise_id,data,key,payload)->{id,expertise_id}`; `case_details_output(work,user,scopes)->DTO`; `case_options(work)->{authority_types,initial_authority_type_id,retained_authority_type_ids}`. Existing ReferenceDTO gains optional report_group. Reference command helpers preserve optional-key backwards compatibility. CaseDetails POST complete payload as spec. No public payload controls report_group directly outside references.manage.

- [x] Backend RED: catalogue authority grouping/strict extras/history/idempotent create+patch/revocation/unique competition/inactive department replay; case fields/options/source fallback/scopedown+dept+inst/closed+issued/unknown False/required evidence/type/document scope/inactive restoration/version+replay/atomic audit/source guard/identity preservation. Hand-derived native report authority shifts and P11/P108 zero/one/null, unchanged journal, literal XLSX P108, fingerprint409, oneSELECT. Run `backend/.venv/Scripts/python.exe infra/local.py backend -m pytest tests/test_reference_commands.py tests/test_case_details.py -q`; Expected missing routes/models/fields.
- [x] Implement focused models/serializers/services/API/catalogue projection and mechanical additive migrations. Same command plus test_form151_registry.py/test_journal_updates.py →green. Concurrency cases: samekey one receipt; material-lock waiting then stale conflict with concurrent source; unique-code race returns defined error; no simultaneous DB pytest.
- [x] Vue RED: generic catalog read-only/manage/search/create subtype fields/deactivate/history, server errors/stale+replay/late response/dirty leave. Case current fields vs source, authority mapping,3214 false/null/evidence existing+new, payload/version/path/uncertainretry/403/409/routechange, readonly history after activation/issue. Navigation registry report without imports and references by permission, no stale placeholder. Implement components; focused frontend then full/build →green.
- [x] One fresh whole-slice reviewer against spec/plan/ledger. Regrade by user effect; Important one RED→GREEN fix pass, fullbackend/frontend/build/check/drift/diff. Expected no unresolved Critical/Important, all suites green. Keep local branch, no second review.
- [x] Backup, old-field/access/source checkpoints; migrate, verify only new table/defaults/seeds. Real browser existingdemo: case fields+catalogue demo create/deactivate+document+reload, allowed and denied roles, report downloadable. Verify original804cells unchanged +12newcells unknown rather thanfalse,816total, 9sheets/template untouched, actual downloadZIP equal. Commit, task-done exact task command plus concurrency; document remaining process requirements, goal active.
