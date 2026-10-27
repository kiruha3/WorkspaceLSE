from datetime import timedelta
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from apps.accounts.commands import execute_once
from apps.accounts.services import audit,check_version
from .models import Expertise,Suspension
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
    counts=calculate_days(work.receipt.received_at,[(s.suspended_on,s.resumed_on) for s in work.suspensions.all()],as_of) if work.state in OPEN_STATES else {"calendar_days":None,"paused_days":None,"active_calendar_days":None}
    return {"as_of":as_of.isoformat(),"method":METHOD,**counts,"initial_due_on":None,"agreed_due_on":None,"current_due_on":None,"last_requested_due_on":None,"overdue_calendar_days":None}


def validate_event_date(work,value,field):
    if value<work.receipt.received_at:raise ValidationError({field:"Дата раньше поступления материалов."})
    if value>timezone.localdate():raise ValidationError({field:"Фактическая дата не может быть будущей."})


@transaction.atomic
def _transition(*,actor,expertise_id,data,key,payload,kind):
    work=get_object_or_404(Expertise.objects.select_for_update(),pk=expertise_id)
    action="expertise."+kind
    require_work(actor,"expertise.view",work)
    require_work(actor,action,work)

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
