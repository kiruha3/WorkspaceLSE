from rest_framework.exceptions import PermissionDenied
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
    if not scope.rules or not scopes.get("expertise.view"):return False
    works=expertise_scope_queryset(user,"expertise.view",scopes).filter(receipt__basis_document=document).prefetch_related("assignments")
    return any(scope.allows(**work_context(work,user,scopes)) for work in works)


def require_document(user,action,document):
    if not can_document(user,action,document):raise PermissionDenied("Нет права на этот документ.")
