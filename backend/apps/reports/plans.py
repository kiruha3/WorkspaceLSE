"""One serialized, idempotent annual command; no inference from work counts."""
from uuid import UUID
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError
from apps.accounts.commands import execute_once
from apps.accounts.policies import can,require
from apps.accounts.services import audit,check_version,require_any
from apps.documents.models import Document
from apps.documents.policies import require_document
from apps.references.api import reference_data
from apps.references.models import Specialty
from apps.expertises.production_serializers import actor_data
from apps.expertises.result_serializers import document_link
from .models import StateAssignmentPlan,StateAssignmentPlanLine,StateAssignmentPlanRevision

MANAGE='reports.plans.manage'

def require_plan_read(user):
    require_any(user,'references.view','references.manage','reports.form151.run',MANAGE)

def plan_values(plan,year):
    return {'year':year,'total':plan.total if plan else None,'basis_text':plan.basis_text if plan else '',
            'document_id':str(plan.document_id) if plan and plan.document_id else None,'version':plan.version if plan else 0,
            'lines':[{'specialty':reference_data(line.specialty),'count':line.count} for line in plan.lines.select_related('specialty').all()] if plan else []}

def retained_specialty_ids(plan):
    ids=set()
    if plan:
        ids.update(str(pk) for pk in plan.lines.values_list('specialty_id',flat=True))
        for revision in plan.revisions.all():
            for snapshot in (revision.before,revision.after):
                ids.update(item['specialty']['id'] for item in snapshot.get('lines',[]))
    return ids

def plan_output(plan,user,year):
    values=plan_values(plan,year);retained=retained_specialty_ids(plan)
    if plan:
        values['lines']=[{'id':str(line.pk),'specialty':reference_data(line.specialty),'count':line.count} for line in plan.lines.select_related('specialty').all()]
    return {**values,'id':str(plan.pk) if plan else None,'document':document_link(plan.document,user) if plan else None,
            'can_edit':can(user,MANAGE),'retained_specialty_ids':sorted(retained),
            'specialties':[reference_data(ref) for ref in Specialty.objects.filter(Q(is_active=True)|Q(pk__in=retained))],
            'revisions':[{'id':str(r.pk),'number':r.number,'actor':actor_data(r.actor) if r.actor else None,'created_at':r.created_at,'reason':r.reason,'before':r.before,'after':r.after} for r in plan.revisions.select_related('actor').all()] if plan else []}

@transaction.atomic
def save_plan(*,actor,year,data,key,payload):
    require(actor,MANAGE)
    # The unique year insert serializes two simultaneous first writes as well
    # as normal edits. A failed command rolls back this version0 placeholder.
    plan,_=StateAssignmentPlan.objects.get_or_create(year=year,defaults={'created_by':actor})
    plan=StateAssignmentPlan.objects.select_for_update().get(pk=plan.pk)
    document=None
    if data['document'] is not None:
        document=get_object_or_404(Document.objects.select_for_update(),pk=data['document'].pk)
        require_document(actor,'documents.view',document)
        if document.source_kind=='uploaded_copy' and not document.versions.exists():
            raise ValidationError({'document_id':'Сначала сохраните файл копии подтверждающего документа.'})
    def operation():
        require(actor,MANAGE);check_version(plan,data['expected_version'])
        retained={UUID(pk) for pk in retained_specialty_ids(plan)};references={}
        for pk in sorted({line['specialty'].pk for line in data['lines']}):
            specialty=get_object_or_404(Specialty.objects.select_for_update(),pk=pk)
            if not specialty.is_active and pk not in retained:
                raise ValidationError({'lines':'Неактивную специальность нельзя выбрать впервые.'})
            references[pk]=specialty
        before=plan_values(plan,year)
        plan.total=data['total'];plan.basis_text=data['basis_text'];plan.document=document;plan.version+=1;plan.save()
        plan.lines.all().delete()
        StateAssignmentPlanLine.objects.bulk_create([StateAssignmentPlanLine(plan=plan,specialty=references[line['specialty'].pk],count=line['count']) for line in data['lines']])
        after=plan_values(plan,year)
        revision=StateAssignmentPlanRevision.objects.create(plan=plan,number=plan.version,actor=actor,reason=data['reason'],before=before,after=after)
        audit(actor,'reports.plan.save',plan,{'revision_id':str(revision.pk),'before':before,'after':after},data['reason'])
        return {'plan_id':str(plan.pk),'revision_id':str(revision.pk)}
    return execute_once(actor=actor,action='reports.plan.save',key=key,payload={'year':year,'data':payload},operation=operation)
