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

def ordered_registry(queryset,params):
    ordering=ordering_key(params,FIELDS)
    if not ordering:return queryset
    minimal=queryset.select_related('receipt','material','department','specialty','complex_group','historical').prefetch_related('assignments__employee','historical__participants__employee')
    return ordered_rows(minimal,ordering,FIELDS)
