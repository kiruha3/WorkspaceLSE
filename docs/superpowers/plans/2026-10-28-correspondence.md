# Корреспонденция и контроль Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline task-by-task. Независимый Vue может выполняться параллельно по точному DTO. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Рабочая переписка по всем основным направлениям: ручная регистрация, файлы, отправка/получение/доставка, частичные ответы и отдельный контроль.

**Architecture:** correspondence Django-модуль, неизменяемые редакции и типизированные факты, общиеscopes/execute_once/documents/audit, Vueреестр/карточка/формы. Не почтовая интеграция.

**Tech Stack:** существующие Django5.2/Python3.13/PostgreSQL17 иVue3/TS/Vite, без новыхзависимостей/серверов.

**Spec:** `docs/superpowers/specs/2026-10-28-correspondence-design.md` (точныеDTO/команды), общаяspec§6/8/9, COR01–08/AC20–22. Baseline d867bcf.

## Global Constraints

- ais-lse/implementation на месте, без push/merge; PHP/web-vue/VM/Excel/Google untouched. Реальные роли не расширять, учебные только explicitopt-in.
- Отправка/получение/доставка/контроль не выводятся из регистрации/черновика/завершенияэкспертизы. ДатыISO/AsiaKrasnoyarsk, unknown≠registrationdate/0.
- Backend pytest только одинпроцесс: ждатьterminalhandle; одинVite0.0.0.0:5173. Не начинатьдругойplan'sscratch.
- Область конкретногодействия; standaloneбезexpertise.view поддержан; общаяпереписканедаетwriteчерезоднусвязь. Файлычитаютсяпосвязисdocuments.view, неgrantupload.
- Всеmutationsversion/key/reason; минимальныйreceipt+freshprojection; locksLetterIDs→DocumentIDs→refs встабильномпорядке, не mixmain/evidence.
- Первичныйполныйbackend195/195/frontend95/95 уже доказан91b0225 безизмененийproductпосле; повторныйbaselineбезнуждынезанимаемCPU.

## Review Focus

- Передачаответственного/эксперта либоотзывdocuments.viewпослепотерянногоответа: replayнеоткрываетсодержимоеилистароеправо.
- Письмоснесколькимиработами/отделамиизодногодоступногоназначениянепозволяетменятьобщуюзаписьиливидетьчужиереквизиты/count.
- Зарегистрированныйчастичныйответилиотправкачастиадресатовнезакрываютконтрольисамипосебенедоказываютполучение.
- Позднийфайл/новаяверсияпослерегистрации/отправкинеменяетпринятыйснимок; печатныйоригиналбезскананевыдаетсязаэлектронныйфайл.
- Одновременныерегистрациисоднимномером,двакомандныхключа,перекрестныеродитель/ответ/документыиclose-versus-sendнеоставляютполусобытий,500илипротиворечивыхдат.

---

### Task 1: Черновики, области, справочники и документы

**Files:** Create backend/apps/correspondence/{__init__,apps,models,policies,serializers,drafts,api,urls}.py andmigrations; referencescorrespondence_seeds.py/seed_correspondence_catalogs command, referencesmodels/api, configsettings/urls, documentsmodels/policies; tests/test_letter_drafts.py/test_letter_scopes.py. ПотребителиexistingAPI/policies/servicesименасохранить.

**Interfaces:** Letter/LetterRevision/LetterRecipient/Attachment изdesign; laterTask2addsotherfacts. `create_letter(*,actor,data,key,payload)`, `save_draft(...)`, `attach_document(...)` returnminimal{id,letter_id}; `letter_scope_queryset(user,action,scopes=None)`, `letter_context(letter,user,action,scopes=None)`, `require_letter`, `can_material`, `require_links`. Produce GEToptions/work/materialoptions/list/detail andPOSTcreate/draft/attachments exactdesign; registration/dispatch/controlplaceholdersuntilTask2, don'tadvertiseunimplemented. Kinds nullableonlydraftDTO. Newrefs LetterKind/LetterJournal(direction,department?)/DispatchChannel/ControlClosureReason(rule), catalogsletter-kinds/letter-journals/dispatch-channels/control-closure-reasons; newRefcreateallowjournalfields/closurerule, updateonlyname/active. Seedidempotentpreserveallsettings/active. Lettersviewownresponsibleorcurrentvisiblework; mutationsdirectresponsibleonly; siblingmaterialdoesn'tgrant. DTOscopedrelatedworks/material/parent, nohiddencounts. Owninitialresponsibleactor; departmentchoiceonlyauthorizedorganizational/visibleownworkscope. Worklinksread+draftscope; Materialviewreceipt/work. Linkedletterfilesfallbackindependentofexpertise.view; doesn'tgrantupload. Preloadauth/currentrevisions/history/docs, paginationbeforecounts.

- [x] Step1 RED APItests: independentstandalonecreateandresave2revisions, nullreceived/date/kindstayunknown; lostcreate/save/attachreplysameIDs/freshstate/keyconflict409; reason/keyrequired; staleversion409; existingdocsattachonceoridempotentreplay, unknownfilemetadataallowed, scopedread/downloadandrevokeredaction; ownunassignedsibling/previousowner/mixedwidescopenotmutation; multiworkfilters/showonlyvisiblelinks; refsseededited/inactivepreserved/newinactiveadoption400; bothincoming/outgoingcreateresponsibleactor. Runfocusedmissingroutes/models expectedRED.
- [x] Step2 Implementminimaltypedmodels/services/scopes/DTO/catalogs/options/endpoints, migrations. Protectnewactivechoicesunderlock; noauto-createdjournalrows. BeforeparentrelationsimplementedGETplaceholderssafe.
- [x] Step3 FocusedGREEN, fullserializedbackend/check/migrationsviatask-done thencommit `feat: add scoped letter drafts and correspondence catalogs` aftersuccess.

