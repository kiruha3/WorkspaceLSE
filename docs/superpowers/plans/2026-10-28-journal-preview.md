# Предпросмотр переноса журнала Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Сохранять воспроизводимый снимок первого листа XLSX/CSV с исходными ячейками, разобранными фактами и диагностикой до исторического применения.

**Architecture:** Чистый source-reader/normalizer, неизменяемый ImportBatch/ImportRow в Django и Vue рабочее место просмотра. Не создавать рабочие экспертизы на этапе предпросмотра.

**Tech Stack:** Текущие Python3.13/Django5.2/PostgreSQL17/Vue3/TS/Vite; чтениеopenpyxl>=3.1.5,<3.2, стандартныйcsv. Без новой службы.

**Spec:** `docs/superpowers/specs/2026-10-28-journal-preview-design.md`; общаяspec§§7/10. Base `ccb7a8c`.

## Global Constraints

- Текущая ais-lse/implementation, без push/merge/worktree, старыхPHP/VM и записи в Excel/Google. Исходный26OctXLSX не применять в бизнес-данные автоматически.
- `apply_available:false`; не менять Expertise/Employee/WorkClosure/MaterialIssue/Document, не создавать ложный результат импорта. Историческое применение и15.1 остаются общей целью.
- Только первый лист/3строкизаголовков;20MiB/64MiB/1000ZIPчастей/10003физстроки/128колонок. Первичные raw/formulas не перезаписывать, null не заменять0.
- institution-only imports.preview/results.view до scopedисторического применения; реальным ролям не добавлять. Учебныйфлагтолькоexplicitoptin/refusereal.
- mutationsreason/key; currentrights before cached response, filecleanup onlyownnew. Один backendpytest/одинVite0.0.0.0:5173/Django8000/PG55432.

## Review Focus

- Заготовленная нумерация A и формулы Z без номера не превращаются в сотни фиктивных регистраций; непустые C:X без B не теряются.
- Две разные B со скобками дают один текущий номер: оба конфликта видны, исторический номер не исправляет текущий.
- Потерян ответ после записи файла/снимка, затем отзыв прав или другой источник с тем же ключом: нет дубля, чужого исходника или принятия нового тела.
- Импорт содержит смешанные/нераспознанные отделы и чувствительные ячейки: institution-only не превращается в доступ по широкому чужому праву; HTML/формулы не исполняются.
- Поздний GET списка/строк и переключение снимка не показывают прежние строки под новым источником; count и summary не относятся только к странице.

### Task 1: Чтение и нормализация источника без записи

**Files:** Create backend/apps/imports/{__init__,source,normalization,types}.py; backend/apps/imports/management/{__init__,commands/__init__,commands/preview_journal}.py; tests/test_journal_source.py/tests/test_journal_normalization.py/tests/journal_samples.py. Modify backend/pyproject.toml+uv.lock, configsettings для регистрацииCLIприложения. Main docs.

**Interfaces:** SourceRow={source_row,raw,formulas,extra}; NormalizedRow addsfacts/diagnostics/normalization_complete; ParsedJournal={source_name,source_kind,date_system,source_sha256,sheet_name,parser_version,rows,summary}, all dataclasses+to_dict. `parse_journal(content:bytes,filename:str)->ParsedJournal`, `normalize_rows(rows:list[SourceRow],*,date_system:str)->list[NormalizedRow]`. `JournalSourceError(ValueError)` withuser-facingmessage. Exactfacts/summarylimitsfromspec; noDatabasequeries. CLIonlysummarydefault/--include-rows explicit.

- [x] Step1 RED tests: headerCSV/XLSX, firstsheetonly/threeheaders/B4, Aonly/Zformulaexcluded/nonemptyCwithoutBretained; UTF8BOM/semicolon/multilineCSV, badencoding/extension/ZIP/headers/empty/limits; XLSXcachedformula+raw/formulas/1904, datatypes. TestfixturesminimalOOXMLzip no realcasevalues. `pytest tests/test_journal_source.py tests/test_journal_normalization.py` expectedmissingmoduleRED.
- [x] Step2 RED normalization: statesaliasesincludingwithout_executionseparate, strictcurrentnumber/historical/duplicatecanonical, Excel60/ISO/local/1904/invaliddateorder; Pnotpickup/explicitW/Xonly/noplannegation/multipleconflictingdates; OvsU/SNDZtypos, explicit0vsblank/1СНДЗ/invalidnegative/fraction/overflow/countmismatch/currency, sourceNcomplexitynotobjects, no name/qualification inference. ExpectedmissingfunctionsRED.
- [x] Step3 implementtypes/reader/normalizer+CLI/openpyxldependency. Sourcebytesreadonly; skiptemplateonlyrowsnotrealinvalidrows. Preserveallknownfieldsanddiagnostics, no fakeend/issue.
- [x] Step4 focusedGREEN/check/migrationscheck/diff; read-onlyCLIrealfirstsheet466matchesindependentartifactanalysis/hashunchanged, stdoutsummaryonly. task-donewithfocusedtests/check; commit `feat: inspect legacy journal sources without applying records`.

