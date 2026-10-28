"""Current case facts with provenance; never rewrite registration or result."""
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied,ValidationError
from apps.accounts.commands import execute_once
from apps.accounts.policies import permission_scopes,AccessScope
from apps.accounts.services import audit,check_version
from apps.documents.models import Document
from apps.documents.policies import require_document
from apps.references.models import AuthorityType
from apps.references.api import reference_data
from apps.references.authority_seeds import legacy_authority_code
from .models import WorkCaseDetails,CaseDetailsRevision
from .history import historical_record
from .historical_reports import correction_context
from .production import locked_work
from .policies import require_work
from .results import locked_reference
from .result_serializers import document_link
from .production_serializers import actor_data
from .case_serializers import TEXT_FIELDS,HISTORY_TEXT_FIELDS


def case_edit_permission(work):
    return 'expertise.work.update' if work.state in ('in_progress','suspended') else 'expertise.closed.correct'


def can_edit_case_details(user,work,scopes=None):
    scopes=permission_scopes(user) if scopes is None else scopes
    context=correction_context(user,work,scopes)
    return (scopes.get('expertise.view',AccessScope()).allows(**context) and
            scopes.get(case_edit_permission(work),AccessScope()).allows(**context))


def require_case_edit(user,work):
    require_work(user,'expertise.view',work)
    if not can_edit_case_details(user,work):
        raise PermissionDenied('Нет права уточнять сведения этой работы.')


def case_values(work):
    details=getattr(work,'case_details',None)
    history=historical_record(work)
    values={field:getattr(details,field) if details else getattr(history,field,'') if field in HISTORY_TEXT_FIELDS else '' for field in TEXT_FIELDS}
    values.update(authority_type=reference_data(details.authority_type) if details and details.authority_type_id else None,
        authority_type_raw=history.authority_type if history and details is None else '',
        decree3214=details.decree3214 if details else None,
        decree_document_id=str(details.decree_document_id) if details and details.decree_document_id else None)
    return values


def case_snapshot(work):
    history=historical_record(work)
    return {**case_values(work),'registration_number':work.registration_number,'state':work.state,
            'department_code':work.registration_department_code,'source_row_id':str(history.source_row_id) if history else None}


def retained_authority_ids(work):
    details=getattr(work,'case_details',None);ids=set()
    if details:
        if details.authority_type_id:ids.add(str(details.authority_type_id))
        for revision in details.revisions.all():
            for snapshot in (revision.before,revision.after):
                ref=snapshot.get('authority_type')
                if ref:ids.add(ref['id'])
    history=historical_record(work)
    code=legacy_authority_code(history.authority_type) if history else None
    if code:ids.update(str(pk) for pk in AuthorityType.objects.filter(code=code).values_list('pk',flat=True))
    return ids


def case_options(work):
    types=list(AuthorityType.objects.all());details=getattr(work,'case_details',None)
    history=historical_record(work)
    code=legacy_authority_code(history.authority_type) if history else None
    initial=str(details.authority_type_id) if details and details.authority_type_id else None
    if details is None:initial=next((str(ref.pk) for ref in types if ref.code==code),None)
    return {'authority_types':[reference_data(ref) for ref in types],
            'initial_authority_type_id':initial,'retained_authority_type_ids':sorted(retained_authority_ids(work))}


def case_details_output(work,user,scopes):
    details=getattr(work,'case_details',None);history=historical_record(work)
    return {**case_values(work),'id':str(details.pk) if details else None,
        'source':'typed' if details else 'history' if history else 'new',
        'can_edit':can_edit_case_details(user,work,scopes),'edit_permission':case_edit_permission(work),
        'decree_document':document_link(details.decree_document,user) if details else None,
        'revisions':[{'id':str(revision.pk),'number':revision.number,'actor':actor_data(revision.actor),
            'created_at':revision.created_at,'reason':revision.reason,'before':revision.before,'after':revision.after}
            for revision in details.revisions.all()] if details else []}


@transaction.atomic
def save_case_details(*,actor,expertise_id,data,key,payload):
    work=locked_work(expertise_id);require_case_edit(actor,work)
    details=WorkCaseDetails.objects.select_for_update().filter(expertise=work).first()
    # Lock and recheck the current evidence even when replay returns a receipt.
    document=data['decree_document']
    if document:
        document=get_object_or_404(Document.objects.select_for_update(),pk=document.pk)
        require_document(actor,'documents.view',document)
        if document.source_kind=='uploaded_copy' and not document.versions.exists():
            raise ValidationError({'decree_document_id':'Сначала подкрепите файл копии документа.'})
    def operation():
        require_case_edit(actor,work);check_version(work,data['expected_version'])
        # Read the same current profile that was locked, without a stale reverse cache.
        work.case_details=details if details is not None else None
        before=case_snapshot(work)
        ref=data['authority_type']
        allowed=retained_authority_ids(work)
        ref=locked_reference(ref,{ref.pk} if ref and str(ref.pk) in allowed else set(),'authority_type_id')
        current=details or WorkCaseDetails(expertise=work,created_by=actor)
        for field in TEXT_FIELDS:setattr(current,field,data[field])
        current.authority_type=ref;current.decree3214=data['decree3214'];current.decree_document=document
        current.save();work.version+=1;work.save(update_fields=['version'])
        work.case_details=current;after=case_snapshot(work)
        previous=current.revisions.order_by('-number').first()
        revision=CaseDetailsRevision.objects.create(details=current,number=previous.number+1 if previous else 1,
            actor=actor,reason=data['reason'],before=before,after=after)
        audit(actor,'expertise.case_details.save',work,{'revision_id':str(revision.pk),'number':revision.number,
            'version':work.version,'before':before,'after':after},data['reason'])
        return {'id':str(revision.pk),'expertise_id':str(work.pk)}
    return execute_once(actor=actor,action='expertise.case_details.save',key=key,
                        payload={'expertise_id':str(expertise_id),'data':payload},operation=operation)
