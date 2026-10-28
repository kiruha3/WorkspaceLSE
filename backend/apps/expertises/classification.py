"""Audited appointment nature and prior conclusions; never changes accepted files."""
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError
from apps.accounts.commands import execute_once
from apps.accounts.services import audit,check_version
from apps.documents.models import Document
from apps.documents.policies import require_document
from .case_details import case_edit_permission,can_edit_case_details,require_case_edit
from .history import historical_record
from .models import WorkClassification,PreviousConclusion,ClassificationRevision
from .production import locked_work
from .production_serializers import actor_data
from .result_serializers import document_link

FIELDS=('reference','organization_name','organization_group','same_input_data','confirms_previous')

def classification_values(work):
    current=getattr(work,'classification',None)
    return {'appointment_nature':work.appointment_nature,'previous_complete':current.previous_complete if current else False,
        'previous_conclusions':[{**{field:getattr(entry,field) for field in FIELDS},'document_id':str(entry.document_id) if entry.document_id else None}
                                for entry in current.previous_conclusions.all()] if current else []}

def classification_snapshot(work):
    history=historical_record(work)
    return {**classification_values(work),'registration_number':work.registration_number,'state':work.state,
            'department_id':str(work.department_id),'department_code':work.department.code,
            'registration_department_code':work.registration_department_code,'receipt_id':str(work.receipt_id),
            'source_row_id':str(history.source_row_id) if history else None}

def classification_output(work,user,scopes):
    current=getattr(work,'classification',None);values=classification_values(work)
    entries=[]
    if current:
        for entry,fields in zip(current.previous_conclusions.all(),values['previous_conclusions']):
            entries.append({**fields,'id':str(entry.pk),'document':document_link(entry.document,user)})
    return {**values,'id':str(current.pk) if current else None,'previous_conclusions':entries,
            'can_edit':can_edit_case_details(user,work,scopes),'edit_permission':case_edit_permission(work),
            'revisions':[{'id':str(r.pk),'number':r.number,'actor':actor_data(r.actor),'created_at':r.created_at,
                          'reason':r.reason,'before':r.before,'after':r.after} for r in current.revisions.all()] if current else []}

@transaction.atomic
def save_classification(*,actor,expertise_id,data,key,payload):
    work=locked_work(expertise_id);require_case_edit(actor,work)
    profile=WorkClassification.objects.select_for_update().filter(expertise=work).first()
    docs={}
    for pk in sorted({entry['document'].pk for entry in data['previous_conclusions'] if entry['document']}):
        document=get_object_or_404(Document.objects.select_for_update(),pk=pk)
        require_document(actor,'documents.view',document)
        if document.source_kind=='uploaded_copy' and not document.versions.exists():
            raise ValidationError({'previous_conclusions':'Сначала сохраните файл предыдущего заключения.'})
        docs[pk]=document
    def operation():
        require_case_edit(actor,work);check_version(work,data['expected_version'])
        if work.origin_kind=='native' and data['appointment_nature'] is None:
            raise ValidationError({'appointment_nature':'В новом учёте характер назначения должен быть известен.'})
        work.classification=profile if profile else None
        before=classification_snapshot(work)
        current=profile or WorkClassification(expertise=work,created_by=actor)
        current.previous_complete=data['previous_complete'];current.save()
        current.previous_conclusions.all().delete()
        PreviousConclusion.objects.bulk_create([PreviousConclusion(classification=current,ordinal=index,
            document=docs.get(entry['document'].pk) if entry['document'] else None,
            **{field:entry[field] for field in FIELDS}) for index,entry in enumerate(data['previous_conclusions'],1)])
        work.appointment_nature=data['appointment_nature'];work.version+=1;work.save(update_fields=['appointment_nature','version'])
        work.classification=current;after=classification_snapshot(work)
        previous=current.revisions.order_by('-number').first()
        revision=ClassificationRevision.objects.create(classification=current,number=previous.number+1 if previous else 1,
            actor=actor,reason=data['reason'],before=before,after=after)
        audit(actor,'expertise.classification.save',work,{'revision_id':str(revision.pk),'before':before,'after':after,'version':work.version},data['reason'])
        return {'id':str(revision.pk),'expertise_id':str(work.pk)}
    return execute_once(actor=actor,action='expertise.classification.save',key=key,
                        payload={'expertise_id':str(expertise_id),'data':payload},operation=operation)
