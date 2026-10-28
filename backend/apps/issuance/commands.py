from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from apps.accounts.commands import execute_once
from apps.accounts.policies import permission_scopes
from apps.accounts.services import audit, check_version
from apps.documents.models import Document
from apps.documents.policies import require_document
from apps.expertises.models import Expertise
from apps.intake.models import Receipt
from apps.intake.locking import locked_material,require_not_issued
from apps.references.models import IssueMethod
from .models import IssuePackage, PackageCheck, CheckWork, CheckFile, MaterialIssue
from .policies import require_material
from .readiness import readiness, current_facts


def locked_package(package_id):
    anchor = get_object_or_404(IssuePackage.objects.only("material_id"), pk=package_id)
    material = locked_material(anchor.material_id)
    list(Receipt.objects.select_for_update().filter(material=material).order_by("pk"))
    list(Expertise.objects.select_for_update().filter(material=material).order_by("pk"))
    package = IssuePackage.objects.select_for_update().get(pk=package_id)
    package.material = material
    return package


def lock_documents(package, evidence=None):
    ids = {document.pk for _, _, document, _ in current_facts(package)[3]}
    if evidence: ids.add(evidence.pk)
    list(Document.objects.select_for_update().filter(pk__in=ids).order_by("pk"))


def run_command(actor, package_id, data, key, payload, action, perform):
    package = locked_package(package_id)
    scopes = permission_scopes(actor)
    require_material(actor, "issue.view", package.material, scopes)
    require_material(actor, action, package.material, scopes)
    def operation():
        check_version(package, data["expected_version"])
        if getattr(package, "issuance", None): raise ValidationError("Материалы уже выданы. Повторная выдача требует отдельной процедуры.")
        require_not_issued(package.material_id)
        lock_documents(package, data.get("evidence_document"))
        result = perform(package, scopes)
        package.version += 1; package.save(update_fields=["version"])
        audit(actor, action, package, result, data["reason"])
        return {"id": str(result["id"]), "package_id": str(package.pk)}
    return execute_once(actor=actor, action=f"{action}:{package_id}", key=key, payload=payload, operation=operation)


@transaction.atomic
def check_package(*, actor, package_id, data, key, payload):
    def perform(package, scopes):
        status = readiness(package, actor, scopes)
        if not status["can_check"]: raise ValidationError({"readiness": [item["message"] for item in status["blockers"]]})
        works, closures, _, files = current_facts(package)
        check = PackageCheck.objects.create(package=package, revision=package.current_revision, actor=actor, reason=data["reason"])
        CheckWork.objects.bulk_create([CheckWork(package_check=check, expertise=work, closure=closures[work.pk]) for work in works])
        CheckFile.objects.bulk_create([CheckFile(package_check=check, item_id=item_id, closure_id=closure_id, document=document, accepted_version_id=version_id) for item_id, closure_id, document, version_id in files])
        return {"id": check.pk, "revision_id": package.current_revision_id}
    return run_command(actor, package_id, data, key, payload, "issue.check", perform)


@transaction.atomic
def issue_material(*, actor, package_id, data, key, payload):
    def perform(package, scopes):
        status = readiness(package, actor, scopes)
        if not status["can_issue"]: raise ValidationError({"readiness": "Комплект неполон или проверка устарела. Проверьте комплект заново."})
        works, closures, _, _ = current_facts(package)
        on = data["issued_on"]
        if on > timezone.localdate() or any(on < max(work.receipt.received_at, closures[work.pk].ended_on) for work in works):
            raise ValidationError({"issued_on": "Дата выдачи должна быть не раньше поступления и окончания работ и не в будущем."})
        evidence = data["evidence_document"]
        accepted = None
        if evidence:
            evidence = Document.objects.get(pk=evidence.pk)
            require_document(actor, "documents.view", evidence)
            accepted = evidence.versions.order_by("-number").first()
            if evidence.source_kind != "paper_original" and accepted is None:
                raise ValidationError({"evidence_document_id": "У копии подтверждения нет сохранённого файла."})
        method = IssueMethod.objects.select_for_update().get(pk=data["method"].pk)
        if not method.is_active: raise ValidationError({"method_id": "Способ выдачи неактивен."})
        check = package.checks.order_by("-created_at", "-pk").first()
        issue = MaterialIssue.objects.create(package=package, package_check=check, issued_on=on, method=method,
            recipient_name=data["recipient_name"], recipient_basis=data["recipient_basis"], tracking=data["tracking"], comment=data["comment"],
            evidence_document=evidence, accepted_evidence_version=accepted, actor=actor, reason=data["reason"])
        return {"id": issue.pk, "check_id": check.pk, "issued_on": on, "accepted_evidence_version_id": accepted.pk if accepted else None}
    return run_command(actor, package_id, data, key, payload, "issue.confirm", perform)
