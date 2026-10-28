from datetime import timedelta
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from apps.accounts.commands import execute_once
from apps.accounts.services import audit,check_version
from .models import Expertise,Suspension,DeadlineEvent
from .policies import require_work

METHOD="calendar_inclusive_pause_half_open_v1"
OPEN_STATES=("in_progress","suspended")


def calculate_days(received_at,intervals,as_of):
    calendar=max((as_of-received_at).days+1,0)
    end=as_of+timedelta(days=1)
    paused=sum(max((min(resumed or end,end)-max(suspended,received_at)).days,0) for suspended,resumed in intervals)
    return {"calendar_days":calendar,"paused_days":paused,"active_calendar_days":max(calendar-paused,0)}


def production_summary(work,as_of=None):
    as_of=as_of or timezone.localdate()
    from .results import latest_closure
    closure=latest_closure(work) if work.state not in OPEN_STATES else None
    from .history import historical_end_on,historical_record
    history=historical_record(work)
    known_end=closure.ended_on if closure else historical_end_on(work)
    through=as_of if work.state in OPEN_STATES else min(known_end,as_of) if known_end else None
    counts=calculate_days(work.receipt.received_at,[(s.suspended_on,s.resumed_on) for s in work.suspensions.all()],through) if through else {"calendar_days":None,"paused_days":None,"active_calendar_days":None}
    if history is not None and not history.suspension_history_complete:counts.update(paused_days=None,active_calendar_days=None)
    events=list(work.deadline_events.all())
    def latest(kind):
        matching=[e for e in events if e.kind==kind]
        return max(matching,key=lambda e:(e.recorded_on,e.created_at,e.id)).due_on if matching else None
    initial,agreed,requested=latest("initial"),latest("agreement"),latest("request")
    current=agreed or initial
    return {"as_of":as_of.isoformat(),"counted_through":through.isoformat() if through else None,"method":METHOD,**counts,"initial_due_on":initial.isoformat() if initial else None,"agreed_due_on":agreed.isoformat() if agreed else None,"current_due_on":current.isoformat() if current else None,"last_requested_due_on":requested.isoformat() if requested else None,"overdue_calendar_days":max((as_of-current).days,0) if current and work.state in OPEN_STATES else None}


def validate_event_date(work,value,field):
    if value<work.receipt.received_at:raise ValidationError({field:"Дата раньше поступления материалов."})
    if value>timezone.localdate():raise ValidationError({field:"Фактическая дата не может быть будущей."})


def locked_work(expertise_id):
    from apps.intake.locking import locked_receipt
    # Material -> receipt -> work also serializes production with full issue.
    receipt_id=get_object_or_404(Expertise.objects.only("receipt_id"),pk=expertise_id).receipt_id
    locked_receipt(receipt_id)
    return get_object_or_404(Expertise.objects.select_for_update(),pk=expertise_id)


@transaction.atomic
def _transition(*,actor,expertise_id,data,key,payload,kind):
    work=locked_work(expertise_id)
    action="expertise."+kind
    require_work(actor,"expertise.view",work)
    require_work(actor,action,work)
    from .history import require_operational
    require_operational(work)

    def operation():
        check_version(work,data["expected_version"])
        if work.state not in OPEN_STATES:raise ValidationError("Производство завершено. Нужна отдельная процедура корректировки.")
        if kind=="suspend":
            if work.state!="in_progress":raise ValidationError("Работа уже приостановлена.")
            on=data["suspended_on"];validate_event_date(work,on,"suspended_on")
            previous=work.suspensions.order_by("-suspended_on","-created_at").first()
            if previous and (previous.resumed_on is None or on<previous.resumed_on):
                raise ValidationError({"suspended_on":"Новая приостановка пересекает предыдущий интервал."})
            event=Suspension.objects.create(expertise=work,suspended_on=on,reason=data["reason"],actor=actor)
            work.state="suspended"
        else:
            if work.state!="suspended":raise ValidationError("Работа не приостановлена.")
            on=data["resumed_on"];validate_event_date(work,on,"resumed_on")
            event=work.suspensions.filter(resumed_on__isnull=True).first()
            if event is None:raise ValidationError("Открытый интервал не найден. Обновите карточку.")
            if on<event.suspended_on:raise ValidationError({"resumed_on":"Возобновление раньше приостановки."})
            event.resumed_on=on;event.resume_reason=data["reason"];event.resumed_by=actor;event.resumed_recorded_at=timezone.now()
            event.save(update_fields=["resumed_on","resume_reason","resumed_by","resumed_recorded_at"])
            work.state="in_progress"
        work.version+=1;work.save(update_fields=["state","version"])
        audit(actor,action,work,{"suspension_id":str(event.id),"state":work.state,"version":work.version,"date":on},data["reason"])
        return {"id":str(event.id),"expertise_id":str(work.id)}

    return execute_once(actor=actor,action=action,key=key,payload={"expertise_id":str(expertise_id),"data":payload},operation=operation)


def suspend_work(**kwargs):return _transition(**kwargs,kind="suspend")


def resume_work(**kwargs):return _transition(**kwargs,kind="resume")


@transaction.atomic
def record_deadline(*,actor,expertise_id,data,key,payload):
    from apps.documents.models import Document
    from apps.documents.policies import require_document
    work=locked_work(expertise_id)
    action="expertise.deadline.record"
    require_work(actor,"expertise.view",work)
    require_work(actor,action,work)
    from .history import require_operational
    require_operational(work)

    def operation():
        check_version(work,data["expected_version"])
        if work.state not in OPEN_STATES:raise ValidationError("Производство завершено. Нужна отдельная процедура корректировки.")
        validate_event_date(work,data["recorded_on"],"recorded_on")
        if data["due_on"]<work.receipt.received_at:raise ValidationError({"due_on":"Срок раньше поступления материалов."})
        document=data.get("document")
        if document:
            document=Document.objects.select_for_update().get(pk=document.pk)
            require_document(actor,"documents.view",document)
            if document.source_kind=="uploaded_copy" and not document.versions.exists():
                raise ValidationError({"document_id":"Сначала сохраните копию документа."})
        if data["kind"]=="agreement" and (document is None or document.kind not in ("deadline_agreement","resolution","decision")):
            raise ValidationError({"document_id":"Согласование требует подтверждения, а не документа запроса."})
        event=DeadlineEvent.objects.create(expertise=work,kind=data["kind"],recorded_on=data["recorded_on"],due_on=data["due_on"],reason=data["reason"],document=document,actor=actor)
        work.version+=1;work.save(update_fields=["version"])
        audit(actor,action,work,{"event_id":str(event.id),"kind":event.kind,"recorded_on":event.recorded_on,"due_on":event.due_on,"document_id":str(event.document_id) if event.document_id else None,"version":work.version},event.reason)
        return {"id":str(event.id),"expertise_id":str(work.id)}

    return execute_once(actor=actor,action=action,key=key,payload={"expertise_id":str(expertise_id),"data":payload},operation=operation)
