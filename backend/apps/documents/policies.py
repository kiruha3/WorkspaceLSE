from rest_framework.exceptions import PermissionDenied
from django.db.models import Q
from apps.accounts.policies import can,permission_scopes,AccessScope


def document_context(document):
    return {"employee_id":document.created_by_id,"department_ids":[document.department_id] if document.department_id else []}


def can_document(user,action,document):
    if can(user,action,**document_context(document)):return True
    # A work's shared basis is readable through an allowed link, not through
    # every sibling work/material. This does not confer write/upload authority.
    if action!="documents.view":return False
    from apps.expertises.policies import expertise_scope_queryset,work_context
    scopes=permission_scopes(user);scope=scopes.get(action,AccessScope())
    if not scope.rules:return False
    if scopes.get("expertise.view"):
        works=expertise_scope_queryset(user,"expertise.view",scopes).filter(Q(receipt__basis_document=document)|Q(deadline_events__document=document)|Q(result_revisions__document=document)|Q(result_revisions__unresolved_allocations__document=document)|Q(closures__document=document)|Q(case_details__decree_document=document)|Q(classification__previous_conclusions__document=document)|Q(timing__notification_document=document)|Q(timing__request_document=document)|Q(timing__breach_document=document)|Q(timing__reasons__document=document)).distinct().select_related('case_details','classification','timing').prefetch_related("assignments","historical__participants","classification__previous_conclusions","timing__reasons")
        for work in works:
            context=work_context(work,user,scopes)
            details=getattr(work,'case_details',None)
            classification=getattr(work,'classification',None)
            previous_document=classification and any(entry.document_id==document.pk for entry in classification.previous_conclusions.all())
            timing=getattr(work,'timing',None)
            timing_document=timing and (document.pk in (timing.notification_document_id,timing.request_document_id,timing.breach_document_id) or any(item.document_id==document.pk for item in timing.reasons.all()))
            if details and details.decree_document_id==document.pk or previous_document or timing_document:
                from apps.expertises.history import current_history_employee_ids
                actor_id=scope.actor_employee_id
                if str(actor_id) in {str(pk) for pk in current_history_employee_ids(work)}:context['employee_id']=actor_id
            if scope.allows(**context):return True
    # Independent correspondence does not require expertise.view. Both the
    # letter and the document action must match their own current scopes.
    if scopes.get("letters.view"):
        from apps.correspondence.policies import letter_scope_queryset
        letters=letter_scope_queryset(user,"letters.view",scopes).filter(
            Q(attachments__document=document)|Q(dispatches__evidence_document=document)|Q(dispatches__deliveries__evidence_document=document)|Q(receipt_fact__evidence_document=document)|Q(registration__files__file_version__document=document)|Q(dispatches__files__file_version__document=document))
        if letter_scope_queryset(user,"documents.view",scopes).filter(pk__in=letters).exists():return True
    if scopes.get("issue.view") and scopes.get("expertise.view"):
        # A shared file needs one legitimate work link, not all sibling scopes.
        works=expertise_scope_queryset(user,"expertise.view",scopes).filter(
            pk__in=expertise_scope_queryset(user,"issue.view",scopes)).filter(
            pk__in=expertise_scope_queryset(user,"documents.view",scopes))
        return works.filter(Q(issue_items__document=document)|Q(material__issue_package__issuance__evidence_document=document)).exists()
    return False


def require_document(user,action,document):
    if not can_document(user,action,document):raise PermissionDenied("Нет права на этот документ.")
