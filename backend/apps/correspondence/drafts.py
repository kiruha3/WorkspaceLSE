from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError
from apps.accounts.commands import execute_once
from apps.accounts.policies import active_employee, permission_scopes
from apps.accounts.services import audit, check_version, require_any_scope
from apps.documents.models import Document
from apps.documents.policies import require_document
from .models import Letter, LetterRevision, LetterRecipient, LetterAttachment
from .policies import require_letter, require_links, require_create_department


def locked_letter(actor, letter_id, action):
    letter = get_object_or_404(Letter.objects.select_for_update(), pk=letter_id)
    scopes = permission_scopes(actor)
    require_letter(actor, "letters.view", letter, scopes)
    require_letter(actor, action, letter, scopes)
    return letter


def checked_reference(reference, previous_ids, field):
    if reference is None: return None
    current = type(reference).objects.select_for_update().get(pk=reference.pk)
    if not current.is_active and current.pk not in previous_ids:
        raise ValidationError({field: "Неактивное значение нельзя выбрать впервые."})
    return current


def append_revision(letter, actor, data, reason):
    values = data.copy(); ids = values.pop("expertise_ids"); recipients = values.pop("recipients")
    if letter.direction == "outgoing" and values["received_on"]:
        raise ValidationError({"received_on": "Получение фиксируется у входящего письма, доставка — отдельным действием."})
    require_links(actor, {**values, "expertise_ids": ids})
    values["kind"] = checked_reference(values["kind"], set(letter.revisions.values_list("kind_id", flat=True)), "kind_id")
    parent_id = letter.current_revision.parent_id if letter.current_revision_id else None
    if not parent_id and values["reply_completeness"]:
        raise ValidationError({"reply_completeness": "Для полноты ответа нужна явная связь с исходным письмом."})
    revision = LetterRevision.objects.create(letter=letter, number=letter.revisions.count() + 1, actor=active_employee(actor), reason=reason, parent_id=parent_id, **values)
    revision.expertises.set(ids)
    LetterRecipient.objects.bulk_create([LetterRecipient(revision=revision, **r) for r in recipients])
    letter.current_revision = revision
    letter.save(update_fields=["current_revision"])
    return revision


def verify_replay(actor, result, action):
    letter = Letter.objects.get(pk=result["letter_id"])
    require_letter(actor, "letters.view", letter)
    require_letter(actor, action, letter)
    return result


@transaction.atomic
def create_letter(*, actor, data, key, payload):
    require_any_scope(actor, "letters.draft")
    def operation():
        values = data.copy(); department = values.pop("department"); direction = values.pop("direction")
        reason = values.pop("reason"); parent_id = values.pop("parent_id")
        if parent_id:
            raise ValidationError({"parent_id": "Связанные ответы станут доступны после включения регистрации переписки."})
        scopes = permission_scopes(actor)
        require_create_department(actor, department, values["expertise_ids"], scopes)
        department = checked_reference(department, set(), "department_id")
        letter = Letter.objects.create(direction=direction, department=department, responsible=active_employee(actor), created_by=active_employee(actor))
        require_letter(actor, "letters.view", letter, scopes)
        revision = append_revision(letter, actor, values, reason)
        audit(actor, "letters.draft", letter, {"revision_id": revision.pk}, reason)
        return {"id": str(revision.pk), "letter_id": str(letter.pk)}
    result = execute_once(actor=actor, action="letters.create", key=key, payload=payload, operation=operation)
    return verify_replay(actor, result, "letters.draft")


@transaction.atomic
def save_draft(*, actor, letter_id, data, key, payload):
    letter = locked_letter(actor, letter_id, "letters.draft")
    def operation():
        values = data.copy(); check_version(letter, values.pop("expected_version")); reason = values.pop("reason")
        revision = append_revision(letter, actor, values, reason)
        letter.version += 1; letter.save(update_fields=["version"])
        audit(actor, "letters.draft", letter, {"revision_id": revision.pk}, reason)
        return {"id": str(revision.pk), "letter_id": str(letter.pk)}
    return execute_once(actor=actor, action=f"letters.draft:{letter_id}", key=key, payload=payload, operation=operation)


@transaction.atomic
def attach_document(*, actor, letter_id, data, key, payload):
    letter = locked_letter(actor, letter_id, "letters.attach")
    def operation():
        check_version(letter, data["expected_version"])
        document = Document.objects.select_for_update().get(pk=data["document"].pk)
        require_document(actor, "documents.view", document)
        if letter.attachments.filter(document=document).exists():
            raise ValidationError({"document_id": "Документ уже прикреплён к письму."})
        item = LetterAttachment.objects.create(letter=letter, document=document, actor=active_employee(actor), reason=data["reason"])
        letter.version += 1; letter.save(update_fields=["version"])
        audit(actor, "letters.attach", letter, {"attachment_id": item.pk, "document_id": document.pk}, data["reason"])
        return {"id": str(item.pk), "letter_id": str(letter.pk)}
    return execute_once(actor=actor, action=f"letters.attach:{letter_id}", key=key, payload=payload, operation=operation)
