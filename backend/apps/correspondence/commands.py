from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError
from apps.accounts.commands import execute_once
from apps.accounts.policies import active_employee, AccessScope, permission_scopes
from apps.accounts.services import audit, check_version
from apps.documents.models import Document
from apps.documents.policies import require_document
from apps.personnel.models import Employee
from .models import (LetterRegistration, LetterRegistrationFile, LetterDispatch, LetterDispatchFile,
    LetterReceipt, LetterDelivery, LetterAssignment, ControlTask, ControlEvent, Letter)
from .locking import locked_letter
from .drafts import checked_reference
from .policies import require_letter


class RegistrationConflict(APIException):
    status_code = 409
    default_code = "registration_conflict"
    default_detail = "Этот номер уже занят в выбранном журнале и году."


def validate_date(on, field, earliest=None):
    if on > timezone.localdate() or (earliest and on < earliest):
        raise ValidationError({field: "Проверьте дату относительно предшествующих фактов и сегодняшнего дня."})


def registration_for(letter):
    registration = LetterRegistration.objects.filter(letter=letter).select_related("revision").first()
    if not registration: raise ValidationError("Сначала зарегистрируйте письмо.")
    return registration


def locked_documents(letter, evidence=None):
    ids = set(letter.attachments.values_list("document_id", flat=True))
    if evidence: ids.add(evidence.pk)
    return {d.pk: d for d in Document.objects.select_for_update().filter(pk__in=ids).order_by("pk").prefetch_related("versions")}


def evidence_data(actor, documents, evidence):
    if evidence is None: return {"evidence_document": None, "accepted_version": None}
    document = documents[evidence.pk]; require_document(actor, "documents.view", document)
    return {"evidence_document": document, "accepted_version": max(document.versions.all(), key=lambda v: v.number, default=None)}


def snapshot_files(letter, documents):
    ids = set(letter.attachments.values_list("document_id", flat=True))
    return [version for document_id, document in documents.items() if document_id in ids and (version := max(document.versions.all(), key=lambda v: v.number, default=None))]


def control_closed(control):
    latest = control.events.exclude(kind="deadline_changed").order_by("-created_at", "-id").first()
    return bool(latest and latest.kind == "closed")


def current_control(letter):
    control = ControlTask.objects.filter(letter=letter).first()
    if not control: raise ValidationError("Письмо ещё не поставлено на контроль.")
    return control


def employee_department_ids(employee):
    today = timezone.localdate()
    return list(employee.org_assignments.filter(Q(valid_from__isnull=True) | Q(valid_from__lte=today), Q(valid_to__isnull=True) | Q(valid_to__gte=today)).values_list("department_id", flat=True))


def can_assign_employee(actor, employee, scopes=None):
    scopes = permission_scopes(actor) if scopes is None else scopes
    return employee.is_active and (not employee.user_id or employee.user.is_active) and scopes.get("control.assign", AccessScope()).allows(employee_id=str(employee.pk), department_ids=employee_department_ids(employee))


@transaction.atomic
def run_command(*, actor, letter_id, data, key, payload, action, operation):
    letter = locked_letter(actor, letter_id, action, extra_ids=[data.get("reply_id")])
    def perform():
        check_version(letter, data["expected_version"])
        event = operation(letter, actor, data)
        letter.version += 1; letter.save(update_fields=["version", "responsible"])
        audit(actor, action, letter, {"event_id": event.pk}, data["reason"])
        return {"id": str(event.pk), "letter_id": str(letter.pk)}
    return execute_once(actor=actor, action=f"{action}:{letter_id}", key=key, payload=payload, operation=perform)


def register(letter, actor, data):
    if LetterRegistration.objects.filter(letter=letter).exists(): raise ValidationError("Письмо уже зарегистрировано.")
    revision = letter.current_revision
    if not revision.subject or not revision.kind_id: raise ValidationError("Для регистрации нужны тема и вид письма.")
    if letter.direction == "incoming" and not revision.sender_name: raise ValidationError({"sender_name": "Укажите отправителя."})
    if letter.direction == "outgoing" and not revision.recipients.exists(): raise ValidationError({"recipients": "Нужен хотя бы один адресат."})
    validate_date(data["registered_on"], "registered_on", revision.document_on)
    documents = locked_documents(letter)
    journal = checked_reference(data["journal"], set(), "journal_id")
    if journal.direction != letter.direction or (journal.department_id and journal.department_id != letter.department_id):
        raise ValidationError({"journal_id": "Журнал не соответствует направлению или отделу письма."})
    year = data["registered_on"].year
    if LetterRegistration.objects.filter(journal=journal, year=year, registration_number=data["registration_number"]).exists(): raise RegistrationConflict()
    event = LetterRegistration.objects.create(letter=letter, revision=revision, journal=journal, registration_number=data["registration_number"], registered_on=data["registered_on"], year=year, actor=active_employee(actor), reason=data["reason"])
    LetterRegistrationFile.objects.bulk_create([LetterRegistrationFile(registration=event, file_version=v) for v in snapshot_files(letter, documents)])
    if letter.direction == "incoming" and revision.received_on:
        validate_date(revision.received_on, "received_on", revision.document_on)
        LetterReceipt.objects.create(letter=letter, received_on=revision.received_on, actor=active_employee(actor), reason=data["reason"])
    return event


