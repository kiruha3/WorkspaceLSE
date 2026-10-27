from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from apps.accounts.policies import AccessScope, active_employee, permission_scopes
from apps.expertises.models import Expertise
from apps.expertises.policies import expertise_scope_queryset
from apps.intake.models import Material, Receipt
from .models import Letter


def visible_works(user, scopes):
    if not scopes.get("expertise.view", AccessScope()).rules:
        return Expertise.objects.none()
    return expertise_scope_queryset(user, "expertise.view", scopes)


def letter_scope_queryset(user, action, scopes=None):
    scopes = permission_scopes(user) if scopes is None else scopes
    scope = scopes.get(action, AccessScope())
    if not scope.rules:
        raise PermissionDenied("Нет права на переписку в выбранной области.")
    own = Q(responsible_id=scope.actor_employee_id)
    if action in ("letters.view", "control.view", "documents.view"):
        # Only CURRENT participation in a visible linked work, never a sibling
        # material, former assignment, old revision, or historical creator.
        works = visible_works(user, scopes).filter(assignments__employee_id=scope.actor_employee_id, assignments__ended_at__isnull=True)
        own |= Q(current_revision__expertises__in=works)
    def predicate(value, rule):
        if value == "institution": return Q(pk__isnull=False)
        if value == "own": return own
        if value == "departments": return Q(department_id__in=rule.department_ids)
        return Q(pk__in=[])
    allowed = Q(pk__in=[])
    for rule in scope.rules:
        allowed |= predicate(rule.scope, rule) & predicate(rule.limit, rule)
    return Letter.objects.filter(allowed).distinct()


def letter_context(letter, user, action, scopes=None):
    scopes = permission_scopes(user) if scopes is None else scopes
    employee = active_employee(user)
    own = employee is not None and letter.responsible_id == employee.pk
    if not own and action in ("letters.view", "control.view", "documents.view") and letter.current_revision_id:
        own = visible_works(user, scopes).filter(letter_revisions=letter.current_revision_id, assignments__employee=employee, assignments__ended_at__isnull=True).exists() if employee else False
    return {"employee_id": str(employee.pk) if own else None, "department_ids": [letter.department_id] if letter.department_id else []}


def require_letter(user, action, letter, scopes=None):
    scopes = permission_scopes(user) if scopes is None else scopes
    if not scopes.get(action, AccessScope()).allows(**letter_context(letter, user, action, scopes)):
        raise PermissionDenied("Нет права на это действие с письмом.")


def material_queryset(user, scopes=None):
    scopes = permission_scopes(user) if scopes is None else scopes
    receipt_scope = scopes.get("receipts.view", AccessScope())
    receipts = Receipt.objects.filter(receipt_scope.query(employee_field="created_by_id", department_field="department_id"))
    return Material.objects.filter(Q(receipts__in=receipts) | Q(receipts__expertises__in=visible_works(user, scopes))).distinct()


def can_material(user, material, scopes=None):
    return material_queryset(user, scopes).filter(pk=material.pk).exists()


def require_links(user, data, scopes=None):
    scopes = permission_scopes(user) if scopes is None else scopes
    ids = data.get("expertise_ids", [])
    if len(ids) != len(set(ids)):
        from rest_framework.exceptions import ValidationError
        raise ValidationError({"expertise_ids": "Работа указана несколько раз."})
    readable = visible_works(user, scopes).filter(pk__in=ids)
    draftable = expertise_scope_queryset(user, "letters.draft", scopes).filter(pk__in=ids)
    if readable.count() != len(ids) or draftable.count() != len(ids):
        raise PermissionDenied("Нужны чтение и подготовка письма в области каждой выбранной работы.")
    if data.get("material") is not None and not can_material(user, data["material"], scopes):
        raise PermissionDenied("Нет права на выбранный материал.")


def require_create_department(user, department, expertise_ids, scopes):
    employee = active_employee(user)
    scope = scopes.get("letters.draft", AccessScope())
    context = {"employee_id": str(employee.pk) if employee else None, "department_ids": [department.pk] if department else []}
    if not scope.allows(**context):
        raise PermissionDenied("Нет права готовить письмо в этой области.")
    if not department: return
    if scope.allows(employee_id=None, department_ids=[department.pk]): return
    today = timezone.localdate()
    own_org = employee.org_assignments.filter(department=department).filter(Q(valid_from__isnull=True) | Q(valid_from__lte=today), Q(valid_to__isnull=True) | Q(valid_to__gte=today)).exists()
    linked = visible_works(user, scopes).filter(pk__in=expertise_ids, department=department).exists()
    if not own_org and not linked:
        raise PermissionDenied("Собственное письмо нельзя отнести к произвольному чужому отделу.")
