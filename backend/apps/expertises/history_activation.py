from django.db import transaction,IntegrityError
from uuid import UUID
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from apps.accounts.commands import execute_once,CommandConflict
from apps.accounts.policies import require,permission_scopes,AccessScope
from apps.accounts.services import audit,check_version
from apps.documents.models import Document
from apps.documents.policies import require_document
from apps.intake.locking import require_not_issued,material_has_issue
from apps.intake.services import validate_basis
from apps.references.models import Specialty
from .models import HistoricalWork,ComplexGroup,Suspension
from .policies import require_work,work_context
from .production import locked_work,validate_event_date
from .results import create_revision,confirm_result,create_closure,return_values


def require_activation(actor,work):
    require_work(actor,'expertise.view',work)
    require(actor,'imports.history.activate')
    require_work(actor,'expertise.register',work)


def can_activate_history(actor,work,scopes=None):
    scopes=permission_scopes(actor) if scopes is None else scopes
    context=work_context(work,actor,scopes)
    return scopes.get('imports.history.activate',AccessScope()).allows() and scopes.get('expertise.register',AccessScope()).allows(**context) and not material_has_issue(work.material_id)


def checked_evidence(actor,data):
    # All evidence locks precede reference locks, as in native result commands.
    documents=[data['basis_document']]
    if 'result' in data:
        documents.extend([data['result']['document'],*[item['document'] for item in data['result']['unresolved_allocations']]])
    if 'return_data' in data:documents.append(data['return_data']['document'])
    ids={document.pk for document in documents if document is not None}
    current={document.pk:document for document in Document.objects.select_for_update().filter(pk__in=ids).order_by('pk')}
    for pk in ids:
        if pk not in current:get_object_or_404(Document,pk=pk)
        require_document(actor,'documents.view',current[pk])
    return current


def validate_intervals(work,data):
    intervals=sorted(data['past_suspensions'],key=lambda item:(item['suspended_on'],item['resumed_on']))
    end=None
    for item in intervals:
        start,resumed=item['suspended_on'],item['resumed_on']
        validate_event_date(work,start,'past_suspensions');validate_event_date(work,resumed,'past_suspensions')
        if resumed<start or end is not None and start<end:raise ValidationError({'past_suspensions':'Даты приостановок перепутаны или интервалы пересекаются.'})
        end=resumed
    opened=data['suspended_on']
    if work.state=='suspended':
        if opened is None:raise ValidationError({'suspended_on':'Для приостановленной работы подтвердите фактическую дату начала паузы.'})
        validate_event_date(work,opened,'suspended_on')
        if end and opened<end:raise ValidationError({'suspended_on':'Открытая пауза пересекает прежний интервал.'})
    elif opened is not None:raise ValidationError({'suspended_on':'Открытая пауза допускается только для приостановленной работы.'})
    return intervals


