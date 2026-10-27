import uuid
import pytest
from django.core.management import call_command
from django.test import Client
from apps.accounts.models import CommandReceipt
from apps.audit.models import AuditEvent

pytestmark = pytest.mark.django_db


def letter_setup(employee_factory, grant, *, department=None):
    actor = employee_factory(department=department)
    for action in ("letters.view", "letters.draft", "letters.attach", "documents.view", "documents.upload"):
        grant(actor, action, "own")
    client = Client(); client.force_login(actor.user)
    return client, actor


def create_letter(client, *, key=None, **values):
    return client.post("/api/v1/letters/", {
        "direction": "incoming", "subject": "Запрос суда", "reason": "Получен запрос",
        **values,
    }, content_type="application/json", HTTP_IDEMPOTENCY_KEY=key or str(uuid.uuid4()))


def save_draft(client, letter, *, key=None, **values):
    return client.post(f"/api/v1/letters/{letter['id']}/draft/", {
        "expected_version": letter["version"], "reason": "Уточнение черновика",
        "subject": "Уточнённый запрос", **values,
    }, content_type="application/json", HTTP_IDEMPOTENCY_KEY=key or str(uuid.uuid4()))


@pytest.mark.parametrize("direction", ["incoming", "outgoing"])
def test_standalone_drafts_keep_unknown_facts_and_append_revisions(employee_factory, grant, direction):
    client, actor = letter_setup(employee_factory, grant)
    response = create_letter(client, direction=direction)
    assert response.status_code == 201
    letter = response.json()["letter"]
    assert letter["responsible"]["id"] == str(actor.pk)
    assert letter["version"] == 1 and letter["state"] == "draft"
    assert letter["received_on"] is None and letter["registration"] is None and letter["control"] is None
    assert letter["content"]["kind"] is None and letter["content"]["received_on"] is None
    assert letter["content"]["document_on"] is None
    second = save_draft(client, letter, body="Дополнение", recipients=[{"name": "Суд", "email": "", "address": "Абакан"}])
    assert second.status_code == 200
    current = second.json()["letter"]
    assert current["version"] == 2 and current["content"]["number"] == 2
    assert [r["subject"] for r in current["content_history"]] == ["Запрос суда", "Уточнённый запрос"]
    assert current["content"]["recipients"][0]["name"] == "Суд"
    assert client.get(f"/api/v1/letters/{letter['id']}/").json() == current
    assert AuditEvent.objects.filter(action="letters.draft").count() == 2


def test_command_replays_return_fresh_state_without_duplicate_revisions(employee_factory, grant):
    client, actor = letter_setup(employee_factory, grant)
    create_key = str(uuid.uuid4()); first = create_letter(client, key=create_key)
    assert first.status_code == 201
    initial = first.json()["letter"]; key = str(uuid.uuid4())
    saved = save_draft(client, initial, key=key)
    assert saved.status_code == 200
    final = save_draft(client, saved.json()["letter"], subject="Третья редакция")
    assert final.status_code == 200
    replay = save_draft(client, initial, key=key)
    assert replay.status_code == 200 and replay.json()["event"] == saved.json()["event"]
    assert replay.json()["letter"]["version"] == 3
    replay_create = create_letter(client, key=create_key)
    assert replay_create.status_code == 201 and replay_create.json()["event"] == first.json()["event"]
    assert replay_create.json()["letter"]["content"]["subject"] == "Третья редакция"
    assert save_draft(client, initial, key=key, subject="Другой запрос").status_code == 409
    assert save_draft(client, initial).status_code == 409
    actor.role_assignments.filter(role__permissions__permission_code="letters.draft").update(is_active=False)
    assert save_draft(client, initial, key=key).status_code == 403
    assert create_letter(client, key=create_key).status_code == 403


@pytest.mark.parametrize("values", [{"reason": " "}, {"direction": "sideways"}, {"received_on": "2099-01-01"}, {"recipients": [{"name": "Суд", "email": "ошибка"}]}, {"responsible_id": str(uuid.uuid4())}])
def test_invalid_create_does_not_leave_command_or_audit(employee_factory, grant, values):
    client, _ = letter_setup(employee_factory, grant); key = str(uuid.uuid4())
    assert create_letter(client, key=key, **values).status_code == 400
    assert not CommandReceipt.objects.filter(key=key).exists()
    assert not AuditEvent.objects.filter(action="letters.draft").exists()


def test_command_key_required(employee_factory, grant):
    client, _ = letter_setup(employee_factory, grant)
    assert create_letter(client, key=" ").status_code == 400


def test_correspondence_seed_preserves_inactive_settings_and_retained_kind(employee_factory, grant):
    client, actor = letter_setup(employee_factory, grant)
    assert client.get("/api/v1/letters/options/").status_code == 200
    call_command("seed_correspondence_catalogs", verbosity=0)
    options = client.get("/api/v1/letters/options/").json()
    assert not options["journals"]
    kind = options["kinds"][0]
    first = create_letter(client, kind_id=kind["id"])
    assert first.status_code == 201
    grant(actor, "references.manage")
    path = f"/api/v1/references/letter-kinds/{kind['id']}/"
    assert client.patch(path, {"expected_version": 1, "name": "Наш вид письма", "is_active": False}, content_type="application/json").status_code == 200
    call_command("seed_correspondence_catalogs", verbosity=0)
    value = next(v for v in client.get("/api/v1/letters/options/").json()["kinds"] if v["id"] == kind["id"])
    assert value["name"] == "Наш вид письма" and value["version"] == 2 and not value["is_active"]
    assert create_letter(client, kind_id=kind["id"]).status_code == 400
    assert save_draft(client, first.json()["letter"], kind_id=kind["id"]).status_code == 200
    journal = client.post("/api/v1/references/letter-journals/", {"code": "IN", "name": "Входящие", "direction": "incoming", "department_id": None}, content_type="application/json")
    assert journal.status_code == 201 and journal.json()["direction"] == "incoming"
    assert client.patch(f"/api/v1/references/letter-journals/{journal.json()['id']}/", {"expected_version": 1, "direction": "outgoing"}, content_type="application/json").status_code == 400


def test_attachment_is_separate_idempotent_event_and_preserves_pending_copy(employee_factory, grant):
    client, _ = letter_setup(employee_factory, grant)
    first = create_letter(client); assert first.status_code == 201
    letter = first.json()["letter"]
    document = client.post("/api/v1/documents/", {"kind": "letter", "source_kind": "uploaded_copy", "title": "Скан запроса позднее"}, content_type="application/json")
    assert document.status_code == 201
    body = {"expected_version": letter["version"], "reason": "Подкрепление", "document_id": document.json()["id"]}
    path = f"/api/v1/letters/{letter['id']}/attachments/"; key = str(uuid.uuid4())
    attached = client.post(path, body, content_type="application/json", HTTP_IDEMPOTENCY_KEY=key)
    assert attached.status_code == 200
    current = attached.json()["letter"]
    assert current["version"] == 2 and len(current["content_history"]) == 1
    assert current["attachments"][0]["document"]["versions"] == []
    assert client.post(path, body, content_type="application/json", HTTP_IDEMPOTENCY_KEY=key).json()["event"] == attached.json()["event"]
    body["expected_version"] = 2
    duplicate = client.post(path, body, content_type="application/json", HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
    assert duplicate.status_code == 400