def send(letter, actor, data):
    registration = registration_for(letter)
    if letter.direction != "outgoing": raise ValidationError("Отправка относится к исходящему письму.")
    validate_date(data["sent_on"], "sent_on", max(d for d in (registration.registered_on, registration.revision.document_on) if d))
    ids = data["recipient_ids"]
    if len(ids) != len(set(ids)) or registration.revision.recipients.filter(pk__in=ids).count() != len(ids): raise ValidationError({"recipient_ids": "Адресаты должны принадлежать зарегистрированной редакции и не повторяться."})
    documents = locked_documents(letter, data["evidence_document"])
    proof = evidence_data(actor, documents, data["evidence_document"])
    channel = checked_reference(data["channel"], set(), "channel_id")
    event = LetterDispatch.objects.create(letter=letter, sent_on=data["sent_on"], channel=channel, tracking=data["tracking"], comment=data["comment"], actor=active_employee(actor), reason=data["reason"], **proof)
    event.recipients.set(ids)
    LetterDispatchFile.objects.bulk_create([LetterDispatchFile(dispatch=event, file_version=v) for v in snapshot_files(letter, documents)])
    return event


def receive(letter, actor, data):
    registration = registration_for(letter)
    if letter.direction != "incoming": raise ValidationError("Получение относится к входящему письму.")
    if LetterReceipt.objects.filter(letter=letter).exists(): raise ValidationError("Получение уже подтверждено; обычная команда его не переписывает.")
    validate_date(data["received_on"], "received_on", registration.revision.document_on)
    documents = locked_documents(letter, data["evidence_document"])
    return LetterReceipt.objects.create(letter=letter, received_on=data["received_on"], actor=active_employee(actor), reason=data["reason"], **evidence_data(actor, documents, data["evidence_document"]))


def deliver(letter, actor, data):
    dispatch = get_object_or_404(LetterDispatch, pk=data["dispatch_id"], letter=letter)
    if not dispatch.recipients.filter(pk=data["recipient_id"]).exists(): raise ValidationError({"recipient_id": "Адресат отсутствует в этой отправке."})
    if LetterDelivery.objects.filter(dispatch=dispatch, recipient_id=data["recipient_id"]).exists(): raise ValidationError("Доставка этому адресату уже подтверждена.")
    validate_date(data["delivered_on"], "delivered_on", dispatch.sent_on)
    documents = locked_documents(letter, data["evidence_document"])
    return LetterDelivery.objects.create(dispatch=dispatch, recipient_id=data["recipient_id"], delivered_on=data["delivered_on"], actor=active_employee(actor), reason=data["reason"], **evidence_data(actor, documents, data["evidence_document"]))


def assign(letter, actor, data):
    employee = get_object_or_404(Employee.objects.select_related("user"), pk=data["responsible_id"])
    if not can_assign_employee(actor, employee): raise PermissionDenied("Сотрудник неактивен или вне области назначения.")
    if letter.responsible_id == employee.pk: raise ValidationError("Этот сотрудник уже ответственный.")
    event = LetterAssignment.objects.create(letter=letter, previous=letter.responsible, responsible=employee, actor=active_employee(actor), reason=data["reason"])
    letter.responsible = employee
    return event


def validate_due(data, opened_on):
    if data["due_on"] and (not data["due_basis"] or data["due_on"] < opened_on):
        raise ValidationError({"due_on": "Известному сроку нужно основание; срок не раньше постановки на контроль."})


def control_event(control, actor, data, kind, actual_on, **values):
    return ControlEvent.objects.create(control=control, kind=kind, actual_on=actual_on, due_on=control.due_on, due_basis=control.due_basis, actor=active_employee(actor), reason=data["reason"], **values)


