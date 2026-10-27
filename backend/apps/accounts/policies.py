from dataclasses import dataclass
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from apps.personnel.models import Employee, EmployeeRole
from .catalog import PERMISSIONS


@dataclass(frozen=True)
class AccessRule:
    scope: str
    limit: str
    department_ids: frozenset[str]
    role_id: str = ""
    role_name: str = ""
    assignment_id: str = ""

    def allows(self, actor_employee_id, *, employee_id=None, department_ids=()):
        def match(scope):
            if scope == "institution":
                return True
            if scope == "own":
                return employee_id is not None and str(employee_id) == str(actor_employee_id)
            if scope == "departments":
                return bool(self.department_ids.intersection(str(d) for d in department_ids))
            return False
        return match(self.scope) and match(self.limit)

    def query(self, actor_employee_id, *, employee_field="pk", department_field="org_assignments__department_id"):
        def predicate(scope):
            if scope == "institution":
                # A concrete true predicate: empty Q() is neutral even in OR,
                # so OR-ing it with the default deny filter would keep deny.
                return Q(pk__isnull=False)
            if scope == "own":
                return Q(**{employee_field: actor_employee_id})
            if scope == "departments":
                return Q(**{department_field + "__in": self.department_ids})
            return Q(pk__in=[])
        return predicate(self.scope) & predicate(self.limit)


@dataclass(frozen=True)
class AccessScope:
    actor_employee_id: str | None = None
    rules: tuple[AccessRule, ...] = ()

    def allows(self, *, employee_id=None, department_ids=()):
        return any(rule.allows(self.actor_employee_id,employee_id=employee_id,department_ids=department_ids) for rule in self.rules)

    def query(self, **fields):
        result = Q(pk__in=[])
        for rule in self.rules:
            result |= rule.query(self.actor_employee_id,**fields)
        return result


def active_employee(user):
    if not getattr(user,"is_authenticated",False) or not user.is_active:
        return None
    return Employee.objects.filter(user_id=user.pk,user__is_active=True,is_active=True).first()


def permission_scopes(user):
    employee = active_employee(user)
    if employee is None:
        return {}
    today = timezone.localdate()
    grants = EmployeeRole.objects.filter(employee=employee,is_active=True,role__is_active=True).filter(
        Q(valid_from__isnull=True)|Q(valid_from__lte=today),
        Q(valid_to__isnull=True)|Q(valid_to__gte=today),
    ).select_related("role").prefetch_related("departments","role__permissions")
    rules = {}
    for grant in grants:
        departments = frozenset(str(d.id) for d in grant.departments.all())
        for permission in grant.role.permissions.all():
            definition = PERMISSIONS.get(permission.permission_code)
            if definition is None or permission.scope not in definition.scopes:
                continue
            if (permission.scope == "departments" or grant.scope_limit == "departments") and not departments:
                continue
            rule = AccessRule(permission.scope,grant.scope_limit,departments,str(grant.role_id),grant.role.name,str(grant.id))
            rules.setdefault(permission.permission_code,[]).append(rule)
    return {code:AccessScope(str(employee.id),tuple(items)) for code,items in rules.items()}


def effective_scope(user, action):
    return permission_scopes(user).get(action,AccessScope())


def can(user, action, *, employee_id=None, department_ids=()):
    return effective_scope(user,action).allows(employee_id=employee_id,department_ids=department_ids)


def require(user, action, **context):
    if not can(user,action,**context):
        raise PermissionDenied("Нет права на это действие в выбранной области.")


def access_snapshot(user):
    return {code:[{
        "scope":r.scope,"scope_limit":r.limit,"department_ids":sorted(r.department_ids),
        "role_id":r.role_id,"role_name":r.role_name,"assignment_id":r.assignment_id,
    } for r in scope.rules] for code,scope in permission_scopes(user).items()}
