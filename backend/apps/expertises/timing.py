"""Audited reporting facts; recording a fact never sends or extends anything."""
from uuid import UUID
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError
from apps.accounts.commands import execute_once
from apps.accounts.services import audit,check_version
from apps.documents.models import Document
from apps.documents.policies import require_document
from apps.references.models import DelayReason
from apps.references.api import reference_data
from .models import WorkTimingFacts,TimingReason,TimingRevision
from .case_details import case_edit_permission,can_edit_case_details,require_case_edit
from .production import locked_work,validate_event_date
from .history import historical_record,historical_end_on
from .results import latest_closure
from .production_serializers import actor_data
from .result_serializers import document_link

FIELDS=('reasons_complete','notification_sent','notification_on','extension_requested','request_on','deadline_breached','breach_basis')
DOC_FIELDS=('notification_document','request_document','breach_document')

def timing_values(work):
    current=getattr(work,'timing',None)
    values={field:getattr(current,field) if current else False if field=='reasons_complete' else '' if field=='breach_basis' else None for field in FIELDS}
    for field in ('notification_on','request_on'):
        if values[field] is not None:values[field]=values[field].isoformat()
    values.update({field+'_id':str(getattr(current,field+'_id')) if current and getattr(current,field+'_id') else None for field in DOC_FIELDS})
    values['primary_reason_id']=str(current.primary_reason_id) if current and current.primary_reason_id else None
    values['reasons']=[{'reason':reference_data(item.reason),'comment':item.comment,'document_id':str(item.document_id) if item.document_id else None} for item in current.reasons.all()] if current else []
    return values

def timing_snapshot(work):
    history=historical_record(work)
    return {**timing_values(work),'registration_number':work.registration_number,'state':work.state,'department_id':str(work.department_id),
            'department_code':work.department.code,'registration_department_code':work.registration_department_code,
            'source_row_id':str(history.source_row_id) if history else None}

def retained_reason_ids(work):
    current=getattr(work,'timing',None);ids=set()
    if current:
        ids.update(str(item.reason_id) for item in current.reasons.all())
        if current.primary_reason_id:ids.add(str(current.primary_reason_id))
        for revision in current.revisions.all():
            for snapshot in (revision.before,revision.after):
                ids.update(item['reason']['id'] for item in snapshot.get('reasons',[]))
                if snapshot.get('primary_reason_id'):ids.add(snapshot['primary_reason_id'])
    return ids

def timing_output(work,user,scopes):
    current=getattr(work,'timing',None);values=timing_values(work)
    if current:
        values['reasons']=[{**fields,'id':str(item.pk),'document':document_link(item.document,user)} for item,fields in zip(current.reasons.all(),values['reasons'])]
    return {**values,'id':str(current.pk) if current else None,'can_edit':can_edit_case_details(user,work,scopes),'edit_permission':case_edit_permission(work),
            **{field:document_link(getattr(current,field),user) if current else None for field in DOC_FIELDS},
            'revisions':[{'id':str(r.pk),'number':r.number,'actor':actor_data(r.actor),'created_at':r.created_at,'reason':r.reason,'before':r.before,'after':r.after} for r in current.revisions.all()] if current else []}

def timing_options(work):
    from django.db.models import Q
    from apps.reports.timing_columns import DELAY_REASON_POLICY
    retained=retained_reason_ids(work)
    return {'delay_reasons':[reference_data(item) for item in DelayReason.objects.filter(Q(is_active=True)|Q(pk__in=retained))],
            'retained_reason_ids':sorted(retained),'delay_reason_policy':DELAY_REASON_POLICY}

@transaction.atomic
def save_timing(*,actor,expertise_id,data,key,payload):
    work=locked_work(expertise_id);require_case_edit(actor,work)
    profile=WorkTimingFacts.objects.select_for_update().filter(expertise=work).first();work.timing=profile
    documents=[data[field] for field in DOC_FIELDS]+[item['document'] for item in data['reasons']]
    docs={}
    for pk in sorted({d.pk for d in documents if d is not None}):
        doc=get_object_or_404(Document.objects.select_for_update(),pk=pk);require_document(actor,'documents.view',doc)
        if doc.source_kind=='uploaded_copy' and not doc.versions.exists():raise ValidationError({'documents':'Сначала сохраните файл копии подтверждающего документа.'})
        docs[pk]=doc
    def operation():
        require_case_edit(actor,work);check_version(work,data['expected_version'])
        for field in ('notification_on','request_on'):
            if data[field] is not None:validate_event_date(work,data[field],field)
        closure=latest_closure(work) if work.state=='completed' else None;history=historical_record(work)
        ended=closure.ended_on if closure else historical_end_on(work)
        kind=closure.result.kind if closure and closure.result else history.result_kind if history else None
        if data['reasons_complete'] and not data['reasons'] and work.state=='completed' and kind=='expert_conclusion' and ended and (ended-work.receipt.received_at).days+1>30:
            raise ValidationError({'reasons':'Для законченного заключения свыше30дней полный список причин не может быть пустым.'})
        retained={UUID(pk) for pk in retained_reason_ids(work)}
        references={}
        for pk in sorted({item['reason'].pk for item in data['reasons']}):
            item=get_object_or_404(DelayReason.objects.select_for_update(),pk=pk)
            if not item.is_active and pk not in retained:raise ValidationError({'reasons':'Неактивную причину нельзя выбрать впервые.'})
            references[pk]=item
        before=timing_snapshot(work);current=profile or WorkTimingFacts(expertise=work,created_by=actor)
        for field in FIELDS:setattr(current,field,data[field])
        for field in DOC_FIELDS:setattr(current,field,docs.get(data[field].pk) if data[field] else None)
        current.primary_reason=references.get(data['primary_reason'].pk) if data['primary_reason'] else None
        current.save();current.reasons.all().delete()
        TimingReason.objects.bulk_create([TimingReason(timing=current,reason=references[item['reason'].pk],comment=item['comment'],document=docs.get(item['document'].pk) if item['document'] else None) for item in data['reasons']])
        work.version+=1;work.save(update_fields=['version']);work.timing=current;after=timing_snapshot(work)
        previous=current.revisions.order_by('-number').first()
        revision=TimingRevision.objects.create(timing=current,number=previous.number+1 if previous else 1,actor=actor,reason=data['reason'],before=before,after=after)
        audit(actor,'expertise.timing.save',work,{'revision_id':str(revision.pk),'before':before,'after':after,'version':work.version},data['reason'])
        return {'id':str(revision.pk),'expertise_id':str(work.pk)}
    return execute_once(actor=actor,action='expertise.timing.save',key=key,payload={'expertise_id':str(expertise_id),'data':payload},operation=operation)
