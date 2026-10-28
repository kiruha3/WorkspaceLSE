# Issue billing and category packs implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline. Steps use checkbox syntax.

**Goal:** Рабочая выдача обычных результатов4/6 и обязательный счёт платной работы с явной платностью.
**Architecture:** Nullable факт по работе в неизменной редакции комплекта; существующие prepare/check/issue и Vue, без нового финансового регистра.
**Tech Stack:** Existing Django/PostgreSQL/Vue3/TypeScript; no new dependencies.
**Spec:** docs/superpowers/specs/2026-10-28-issue-billing-design.md

## Global Constraints

Не выводить платность из суммы/категории; unknown неFalse. Счёт2/3 и уведомление1/5 сохранены. СНДЗ/возврат/комиссия/частичнаявыдача не утверждены по аналогии. Без реальных financialfacts/grants/PHP/Googlewrites/push/merge/worktree. Только additive issuance0002 после backup;65oldtables/13files/472real8demo/996reportcells+records неизменны. DBpytest только по одному. Старые outputs/ и запрещённое к удалению .superpowers сохраняются. Автономный inline, один finalreview/один Importantfixpass.

## Review Focus

- Оmitted/empty billing не стирает текущие значения, explicitnull очищает; чужой/повторный work не создаёт частичную редакцию.
- Требования сопоставляют category+closure.result.kind и nullableплатность, не сумму; invoice не дублируется для paid2/3.
- Новая редакция платности делает прежний check stale и проверяется фактической командой issue, не только UI.
- Потеря ответа/409/403 сохраняет ввод и прежний командный packet, включая billing, при позднем GET.
- Несколько работ одного материала имеют независимую платность; неподтверждённый вид/комиссия не разблокируются.

### Task 1: Versioned billing and approved ordinary packs

**Files:** backend/apps/issuance/{models.py,serializers.py,readiness.py,drafts.py,api.py,migrations/0002_packageworkbilling.py}; backend/tests/{test_issue_billing.py,test_http_issue_billing.py,test_issue_drafts.py,test_issue_commands.py}; frontend/src/api/issuance.ts; frontend/src/modules/issuance/{IssuePackageDraft.vue,IssueFiles.vue,IssuePackagePage.vue,issuance.test.ts}; docs/specification.md; docs/verification/issue-billing-2026-10-28.md.
**Interfaces:** PackageWorkBilling(revision,expertise,is_paid nullable); ContentInput.billing optional list, explicitnull clears, omitted/empty preserve previous. DTO revision.billing array + works.is_paid. required_items(work,closure,is_paid=None) list; current_facts4tuple/check_matches unchanged, revision ID pins billing. No new routes/rights. Codes billing_unknown/item_missing/policy_unconfirmed.

- [ ] RED test_issue_billing: literal requiredpacks4/6 false/true,1/5true notification+invoice,2/3true invoiceonce, unknownblock; create/draft billing values/merge/null/history/replay, duplicate/foreign invalidatomic, realcheck→billingchange→issue400→recheck→issue200, multiworkisolation. RealHTTP4expert_conclusion/6research_act checks/issues; mismatch/SNДЗ/return/commissionremainblocked. Run newfiles serial (`infra/local.py backend -m pytest tests/test_issue_billing.py tests/test_http_issue_billing.py -o addopts= -q`), expected missingfield400/unsupportedpack/billingnotread. Implement additive model/migration/strictinput/versioncopy/requirements/DTO, update only old policy expectations+fixtureexplicitFalse, focusednew+issue_drafts/commands/scopes/concurrency+case regression, expectedgreen.
- [ ] RED Vue paidselector/unknownlabel/snapshotpayload/recovery/403409 preservation, separateworkbilling, serverrequiredinvoice/actpreview/history. Implement typedDTO/form/view/history without frontendduplicaterules; run issuance.test.ts then fullfrontend/typecheck/build, expectedgreen.
- [ ] Commit product, one fresh finalreview range/spec/ledger, Important oneRED→GREENpass/no rereview/minorpolish. Then fullbackend serial +frontend/check/drift/diff expectedgreen, all subprocesses terminal.
- [ ] Live checkpoint+backup, issuance0002 additive only, compare65oldtables/13files/996cells+records with source472real8demo, newtableempty, no grants/realbillingwrites. RestartoneDjango/oneVite/readDTO/UI/screenshot/no submit. Verificationdoc+rulings/deferred/limits, commit. task-done newfiles+issue_drafts/commands/scopes/concurrency, expectedallgreen, closeplan/fullgoalactive.
