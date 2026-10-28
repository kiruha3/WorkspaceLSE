# Repeat examinations implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline. Steps use checkbox syntax.

**Goal:** Уточнять характер назначения и предыдущие заключения в карточке и получать H:N раздела4 из тех же фактов.
**Architecture:** WorkClassification1:1, PreviousConclusion1:N, immutable revisions, existing metadata permissions/locks/command receipts; oneSELECT registry projection and shared Vue forms.
**Tech Stack:** existing Django/PostgreSQL/Vue3/TypeScript/Vitest; no new packages.
**Spec:** docs/superpowers/specs/2026-10-28-repeat-examinations-design.md

## Global Constraints

implementation in place, no grants/push/merge/worktree/packages/newservices. Google read-only, PHP untouched. No fake facts in472 real works. Preserve all old numbers/state/dept/people/accepted results/issues/source. Backup before additive expertises0010. QA only existing explicitdemo900301, atmost2newsyntheticdocuments/files, no newworks/closure/issue. Previous816registry cells unchanged; journal660 unchanged. СНДЗ repeat policy unknown unless owner answers.

## Review Focus

- Partial or unknown previous conclusions must not look like absence/nonconfirmation; positive group claims must not multiply one work.
- Lost nested-document response and later409 must recover without recreating documents or replacing another route's card.
- Import/activation/closed correction racing with metadata must either serialize or409 without dropping accepted facts or history.
- Exact linked-document scope, inactive/revoked rights, replay and historical ownership must not expand native command access.
- Native closure versus history, unknown dates/specialty and СНДЗ policy must preserve aggregate uncertainty; oneSELECT/fingerprint must include every effective fact.

### Task 1: Classification and repeat report pipeline

**Files:** expertises/models.py/migrations0010, new classification.py/classification_serializers.py/classification_api.py; api.py/serializers.py/urls.py; imports/updates.py, history_activation.py; documents/policies.py; reports/newrepeat_columns.py/registry.py/calculation.py/reason_columns.py; frontend api/types.ts,new expertises/ClassificationPanel.vue/test,ExpertisePage.vue,shared/FactHistory.vue,references/catalogs.ts,reports/ReportsPage.vue/reports.test.ts; backend tests/test_classification.py,test_classification_concurrency.py,test_form151_repeat.py; docs/verification/repeat-examinations-2026-10-28.md.

**Interfaces:** save_classification(actor,expertise_id,data,key,payload), classification_output(work,user,scopes). POST strict fullpayload per spec, DTO optional classification for backwardfixtures only. repeat_summary(facts)->{repeated,groups:{ministry,other_state,other:{present,not_confirmed}},gaps}; gates use explicit bool/None, calc writesH:N using put. Snapshot factualdeptID/code separate historicalnumberdept. ArraySubquery selected currentrefs/complete/profile/nature feeds sameSELECT fingerprint.

Owner addition: new reports/column_rules.py provides versioned explanations for every calculated section/column, attached to report DTO by calculation.py and included in registry fingerprint. reports.test.ts +test_form151_column_rules.py RED all-column coverage/formula semantics/source modes/no-SQL and UIclick→actualserverrule; ReportsPage.vue opens per-column meaning/date/unit/source/unknown/limitations, discards stale guide on source/period change. Missing-server-rule is explicit, never guessed. Existing cell provenance remains.

- [x] RED backend route/fields/strict/bounds/nature-null/nativeconstraints/partialfalse/history/audit/exactdocsharing/currentreplayrights/own-dept-institution/issued/stale/atomicversion/source+activationguard; report handfixtures ordinaryrepeated2previoussamegroup→H107=1/I107=1/J107=1, othergroups0 onlycomplete; partial/missing/unknown group→null, additional0, fullSNДЗ unknown-policy gap, latestnativeclosure only. LiteralXLSX H107,900cells/journal660 and oneSELECT. Run backend pytest tests/test_classification.py tests/test_form151_repeat.py; expected missingroutes/columns.
- [x] Implement minimal domain/API/report/migration; same command plus test_classification_concurrency.py and old case/history/registry/application tests→green. Concurrency samekey/diffkey and material/sourcewinner; expected one revision, competingexpectedversion409, no partial writes. No concurrentDBpytest.
- [x] RED Vue currentnature/readonly/source, previous add/remove/complete/three-state,payload/doc selection+realnewupload,lostresponse→409→explicitversion,403draft,dirtyleave/latecard, historybeforeafterdocument-only; registryrepeatcolumns/provenance journalnoextra. Implement; focused/full frontend/build→green.
- [x] Onefresh whole-slice review then Important onefixpass RED→GREEN/full suites; check/drift/diff→clean. No rereview, allMinorsledgered. Expected no unresolvedCritical/Important.
- [x] Backup+oldfield/access/source/result/doc checkpoints; migrate; normalUI existingdemo classification and atmost2evidencefiles; roleallowdeny; real472/oldcorefactsunchanged. Registry900 withold816equal/new84unknown, actualdownloadZIPequal, ArtifactTool/XLSXsection4render. Commit/task-done focusedcombinedtests includingconcurrency, closeplan; goalactive.

## Outcome

Product318f171, verification-contract/acceptance e2b1fc1. Fullbackend719/719 in606.18s, frontend281/281 and build/check/drift green. One fresh reviewCritical0/Important0; one wordingminor deferred. Task-done85/85 in44.46s. Live additive0010 plus two bounded DEMO revisions/documents;53oldtables/9oldfilebytes unchanged.900XLSXcells verified,816priorcells unchanged,75column rules displayed. Detailed evidence: docs/verification/repeat-examinations-2026-10-28.md. No push/merge, fullgoalactive. Previously denied scratch deletion not retried. The unresolved repeated-SNДЗ policy stays explicit, not invented.
