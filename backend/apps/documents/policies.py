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
        works=expertise_scope_queryset(user,"expertise.view",scopes).filter(Q(receipt__basis_document=document)|Q(deadline_events__document=document)|Q(result_revisions__document=document)|Q(result_revisions__unresolved_allocations__document=document)|Q(closures__document=document)).distinct().prefetch_related("assignments")
        if any(scope.allows(**work_context(work,user,scopes)) for work in works):return True
    # Independent correspondence does not require expertise.view. Both the
    # letter and the document action must match their own current scopes.
    if scopes.get("letters.view"):
        from apps.correspondence.policies import letter_scope_queryset
        letters=letter_scope_queryset(user,"letters.view",scopes).filter(
            Q(attachments__document=document)|Q(dispatches__evidence_document=document)|Q(dispatches__deliveries__evidence_document=document)|Q(receipt_fact__evidence_document=document)|Q(registration__files__file_version__document=document)|Q(dispatches__files__file_version__document=document))
        if letter_scope_queryset(user,"documents.view",scopes).filter(pk__in=letters).exists():return True
    if scopes.get("issue.view"):
        from apps.issuance.policies import package_queryset
        packages=package_queryset(user,scopes=scopes).filter(Q(revisions__items__document=document)|Q(checks__files__document=document)|Q(issuance__evidence_document=document))
        return package_queryset(user,"documents.view",scopes).filter(pk__in=packages).exists()
    return False


def require_document(user,action,document):
    if not can_document(user,action,document):raise PermissionDenied("Нет права на этот документ.")