### Task 2: Устойчивые снимки и API предпросмотра

**Files:** Create imports/{apps,models,policies,serializers,services,api,urls}.py+migrations; tests/test_journal_preview_api.py/test_journal_preview_concurrency.py. Modify configurls/settings/accounts catalog/views/template+workflowdemo/infra, docs/api-journal-preview.md/docs/verification-journal-preview.md.

**Interfaces:** ConsumeTask1ParsedJournal.to_dict andpureparser. `create_preview(*,actor,upload,reason,key)->{id,batch_id}` minimalreceipt; `batch_data(batch,user)->BatchDTO`, `row_data(row)->RowDTO` exactspec. institution-onlybothrightsforcreate, resultsviewforreads. GETlist/detail/rows/source andPOSTpreview; filterssearch/severityerror|warning|info/stateknownenum, exactbatchnoapply. Batchuploaded_byUser; filesprotectedserveonlyafterrights. preservefilebytes/writes/auditatomicfail.

- [x] Step1 RED tests exactAPI201/DTO/storedrows/sourcebytes/4existingbusinesstablecountsunchanged; no keys/reason/forbiddenfields400, samekeyfreshsameid/audit/file1, differentbody409, currentview/previewrevocation403, departmentnotgrantinstitution; paginatedfilters/count/globalrawsummary, malformedfilefailednoDB/storage/auditreceipt, auditfailurecleansnewfileonly; two simultaneoussamekeyonebatch/file/audit. Runnewtests expected404RED.
- [x] Step2 implementmodels/migration/services/API/currentrights+capabilityjournal_import_previewonlyread/createready; no apply route. Addtwoinitialtemplatepermissionsonlynewroles, explicit--enable-import-previewDEMOclerk/refusereal/preserveedits. Fullbackendregressionsoneprocess.
- [x] Step3 focusedthenfullbackend/check/migrations/diff/task-done; commit `feat: store immutable journal import previews`.

### Task 3: Vue рабочее место и приёмка снимка

**Files:** Create frontend/src/api/imports.ts, modules/imports/{ImportPreviewsPage,ImportPreviewPage,ImportUpload,ImportRowDetails}.vue+tests. Modify types/session/router/App/Home, README/docs/api+verification. Main runtimeonly.

**Interfaces:** ConsumeTask2exactBatchDTO/RowDTO/endpoints. Moduleflag+imports.results.viewnav, imports.previewform. File/reason/keybeforePOST, normalizedretryoriginalbodykey/dirtyguard, safeURLfiltersreturn/cancelLatestGET. Rowdetailsraw/facts/diagnosticswithoutv-html; sourceURLonlyserverpath. Neverrenderfakeapplysuccess.

- [x] Step1 RED components exactmultipart/key/reason, pending/success/servererrors/fileloss403409/changedfilekey/dirtyguard; module/actiongates, URLsearch/severity/statepagination/counts, rowdetailsandunknowns, oldGETdiscardafterroutechange. ExpectedmissingcomponentsRED.
- [x] Step2 implementexistingfullwidthdesignwithclearpreviewnotappliedandnextreconciliationcallout; no additionalNodeprocesses.
- [x] Step3 fullfrontend/type/build, actualIABDEMOcsvupload→list→detail/filter→rowraw/facts→download, repeatedreadonlyscope/no mutationtoexistingworks. CurrentownerXLSXonlyCLIuntilfreshsourceconfirmed.
- [x] Step4 onefreshwhole-slicereviewfromccb7a8c, mainregradeoneImportant/CriticalTDDfixpass/fullgates; recordrulings/minors, keepbranch/nopush, taskdone. Overallgoalactiveforhistoricalapply/reports/documents/policies.

Self-review: Task1producesalltype/parserfieldsTask2persists; Task2ownsfile/rights/capability/CLIappregistration beforeTask3consumes. FiveReviewFocusinputs coveredbyTask1orTask2/3tests. No unownedapplyorreportfunction; explicitlynextplanratherthanunimplementedpromiseinUI. Onefinalreview/inlineexecutionpreservedperownerinstructiontocontinue.