### Task 2: Регистрация, доставка, ответы и контроль

**Files:** correspondence/models,commands.py,command_serializers.py,command_api.py,serializers/api/urls/policies; accounts/catalog/bootstraptemplates, bootstrap_workflow_demo/infra; tests/test_letter_commands.py/test_letter_concurrency.py/test_http_letters.py/test_workflow_demo.py.

**Interfaces:** ConsumeTask1Letter/Revision/scopes/DTO/documentlink. AddtypedRegistration/RegistrationFile/Dispatch/DispatchFile/Delivery/Receipt/Assignment/ControlTask/ControlEvent fromdesign. `register_letter`, `send_letter`, `receive_letter`, `deliver_letter`, `assign_letter`, `open_control`, `change_control_deadline`, `close_control`, `reopen_control` keywordactor/letter_id/data/key/payload minimalreceipt. Parent/replyimmutablelinkinRevisioncreation, opposite/registered/viewable; replyrequiresbothdraft+reply; linkedchildrenonlypermitted. Commonlocksparent/current/reply sortedUUID thenallDocuments sortedUUID beforecatalog. Registrationnumberfreeformuniquejournal/year/number; concurrentcollision409atomicrollback. Freezecontentonregister, knownincomingreceivedcreatesReceiptunknownstaysnull, pinfileversions. PartialrecipientSend/repeatDispatch andindependentDeliverytyped, noautomaticexternalcontact. Replysent/receivedcloseconditionsfromdesign; due-nullallowedknownneedsbasis, taskstatus/progress/overduecomputed; closeandreopenappend, noexpertisechanges. Assignactiveemployee+control.assignscopeandclearformerownvisibility. Newtemplatepermissionsonlynewroles; --enable-correspondenceonlynewflagpermissionsontwoDEMOroles(withrefuserealparticipants), don'trestorerevokedoldrights/passwords.

- [x] Step1 RED: registerdraftvalidincoming/outgoing/recipientrequirements; wrongjournal/duplicate/inactivenew400or409; replaysafterlaterchangesfresh; unknownrecvnotregistrationdate; datesfuture/orderrejected. Partialsendto1of2→partial,sentall→sent, deliveryindependent; oldregistration/sendsnapshotsstayV1afterV2upload. Twooppositedirectionpartialanswers+final, draftdoesn'tclose; outgoingreplyregisteredbutunsentcannotreply_sentclose; incomingreplyunknownreceivedcannotreply_receivedclose; explicitwithdrawn/otherrequirescomment; reopeningmaintainshistory; completedExpertisestaysunchangedcontrolopen. Scope/view/action, formerownerreplay403, documentrevokeredacted; concurrentnumberkeysonefact/samekeyoneID; close-versus-send/parentcrosslocksnoinvalidfacts. RealHTTPclerk/expertseparatesessionsfullinbound/outboundflow. Demodefaultpreserved/flagonlynew/refusereal. FocusedREDwithoutsecondrunner.
- [x] Step2 Implementtypedcommands/timelineDTO/flags/filters/allowed_actionsanddemoopt-in,migrations.
- [x] Step3 FocusedGREEN, fullbackend/check/migrationsserializedtask-done thencommit `feat: register correspondence and control reply lifecycle`.

### Task 3: Vue рабочий журнал и полные сценарии

**Files:** frontend/src/modules/letters/{LettersPage,LetterPage,LetterDraftForm,LetterActions,LetterAttachments,LetterHistory,ExpertiseLetters}.vue andtests; api/types, router, App/Home/expertiseintegration, testsfixtures. MainownsREADME/docs/verification-correspondence.md/runtime only.

**Interfaces:** ExactDTO/body/optionsinbindingdesign. Allformsfromallowed_actions; typedfacts/history, partialsent≠received≠control. Controlledcatalogs, minimalemployee/work/materialselectors, multiworks, standalone, parentreplycreateprefill, body/text unknownfaithful. SharedBasisDocumentForm/Previewstagedupload+lateattach withprooffileversionmarkers. Persistentwithinopenpageattemptnormalizedbody/key/version/reasonthrough409/403/lostreply/refresh, explicitnewversionaccept; nativeuncertainformnovalidate. Dirtyguard/staleGETcancellation. Sidebar/Homeactuallettersbyrights, expertisepanellinkedletters/createquery. Noexecutionmailbutton, nofakepolicy/role.

- [x] Step1 REDcomponenttestsregister/page/filter/returnURL/rolepermissions, unknownandpartialstates, exactcommandbodies, separatedreplyfinal/close; dirtyguard/403/409/lostreply/date/native/stagedfile/lateGET, retaineddraft/sharedsnapshotpreview. Keepallcurrenttests.
- [x] Step2 ImplementconsistentfullwidthVueforms/registry/detail/historyandlinkedworkpanel. GateAPIdependentUIuntilnewbackendready; noextrastartservers.
- [x] Step3 Frontendfulltests/typecheck/build; mainactualIABtwoDEMOflowspathswithfilesandown/departmentdenialviaHTTP; updateverification/README,commit `feat: connect correspondence workplace and reply control in Vue`.
- [x] Step4 Onefreshwhole-slicereviewfromd867bcf, oneImportant/CriticalTDDfixpass/fullgreen. Recordallrulings/deferredminorsdurably. Keepbranch/nopush; globalgoalactiveuntilrestdone.