def open_task(letter, actor, data):
    registration = registration_for(letter)
    if ControlTask.objects.filter(letter=letter).exists(): raise ValidationError("Контроль уже создан; возобновление — отдельное действие.")
    validate_date(data["opened_on"], "opened_on", registration.registered_on); validate_due(data, data["opened_on"])
    control = ControlTask.objects.create(letter=letter, opened_on=data["opened_on"], due_on=data["due_on"], due_basis=data["due_basis"])
    return control_event(control, actor, data, "opened", data["opened_on"])


def deadline(letter, actor, data):
    control = current_control(letter)
    if control_closed(control): raise ValidationError("Сначала явно возобновите закрытый контроль.")
    validate_due(data, control.opened_on)
    control.due_on = data["due_on"]; control.due_basis = data["due_basis"]; control.version += 1; control.save()
    return control_event(control, actor, data, "deadline_changed", timezone.localdate())


def close(letter, actor, data):
    control = current_control(letter)
    if control_closed(control): raise ValidationError("Контроль уже закрыт.")
    previous = list(control.events.values_list("actual_on", flat=True))
    validate_date(data["closed_on"], "closed_on", max([control.opened_on, *previous]))
    reason = checked_reference(data["closure_reason"], set(), "closure_reason_id")
    reply = None
    if reason.rule in ("reply_sent", "reply_received"):
        if not data["reply_id"]: raise ValidationError({"reply_id": "Выберите завершающий ответ."})
        reply = get_object_or_404(Letter, pk=data["reply_id"])
        require_letter(actor, "letters.view", reply)
        revision = reply.current_revision
        if revision.parent_id != letter.pk or revision.reply_completeness != "final": raise ValidationError({"reply_id": "Нужен явно связанный завершающий ответ, не частичный или дополнительный."})
        registration = registration_for(reply)
        if registration.registered_on > data["closed_on"]: raise ValidationError({"closed_on": "Ответ зарегистрирован позже закрытия."})
        if reason.rule == "reply_sent":
            if letter.direction != "incoming" or reply.direction != "outgoing": raise ValidationError("Ожидается исходящий ответ на входящее письмо.")
            recipient_ids = set(registration.revision.recipients.values_list("pk", flat=True))
            sent_ids = set(LetterDispatch.objects.filter(letter=reply, sent_on__lte=data["closed_on"]).values_list("recipients__pk", flat=True))
            if not recipient_ids or not recipient_ids.issubset(sent_ids): raise ValidationError("Завершающий ответ ещё не отправлен всем адресатам на дату закрытия.")
        else:
            if letter.direction != "outgoing" or reply.direction != "incoming": raise ValidationError("Ожидается входящий ответ на исходящее письмо.")
            received = LetterReceipt.objects.filter(letter=reply).first()
            if not received or received.received_on > data["closed_on"]: raise ValidationError("Нет подтверждённого получения завершающего ответа на дату закрытия.")
    elif not data["comment"]: raise ValidationError({"comment": "Для самостоятельного решения нужно пояснение."})
    elif data["reply_id"]: raise ValidationError({"reply_id": "Это основание не связывается с ответом."})
    return control_event(control, actor, data, "closed", data["closed_on"], closure_reason=reason, reply=reply, comment=data["comment"])


def reopen(letter, actor, data):
    control = current_control(letter)
    if not control_closed(control): raise ValidationError("Контроль не закрыт.")
    validate_date(data["reopened_on"], "reopened_on", max(control.events.values_list("actual_on", flat=True)))
    return control_event(control, actor, data, "reopened", data["reopened_on"], comment=data["comment"])


def register_letter(**kwargs): return run_command(**kwargs, action="letters.register", operation=register)
def send_letter(**kwargs): return run_command(**kwargs, action="letters.mark_sent", operation=send)
def receive_letter(**kwargs): return run_command(**kwargs, action="letters.mark_received", operation=receive)
def deliver_letter(**kwargs): return run_command(**kwargs, action="letters.mark_delivered", operation=deliver)
def assign_letter(**kwargs): return run_command(**kwargs, action="control.assign", operation=assign)
def open_control(**kwargs): return run_command(**kwargs, action="control.assign", operation=open_task)
def change_control_deadline(**kwargs): return run_command(**kwargs, action="control.assign", operation=deadline)
def close_control(**kwargs): return run_command(**kwargs, action="control.close", operation=close)
def reopen_control(**kwargs): return run_command(**kwargs, action="control.reopen", operation=reopen)
