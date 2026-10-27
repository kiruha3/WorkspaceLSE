# Перенос журнала в рабочие записи Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Читать выбранный Google-источник, явно сопоставлять строки, переносить подтверждённые записи в общий реестр и подтверждать продолжение исторической работы без фиктивных документов/дат/допусков.

**Architecture:** Existing immutable ImportBatch/Row → saved versioned ImportSelection → atomic ImportApplication → core Expertise/HistoricalWork. Google only configured CSV read. Historical facts remain typed, native workflow retains validators; activation explicitly connects the two.

**Tech Stack:** Existing Python3.13/Django5.2/PostgreSQL17/Vue3/TS/Vite/openpyxl3.1, standard urllib; no new dependency/service.

**Spec:** `docs/superpowers/specs/2026-10-28-journal-application-design.md`; general spec§§5/7/10. BASE `b35d017`.

## Global Constraints

- Current ais-lse/implementation, no push/merge/worktree, no PHP/VM/XLSX/Google writes. Current Google source only;472 is observed count, not a hardcoded ceiling.
- Only configured spreadsheet_id/gid/sheet_name, HTTPS CSV read timeout20с,20MiB+1 bound; no OAuth cookies, publishing or sharing change.
- Never invent documents, dates, historical assignment events or qualified status. Unknown remains null; native requirements remain enforced.
- Institution-only imports.reconcile/imports.apply/imports.history.activate plus existing source read; real roles not expanded. Explicit DEMO-only opt-in/refusereal/preserveedits.
- Mutations reason/key/currentrights/version; one backendpytest, one Vite0.0.0.0:5173/Django8000/PG55432. File cleanup only owned new files.
- Do not apply real472 rows automatically. Actual Google preview permitted; actual business apply after operator reconciliation/confirmation. Typed historical core is not a second archive.

## Review Focus

- Потерян ответ Google-preview, таблица или конфигурация изменилась: повтор не читает новые байты под старым ключом и не возвращает чужой источник после отзыва права.
- Две одновременные выборки из разных снимков содержат один номер или одинаковый ключ комплекса: нет дубля, частичного пакета или случайного объединения материалов.
- У сотрудника есть историческая связь, но обучение/неподтверждённая специальность: доступ к своей карточке не превращается в живое назначение или допуск.
- Закрытая историческая работа без даты либо история без известных пауз: UI, SQL-фильтр и предметная проекция не считают её до сегодня и не показывают неизвестное нулём.
- Исходная выдача известна, итоговый файл добавлен позже или права изменены: активация/выдача не создают повторную передачу и не обходят текущие ограничения через сохранённый ответ.

### Task 1: Настроенный Google-источник и воспроизводимый снимок

**Files:** Create imports/google_source.py,tests/test_google_journal_source.py,tests/test_google_journal_preview.py. Modify imports/{services,models,serializers,api,urls}.py+migration0002,config/settings.py,infra/local.py,accounts/views.py,docs/api-journal-preview.md. No frontend yet.

**Interfaces:** `GoogleSource` dataclass(spreadsheet_id:str,gid:str,sheet_name:str,label:str=""). `configured_google_source()->GoogleSource|None`; `.url` canonicaleditURL; `fetch_google_csv(source:GoogleSource)->bytes` pure bounded network boundary, raises JournalSourceError. `persist_preview(*,actor,parsed:ParsedJournal,content:bytes,reason:str,source_origin="upload",origin_url="",source_observed_at=None)->{id,batch_id}` WITHOUT transaction/idempotency ownership: callers provide both. `create_preview` preserves existing behavior, uses persist_preview. `create_google_preview(*,actor,reason,spreadsheet_id,gid,key)->receipt` current config/rights, execute_once before fetch.

- [ ] Step1 RED `test_google_source_config_and_bounds`: unset→None, validid/gid→canonicalURL; fetch200CSV exactbytes; HTML/401/timeout/oversize→JournalSourceError; rejected nonHTTPS/nonGoogle redirect, no arbitraryhost request. Run `pytest tests/test_google_journal_source.py -q`, Expected missingmodule RED.
- [ ] Step2 RED `test_google_preview_replay_never_refetches_changed_source`: firstcreates, monkeypatch secondreadchangedbytes, repeat sameid/count1/readcalls1; changedreason409, configchanged409, currentview/previewrevoked403, no snapshot/file/receipt on remoteerror; metadata source_origin/googleurl/observedAt and olduploaddefaults retained. Expected404 RED.
- [ ] Step3 implement exact boundaries/0002/GETgoogle-source/POSTgoogle-preview. Supportedmodule `journal_google_preview` only after endpoints ready. `infra/local.py journal-source <id> <gid> <sheet_name>` validates/stores only source config inside ignored connection config; backend passes three AIS_JOURNAL_GOOGLE_*envvars. Does not print connection/password.
- [ ] Step4 focused then fullbackend/check/no drift/diff/task-done; Expected allgreen. Commit `feat: inspect configured Google journal without changing source`.

