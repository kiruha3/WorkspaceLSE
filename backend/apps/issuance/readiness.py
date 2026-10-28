from apps.accounts.policies import permission_scopes
from apps.documents.policies import can_document
from apps.expertises.results import latest_closure

DOCUMENT_KINDS = {
    "expert_subscription": ["expert_subscription"], "cover_letter": ["cover_letter", "letter"],
    "notification": ["notification", "letter"], "invoice": ["invoice"],
    "other": ["expert_subscription", "cover_letter", "notification", "invoice", "letter"],
}


def required_items(work, closure):
    if not closure: return []
    if work.is_commission or closure.kind != "completed" or closure.result.kind != "expert_conclusion" or work.category_code not in ("1", "2", "3", "5"): return []
    return ["expert_subscription", "cover_letter", "notification" if work.category_code in ("1", "5") else "invoice"]


def current_facts(package):
    works = list(package.material.expertises.select_related("department", "receipt","historical").prefetch_related("closures__document__versions", "closures__result"))
    closures = {work.pk: latest_closure(work) for work in works}
    items = list(package.current_revision.items.select_related("document").prefetch_related("document__versions"))
    files = []
    for closure in closures.values():
        if closure:
            files.append((None, closure.pk, closure.document, closure.accepted_version_id))
    for item in items:
        latest = max(item.document.versions.all(), key=lambda value: value.number, default=None)
        files.append((item.pk, None, item.document, latest.pk if latest else None))
    return works, closures, items, files


def check_matches(package, facts=None):
    checks = list(package.checks.all())
    if not checks: return False
    check = checks[-1]
    if check.revision_id != package.current_revision_id: return False
    works, closures, _, files = facts if facts is not None else current_facts(package)
    expected_works = {(work.pk, closures[work.pk].pk) for work in works if closures[work.pk]}
    actual_works = {(item.expertise_id, item.closure_id) for item in check.works.all()}
    expected_files = {(item_id, closure_id, document.pk, version_id) for item_id, closure_id, document, version_id in files}
    actual_files = {(item.item_id, item.closure_id, item.document_id, item.accepted_version_id) for item in check.files.all()}
    return len(expected_works) == len(works) and expected_works == actual_works and expected_files == actual_files


def readiness(package, user, scopes=None):
    scopes = permission_scopes(user) if scopes is None else scopes
    blockers = []
    def add(code, field, message, work=None):
        item = {"code": code, "field": field, "message": message}
        if work: item["expertise_id"] = str(work.pk)
        blockers.append(item)
    facts = current_facts(package)
    works, closures, items, files = facts
    if not package.current_revision.materials_description.strip(): add("materials_missing", "materials_description", "Опишите передаваемые материалы дела.")
    if not works: add("works_missing", "works", "У материала нет зарегистрированных работ.")
    for work in works:
        history=getattr(work,"historical",None)
        if history and history.issued_on is not None:add("historical_issue_recorded","works","В журнале уже отмечена выдача. Нужна отдельная сверка движения материалов.",work)
        closure = closures[work.pk]
        if work.state not in ("completed", "without_execution") or not closure:
            add("work_open", "works", "Работа ещё не завершена.", work); continue
        if work.is_commission:
            add("commission_policy_unconfirmed", "items", "Нужно подтвердить комплект подписок комиссии.", work)
        elif not required_items(work, closure):
            add("policy_unconfirmed", "items", "Состав выдачи для этого вида результата или категории пока не утверждён.", work)
        for kind in required_items(work, closure):
            if not any(item.kind == kind and item.expertise_id == work.pk for item in items):
                add("item_missing", kind, "Нет обязательного документа комплекта.", work)
        if not closure.accepted_version_id: add("file_missing", "result", "У подтверждённого итога нет принятого файла.", work)
    for item_id, closure_id, document, version_id in files:
        if not can_document(user, "documents.view", document):
            add("document_unavailable", "items" if item_id else "result", "Документ недоступен для проверки.")
        elif not version_id and document.source_kind != "paper_original":
            add("file_missing", "items" if item_id else "result", "У загружаемой копии нет сохранённого файла.")
    current = check_matches(package, facts)
    issued = getattr(package, "issuance", None)
    return {"blockers": blockers, "can_check": not blockers and not issued, "can_issue": not blockers and current and not issued, "check_current": current}