def _activate_history(*,actor,expertise_id,data,key,payload):
    with transaction.atomic():
        work=locked_work(expertise_id)
        require_activation(actor,work)
        documents=checked_evidence(actor,data)  # Current document rights also on replay.
        def operation():
            require_activation(actor,work);check_version(work,data['expected_version'])
            require_not_issued(work.material_id)
            history=HistoricalWork.objects.select_for_update().filter(expertise=work).first()
            if work.origin_kind!='historical' or history is None:raise ValidationError('Это не историческая работа с подтверждаемым источником.')
            if history.operational:raise CommandConflict('Продолжение учёта уже подтверждено. Обновите карточку.')
            if any(manager.exists() for manager in (work.assignments,work.suspensions,work.deadline_events,work.result_revisions,work.closures)):
                raise CommandConflict('В работе уже есть события нового учёта; автоматическое смешение истории не выполняется.')
            specialty=data['specialty']
            if work.specialty_id:
                if specialty is not None and specialty.pk!=work.specialty_id:raise ValidationError({'specialty_id':'Подтверждённая специальность здесь не заменяется.'})
                specialty=get_object_or_404(Specialty.objects.select_for_update(),pk=work.specialty_id)
            elif specialty is None:raise ValidationError({'specialty_id':'Подтвердите специальность исторической работы.'})
            else:specialty=get_object_or_404(Specialty.objects.select_for_update(),pk=specialty.pk)
            group=data['complex_group']
            if work.complex_group_id and (group is None or group.pk!=work.complex_group_id):raise ValidationError({'complex_group_id':'Явно перенесённая комплексная группа сохраняется.'})
            if group:
                group=get_object_or_404(ComplexGroup.objects.select_for_update(),pk=group.pk)
                if group.material_id!=work.material_id:raise ValidationError({'complex_group_id':'Комплекс относится к другому материалу.'})
            intervals=validate_intervals(work,data)
            if work.state=='completed':
                if 'result' not in data or 'return_data' in data:raise ValidationError({'result':'Подтвердите результат завершённой работы, не меняя вид закрытия.'})
            elif work.state=='without_execution':
                if 'return_data' not in data or 'result' in data:raise ValidationError({'return_data':'Подтвердите решение без исполнения, не меняя вид закрытия.'})
            elif 'result' in data or 'return_data' in data:raise ValidationError('Продолжение открытой работы не является новым окончанием.')
            receipt=work.receipt
            receipt.basis_document=documents[data['basis_document'].pk]
            validate_basis(receipt)
            receipt.status='accepted';receipt.version+=1;receipt.save(update_fields=['basis_document','status','version'])
            work.specialty=specialty;work.appointment_nature=data['appointment_nature'];work.is_commission=data['is_commission'];work.complex_group=group
            work.save(update_fields=['specialty','appointment_nature','is_commission','complex_group'])
            for item in intervals:
                Suspension.objects.create(expertise=work,**item,actor=actor,resumed_by=actor,resume_reason=item['reason'],resumed_recorded_at=timezone.now())
            if work.state=='suspended':Suspension.objects.create(expertise=work,suspended_on=data['suspended_on'],reason=data['reason'],actor=actor)
            closure=None
            from .historical_reports import previous_reference_ids
            retained={field:{UUID(pk) for pk in previous_reference_ids(history,field)} for field in ('sndz_reason','return_reason','unresolved_allocations')}
            if work.state=='completed':
                result=create_revision(work,actor,data['result'],data['reason'],retained_references=retained);confirm_result(work,actor,result)
                closure=create_closure(work,actor,reason=data['reason'],kind='completed',ended_on=result.completed_on,document=result.document,result=result)
            elif work.state=='without_execution':closure=create_closure(work,actor,reason=data['reason'],**return_values(work,actor,data['return_data'],retained_references=retained))
            else:
                work.version+=1;work.save(update_fields=['version'])
            history.operational=True;history.complex_known=True;history.suspension_history_complete=data['suspension_history_complete']
            history.save(update_fields=['operational','complex_known','suspension_history_complete'])
            event=audit(actor,'imports.history.activate',work,{'historical_id':str(history.pk),'version':work.version,'basis_document_id':str(receipt.basis_document_id),
                'specialty_id':str(specialty.pk),'appointment_nature':work.appointment_nature,'is_commission':work.is_commission,'complex_group_id':str(group.pk) if group else None,
                'suspension_history_complete':history.suspension_history_complete,'closure_id':str(closure.pk) if closure else None},data['reason'])
            return {'id':str(event.pk),'expertise_id':str(work.pk)}
        return execute_once(actor=actor,action='imports.history.activate',key=key,payload={'expertise_id':str(work.pk),'data':payload},operation=operation)


def activate_history(**kwargs):
    try:return _activate_history(**kwargs)
    except IntegrityError as error:
        if getattr(error.__cause__,'sqlstate',None)=='23505':raise CommandConflict('Специальность комплекса или событие уже подтверждены другой командой.') from error
        raise