### Task 2: Исторические факты и основной реестр

**Files:** Modify expertises/{models,api,policies,serializers,production,calendar_query,services}.py, intake/{models,services,locking}.py, issuance/{readiness,commands}.py. Create expertises/history.py,tests/test_historical_work.py; migrations expertises0007/intake0002. HistoricalWork/Participant belong expertises core, reference imports.ImportRow(PROTECT); migration depends imports0002. No apply route/module yet.

**Interfaces:** `historical_record(work)->HistoricalWork|None`; `require_operational(work)->None|ValidationError`; `historical_facts(work)->dict` stable typed DTO from spec§2/3, native closure/result wins when present. `historical_output(work,user,scopes)->dict|None` protects origin URL by imports.results.view institution. `historical_end_on(work)->date|None`; `current_history_employee_ids(work)->set[UUID]` only when no real assignment history. `work_context` keeps write context from actualassignments; `require_work(...,"expertise.view",...)` may include historicalreadlink, otheractions cannot.

- [ ] Step1 RED model/DTO tests: null nature/commission validonlyhistorical; native unknowns DBerror. Historical DTO returns exact knownnull facts and no fullmixedsource for ownexpert. No Documents/FileVersions/ResultRevision/Closure/Assignment created by fixtures beyond explicitlycreatedhistorical core.
- [ ] Step2 RED calendar/filter consistency: completedknownendclamped, completedunknownend→allnull/notfilter, openknowncalendar but unknownpause→paused/active null. Own historyparticipant canread/filter but cannot mutate; current realreassignment moves filter to recipient. Knownhistoricalissued blocks newissue/adoption and sharedmaterialchange.
- [ ] Step3 implement models/projections/guards/eagerloading. Receipt.statushistorical notaccepted and directamend blocked until activation; native registration stillvalidate_basis. Guards underlocked_work and _set_experts; no unsupportedaction advertising. Unknownhistorywithoutprofile fails closed, no fictitiousprimary/sole/emptyknownpauses.
- [ ] Step4 focused/fullbackend/check/no drift/diff/task-done, Expected allgreen. Commit `feat: represent imported expertise facts without inventing workflow events`.

### Task 3: Сверка, сопоставления и атомарный пакет

**Files:** Create imports/{reconciliation,application,reconciliation_serializers,reconciliation_api}.py,tests/test_journal_application.py,tests/test_journal_application_concurrency.py. Modify imports/{models,urls,serializers}.py+0003, accounts/{catalog,views,management/commands/bootstrap_access,management/commands/bootstrap_workflow_demo}.py;docs/api-journal-application.md.

**Interfaces:** `classify_row(row)->{classification,existing_work,blockers,suggested_department,suggested_specialty}`; `save_selection(*,actor,row_id,data,key,payload)->{id,selection_id}` versioned separate ImportSelection; fields from spec§4. `apply_selection(*,actor,batch_id,selections,reason,key,payload)->{id,application_id}` receipt only IDs. `application_data(application)->ApplicationDTO` exactspec. `ImportApplication` actor,batch,reason,created_at; `ImportApplicationItem` FK application,row(unique),work,action. ImportSelection unique row/version/actor/reason/mappings, immutable after item exists. No automatic update of existing work.

- [ ] Step1 RED selections: exactoptionsminimalDTO; savedselection changes no businesstables; strictfields/version/key/reason/currentright; exactcode/inactive historical refs allowed/unknownnull counts; confirmed stats onlyfullvalidsum, commissionparticipants≥2; conflictcodesexposed and raw untouched.
- [ ] Step2 RED apply: selectednewrows createsprimaryExpertise+History notevents/files/qualifications; unknownnull visible; explicitcomplexgroup shares material, specialties unique; sameop replayonereceipt/audit/item; changedbody409/revoked403/staleversion409; invalidoneof2 rollsallback; existingnewSnapshotnumber changedorunchanged no duplicate/update. Late selectionedit afterapplied denied.
- [ ] Step3 RED concurrency: twoactors/differentbatches/samenumber onecreation, secondmanaged409not500; no deadlock oppositeorder rows/groups; limits1000/distinct selections/groupkeylocaltobatch. Then implement deterministicnumber advisorylocks + batch/selections/ref locks and atomicmodels/audit. Uniqueconstraints map conflicts to409.
- [ ] Step4 implement GETreconciliation/options PUTselection POSTapply GETapplication; moduleflagjournal_application + BatchDTOapply_available percurrentapplyright. Add institution-onlypermissions and explicitDEMO --enable-journal-application(refusereal/preserveedits); no realroleexpansion.
- [ ] Step5 fullbackend/check/no drift/diff/task-done allgreen; commit `feat: reconcile and atomically apply historical journal rows`.

### Task 4: Подтверждённое продолжение исторической работы

**Files:** Create expertises/history_activation.py,history_serializers.py,tests/test_history_activation.py,tests/test_history_activation_concurrency.py; modify expertises/{api,urls,serializers}.py,docs/api-journal-application.md.

