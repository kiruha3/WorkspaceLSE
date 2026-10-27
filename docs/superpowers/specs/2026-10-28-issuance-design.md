# Комплект и фактическая выдача материалов

Продолжение после `cfd2b2e`. Основания: `docs/specification.md` §5.4/6/7, `docs/access-control.md` §5/6, подтверждённый владельцем путь «эксперт завершает, делопроизводитель выдаёт». Прежний этап переписки принят: 244 backend / 122 frontend. Общая цель остаётся полным путём и отчётом 15.1, не одним этим срезом. Пользователь поручил продолжать без повторного согласования уже выбранного Django/Vue подхода.

## Выбор и границы

Выбран отдельный модуль `issuance` в том же Django-монолите. Комплект связан с материалом и всеми его работами. Флажок «выдано» у одного номера не подходит: при комплексе или нескольких работах он скрывает продолжающуюся работу и не фиксирует состав. Почтовая интеграция и электронная подпись не нужны для ручного факта выдачи. Повторно используются роли, версии, execute_once, документы/версии, аудит и Vue-компоненты.

Одна полная выдача на материал, один редактируемый комплект до неё. Это решение исполнителя, соответствующее запрету неутверждённой частичной выдачи. После выдачи новый номер на прежнем материале, изменение поступления и исправление закрытого результата требуют отдельной будущей процедуры: нельзя менять уже выданный пакет молча. Повтор команды с прежним ключом остаётся доступен по нынешним правам и возвращает прежний факт, не создавая второй.

Состав для обычного заключения: подтверждённый итоговый документ каждой работы, описание передаваемых материалов, подписка, сопроводительное; категории 1/5 дополнительно уведомление, 2/3 — счёт. Счёт не означает оплату, предоплата не блокирует выдачу. Документы готовятся вне системы и прикрепляются; автоматическая печать требует утверждённых шаблонов и остаётся следующим срезом. Подписка/сопроводительное/уведомление/счёт — новые типы Document. Имеющийся `letter` допустим для сопроводительного/уведомления, но не автоматически означает отправку.

Владельцу заданы два неблокирующих вопроса: комплекты 4/6/СНДЗ/возврата и число подписок комиссии. Пока нет ответа, соответствующие варианты дают `policy_unconfirmed`/`commission_policy_unconfirmed`, а не угадывают регламент. Эти варианты входят в общую цель и не объявляются готовыми. Неполная отчётная статистика не блокирует физическую выдачу сама по себе.

## Модель

- IssuePackage: UUID, OneToOne Material, version, created_by(User), created_at, current_revision nullable. Одна корневая версия для всех команд.
- PackageRevision: неизменяемая number, materials_description, note, actor(User), reason, created_at. PackageItem: revision, kind `expert_subscription|cover_letter|notification|invoice|other`, expertise(FK), document(FK), note. Документ можно сослать на несколько работ без копирования файла; повтор role/work запрещён кроме `other`. Результат не выбирается произвольно: берётся latest WorkClosure.accepted_version.
- PackageCheck: package, revision, actor/time/reason. CheckWork: check, expertise, closure — точный набор подтверждённых окончаний. CheckFile: check, item nullable, closure nullable, document, accepted_version nullable. Для бумажного оригинала копия необязательна; загружаемой копии нужен фактический файл. Ровно одна связь item или closure. Проверка фиксирует все версии под блокировкой документов.
- MaterialIssue: OneToOne package, checkFK, issued_on, methodFK IssueMethod, recipient_name, recipient_basis, tracking, comment, evidence_document?, accepted_evidence_version?, actor/time/reason. Дата не раньше поступлений и окончаний, не в будущем. Все ключевые факты типизированы; произвольного JSON «готовый пакет» нет.
- IssueMethod: обычный расширяемый Reference; начальные in_person/post/courier/other только ручные способы, seed сохраняет правки/неактивность. Новый неактивный выбор запрещён, сохранённая история читается.

Проверка комплекта не вводит согласование начальником. Её выполняет роль с `issue.check`; тот же делопроизводитель может подготовить, проверить и выдать, если назначены все права. Последующая новая редакция/работа/окончание или новая версия дополнительного документа делает проверку устаревшей. Новая версия уже принятого итогового файла сама по себе не заменяет WorkClosure.accepted_version. Перед выдачей готовность и совпадение снимка перепроверяются под блокировкой.

## Доступ и сериализация команд

Новые `issue.view` (own/departments/institution), `issue.prepare` и `issue.check` (departments/institution), существующее `issue.confirm` сохраняет смысл. Начальный делопроизводитель получает новые права только при создании шаблона; существующие реальные роли не расширяются. Учебные роли — только явным `--enable-issuance`, с отказом при неучебных участниках и без восстановления других отозванных прав.

Полная карточка/список комплекта требуют `expertise.view` и `issue.view` для **всех** работ материала. Действие требует своей области для всех работ, не наиболее широкого другого права. Пустой материал не выдаётся. Эксперт с own видит краткий факт выдачи своей работы, но не чужой состав. Недоступные документы остаются `{id,restricted:true}`; это блокирует проверку/выдачу, не раскрывая реквизитов. Прежний исполнитель после передачи не сохраняет own-доступ через старый ключ.

