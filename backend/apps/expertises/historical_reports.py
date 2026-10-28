"""Retrospective metadata corrections, not new result/closure/issue events."""
from django.db import transaction,IntegrityError
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied,ValidationError
from apps.accounts.commands import execute_once,CommandConflict
from apps.accounts.policies import permission_scopes,AccessScope
from apps.accounts.services import audit,check_version
from apps.documents.models import Document
from apps.documents.policies import require_document
from apps.issuance.models import IssuePackage
from .models import HistoricalWork,HistoricalCorrection,HistoricalUnresolvedAllocation
from .policies import require_work,work_context
from .production import locked_work,validate_event_date
from .results import locked_reference
from .historical_report_serializers import historical_snapshot


def correction_context(user,work,scopes):
    context=work_context(work,user,scopes)
    if work.origin_kind=='historical' and not work.assignments.exists():
        from .history import current_history_employee_ids
        employee_id=next((scope.actor_employee_id for scope in scopes.values()),None)
        if str(employee_id) in {str(pk) for pk in current_history_employee_ids(work)}:context['employee_id']=employee_id
    return context


def require_correction_permission(user,work):
    require_work(user,'expertise.view',work)
    scopes=permission_scopes(user)
    if not scopes.get('expertise.closed.correct',AccessScope()).allows(**correction_context(user,work,scopes)):
        raise PermissionDenied('Нет права уточнять эту закрытую историческую работу.')


def correction_blockers(work,history):
    if work.origin_kind!='historical' or history is None:return ['Это не перенесённая историческая работа.']
    if history.operational or work.state not in ('completed','without_execution'):return ['Уточнение допускается только для старой закрытой работы без продолжения нового учёта.']
    if any(manager.exists() for manager in (work.assignments,work.suspensions,work.deadline_events,work.result_revisions,work.closures)) or IssuePackage.objects.filter(material_id=work.material_id).exists():
        return ['Есть события или комплект нового учёта. Используйте корректировку соответствующего рабочего процесса.']
    return []


def can_correct_historical_report(user,work,scopes=None):
    scopes=permission_scopes(user) if scopes is None else scopes
    history=getattr(work,'historical',None)
    return scopes.get('expertise.closed.correct',AccessScope()).allows(**correction_context(user,work,scopes)) and not correction_blockers(work,history)


def previous_reference_ids(history,field):
    ids=set()
    for c in history.corrections.all():
        for state in (c.before,c.after):
            if field=='unresolved_allocations':ids.update(item['reason']['id'] for item in state.get(field,[]))
            elif value:=state.get(field):ids.add(value['id'])
    current=history.expertise.specialty if field=='specialty' else getattr(history,field,None)
    if field=='unresolved_allocations':ids.update(str(pk) for pk in history.unresolved_allocations.values_list('reason_id',flat=True))
    elif current is not None:ids.add(str(current.pk))
    return {str(pk) for pk in ids}


def checked_reference(history,field,reference):
    return locked_reference(reference,{reference.pk} if reference and str(reference.pk) in previous_reference_ids(history,field) else set(),field)


def _correct_historical_report(*,actor,expertise_id,data,key,payload):
    with transaction.atomic():
        work=locked_work(expertise_id);require_correction_permission(actor,work)
        history=HistoricalWork.objects.select_for_update().filter(expertise=work).first()
        values=data['result' if data['correction_kind']=='result' else 'return_data']
        allocations=values.get('unresolved_allocations',[])
        document_ids={item['document'].pk for item in allocations if item['document'] is not None}
        documents={doc.pk:doc for doc in Document.objects.select_for_update().filter(pk__in=document_ids).order_by('pk')}
        # Evidence rights are current even when execute_once returns a receipt.
        for pk in document_ids:
            if pk not in documents:get_object_or_404(Document,pk=pk)
            require_document(actor,'documents.view',documents[pk])
        def operation():
            require_correction_permission(actor,work);check_version(work,data['expected_version'])
            if blockers:=correction_blockers(work,history):raise CommandConflict(' '.join(blockers))
            expected='result' if work.state=='completed' else 'return'
            if data['correction_kind']!=expected:raise ValidationError('Вид уточнения не соответствует закрытому состоянию работы.')
            before=historical_snapshot(work,history)
            specialty=checked_reference(history,'specialty',data['specialty'])
            if expected=='result':
                kind=values['kind']
                if kind and ((work.category_code=='6')!=(kind=='research_act')):raise ValidationError({'kind':'Вид результата не соответствует категории номера.'})
                if values['completed_on'] is not None:validate_event_date(work,values['completed_on'],'completed_on')
                sndz=checked_reference(history,'sndz_reason',values['sndz_reason'])
                checked=[]
                for item in sorted(allocations,key=lambda a:str(a['reason'].pk)):
                    ref=checked_reference(history,'unresolved_allocations',item['reason'])
                    checked.append(HistoricalUnresolvedAllocation(history=history,reason=ref,count=item['count'],comment=item['comment'],document=documents.get(item['document'].pk) if item['document'] else None))
                for field in ('completed_on','complexity_level','questions','categorical','probable','unresolved','allocations_complete','sndz_comment'):setattr(history,field,values[field])
                history.result_kind=kind;history.statistics_confirmed=values['statistics_complete'];history.sndz_reason=sndz;history.report_note=values['note']
                history.unresolved_allocations.all().delete();HistoricalUnresolvedAllocation.objects.bulk_create(checked)
            else:
                if values['decided_on'] is not None:validate_event_date(work,values['decided_on'],'decided_on')
                history.return_decided_on=values['decided_on'];history.return_reason=checked_reference(history,'return_reason',values['return_reason']);history.return_comment=values['comment']
            history.save();work.specialty=specialty;work.version+=1;work.save(update_fields=['specialty','version'])
            history.refresh_from_db();after=historical_snapshot(work,history)
            previous=history.corrections.order_by('-number').first()
            correction=HistoricalCorrection.objects.create(history=history,number=previous.number+1 if previous else 1,actor=actor,reason=data['reason'],before=before,after=after)
            audit(actor,'expertise.history.report.correct',work,{'correction_id':str(correction.pk),'number':correction.number,'version':work.version,'before':before,'after':after},data['reason'])
            return {'id':str(correction.pk),'expertise_id':str(work.pk)}
        return execute_once(actor=actor,action='expertise.history.report.correct',key=key,payload={'expertise_id':str(expertise_id),'data':payload},operation=operation)


def correct_historical_report(**kwargs):
    try:return _correct_historical_report(**kwargs)
    except IntegrityError as error:
        if getattr(error.__cause__,'sqlstate',None)=='23505':raise CommandConflict('Специальность комплекса или редакция уже изменена. Обновите карточку.') from error
        raise
