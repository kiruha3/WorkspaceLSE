from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import APIException, ValidationError
from apps.accounts.commands import execute_once
from apps.accounts.services import audit, check_version
from apps.documents.policies import require_document
from apps.intake.models import Material
from apps.intake.locking import require_not_issued
from .models import IssuePackage, PackageRevision, PackageItem, PackageWorkBilling
from .policies import require_material
from .readiness import DOCUMENT_KINDS


class PackageConflict(APIException):
    status_code = 409
    default_code = "issue_package_exists"
    default_detail = "Комплект уже создан. Откройте существующую карточку."


def append_revision(package, actor, data):
    values = data.copy(); reason = values.pop("reason"); items = values.pop("items")
    updates = values.pop("billing", [])
    values.pop("expected_version", None)
    if package.current_revision_id:
        # No silent unlink through a redacted document projection.
        for item in package.current_revision.items.select_related("document"):
            require_document(actor, "documents.view", item.document)
    seen = set()
    for item in items:
        key = item["kind"], item["expertise_id"]
        if item["kind"] != "other" and key in seen: raise ValidationError({"items": "Документ этого назначения для работы указан повторно."})
        seen.add(key)
        if not package.material.expertises.filter(pk=item["expertise_id"]).exists():
            raise ValidationError({"items": "Работа не относится к этому материалу."})
        require_document(actor, "documents.view", item["document"])
        if item["document"].kind not in DOCUMENT_KINDS[item["kind"]]:
            raise ValidationError({"items": "Вид документа не соответствует назначению в комплекте."})
    previous = package.current_revision
    billing = {item.expertise_id: item.is_paid for item in previous.billing.all()} if previous else {}
    allowed = set(package.material.expertises.values_list("pk", flat=True))
    seen_billing = set()
    for item in updates:
        work_id = item["expertise_id"]
        if work_id in seen_billing:
            raise ValidationError({"billing": "Платность одной работы указана повторно."})
        if work_id not in allowed:
            raise ValidationError({"billing": "Работа не относится к этому материалу."})
        seen_billing.add(work_id)
        billing[work_id] = item["is_paid"]
    revision = PackageRevision.objects.create(package=package, number=previous.number + 1 if previous else 1, actor=actor, reason=reason, **values)
    PackageItem.objects.bulk_create([PackageItem(revision=revision, **item) for item in items])
    PackageWorkBilling.objects.bulk_create([PackageWorkBilling(revision=revision, expertise_id=pk, is_paid=paid) for pk, paid in billing.items()])
    package.current_revision = revision; package.save(update_fields=["current_revision"])
    audit(actor, "issue.prepare", package, {"revision_id": revision.pk}, reason)
    return {"id": str(revision.pk), "package_id": str(package.pk)}


@transaction.atomic
def create_package(*, actor, material_id, data, key, payload):
    material = get_object_or_404(Material.objects.select_for_update(), pk=material_id)
    require_material(actor, "issue.view", material); require_material(actor, "issue.prepare", material)
    def operation():
        require_not_issued(material.pk)
        if IssuePackage.objects.filter(material=material).exists(): raise PackageConflict()
        package = IssuePackage.objects.create(material=material, created_by=actor)
        return append_revision(package, actor, data)
    return execute_once(actor=actor, action=f"issue.create:{material_id}", key=key, payload=payload, operation=operation)


@transaction.atomic
def save_package(*, actor, package_id, data, key, payload):
    anchor = get_object_or_404(IssuePackage.objects.only("material_id"), pk=package_id)
    material = Material.objects.select_for_update().get(pk=anchor.material_id)
    package = IssuePackage.objects.select_for_update().get(pk=package_id)
    require_material(actor, "issue.view", material); require_material(actor, "issue.prepare", material)
    def operation():
        check_version(package, data["expected_version"])
        if getattr(package, "issuance", None): raise ValidationError("Материалы уже выданы. Нужна отдельная процедура корректировки.")
        require_not_issued(material.pk)
        result = append_revision(package, actor, data)
        package.version += 1; package.save(update_fields=["version"])
        return result
    return execute_once(actor=actor, action=f"issue.draft:{package_id}", key=key, payload=payload, operation=operation)
