from django.db.models import FilteredRelation, Q
from rest_framework.exceptions import PermissionDenied
from apps.accounts.policies import AccessScope, permission_scopes
from .models import Expertise


def expertise_scope_queryset(user, action, scopes=None):
    scopes = permission_scopes(user) if scopes is None else scopes
    scope = scopes.get(action, AccessScope())
    if not scope.rules: raise PermissionDenied("Нет права просматривать экспертизы.")
    return Expertise.objects.annotate(current=FilteredRelation("assignments", condition=Q(assignments__ended_at__isnull=True))).filter(
        scope.query(employee_field="current__employee_id",department_field="department_id")).distinct()


def work_context(work, user, scopes=None):
    scopes = permission_scopes(user) if scopes is None else scopes
    employee_id = next((s.actor_employee_id for s in scopes.values()), None)
    assigned = any(str(a.employee_id)==str(employee_id) and a.ended_at is None for a in work.assignments.all())
    return {"employee_id":employee_id if assigned else None,"department_ids":[work.department_id]}


def require_work(user, action, work, scopes=None):
    scopes = permission_scopes(user) if scopes is None else scopes
    if not scopes.get(action,AccessScope()).allows(**work_context(work,user,scopes)):
        raise PermissionDenied("Нет права на это действие с выбранной экспертизой.")