**Interfaces:** `activate_history(*,actor,expertise_id,data,key,payload)->{id,expertise_id}` spec§5. `HistoryActivationInput` fields reason,expected_version,basis_document_id,appointment_nature,is_commission,complex_known(true),complex_group_id(nullable),suspension_history_complete(bool),past_suspensions(list of suspended_on,resumed_on,reason),suspended_on(nullable); closedresult/return subpayload existingexactResult/Return schemas. Date before receipt/future/intersection invalid. Existing create_revision/confirm_result/create_closure validators reused, no weakenednativecommand.

- [ ] Step1 RED openactivation: realbasis+knowncomposition mandatory; historical+register/view/docs currentrights; no qualifier/assignmentauto, then normal qualified assignment succeeds/traineefails. With suspended no start→400, validopeninterval→resume works, historicalunknownpastpause active-daysnull. Historicalalreadyissued→400/no closure/receipt rewrite.
- [ ] Step2 RED closedactivation: kindunchanged, actualfile/date mandatory; creates firstacceptedclosure notoverwritehistory; nativeclosedcorrectionthenworks, historydate remainsprovenance. samekeyreplay/versionrightcheck/differentbody409; concurrentactivation oneevent. Complexknownfalse/mismatchedgroup rejected.
- [ ] Step3 implement lockedMaterial→Receipt→Work activation/participantpreservation/nativevalidators/operationalflag+audit. Command response currentallowedactions/docprojection, never cachedbroaderauthority. Endpoint advertised only now.
- [ ] Step4 fullbackend/check/no drift/diff/task-done allgreen; commit `feat: activate historical expertise through explicit evidence confirmation`.

### Task 5: Vue — от Google до рабочей карточки

**Files:** Modify frontend/src/api/{imports,types}.ts, modules/imports/{ImportPreviewsPage,ImportPreviewPage,ImportUpload}.vue, modules/expertises/{ExpertisePage,ExpertisesPage,ProductionPanel}.vue,router.ts/session.ts. Create modules/imports/{GooglePreview,ReconciliationPage,SelectionEditor,ApplicationResult}.vue,modules/expertises/{HistoricalFacts,HistoryActivation}.vue,frontendtests imports/google,reconciliation,historical. README/docsverification main.

**Interfaces:** Typed SourceInfo/GooglePreview body/SelectionDTO/ReconciliationRow/Page/ApplicationDTO/HistoricalDTO/ActivationDTO exact Task1-4/spec. Consume allowedactions and moduleflags; no clientinferredqualification/state. Preservefileupload/list; source access unavailable doesn'thidepermittedworkfacts.

- [ ] Step1 RED Google UI: configured/unconfigured/error, onlycurrentrights/flag; exactreason/id/gid/keybeforePOST; lostreplyreusesbodykey, sourcechange/conflictneverchangesattemptsilently, successgoesrealbatch, no Googlewrite.
- [ ] Step2 RED reconciliation: classificationglobalcount/URLfilter/page/back; rowselectionexactnullunknown/versionedbody/dirtyguard; group/commission/statisticsfields; multiapplyonlysavedselections expectedversions/exactIDs, managedconflict/error retainsediting, successfulprotocolrealworklinks; absentrights/capabilitynoAPI, lateGETsourceflipdiscarded.
- [ ] Step3 RED workcard/historyactivation: knownnull display notprimary/sole/fakefile; historicalemployees notrealassignment; incompletepause active-daysunknown; exactbasis/composition/date/file/key/version, nopermissioncontrols; actualactivationrefreshesAPI/normalassignmentform. No stalehistoricalfactsundernewworkroute.
- [ ] Step4 implement currentfullwidthdesign/sharedcomponents. Fullfrontend/type/build, Expected allgreen. ActualIAB readconfiguredGoogle→real472rowpreview (notbusinessapply), DEMO3-row savedselection→apply→workcard→evidenceactivation→qualifiedheadassignment→expertproduction, negative trainee/foreignrole/unknownend. Businessrealdata notapplied automatically.
- [ ] Step5 commit feature before ONE finalwhole-slicereview BASEb35d017; mainregradesallfindings/declined,oneCriticalImportantTDDpass/fullgates. task-done frontendfull/check/diff plus backendfull ifbackendchanged. Keepbranch/nopush, overallgoalactivefornext15.1 plan and remainingpolicies/docs.

Self-review: Task1 persists current source metadata and exact CSV; Task2 only introduces typed historical core/projections; Task3 produces allselection/applicationIDs Task5consumes; Task4 makes existingworkflowvalidwithoutforgery. FiveReviewFocus cases pinned in Tasks1-4 and clientguards. Imports0003 depends expertises0007; expertises0007 depends imports0002 (no reverse dependency). Source provenance stays immutable; working primary IDs notnewparallelarchive. Remaining confirmed-update/regroup procedures and15.1 remain named extensions, not silently claimed complete.
