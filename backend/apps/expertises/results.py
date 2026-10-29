from django.db import transaction
from rest_framework.exceptions import ValidationError
from apps.accounts.commands import execute_once
from apps.accounts.services import audit, check_version
from apps.documents.models import Document
from apps.documents.policies import require_document
from apps.intake.locking import require_not_issued
from .models import ResultRevision, UnresolvedAllocation, WorkClosure
from .policies import require_work
from .production import locked_work, validate_event_date, OPEN_STATES


def latest_result(work):
    return max(work.result_revisions.all(),key=lambda r:r.number,default=None)


def latest_closure(work):
    return max(work.closures.all(),key=lambda c:c.number,default=None)


def validate_ending(work,on,field="completed_on"):
    validate_event_date(work,on,field)
    dates=[s.suspended_on for s in work.suspensions.all()]
    dates += [s.resumed_on for s in work.suspensions.all() if s.resumed_on]
    dates += [e.recorded_on for e in work.deadline_events.all()]
    if dates and on<max(dates):
        raise ValidationError({field:"Окончание раньше внесённого факта производства. Уточните даты по документам."})


def locked_reference(reference,previous_ids,field):
    if reference is None:return None
    current=type(reference).objects.select_for_update().get(pk=reference.pk)
    if not current.is_active and current.pk not in previous_ids:
        raise ValidationError({field:"Неактивное значение нельзя выбрать впервые."})
    return current


def checked_document(actor,document,*,kind=None):
    if document is None:return None
    document=Document.objects.select_for_update().get(pk=document.pk)
    require_document(actor,"documents.view",document)
    if kind and document.kind!=kind:
        raise ValidationError({"document_id":"Вид документа не соответствует результату."})
    return document


def create_revision(work,actor,data,reason,*,retained_references=None):
    retained_references=retained_references or {}
    values=data.copy();allocations=values.pop("unresolved_allocations")
    previous=latest_result(work)
    kind=values["kind"]
    if kind and ((work.category_code=="6" and kind!="research_act") or (work.category_code!="6" and kind=="research_act")):
        raise ValidationError({"kind":"Вид результата не соответствует категории работы."})
    if values["completed_on"]:validate_event_date(work,values["completed_on"],"completed_on")
    document_ids={d.pk for d in [values["document"],*[a["document"] for a in allocations]] if d is not None}
    # Acquire ALL document locks before reference locks, including the main
    # document: different works can cross-reference each other's evidence.
    list(Document.objects.select_for_update().filter(pk__in=document_ids).order_by("pk"))
    values["document"]=checked_document(actor,values["document"],kind=kind)
    values["sndz_reason"]=locked_reference(values["sndz_reason"],set(work.result_revisions.values_list("sndz_reason_id",flat=True))|retained_references.get('sndz_reason',set()),"sndz_reason_id")
    previous_reasons=set(UnresolvedAllocation.objects.filter(result__expertise=work).values_list("reason_id",flat=True))|retained_references.get('unresolved_allocations',set())
    # Deterministic reference/document order avoids opposite allocation lock orders.
    checked=[]
    for allocation in sorted(allocations,key=lambda a:str(a["reason"].pk)):
        item=allocation.copy()
        item["reason"]=locked_reference(item["reason"],previous_reasons,"unresolved_allocations")
        item["document"]=checked_document(actor,item["document"])
        checked.append(item)
    revision=ResultRevision.objects.create(expertise=work,number=previous.number+1 if previous else 1,actor=actor,reason=reason,**values)
    UnresolvedAllocation.objects.bulk_create([UnresolvedAllocation(result=revision,**item) for item in checked])
    return revision


def result_readiness(work,result=None):
    result=result if result is not None else latest_result(work)
    blockers=[];gaps=[];documents=[]
    def issue(target,code,field,message):target.append({"code":code,"field":field,"message":message})
    closure=latest_closure(work)
    if work.state=="without_execution" and closure:
        if closure.document is None or not (closure.document.source_url or closure.document.versions.exists()):
            issue(documents,"file_missing","document_id","Не прикреплён документ решения без исполнения. Можно добавить позднее.")
        if closure.return_reason_id is None:issue(gaps,"return_reason_missing","return_reason_id","Не определена причина решения без исполнения.")
        return {"completion_blockers":blockers,"report_gaps":gaps,"document_gaps":documents}
    if result is None:
        issue(blockers,"result_missing","result_id","Сначала сохраните результат.")
        return {"completion_blockers":blockers,"report_gaps":gaps,"document_gaps":documents}
    if result.kind is None:issue(blockers,"kind_missing","kind","Укажите вид результата.")
    if result.completed_on is None:issue(blockers,"date_missing","completed_on","Укажите дату окончания.")
    else:
        try:validate_ending(work,result.completed_on,"completed_on")
        except ValidationError:issue(blockers,"date_invalid","completed_on","Проверьте дату окончания относительно поступления и текущей даты.")
    if result.document_id is None or not (result.document.source_url or result.document.versions.exists()):
        issue(documents,"file_missing","document_id","Не прикреплён итоговый документ. Можно завершить работу и добавить документ позднее.")
    if result.document_id is not None and result.kind!=result.document.kind:
        issue(blockers,"document_kind","document_id","Вид документа не соответствует результату.")
    if not result.statistics_complete:issue(gaps,"statistics_unconfirmed","statistics_complete","Статистика вопросов не подтверждена как полная; пустое не равно нулю.")
    if result.complexity_level is None:issue(gaps,"complexity_missing","complexity_level","Не указана категория сложности.")
    if result.kind=="sndz" and result.sndz_reason_id is None:
        issue(gaps,"sndz_reason_missing","sndz_reason_id","Не определена причина полного СНДЗ.")
    if result.unresolved and not result.allocations_complete:
        issue(gaps,"allocations_unconfirmed","allocations_complete","Причины нерешённых вопросов не распределены полностью.")
    return {"completion_blockers":blockers,"report_gaps":gaps,"document_gaps":documents}


