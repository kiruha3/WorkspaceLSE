from rest_framework.exceptions import PermissionDenied
from apps.accounts.policies import permission_scopes
from apps.expertises.models import Expertise
from apps.expertises.policies import expertise_scope_queryset
from apps.intake.models import Material
from .models import IssuePackage


def material_queryset(user, action, scopes=None):
    scopes = permission_scopes(user) if scopes is None else scopes
    if not scopes.get("expertise.view") or not scopes.get(action): return Material.objects.none()
    readable = expertise_scope_queryset(user, "expertise.view", scopes)
    actionable = expertise_scope_queryset(user, action, scopes).filter(pk__in=readable)
    excluded = Expertise.objects.exclude(pk__in=actionable)
    return Material.objects.filter(expertises__in=actionable).exclude(expertises__in=excluded).distinct()


def package_queryset(user, action="issue.view", scopes=None):
    return IssuePackage.objects.filter(material__in=material_queryset(user, action, scopes))


def require_material(user, action, material, scopes=None):
    if not material_queryset(user, action, scopes).filter(pk=material.pk).exists():
        raise PermissionDenied("Нужны соответствующие права на все работы материала.")
