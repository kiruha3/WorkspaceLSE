"""Explicit undo of completion, without deleting accepted evidence/history."""
from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError
from apps.accounts.commands import execute_once
from apps.accounts.policies import AccessScope, permission_scopes
from apps.accounts.services import audit, check_version
from apps.intake.locking import material_has_issue, require_not_issued
from .history import historical_record, current_history_employee_ids
from .models import WorkReopening
from .policies import require_work, work_context
from .production import locked_work
from .results import latest_closure


def reopen_context(work,user,scopes):
    context=work_context(work,user,scopes)
    employee_id=next((scope.actor_employee_id for scope in scopes.values()),None)
    if str(employee_id) in {str(pk) for pk in current_history_employee_ids(work)}:
        context['employee_id']=employee_id
    return context


def can_reopen(work,user,scopes):
    return (work.state=='completed'
        and scopes.get('expertise.reopen',AccessScope()).allows(**reopen_context(work,user,scopes))
        and not material_has_issue(work.material_id))


@transaction.atomic
def reopen_work(*,actor,expertise_id,data,key,payload):
    work=locked_work(expertise_id);action='expertise.reopen'
    scopes=permission_scopes(actor);require_work(actor,'expertise.view',work,scopes)
    if not scopes.get(action,AccessScope()).allows(**reopen_context(work,actor,scopes)):
        raise PermissionDenied('Нет права возвращать эту экспертизу в работу.')
    def operation():
        check_version(work,data['expected_version'])
        if work.state!='completed':
            raise ValidationError('Вернуть в работу можно только завершённую экспертизу.')
        require_not_issued(work.material_id)
        history=historical_record(work)
        restored='suspended' if work.suspensions.filter(resumed_on__isnull=True).exists() else 'in_progress'
        event=WorkReopening.objects.create(expertise=work,closure=latest_closure(work),
            historical_completed_on=history.completed_on if history else None,
            historical_return_decided_on=history.return_decided_on if history else None,
            restored_state=restored,actor=actor,reason=data['reason'])
        if history:
            history.completed_on=None;history.return_decided_on=None
            history.save(update_fields=['completed_on','return_decided_on'])
        work.state=restored;work.version+=1;work.save(update_fields=['state','version'])
        audit(actor,action,work,{'reopening_id':str(event.pk),'closure_id':str(event.closure_id) if event.closure_id else None,
            'previous_state':'completed','state':restored,'version':work.version},data['reason'])
        return {'id':str(event.pk),'expertise_id':str(work.pk)}
    return execute_once(actor=actor,action=action,key=key,payload={'expertise_id':str(expertise_id),'data':payload},operation=operation)
