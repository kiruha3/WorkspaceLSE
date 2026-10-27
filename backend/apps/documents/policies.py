from apps.accounts.policies import can,require


def document_context(document):
    return {"employee_id":document.created_by_id,"department_ids":[document.department_id] if document.department_id else []}


def can_document(user,action,document):
    return can(user,action,**document_context(document))


def require_document(user,action,document):
    require(user,action,**document_context(document))
