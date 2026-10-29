from apps.common.ordering import ordered_rows,ordering_key

STATES={'in_progress':'В производстве','suspended':'Приостановлена','completed':'Завершена','without_execution':'Без исполнения'}
NATURES={'primary':'Первичная','repeated':'Повторная','additional':'Дополнительная'}

def executors(work):
    names=[item.employee.full_name for item in work.assignments.all() if item.ended_at is None]
    history=getattr(work,'historical',None) if work.origin_kind=='historical' else None
    return sorted(names or [item.employee.full_name for item in history.participants.all()] if history else names)

FIELDS={
    'registration_number':lambda w:w.registration_number,
    'received_at':lambda w:w.receipt.received_at,
    'department':lambda w:(w.department.code,w.specialty.code if w.specialty_id else None),
    'executors':executors,
    'composition':lambda w:(NATURES.get(w.appointment_nature),w.is_commission,w.complex_group.title if w.complex_group_id else None),
    'state':lambda w:STATES.get(w.state,w.state),
}

def registry_queryset(queryset):
    from django.db.models import Prefetch
    from .models import ExpertAssignment,HistoricalParticipant
    assignments=ExpertAssignment.objects.select_related('employee').only('id','expertise_id','employee_id','employee__full_name','ended_at','started_at')
    participants=HistoricalParticipant.objects.select_related('employee').only('id','history_id','employee_id','employee__full_name')
    return queryset.prefetch_related(None).select_related('receipt','material','department','specialty','complex_group','historical').only(
        'id','origin_kind','registration_number','historical_number','receipt_id','receipt__received_at',
        'material_id','material__title','material__is_demo','department_id','department__code','department__name',
        'specialty_id','specialty__code','specialty__name','complex_group_id','complex_group__title',
        'appointment_nature','is_commission','state','historical__id','historical__expertise_id',
    ).prefetch_related(Prefetch('assignments',queryset=assignments),Prefetch('historical__participants',queryset=participants))

def ordered_registry(queryset,params):
    ordering=ordering_key(params,FIELDS)
    if not ordering:return queryset
    minimal=registry_queryset(queryset)
    return ordered_rows(minimal,ordering,FIELDS)
