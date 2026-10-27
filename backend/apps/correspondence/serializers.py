from django.utils import timezone
from rest_framework import serializers
from apps.accounts.serializers import StrictSerializer
from apps.accounts.policies import AccessScope, permission_scopes
from apps.documents.models import Document
from apps.expertises.result_serializers import document_link
from apps.intake.models import Material
from apps.references.api import reference_data
from apps.references.models import Department, LetterKind
from .policies import can_material, letter_context, visible_works, letter_scope_queryset


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
            registration = getattr(revision.parent, "registration", None)
            parent = {"id": str(revision.parent_id), "subject": revision.parent.current_revision.subject, "direction": revision.parent.direction, "registration_number": registration.registration_number if registration else None}
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
    registration = getattr(letter, "registration", None)
    receipt = getattr(letter, "receipt_fact", None)
    replies = list(letter_scope_queryset(user, "letters.view", scopes).filter(current_revision__parent=letter).select_related("current_revision", "registration").prefetch_related("dispatches__recipients", "current_revision__recipients"))
    control = getattr(letter, "control", None)
    control_allowed = scopes.get("control.view", AccessScope()).allows(**letter_context(letter, user, "control.view", scopes))
    actions = allowed_actions(letter, user, scopes, registration, receipt, control, control_allowed)
    return {
        "id": str(letter.pk), "direction": letter.direction,
        "department": reference_data(letter.department) if letter.department_id else None,
        "responsible": person_data(letter.responsible), "version": letter.version, "created_at": letter.created_at,
        "state": letter_state(letter), "received_on": receipt.received_on if receipt else None,
        "content": content_data(content, user, scopes), "content_history": [content_data(r, user, scopes) for r in revisions],
        "attachments": [{"id": str(a.pk), "document": document_link(a.document, user), "actor": person_data(a.actor), "created_at": a.created_at, "reason": a.reason} for a in letter.attachments.all()],
        "registration": registration_data(registration, user) if registration else None,
        "dispatches": [dispatch_data(d, user) for d in letter.dispatches.all()],
        "deliveries": [{**recorded_data(d), "dispatch_id": str(d.dispatch_id), "recipient_id": str(d.recipient_id), "delivered_on": d.delivered_on, "evidence": proof_data(d, user)} for dispatch in letter.dispatches.all() for d in dispatch.deliveries.all()],
        "receipts": [{**recorded_data(receipt), "received_on": receipt.received_on, "evidence": proof_data(receipt, user)}] if receipt else [],
        "assignment_history": [{**recorded_data(a), "previous": person_data(a.previous), "responsible": person_data(a.responsible)} for a in letter.assignment_history.all()],
        "replies": [letter_summary(r) for r in replies], "control": control_data(control, replies, user, scopes) if control and control_allowed else None,
        "allowed_actions": actions,
    }


def letter_summary(letter):
    registration = getattr(letter, "registration", None)
    return {"id": str(letter.pk), "direction": letter.direction, "subject": letter.current_revision.subject, "registration_number": registration.registration_number if registration else None, "reply_completeness": letter.current_revision.reply_completeness, "state": letter_state(letter)}


def letter_state(letter):
    if not getattr(letter, "registration", None): return "draft"
    if letter.direction == "incoming": return "registered"
    recipients = {r.pk for r in letter.current_revision.recipients.all()}
    sent = {r.pk for dispatch in letter.dispatches.all() for r in dispatch.recipients.all()}
    if recipients and recipients.issubset(sent): return "sent"
    return "partially_sent" if sent else "registered"


def recorded_data(event):
    return {"id": str(event.pk), "actor": person_data(event.actor), "created_at": event.created_at, "reason": event.reason}


def proof_data(event, user):
    return document_link(event.evidence_document, user, event.accepted_version_id)


def registration_data(registration, user):
    return {**recorded_data(registration), "journal": reference_data(registration.journal), "registration_number": registration.registration_number,
        "registered_on": registration.registered_on, "year": registration.year, "revision_id": str(registration.revision_id),
        "files": [document_link(f.file_version.document, user, f.file_version_id) for f in registration.files.all()]}


def dispatch_data(dispatch, user):
    return {**recorded_data(dispatch), "sent_on": dispatch.sent_on, "channel": reference_data(dispatch.channel), "recipient_ids": [str(r.pk) for r in dispatch.recipients.all()],
        "tracking": dispatch.tracking, "comment": dispatch.comment, "evidence": proof_data(dispatch, user),
        "files": [document_link(f.file_version.document, user, f.file_version_id) for f in dispatch.files.all()]}


def control_is_closed(control):
    events = [event for event in control.events.all() if event.kind != "deadline_changed"]
    return bool(events and events[-1].kind == "closed")


def control_data(control, replies, user, scopes):
    progress = "none"
    for reply in replies:
        if not getattr(reply, "registration", None): continue
        completeness = reply.current_revision.reply_completeness
        if completeness == "final": progress = "final"
        elif completeness in ("partial", "additional") and progress != "final": progress = "partial"
        elif progress == "none": progress = "registered"
    events = []
    for event in control.events.all():
        reply = None
        if event.reply_id:
            permitted = scopes.get("letters.view", AccessScope()).allows(**letter_context(event.reply, user, "letters.view", scopes))
            reply = {"id": str(event.reply_id), "subject": event.reply.current_revision.subject} if permitted else {"id": str(event.reply_id), "restricted": True}
        events.append({**recorded_data(event), "kind": event.kind, "actual_on": event.actual_on, "due_on": event.due_on, "due_basis": event.due_basis,
            "closure_reason": reference_data(event.closure_reason) if event.closure_reason_id else None, "reply": reply, "comment": event.comment})
    closed = control_is_closed(control)
    return {"id": str(control.pk), "opened_on": control.opened_on, "due_on": control.due_on, "due_basis": control.due_basis,
        "status": "closed" if closed else "open", "response_progress": progress,
        "overdue": bool(not closed and control.due_on and control.due_on < timezone.localdate()), "events": events}


def allowed_actions(letter, user, scopes, registration, receipt, control, control_allowed):
    possible = ["letters.attach", "control.assign", "control.view"]
    if not registration: possible += ["letters.draft", "letters.register"]
    else:
        if scopes.get("letters.draft", AccessScope()).allows(**letter_context(letter, user, "letters.draft", scopes)): possible.append("letters.reply")
        if letter.direction == "outgoing":
            possible.append("letters.mark_sent")
            if letter.dispatches.exists(): possible.append("letters.mark_delivered")
        elif not receipt: possible.append("letters.mark_received")
    if control and control_allowed: possible.append("control.reopen" if control_is_closed(control) else "control.close")
    return [action for action in possible if scopes.get(action, AccessScope()).allows(**letter_context(letter, user, action, scopes))]
