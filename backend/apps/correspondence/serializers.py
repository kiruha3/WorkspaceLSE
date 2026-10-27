from django.utils import timezone
from rest_framework import serializers
from apps.accounts.serializers import StrictSerializer
from apps.accounts.policies import AccessScope, permission_scopes
from apps.documents.models import Document
from apps.expertises.result_serializers import document_link
from apps.intake.models import Material
from apps.references.api import reference_data
from apps.references.models import Department, LetterKind
from .policies import can_material, letter_context, visible_works


class RecipientInput(StrictSerializer):
    name = serializers.CharField(max_length=500)
    address = serializers.CharField(allow_blank=True, required=False, default="")
    email = serializers.EmailField(allow_blank=True, required=False, default="")


class ContentInput(StrictSerializer):
    kind_id = serializers.PrimaryKeyRelatedField(source="kind", queryset=LetterKind.objects.all(), allow_null=True, required=False, default=None)
    subject = serializers.CharField(max_length=500, allow_blank=True, required=False, default="")
    body = serializers.CharField(allow_blank=True, required=False, default="")
    sender_name = serializers.CharField(max_length=500, allow_blank=True, required=False, default="")
    external_number = serializers.CharField(max_length=200, allow_blank=True, required=False, default="")
    external_on = serializers.DateField(allow_null=True, required=False, default=None)
    document_on = serializers.DateField(allow_null=True, required=False, default=None)
    received_on = serializers.DateField(allow_null=True, required=False, default=None)
    note = serializers.CharField(allow_blank=True, required=False, default="")
    material_id = serializers.PrimaryKeyRelatedField(source="material", queryset=Material.objects.all(), allow_null=True, required=False, default=None)
    expertise_ids = serializers.ListField(child=serializers.UUIDField(), required=False, default=list)
    reply_completeness = serializers.ChoiceField(choices=["partial", "additional", "final"], allow_null=True, required=False, default=None)
    recipients = RecipientInput(many=True, required=False, default=list)

    def validate(self, data):
        for field in ("external_on", "document_on", "received_on"):
            if data[field] and data[field] > timezone.localdate():
                raise serializers.ValidationError({field: "Факт не может быть в будущем."})
        if data["document_on"] and data["received_on"] and data["received_on"] < data["document_on"]:
            raise serializers.ValidationError({"received_on": "Получение раньше даты документа."})
        return data


class LetterCreate(ContentInput):
    direction = serializers.ChoiceField(choices=["incoming", "outgoing"])
    department_id = serializers.PrimaryKeyRelatedField(source="department", queryset=Department.objects.all(), allow_null=True, required=False, default=None)
    parent_id = serializers.UUIDField(allow_null=True, required=False, default=None)
    reason = serializers.CharField()


class DraftInput(ContentInput):
    expected_version = serializers.IntegerField(min_value=1)
    reason = serializers.CharField()


class AttachmentInput(StrictSerializer):
    expected_version = serializers.IntegerField(min_value=1)
    reason = serializers.CharField()
    document_id = serializers.PrimaryKeyRelatedField(source="document", queryset=Document.objects.all())


def person_data(person):
    return {"id": str(person.pk), "full_name": person.full_name} if person else None


def content_data(revision, user, scopes):
    works = list(revision.expertises.all())
    allowed_ids = set(visible_works(user, scopes).filter(pk__in=[w.pk for w in works]).values_list("pk", flat=True)) if works else set()
    material = revision.material if revision.material_id and can_material(user, revision.material, scopes) else None
    parent = None
    if revision.parent_id:
        allowed = scopes.get("letters.view", AccessScope()).allows(**letter_context(revision.parent, user, "letters.view", scopes))
        parent = {"id": str(revision.parent_id), "restricted": True}
        if allowed:
            parent = {"id": str(revision.parent_id), "subject": revision.parent.current_revision.subject, "direction": revision.parent.direction, "registration_number": None}
    return {
        "id": str(revision.pk), "number": revision.number,
        "kind": reference_data(revision.kind) if revision.kind_id else None,
        **{field: getattr(revision, field) for field in ("subject", "body", "sender_name", "external_number", "external_on", "document_on", "received_on", "note", "reply_completeness")},
        "material": {"id": str(material.pk), "title": material.title} if material else None,
        "expertises": [{"id": str(w.pk), "registration_number": w.registration_number} for w in works if w.pk in allowed_ids],
        "parent": parent,
        "recipients": [{"id": str(r.pk), "name": r.name, "address": r.address, "email": r.email} for r in revision.recipients.all()],
        "actor": person_data(revision.actor), "created_at": revision.created_at, "reason": revision.reason,
    }


def letter_data(letter, user, scopes=None):
    scopes = permission_scopes(user) if scopes is None else scopes
    revisions = list(letter.revisions.all())
    content = next(r for r in revisions if r.pk == letter.current_revision_id)
    actions = [action for action in ("letters.draft", "letters.attach") if scopes.get(action, AccessScope()).allows(**letter_context(letter, user, action, scopes))]
    return {
        "id": str(letter.pk), "direction": letter.direction,
        "department": reference_data(letter.department) if letter.department_id else None,
        "responsible": person_data(letter.responsible), "version": letter.version, "created_at": letter.created_at,
        "state": "draft", "received_on": None,
        "content": content_data(content, user, scopes), "content_history": [content_data(r, user, scopes) for r in revisions],
        "attachments": [{"id": str(a.pk), "document": document_link(a.document, user), "actor": person_data(a.actor), "created_at": a.created_at, "reason": a.reason} for a in letter.attachments.all()],
        "registration": None, "dispatches": [], "deliveries": [], "receipts": [], "assignment_history": [], "replies": [], "control": None,
        "allowed_actions": actions,
    }


def letter_summary(letter):
    return {"id": str(letter.pk), "direction": letter.direction, "subject": letter.current_revision.subject, "registration_number": None, "reply_completeness": letter.current_revision.reply_completeness, "state": "draft"}
