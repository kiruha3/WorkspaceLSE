from django.db import transaction
from rest_framework.exceptions import ValidationError
from apps.accounts.commands import execute_once
from apps.accounts.services import audit, check_version
from apps.documents.models import Document
from apps.documents.policies import require_document
from .models import ResultRevision, UnresolvedAllocation
from .policies import require_work
from .production import locked_work, validate_event_date, OPEN_STATES


def latest_result(work):
    return max(work.result_revisions.all(),key=lambda r:r.number,default=None)


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


def create_revision(work,actor,data,reason):
    values=data.copy();allocations=values.pop("unresolved_allocations")
    previous=latest_result(work)
    kind=values["kind"]
    if kind and ((work.category_code=="6" and kind!="research_act") or (work.category_code!="6" and kind=="research_act")):
        raise ValidationError({"kind":"Вид результата не соответствует категории работы."})
    if values["completed_on"]:validate_event_date(work,values["completed_on"],"completed_on")
    values["document"]=checked_document(actor,values["document"],kind=kind)
    values["sndz_reason"]=locked_reference(values["sndz_reason"],{previous.sndz_reason_id} if previous else set(),"sndz_reason_id")
    previous_reasons={a.reason_id for a in previous.unresolved_allocations.all()} if previous else set()
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
    blockers=[];gaps=[]
    def issue(target,code,field,message):target.append({"code":code,"field":field,"message":message})
    if result is None:
        issue(blockers,"result_missing","result_id","Сначала сохраните результат.")
        return {"completion_blockers":blockers,"report_gaps":gaps}
    if result.kind is None:issue(blockers,"kind_missing","kind","Укажите вид результата.")
    if result.completed_on is None:issue(blockers,"date_missing","completed_on","Укажите дату окончания.")
    else:
        try:validate_event_date(work,result.completed_on,"completed_on")
        except ValidationError:issue(blockers,"date_invalid","completed_on","Проверьте дату окончания относительно поступления и текущей даты.")
    if result.document_id is None or not result.document.versions.exists():
        issue(blockers,"file_missing","document_id","Подкрепите сохранённый файл итогового документа.")
    elif result.kind!=result.document.kind:
        issue(blockers,"document_kind","document_id","Вид документа не соответствует результату.")
    if not result.statistics_complete:issue(gaps,"statistics_unconfirmed","statistics_complete","Статистика вопросов не подтверждена как полная; пустое не равно нулю.")
    if result.complexity_level is None:issue(gaps,"complexity_missing","complexity_level","Не указана категория сложности.")
    if result.kind=="sndz" and result.sndz_reason_id is None:
        issue(gaps,"sndz_reason_missing","sndz_reason_id","Не определена причина полного СНДЗ.")
    if result.unresolved and not result.allocations_complete:
        issue(gaps,"allocations_unconfirmed","allocations_complete","Причины нерешённых вопросов не распределены полностью.")
    return {"completion_blockers":blockers,"report_gaps":gaps}


@transaction.atomic
def save_result(*,actor,expertise_id,data,key,payload):
    work=locked_work(expertise_id);action="expertise.result.draft"
    require_work(actor,"expertise.view",work);require_work(actor,action,work)
    def operation():
        check_version(work,data["expected_version"])
        if work.state not in OPEN_STATES:raise ValidationError("Для закрытой работы нужна отдельная корректировка.")
        values={k:v for k,v in data.items() if k not in ("expected_version","reason")}
        revision=create_revision(work,actor,values,data["reason"])
        work.version+=1;work.save(update_fields=["version"])
        audit(actor,action,work,{"result_id":str(revision.id),"number":revision.number,"version":work.version},data["reason"])
        return {"id":str(revision.id),"expertise_id":str(work.id)}
    return execute_once(actor=actor,action=action,key=key,payload={"expertise_id":str(expertise_id),"data":payload},operation=operation)
