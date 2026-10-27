# Результат и завершение Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Эксперт сохраняет результат/статистику, завершает работу либо оформляет решение без исполнения; исправление сохраняет историю, данные пригодны для последующего15.1.

**Architecture:** Типизированные неизменяемые ResultRevision/UnresolvedAllocation/WorkClosure; предметные команды используют существующие locks/policy/idempotency/audit. Inline backend, независимый Vue по точным DTO; одно итоговое ревью с одним TDD исправительным проходом.

**Tech Stack:** существующие Python3.13/Django5.2/DRF/PostgreSQL17, Vue3/TypeScript/Vite. Без новых зависимостей, Node-серверов, VM и workers.

**Spec:** `docs/superpowers/specs/2026-10-28-results-completion-design.md`, общая `docs/specification.md` §5.4/8 и `docs/access-control.md`; причины из `../web-vue/docs/reference-catalogue.md` REF13–15. Baseline8f78697.

## Global Constraints

- ais-lse/implementation сохраняется на месте по указанию владельца, без push/merge. PHP/web-vue/Excel/Google/старая VM не меняются.
- Неизвестное null, не ноль/other. СНДЗ и нерешённый вопрос различны; решение без исполнения и выдача различны.
- Одна работа комиссии, независимые номера комплекса; чужой соседний номер не изменяется. Роль/должность/квалификация не смешиваются.
- Все даты Asia/Krasnoyarsk. Реальные роли не расширять автоматически; demo opt-in отдельно.
- Backend DB suites только последовательно, дождаться terminal handle. Один Vite0.0.0.0:5173, Django/PG loopback.
- API/UI договоры DTO и тела команд — точные в design, не заменять несогласованным PATCH.

## Review Focus

- Повтор старого save/complete/correct после следующего события не откатывает состояние и не раскрывает документы после отзыва права.
- Правка поступления, завершение и другая команда производства не оставляют конец до связанных фактов при конкурентных запросах.
- Число0, null, полный СНДЗ и T>0 не сливаются; готовность окончания не выдаётся за полноту отчёта.
- После закрытия счётчик и фильтр используют конец, а незакрытая пауза не изображает несуществующее возобновление.
- Потеря ответа/409/перечитывание карточки сохраняют нормализованный payload/key, файл и черновик, включая нативную отправку браузером.

---

### Task 1: Справочники причин и неизменяемые черновики результата

**Files:** Create `backend/apps/expertises/{results,result_serializers,result_api}.py`, `backend/apps/references/result_seeds.py`, `management/commands/seed_result_catalogs.py`; modify expertises models/serializers/api/urls, references models/api, documents models/serializers/policies, accounts/catalog.py; migrations. Tests `backend/tests/test_result_drafts.py`.

**Interfaces:** Consume locked_work,require_work,execute_once,audit,DocumentLink/Reference serializers. Produce ResultRevision FKwork unique(work,number), all typed result fields from design, document/whole-SNDZ reason nullable, actor/created/reason. UnresolvedAllocation unique(result,reason), count>=1, comment/document. Separate SndzReason,UnresolvedQuestionReason,ReturnReason inherit Reference, catalogs sndz-reasons/unresolved-question-reasons/return-reasons. seed_result_catalogs is idempotent, preserves names/deactivation. `save_result(*,actor,expertise_id,data,key,payload)` stores minimal event receipt; GET result-options and POST result match design. Current result is latest revision; GET work adds histories/readiness; closure placeholders until Task2. New references allowed for expertise.view/result.draft/complete/closed.correct, independently from references.manage. Readiness distinguishes completion blockers from report gaps, full stats/allocations known checks without zero inference. Existing inactive selection can be retained in same work but not newly introduced. Result document kinds scoped links do not grant upload.

- [x] Step1: RED tests: 2+1+1=4, unknown S remainsnull; 4≠2+1+0 rejected; negative/fractional rejected; complete flag needs all values; known parts>Q rejected. Allocation sum2=T2 valid, sum3>T2 or duplicate reason invalid; other without comment invalid, unknown staysempty. Save twice append revisions, no state close; same-key replay after next save fresh version with original event ID. Inactive new choice400/retained old allowed; seed twice preserves edited/deactivated and no journal changes. Kind/category conflict400. Pending copy allowed draft/readiness blocks, wrong kind rejected, unrelated doc403, linked clerk file own readable/revoked redacted/upload denied. Mixed rights/own scope sibling denied. Run focused expected missing models/routes RED, not environment errors.
- [x] Step2: Implement typed schema and serializers/services/options/readiness, preload histories, document policy and catalog extensions. No completion advertised until implemented. Migration generated.
- [x] Step3: Run focused GREEN then task-done full backend `infra/local.py backend -m pytest`, check/makemigrations check; commit `feat: save versioned expertise results and reason catalogs` only after success. No concurrent pytest.

