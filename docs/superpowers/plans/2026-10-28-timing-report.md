# Timing facts and section 3 implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline. Steps use checkbox syntax.

**Goal:** Сохранять причины длительности и подтверждённые факты информирования/ходатайства/нарушения, получать G:N раздела3 из тех же данных.
**Architecture:** WorkTimingFacts1:1, TimingReason1:N, immutableTimingRevision, extensibleDelayReason; existing metadata command/locks/versions/document helpers and1SELECTregistry.
**Tech Stack:** existing Django/PostgreSQL/Vue3/TypeScript/Vitest, no new dependencies.
**Spec:** docs/superpowers/specs/2026-10-28-timing-report-design.md

## Global Constraints

implementation in place, no grants/push/merge/worktree/packages/newservices. Google read-only, PHP untouched. Preserve all472real and8demo corefacts/numbers/dept/people/source/results/issues/access. Backup before references0006/expertises0011. QA only existingdemo900301 with atmost2newsyntheticdocuments/versions and2TimingRevision; no newwork/event/closure/issue/assignment. Old900registry/journal660 cells unchanged; total996registry. Unknown owner multiple-reason policy is not guessed. No legal inference from calendar/request/absent agreement.

## Review Focus

- A typed false, unknown and partially evidenced true must stay distinct; dates after completion do not satisfy timely communication.
- Custom/unmapped/inactive/retained reasons and multiple refs in one group must not make false zeros or multiply one work.
- Nested document loss and409 must preserve path/body/key and reuse uploaded files; stale route response cannot replace another card.
- Imports/activation/issue concurrency and historical own scope must preserve accepted facts without widening native commands or sibling-file access.
- Request is not sending/agreement; M/N have no>30 gate, while G:L do. Accepted closure/projection/fingerprint must remain coherent in1SELECT.

### Task 1: Timing facts to report pipeline

**Files:** references/models.py/api.py+newtiming_seeds.py/migration0006; expertises/models.py/newtiming.py/timing_serializers.py/timing_api.py/migration0011/api.py/serializers.py/urls.py; imports/updates.py; documents/policies.py; reports/newtiming_columns.py/registry.py/calculation.py/reason_columns.py/column_rules.py; frontendapi/types.ts/newTimingPanel.vue+test,ExpertisePage.vue,references/catalogs.ts/ReferenceEditor.vue(or actual existing editor),ReportsPage.vue/reports.test.ts; tests/test_timing_facts.py/test_timing_concurrency.py/test_form151_timing.py; docs/verification/timing-report-2026-10-28.md.

**Interfaces:** save_timing(actor,expertise_id,data,key,payload), timing_values/snapshot/output(work,user,scopes); strict POST per spec, GET choices+retainedIDs+policy. delay_counts(facts,policy)->dict[6codes,bool|None], communication_qualifies(facts,completed)->bool|None. DELAY_REASON_POLICY=None until owner decision; combine all/primary results when unknown, count once per matching group. Registry selects profile/children facts in same1SELECT; current reference.report_group in fingerprint. Column rules adds8explanations/rulesv2, includespolicy in fingerprint.

- [ ] RED API/test_timing_facts: no implicit profile/false; full save/history/audit/exactfields/identity; invalid dates/empty known evidence/duplicate or>100reasons/primaryoutside list/known-long emptycomplete; partial true with unknown date retained; inactive retained/restore and inactive new denied; samekey replay/stale/newbody/revokedwork or document rights; own/dept/institution/outsider; metadata afterissue; profile protects source/activation; exactdoc sharing. RED report/test_form151_timing: handfixture65days2reasonsall→G107=1/I107=1 not2, onlyprimary→G107=1/I107=0, unknownpolicy→G107=1/I107=None; fullsinglegroupdedup/partial/unmapped; M beforecompletiondualyes1, missingdateNone/oneFalse0/late0; N explicittrue1/false0/unknownNone; research/SNДЗ/return/open/future excluded;20dayordinary M/Nstillcount; old900equal/996cells/journal660/1SELECT/fingerprint/policy version/literalXLSX G107. Run focusedfiles; expectedmissingroute/model/column failures.
- [ ] Implement models/migrations/seeds/catalog/API/command/report/rules. Add concurrency samekey/differentkey +material/importwinner, oneprofile/revision/version and409, no partial effects. Run focused plus oldclassification/case/history/registry/import tests, expectedallgreen. DBpytest serialonly.
- [ ] RED Vue TimingPanel: serverreadonly, allnullableflags/list/primary/payload, referencesretained, actualnewfileupload+lostresponse→samepacket→409→newversionwithoutrecreateddocs,403draft/dirty/latecard, readabledocument-onlyhistory; report8cols/rules/provenance andjournalnoextras, reference-group save. Implement with sharedhelpers. Fullfrontend/test/typecheck/build green.
- [ ] Onefresh whole-slice review, Important onlyoneRED→GREENfixpass; fullbackend+frontend/check/drift/diff green. Record all Minors, no rereview. No snapshot-complete claim from focusedtests alone.
- [ ] Backup/checkpoint/migrate+existingdemo boundedUI2revisions/2docs/roleallowdeny; realdata/access/source/files unchanged. Actualreportbuttondownload, allZIPparts equalAPI, ArtifactTool996cells andsection3render; old900same/new96unknown, positivecountsprovenfixtures. Commit/task-done focusedcombinedincludingconcurrency, closeplan. Leavegoalactive; preserve previouslydenied scratchdeletion.