Единый порядок блокировок: Material → Receipt UUIDs → Expertise UUIDs → IssuePackage → Document UUIDs → Reference. Регистрация, поправка поступления и `production.locked_work` переходят на Material-first; подтверждение выдачи сериализуется с регистрацией нового номера и корректировкой результата. Отдельные команды переписки не блокируют Material и не закрываются автоматически выдачей. Документы не берут блокировку материала после собственной блокировки.

Каждая mutation требует reason/Idempotency-Key и expected_version комплекта кроме create. execute_once хранит только event/package IDs; свежий ответ строится после повторной проверки прав. Все отказы откатывают редакции/факты/аудит/receipt. Выданный комплект неизменяем. Исправление после выдачи отдельной процедурой остаётся явно незавершённой частью общей цели.

## Контракт

Префикс `/api/v1`. POST отвечает `{event:{id},package:PackageDTO}`, create201, остальные200. GET `/materials/{id}/issue-packages/` → `{material:{id,title},package:PackageDTO|null,can_prepare:boolean}`; POST туда создаёт черновик из Content+reason. GET `/issue-packages/` — стандартная пагинация PackageDTO, фильтры `search`, `state:draft|checked|needs_recheck|issued`, `issued_from/to` (только фактическая дата). GET `/issue-packages/{id}/`, GET `/{id}/readiness/`.

ContentInput={materials_description:string,note:string,items:[{kind,expertise_id,document_id,note}]}; пустые строки/массивы допустимы в черновике. POST `/{id}/draft/` = ContentInput+expected_version+reason, полная новая редакция. POST `/{id}/check/`={expected_version,reason}. POST `/{id}/issue/`={expected_version,reason,issued_on,method_id,recipient_name,recipient_basis,tracking,comment,evidence_document_id:null|UUID}. GET `/issue-packages/options/` → {methods:Reference[],item_kinds:[{code,name,document_kinds:string[]}]}. GET `/{id}/document-options/?kind&search` — постраничные доступные DocumentDTO, для выбора существующего документа.

PackageDTO={id,material:{id,title},version,state,content:Revision,content_history:Revision[],works:Work[],readiness:Readiness,checks:Check[],issuance:Issue|null,allowed_actions:string[]}. Revision={id,number,materials_description,note,items:[{id,kind,expertise_id,document:DocumentLink,note}],actor:Person,created_at,reason}. Work={id,registration_number,category_code,state,department:{id,code,name},is_commission,closure:{id,kind,ended_on,result_kind,document:DocumentLink}|null,required_items:string[]}. Readiness={blockers:[{code,field,message,expertise_id?:UUID}],can_check:boolean,can_issue:boolean,check_current:boolean}. Check={id,revision_id,actor,created_at,reason,works:[{expertise_id,closure_id}],files:[{item_id:null|UUID,closure_id:null|UUID,document:DocumentLink}]}. Issue={id,check_id,issued_on,method:Reference,recipient_name,recipient_basis,tracking,comment,evidence:DocumentLink,actor,created_at,reason}. Person={id,full_name}. State derives from issued fact, current check and live readiness.

GET `/expertises/{id}/issue-status/` → `{status:unavailable|not_issued|issued,issued_on:null|date,package:null|{id,restricted?:true}}`, требует workview; не сообщает скрытые работы/счётчики. `supported_modules` добавляет `issuance` только после готовности команд. Vue без признака скрывает модуль.

UI `/issue-packages` журнал, `/issue-packages/:id` комплект. В карточке экспертизы — отдельный блок выдачи и переход к материалу `/issue-packages/new?material_id=...`. Сначала показаны все доступные работы и недостающие части; общий итог не выдумывается по одному номеру. Подготовка, проверка и фактическая выдача отдельными формами. Использовать существующие BasisDocumentForm/Preview, неизвестный файл/дата не превращаются в подтверждённые. Незавершённые вводы/подготовленный файл/ключ сохраняются при409/403/потереответа, версия формы привязана к источнику, refresh не перебазирует черновик молча; явная приёмка новой версии. Dirtyguards, scopednavigation, безопасныйreturnURL, отмена запоздалыхGET.

## Проверка

PostgreSQL pytest последовательно; неполные/разные комплекты, неизвестные политики, физические материалы, все работы/чужой отдел, дата/получатель, бумажный оригинал, версия принятого результата, поздние файлы/устаревшая проверка, повтор/коллизия ключей, отзыв прав, гонки выдача↔регистрация/корректировка и две выдачи. Fullfrontend/typecheck/build; IAB полный учебный путь подготовки→проверки→выдачи и запрет преждевременной выдачи, эксперт читает факт без права выдать. Один итоговый freshreview/одинImportantfixpass. PHP/старые базы/Excel/Google не трогать; одинVite0.0.0.0:5173, одинbackend8000, PG55432, без новыхзависимостей/push/merge/VM.
