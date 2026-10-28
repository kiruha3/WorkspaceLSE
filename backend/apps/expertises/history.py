"""Typed source facts, not invented native workflow events."""
from rest_framework.exceptions import ValidationError
from apps.accounts.policies import AccessScope

FIELDS=("result_kind","completed_on","return_decided_on","issued_on","complexity_level","questions","categorical","probable","unresolved","amount","authority_type","authority_name","official","contact","basis_text","case_description","inventory","executor_raw","unresolved_note","unresolved_reason_raw","notes","delivery")


def historical_record(work):
    return getattr(work,"historical",None) if work.origin_kind=="historical" else None


def require_operational(work):
    if work.origin_kind=="historical" and not (historical_record(work) and work.historical.operational):
        raise ValidationError("Историческая работа требует отдельного подтверждения основания и сведений для продолжения нового учёта.")


def current_history_employee_ids(work):
    history=historical_record(work)
    if history is None or list(work.assignments.all()):return set()
    return {item.employee_id for item in history.participants.all()}


def historical_end_on(work):
    history=historical_record(work)
    if history is None:return None
    return history.completed_on if work.state=="completed" else history.return_decided_on if work.state=="without_execution" else None


def historical_facts(work):
    from .results import latest_closure
    from apps.issuance.models import MaterialIssue
    history=historical_record(work)
    facts={field:getattr(history,field) if history else None for field in FIELDS}
    facts.update(expertise_id=str(work.pk),registration_number=work.registration_number,origin_kind=work.origin_kind,
        state=work.state,received_on=work.receipt.received_at,category_code=work.category_code,
        department_code=work.department.code,specialty_code=work.specialty.code if work.specialty_id else None,
        appointment_nature=work.appointment_nature,is_commission=work.is_commission,
        statistics_confirmed=history.statistics_confirmed if history else False,
        source_row_id=str(history.source_row_id) if history else None)
    closure=latest_closure(work)
    if closure:
        facts.update(completed_on=closure.ended_on if closure.kind=="completed" else None,
            return_decided_on=closure.ended_on if closure.kind=="without_execution" else None)
        accepted=closure.result
        for field in ("complexity_level","questions","categorical","probable","unresolved"):
            facts[field]=getattr(accepted,field) if accepted else None
        facts["result_kind"]=accepted.kind if accepted else None
        facts["statistics_confirmed"]=accepted.statistics_complete if accepted else False
    issue=MaterialIssue.objects.filter(package__material_id=work.material_id).first()
    if issue:facts["issued_on"]=issue.issued_on
    return facts


def report_gaps(work,history):
    gaps=[]
    def gap(code,field,message):gaps.append({"code":code,"field":field,"message":message})
    if work.specialty_id is None:gap("specialty_missing","specialty_id","Специальность исторической работы не уточнена; известные общие показатели не пропадают.")
    if work.appointment_nature is None or work.is_commission is None or not history.complex_known:gap("composition_unknown","composition","Характер назначения или состав работы пока не уточнены.")
    if work.state=="completed":
        if history.completed_on is None:gap("historical_end_unknown","completed_on","В журнале нет достоверной даты окончания.")
        if history.result_kind is None:gap("historical_result_unknown","result_kind","Вид исторического результата не уточнён.")
    if work.state=="without_execution" and history.return_decided_on is None:gap("historical_end_unknown","return_decided_on","Дата решения без исполнения не уточнена; выдача не заменяет её.")
    if not history.suspension_history_complete:gap("pause_history_unknown","suspensions","История приостановок до переноса не подтверждена как полная.")
    if not history.statistics_confirmed:gap("statistics_unconfirmed","statistics_confirmed","Статистика вопросов источника не подтверждена как полная.")
    if history.unresolved:gap("historical_reasons_unmapped","unresolved_reason_raw","Причины нерешённых вопросов сохранены текстом, но не распределены по справочнику.")
    return gaps


def historical_output(work,user,scopes):
    history=historical_record(work)
    if history is None:return None
    source=history.source_row;batch=source.batch
    can_source=scopes.get("imports.results.view",AccessScope()).allows()
    values={field:getattr(history,field) for field in FIELDS}
    values["amount"]=str(history.amount) if history.amount is not None else None
    return {"id":str(history.pk),**values,"operational":history.operational,"complex_known":history.complex_known,
        "composition_known":work.appointment_nature is not None and work.is_commission is not None and history.complex_known,
        "suspension_history_complete":history.suspension_history_complete,"statistics_confirmed":history.statistics_confirmed,
        "current_participants":[{"id":str(item.employee_id),"full_name":item.employee.full_name} for item in history.participants.all()],
        "source":{"batch_id":str(batch.pk),"row_id":str(source.pk),"source_row":source.source_row,"origin_url":batch.origin_url if can_source else None,"source_observed_at":batch.source_observed_at},
        "report_gaps":report_gaps(work,history)}
