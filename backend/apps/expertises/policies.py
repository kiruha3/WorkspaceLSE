from django.db.models import FilteredRelation, Q
from rest_framework.exceptions import PermissionDenied
from apps.accounts.policies import AccessScope, permission_scopes
from .models import Expertise


def expertise_scope_queryset(user, action, scopes=None):
    scopes = permission_scopes(user) if scopes is None else scopes
    scope = scopes.get(action, AccessScope())
    if not scope.rules: raise PermissionDenied("Нет права просматривать экспертизы.")
    predicate=scope.query(employee_field="current__employee_id",department_field="department_id")
    if action=="expertise.view":
        predicate |= Q(origin_kind="historical",assignments__isnull=True)&scope.query(employee_field="historical__participants__employee_id",department_field="department_id")
    return Expertise.objects.annotate(current=FilteredRelation("assignments", condition=Q(assignments__ended_at__isnull=True))).filter(predicate).distinct()


def work_context(work, user, scopes=None):
    scopes = permission_scopes(user) if scopes is None else scopes
    employee_id = next((s.actor_employee_id for s in scopes.values()), None)
    assigned = any(str(a.employee_id)==str(employee_id) and a.ended_at is None for a in work.assignments.all())
    return {"employee_id":employee_id if assigned else None,"department_ids":[work.department_id]}


def require_work(user, action, work, scopes=None):
    scopes = permission_scopes(user) if scopes is None else scopes
    context=work_context(work,user,scopes)
    if action=="expertise.view":
        from .history import current_history_employee_ids
        employee_id=next((s.actor_employee_id for s in scopes.values()),None)
        if str(employee_id) in {str(value) for value in current_history_employee_ids(work)}:context["employee_id"]=employee_id
    if not scopes.get(action,AccessScope()).allows(**context):
        raise PermissionDenied("Нет права на это действие с выбранной экспертизой.")
