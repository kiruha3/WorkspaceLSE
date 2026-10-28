from rest_framework import serializers
from apps.accounts.serializers import StrictSerializer
from apps.accounts.policies import permission_scopes
from apps.documents.models import Document
from apps.documents.policies import can_document
from apps.expertises.result_serializers import document_link
from apps.references.api import reference_data
from .models import ITEM_KINDS
from .policies import material_queryset
from .readiness import current_facts, required_items, readiness, billing_values


class ItemInput(StrictSerializer):
    kind = serializers.ChoiceField(choices=ITEM_KINDS)
    expertise_id = serializers.UUIDField()
    document_id = serializers.PrimaryKeyRelatedField(source="document", queryset=Document.objects.all())
    note = serializers.CharField(allow_blank=True, required=False, default="")


class WorkBillingInput(StrictSerializer):
    expertise_id = serializers.UUIDField()
    is_paid = serializers.BooleanField(allow_null=True)


class ContentInput(StrictSerializer):
    materials_description = serializers.CharField(allow_blank=True, required=False, default="")
    note = serializers.CharField(allow_blank=True, required=False, default="")
    items = ItemInput(many=True, required=False, default=list)
    billing = WorkBillingInput(many=True, required=False, max_length=1000)
    reason = serializers.CharField()


class DraftInput(ContentInput):
    expected_version = serializers.IntegerField(min_value=1)


class PackageFilters(StrictSerializer):
    search = serializers.CharField(allow_blank=True, required=False)
    state = serializers.ChoiceField(choices=["draft", "checked", "needs_recheck", "issued"], required=False)
    issued_from = serializers.DateField(required=False)
    issued_to = serializers.DateField(required=False)
    page = serializers.IntegerField(min_value=1, required=False)

    def validate(self, data):
        if data.get("issued_from") and data.get("issued_to") and data["issued_from"] > data["issued_to"]:
            raise serializers.ValidationError({"issued_to": "Конец периода раньше начала."})
        return data


def recorded_data(record):
    employee = getattr(record.actor, "employee", None)
    return {"id": str(record.pk), "actor": {"id": str(employee.pk), "full_name": employee.full_name} if employee else None, "created_at": record.created_at, "reason": record.reason}


def revision_data(revision, user):
    return {**recorded_data(revision), "number": revision.number, "materials_description": revision.materials_description, "note": revision.note,
        "billing": [{"expertise_id": str(item.expertise_id), "is_paid": item.is_paid} for item in revision.billing.all()],
        "items": [{"id": str(item.pk), "kind": item.kind, "expertise_id": str(item.expertise_id), "document": document_link(item.document, user), "note": item.note} for item in revision.items.all()]}


def package_data(package, user, scopes=None):
    scopes = permission_scopes(user) if scopes is None else scopes
    revisions = list(package.revisions.all())
    current = next(item for item in revisions if item.pk == package.current_revision_id)
    package.current_revision = current
    billing = billing_values(package)
    ready = readiness(package, user, scopes)
    works, closures, _, _ = current_facts(package)
    check_records = list(package.checks.all())
    issue = getattr(package, "issuance", None)
    state = "issued" if issue else "checked" if ready["check_current"] else "needs_recheck" if check_records else "draft"
    actions = []
    if not issue:
        for action, possible in (("issue.prepare", all(can_document(user, "documents.view", item.document) for item in current.items.all())), ("issue.check", ready["can_check"]), ("issue.confirm", ready["can_issue"])):
            if possible and material_queryset(user, action, scopes).filter(pk=package.material_id).exists(): actions.append(action)
    return {"id": str(package.pk), "material": {"id": str(package.material_id), "title": package.material.title}, "version": package.version, "state": state,
        "content": revision_data(current, user), "content_history": [revision_data(revision, user) for revision in revisions],
        "works": [{"id": str(work.pk), "registration_number": work.registration_number, "category_code": work.category_code, "state": work.state,
            "department": {"id": str(work.department_id), "code": work.department.code, "name": work.department.name}, "is_commission": work.is_commission,
            "closure": {"id": str(closures[work.pk].pk), "kind": closures[work.pk].kind, "ended_on": closures[work.pk].ended_on,
                "result_kind": closures[work.pk].result.kind if closures[work.pk].result_id else None,
                "document": document_link(closures[work.pk].document, user, closures[work.pk].accepted_version_id)} if closures[work.pk] else None,
            "is_paid": billing.get(work.pk), "required_items": required_items(work, closures[work.pk], billing.get(work.pk))} for work in works],
        "readiness": ready,
        "checks": [{**recorded_data(check), "revision_id": str(check.revision_id), "works": [{"expertise_id": str(work.expertise_id), "closure_id": str(work.closure_id)} for work in check.works.all()],
            "files": [{"item_id": str(file.item_id) if file.item_id else None, "closure_id": str(file.closure_id) if file.closure_id else None, "document": document_link(file.document, user, file.accepted_version_id)} for file in check.files.all()]} for check in check_records],
        "issuance": {**recorded_data(issue), "check_id": str(issue.package_check_id), "issued_on": issue.issued_on, "method": reference_data(issue.method),
            "recipient_name": issue.recipient_name, "recipient_basis": issue.recipient_basis, "tracking": issue.tracking, "comment": issue.comment,
            "evidence": document_link(issue.evidence_document, user, issue.accepted_evidence_version_id)} if issue else None,
        "allowed_actions": actions}