@transaction.atomic
def save_result(*,actor,expertise_id,data,key,payload):
    work=locked_work(expertise_id);action="expertise.result.draft"
    require_work(actor,"expertise.view",work);require_work(actor,action,work)
    from .history import require_operational
    require_operational(work)
    def operation():
        check_version(work,data["expected_version"])
        if work.state not in OPEN_STATES:raise ValidationError("Для закрытой работы нужна отдельная корректировка.")
        values={k:v for k,v in data.items() if k not in ("expected_version","reason")}
        revision=create_revision(work,actor,values,data["reason"])
        work.version+=1;work.save(update_fields=["version"])
        audit(actor,action,work,{"result_id":str(revision.id),"number":revision.number,"version":work.version},data["reason"])
        return {"id":str(revision.id),"expertise_id":str(work.id)}
    return execute_once(actor=actor,action=action,key=key,payload={"expertise_id":str(expertise_id),"data":payload},operation=operation)


def confirm_result(work,actor,result):
    if result is None:raise ValidationError({"result_id":"Сохраните текущую редакцию результата."})
    if result.completed_on:validate_ending(work,result.completed_on)
    blockers=result_readiness(work,result)["completion_blockers"]
    if blockers:raise ValidationError({item["field"]:item["message"] for item in blockers})
    checked_document(actor,result.document,kind=result.kind)


def create_closure(work,actor,*,reason,kind,ended_on,document,result=None,return_reason=None,comment=""):
    previous=latest_closure(work)
    # checked_document already holds the same lock as add_file_version. Pin
    # the actual accepted bytes, not a moving "latest file" relation.
    accepted=document.versions.order_by("-number").first() if document is not None else None
    closure=WorkClosure.objects.create(expertise=work,number=previous.number+1 if previous else 1,kind=kind,ended_on=ended_on,document=document,accepted_version=accepted,result=result,return_reason=return_reason,comment=comment,actor=actor,reason=reason)
    work.state=kind;work.version+=1;work.save(update_fields=["state","version"])
    return closure


def return_values(work,actor,data,*,retained_references=None):
    validate_ending(work,data["decided_on"],"decided_on")
    document=checked_document(actor,data["document"],kind="return_decision")
    reason=locked_reference(data["return_reason"],set(work.closures.values_list("return_reason_id",flat=True))|(retained_references or {}).get('return_reason',set()),"return_reason_id")
    if reason and reason.code=="other" and not data["comment"]:
        raise ValidationError({"comment":"Для иной причины нужно пояснение."})
    return {"kind":"without_execution","ended_on":data["decided_on"],"document":document,"return_reason":reason,"comment":data["comment"]}


@transaction.atomic
def _close(*,actor,expertise_id,data,key,payload,command):
    work=locked_work(expertise_id)
    action={"complete":"expertise.complete","return":"expertise.return_without_execution","correct":"expertise.closed.correct"}[command]
    require_work(actor,"expertise.view",work);require_work(actor,action,work)
    from .history import require_operational
    require_operational(work)
    def operation():
        check_version(work,data["expected_version"])
        if command=="correct":
            require_not_issued(work.material_id)
            previous=latest_closure(work)
            if work.state in OPEN_STATES or previous is None:raise ValidationError("Нет подтверждённого окончания для корректировки.")
            expected="result" if work.state=="completed" else "return"
            if data["correction_kind"]!=expected:raise ValidationError({"correction_kind":"Корректировка не меняет вид закрытия и не переоткрывает работу."})
            if expected=="result":
                result=create_revision(work,actor,data["result"],data["reason"])
                confirm_result(work,actor,result)
                values={"kind":"completed","ended_on":result.completed_on,"document":result.document,"result":result}
            else:values=return_values(work,actor,data)
        else:
            if work.state not in OPEN_STATES:raise ValidationError("Работа уже закрыта. Нужна отдельная корректировка.")
            if command=="complete":
                result=latest_result(work)
                if result is None or result.pk!=data["result_id"]:raise ValidationError({"result_id":"Подтвердить можно только текущую редакцию результата."})
                confirm_result(work,actor,result)
                values={"kind":"completed","ended_on":result.completed_on,"document":result.document,"result":result}
            else:values=return_values(work,actor,data)
        closure=create_closure(work,actor,reason=data["reason"],**values)
        audit(actor,action,work,{"closure_id":str(closure.pk),"accepted_version_id":str(closure.accepted_version_id),"result_id":str(closure.result_id) if closure.result_id else None,"kind":closure.kind,"ended_on":closure.ended_on,"version":work.version},data["reason"])
        return {"id":str(closure.pk),"expertise_id":str(work.pk)}
    return execute_once(actor=actor,action=action,key=key,payload={"expertise_id":str(expertise_id),"data":payload},operation=operation)


def complete_work(**kwargs):return _close(**kwargs,command="complete")
def return_work(**kwargs):return _close(**kwargs,command="return")
def correct_closed_work(**kwargs):return _close(**kwargs,command="correct")