### Task 2: Завершение возврат и корректировка с достоверной хронологией

**Files:** Modify expertises results/result_api/result_serializers/models/production/api/serializers/urls, intake/services, documents/policies, accounts/catalog and bootstrap templates; create `calendar_query.py`, migrations, tests `test_result_completion.py`, `test_result_concurrency.py`, `test_http_results.py`; opt-in in bootstrap_workflow_demo/infra/local.py and tests.

**Interfaces:** Consume Task1 revisions/readiness/DTO and Receipt→Expertise lock. Produce WorkClosure immutable unique(work,number), kind,ended_on,result_revision?,document?,return_reason?,comment,actor,created_at,reason; latest proof drives current end. `complete_work`, `return_work`, `correct_closed_work` same keyword conventions returning minimal event ID; endpoints and bodies exactly design. Closed correct creates revision/proof, no reopen or kind switch. completed_on cannot precede received/latest suspension/resume/deadline factual date or be future; current due may be later. Completion requires latest revision/date/persisted correctly typed file, not every optional statistic. Return needs persisted return_decision, unknown reason stays gap, no issue date. production.counted_through ends known closed counts, open pause clipped at end without fake resume. Scoped SQL calendar filters include known closed before pagination, exclude unknown. Receipt amendment protects latest confirmed closure. Demo --enable-results adds only new own expert draft/return rights explicitly, never alters existing real members/passwords/qualifications.

- [x] Step1: RED: complete draft-without-file400, actual file works/statecompleted/immutable closure/current assignments retained; expired/new role authority not inferred from title, former/sibling denies. Full SNDZ distinct from conclusion with T; research_act onlycat6. Unknown optional stats allowed with report_gaps, no inferred zeros. Return statewithout_execution, no issue/issued date; ordinary complete cannot edit closed. closed.correct retains old versions, requiresreason andspecificright, can't reopen/switch closure type. Dates before factual pause/deadline/before receipt/future rejected; open pause closes counting but no resumed_on. Closed calendar10 through10.10 stays10 whenas_of20.10, range boundaries before pagination known/unknown. Same key retry after correction fresh proof; concurrent distinctkeys one success/409, samekey one event; amend-versus-complete no invalid chronology. Separate real HTTP sessions draft/complete/read/correct; revoked evidence redacted. Demo default preserves roles; explicit only demo new rights and refuses real role members.
- [x] Step2: Implement atomic commands, closure-linked policy, production end and SQL filters. Add migrations; existing registration/upload/production replay tests remain.
- [x] Step3: Focused GREEN then task-done full serialized backend/check/migrations, commit `feat: complete and correct expertise results with closure history` after success.

### Task 3: Vue результат и реальные рабочие сценарии

**Files:** Create `frontend/src/modules/expertises/{ResultPanel.vue,ResultPanel.test.ts}`; modify ExpertisePage, ProductionPanel/tests, shared document form/types/fixtures and registry if needed. Update README and `docs/verification-results.md`.

**Interfaces:** Consume exact design DTOs/options/commands/allowed_actions. Forms explicit draft/complete/return/correct; no fictional issue button. Dynamic separate reason selects, numbers preserve empty=null, optional partial stats and readiness gaps plainly labelled. Preview typed result/return docs, revision/proof history; completion and issue distinct. Dirty guard and exact attempt-body/key through403/409/lost reply/unchanged refresh; normalized whitespace not new payload, replay not blocked by native changed min. Current assignments not ended by frontend. Counter shows counted_through and terminal pause correctly.

- [x] Step1: RED component tests for permission gates, null/zero, separate SNDZ/T and return, dynamic catalogs/inactive choices, complete blocked without file, draft save versus complete/correct endpoints, histories/readiness, staleGET cancellation, retained numeric/doc drafts after409/lost reply; preserve full existing suite.
- [x] Step2: Implement full-width consistent result panel, integrate typed contracts and guarded forms; no hard-coded role switcher.
- [x] Step3: Full frontend tests/typecheck/build, full backend already serialized; actual browser demo expert2 draft→upload→complete→read/authorized correct, no automatic issue. Return on another explicitly DEMO work; role denial via HTTP. Keep one Vite, no push.
- [x] Step4: Commit `feat: connect result completion and correction forms in Vue`; one fresh whole-slice review and one TDD Important/Critical fix pass, preserve all rulings/minors in tracked record. Entire goal remains active until correspondence/issue/import/15.1 and full-role verification are done.
