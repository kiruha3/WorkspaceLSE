# Work document vault implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline. Steps use checkbox syntax.

**Goal:** Единый архив работы с общими документами, сохранёнными версиями, URL и разовой загрузкой выбранной папки.
**Architecture:** Existing Document/FileVersion plus soft-detached WorkDocumentLink, aggregate read projection and dedicated Vue route. No server URL download or disk scanning.
**Tech Stack:** Existing Django/PostgreSQL/Vue3/TypeScript, no new dependencies.
**Spec:** docs/superpowers/specs/2026-10-28-work-document-vault-design.md

## Global Constraints

Сохранить старые принятые файлы/снимки и старые успешные keys. Никаких копий на каждый номер/удаления файла приdetach/авторизации по строке должности. Безавтогрантов/реальныхсвязей/файлов/PHP/Googlewrites/push/merge/newworktree. URLs — толькоHTTP/HTTPS безавтоfetch; папка только явныйbrowserвыбор, не постоянный доступ сервера. URLбезкопии не файл/неоригинал для подтверждения. documents0006 additive/пустые новые поля;66oldtables(originalcolumns)/13files/472real8demo/996cells+records unchanged. ОдинDBpytest. Существующие outputs/.superpowers сохраняются. Officepreview/managedfolder/documentsupplements-replaces/allrole/production/officialreport остаются общей целью, не объявлять выполненными этой частью.

## Review Focus

- SharedDocument/бывший исполнитель/детач: снимается только одна дополнительная связь, не чужой файл/другая работа/принятая связь, не остаётся bypass через историю.
- Принятый файлV1/null при существующейV2 не подменяется latest в объединённом архиве; недоступная переписка не выдаёт контекст/номера.
- Новое external_link не проходит старые guards uploaded_copy как мнимый бумажный оригинал; хранение URL не выполняет сетевых запросов.
- Новый relative_path не используется для storage, не допускает traversal/drive, не ломает повтор старых upload keys; новые links не дают documents.upload.
- Папка/несколькофайлов: частичный успех и lostresponse/403/409 не дают дублей, потери выбора/версии или изменений захваченного packet от позднего GET.

### Task 1: Typed sources, associations and unified archive API

**Files:** backend/apps/documents/{models.py,migrations/0006_work_document_vault.py,sources.py,serializers.py,services.py,policies.py,work_library.py,work_commands.py,work_api.py,urls.py}; backend/apps/accounts/{catalog.py,views.py}; existingguards backend/apps/{intake/services.py,expertises/production.py,expertises/case_details.py,expertises/classification.py,expertises/timing.py,reports/plans.py}; backend/tests/{test_work_document_vault.py,test_document_sources.py,test_http_work_documents.py}.
**Interfaces:** WorkDocumentLink model and sources constants as spec; Document.source_url+FileVersion.relative_path; add_file_version(...,relative_path='') unchanged callers; library_data(work,user,query)->context+Page<DocumentEntry>; document origins accepted_version_id explicitpresence; can_link_work(user,action,work,scopes) uses declared own semantics. link_document/detach_document(actor,work_id,data,key,payload) locked work/version/audit/execute_once; new docs.link/unlink permissions no grants; /me capability work_documents. API paths/body exactspec, no changes to current expertise/result/issue responses except newdocument fields.

- [ ] Write RED HTTP tests for404library/routes/source400: paperbasis+acceptedresultV1/V2 and selectedorigins; explicitsharedDoc two workIDs/detachone/exactfilehash/remainingread, restrictedworkhistory and upload403, duplicate/foreign/stale/currentrightsreplay rollback; sourceURL syntax andnoautofetch, copyupload/relative_path andoldpayloadrepeat. Run serial newfiles (`infra/local.py backend -m pytest tests/test_work_document_vault.py tests/test_document_sources.py tests/test_http_work_documents.py -o addopts= -q`), expected404/unsupportedsource. Implement minimal models/schema/sources/projection/commands/currentpolicy/API. Then RED consumer-guard tests after newsource accepted: intake/sрок/3214-р/classification/timing/plan rejectno-file URL, completion/letters/issue existingguards retained. Centralize archiveevidence predicate if needed and makeallgreen without loosening paper/versions. Regression focused existing documents/basis/receipts/result/issue/plan/case/timing. Expectedallgreen. Commit product; task-done newbackendfiles afterreadactualresults, no fullbaseline867rerun beforechange.

### Task 2: Usable archive and source/folder upload

**Files:** frontend/src/api/{types.ts,workDocuments.ts}; frontend/src/stores/session.ts; frontend/src/router.ts; frontend/src/modules/expertises/ExpertisePage.vue; frontend/src/modules/documents/{WorkDocumentsPage.vue,DocumentSourceForm.vue,DocumentBatchUpload.vue,DocumentVersionUpload.vue,WorkDocuments.test.ts}; frontend/src/shared/{BasisDocumentForm.vue,BasisPreview.vue,BasisDocumentForm.test.ts,BasisPreview.test.ts}; docs/{specification.md,api-documents.md,verification/work-document-vault-2026-10-28.md}.
**Interfaces:** consumesTask1 DTO/permission/capability/paths. Newroute /expertises/:id/documents, typedreturnURL. Commonbasis helper optional allowExternalSource/initialFile props keepdefaultoldbody, source_urlconditional, FileVersion.relative_pathfromwebkitRelativePathonlynonempty. BasisPreview externalexplicitload/pinned origin handling, new case_material label. DocumentBatchUpload max100, serialized per-file metadata/file/link stable keys, confirmed success skip, retainedfailedrows. Library read refresh never overwrites packet, expectedworkversion captures beforeupload, explicitacceptafter409.

- [ ] RED realVue newpage list/read-only/scopes/search/return/acceptedV1/null withV2, selectionexistingDoc, paper/upload/URL creation, explicitpreviewonly/noautofetch; twofolderfiles paths/progress/partialfailure/retry/no duplicateDoc/upload/link,403409/lateGET/dirty. Oldhelperpayload unchanged unlessnewsource/path used. Run focusednew+shared tests, expectedmissingroute/fields. Implement components/DTO/sharedextensions, then focused/fullfrontend/typecheck/build expectedgreen. Commit implementation, task-done new+sharedfrontendtests.
- [ ] Onefreshfinalreview BASEbeforeTask1throughHEAD/spec/ledger/ReviewFocus; ImportantoneRED→GREENpass/no rereview, deferredMinorsrecord. Fullbackendoneprocess +frontend/check/drift/diff, expectedgreen. Beforelive take66oldtable/13file/996cellssnapshot+backup; applyONLYdocuments0006, originalcolumns unchanged/newfieldsblank/newlinks0/no grants. OneDjangorestart/readHTTP/UI/screenshot/no successfulrealwrites; documentevidence+rulings/limits. Closeplan onlyafteractualchecks; fullgoalactive.
