import uuid
import pytest
from django.core.management import call_command
from django.test import Client
from apps.accounts.models import CommandReceipt
from apps.references.models import LetterJournal
from test_letter_drafts import letter_setup, create_letter, save_draft
from test_basis_documents import upload

pytestmark = pytest.mark.django_db


def command_setup(employee_factory, grant):
    client, actor = letter_setup(employee_factory, grant)
    for action in ("letters.view", "letters.draft", "letters.reply", "letters.attach", "letters.register", "letters.mark_sent", "letters.mark_received", "letters.mark_delivered", "control.view", "control.assign", "control.close", "control.reopen"):
        grant(actor, action)
    call_command("seed_correspondence_catalogs", verbosity=0)
    options = client.get("/api/v1/letters/options/").json()
    journals = {direction: LetterJournal.objects.create(code=direction, name=direction, direction=direction) for direction in ("incoming", "outgoing")}
    return client, actor, options, journals


def command(client, letter, endpoint, *, key=None, **values):
    return client.post(f"/api/v1/letters/{letter['id']}/{endpoint}/", {"expected_version": letter["version"], "reason": "ДЕМО · факт по документу", **values}, content_type="application/json", HTTP_IDEMPOTENCY_KEY=key or str(uuid.uuid4()))


def make_letter(client, options, *, direction="incoming", parent=None, completeness=None, received=None):
    values = {"direction": direction, "kind_id": options["kinds"][0]["id"], "sender_name": "Суд", "document_on": "2026-10-01", "received_on": received, "recipients": [{"name": "Суд", "email": ""}, {"name": "Следователь", "address": "Абакан"}] if direction == "outgoing" else []}
    if parent: values.update(parent_id=parent["id"], reply_completeness=completeness)
    response = create_letter(client, **values); assert response.status_code == 201
    return response.json()["letter"]


def registered(client, letter, journals, *, number="ВХ-1", on="2026-10-02"):
    response = command(client, letter, "register", journal_id=str(journals[letter["direction"]].pk), registration_number=number, registered_on=on)
    assert response.status_code == 200
    return response.json()["letter"]


def closure_reason(options, rule):
    return next(r["id"] for r in options["closure_reasons"] if r["rule"] == rule)


def test_registration_freezes_content_not_unknown_receipt_and_keeps_replays_fresh(employee_factory, grant):
    client, _, options, journals = command_setup(employee_factory, grant)
    letter = make_letter(client, options); initial = letter; key = str(uuid.uuid4())
    values = {"journal_id": str(journals["incoming"].pk), "registration_number": "ВХ-1", "registered_on": "2026-10-02"}
    response = command(client, letter, "register", key=key, **values); assert response.status_code == 200
    letter = response.json()["letter"]
    assert letter["state"] == "registered" and letter["received_on"] is None and letter["receipts"] == []
    assert "letters.draft" not in letter["allowed_actions"]
    assert save_draft(client, letter).status_code == 400
    received = command(client, letter, "mark-received", received_on="2026-10-01", evidence_document_id=None)
    assert received.status_code == 200 and received.json()["letter"]["received_on"] == "2026-10-01"
    replay = command(client, initial, "register", key=key, **values)
    assert replay.status_code == 200 and replay.json()["event"] == response.json()["event"]
    assert replay.json()["letter"]["version"] == received.json()["letter"]["version"]
    assert command(client, received.json()["letter"], "mark-received", received_on="2026-10-02").status_code == 400
    known = registered(client, make_letter(client, options, received="2026-10-01"), journals, number="ВХ-2")
    assert known["received_on"] == "2026-10-01" and len(known["receipts"]) == 1


@pytest.mark.parametrize("variant", ["empty_subject", "empty_sender", "empty_recipients", "wrong_journal", "inactive_journal", "future", "before_document", "duplicate"])
def test_registration_invalid_or_colliding_facts_roll_back(employee_factory, grant, variant):
    client, _, options, journals = command_setup(employee_factory, grant)
    letter = make_letter(client, options, direction="outgoing" if variant == "empty_recipients" else "incoming")
    if variant in ("empty_subject", "empty_sender", "empty_recipients"):
        content = {"subject": "Тема", "sender_name": "Суд", "kind_id": options["kinds"][0]["id"]}
        if variant == "empty_subject": content["subject"] = ""
        if variant == "empty_sender": content["sender_name"] = ""
        edited = save_draft(client, letter, **content); assert edited.status_code == 200
        letter = edited.json()["letter"]
    if variant == "inactive_journal": LetterJournal.objects.filter(pk=journals["incoming"].pk).update(is_active=False)
    if variant == "duplicate": registered(client, make_letter(client, options), journals)
    key = str(uuid.uuid4())
    response = command(client, letter, "register", key=key, journal_id=str(journals["outgoing" if variant == "wrong_journal" else letter["direction"]].pk), registration_number="ВХ-1", registered_on="2099-01-01" if variant == "future" else "2026-09-30" if variant == "before_document" else "2026-10-02")
    assert response.status_code == (409 if variant == "duplicate" else 400)
    assert not CommandReceipt.objects.filter(key=key).exists()


def test_partial_sends_delivery_and_accepted_file_versions_are_independent(employee_factory, grant, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    client, _, options, journals = command_setup(employee_factory, grant)
    letter = make_letter(client, options, direction="outgoing")
    document = client.post("/api/v1/documents/", {"kind": "letter", "title": "ДЕМО · письмо", "source_kind": "uploaded_copy"}, content_type="application/json").json()
    v1 = upload(client, document["id"]).json()
    attached = command(client, letter, "attachments", document_id=document["id"]); assert attached.status_code == 200
    letter = registered(client, attached.json()["letter"], journals)
    assert letter["registration"]["files"][0]["accepted_version_id"] == v1["id"]
    v2 = upload(client, document["id"], version=2).json()
    recipients = [r["id"] for r in letter["content"]["recipients"]]
    sent = command(client, letter, "mark-sent", sent_on="2026-10-03", channel_id=options["channels"][0]["id"], recipient_ids=recipients[:1], evidence_document_id=None)
    assert sent.status_code == 200
    letter = sent.json()["letter"]
    assert letter["state"] == "partially_sent" and letter["deliveries"] == []
    dispatch = letter["dispatches"][0]
    assert dispatch["files"][0]["accepted_version_id"] == v2["id"]
    delivered = command(client, letter, "mark-delivered", dispatch_id=dispatch["id"], recipient_id=recipients[0], delivered_on="2026-10-04", evidence_document_id=None)
    assert delivered.status_code == 200 and delivered.json()["letter"]["state"] == "partially_sent"
    letter = delivered.json()["letter"]
    assert command(client, letter, "mark-delivered", dispatch_id=dispatch["id"], recipient_id=recipients[1], delivered_on="2026-10-04").status_code == 400
    assert command(client, letter, "mark-sent", sent_on="2026-10-01", channel_id=options["channels"][0]["id"], recipient_ids=recipients).status_code == 400
    final = command(client, letter, "mark-sent", sent_on="2026-10-04", channel_id=options["channels"][0]["id"], recipient_ids=recipients[1:])
    assert final.status_code == 200 and final.json()["letter"]["state"] == "sent"
    assert final.json()["letter"]["registration"]["files"][0]["accepted_version_id"] == v1["id"]


def test_incoming_request_needs_final_fully_sent_reply_for_explicit_control_close(employee_factory, grant):
    client, _, options, journals = command_setup(employee_factory, grant)
    root = registered(client, make_letter(client, options), journals)
    opened = command(client, root, "control", opened_on="2026-10-02", due_on=None, due_basis="")
    assert opened.status_code == 200
    root = opened.json()["letter"]
    assert root["control"]["status"] == "open" and root["control"]["due_on"] is None
    reply = registered(client, make_letter(client, options, direction="outgoing", parent=root, completeness="final"), journals, number="ИСХ-1", on="2026-10-03")
    close = {"closed_on": "2026-10-04", "closure_reason_id": closure_reason(options, "reply_sent"), "reply_id": reply["id"], "comment": ""}
    assert command(client, root, "control/close", **close).status_code == 400
    sent = command(client, reply, "mark-sent", sent_on="2026-10-04", channel_id=options["channels"][0]["id"], recipient_ids=[r["id"] for r in reply["content"]["recipients"]])
    assert sent.status_code == 200
    assert client.get(f"/api/v1/letters/{root['id']}/").json()["control"]["status"] == "open"
    closed = command(client, root, "control/close", **close)
    assert closed.status_code == 200 and closed.json()["letter"]["control"]["status"] == "closed"
    reopened = command(client, closed.json()["letter"], "control/reopen", reopened_on="2026-10-05", comment="Нужны дополнительные сведения")
    assert reopened.status_code == 200
    assert [e["kind"] for e in reopened.json()["letter"]["control"]["events"]] == ["opened", "closed", "reopened"]


def test_outgoing_request_partial_and_additional_answers_do_not_replace_final_receipt(employee_factory, grant):
    client, _, options, journals = command_setup(employee_factory, grant)
    root = registered(client, make_letter(client, options, direction="outgoing"), journals)
    root = command(client, root, "control", opened_on="2026-10-02", due_on="2026-10-06", due_basis="В запросе").json()["letter"]
    replies = []
    for index, completeness in enumerate(("partial", "additional", "final"), 1):
        replies.append(registered(client, make_letter(client, options, parent=root, completeness=completeness, received="2026-10-03" if index < 3 else None), journals, number=f"ОТВ-{index}", on="2026-10-03"))
    close = {"closed_on": "2026-10-05", "closure_reason_id": closure_reason(options, "reply_received"), "comment": ""}
    assert command(client, root, "control/close", reply_id=replies[0]["id"], **close).status_code == 400
    assert command(client, root, "control/close", reply_id=replies[2]["id"], **close).status_code == 400
    received = command(client, replies[2], "mark-received", received_on="2026-10-05")
    assert received.status_code == 200
    closed = command(client, root, "control/close", reply_id=replies[2]["id"], **close)
    assert closed.status_code == 200
    assert closed.json()["letter"]["control"]["response_progress"] == "final"
    assert len(closed.json()["letter"]["replies"]) == 3


def test_other_closure_requires_comment_and_control_deadline_is_not_reopening(employee_factory, grant):
    client, _, options, journals = command_setup(employee_factory, grant)
    root = registered(client, make_letter(client, options), journals)
    assert command(client, root, "control", opened_on="2026-10-02", due_on="2026-10-03", due_basis="").status_code == 400
    root = command(client, root, "control", opened_on="2026-10-02", due_on=None).json()["letter"]
    assert command(client, root, "control/close", closed_on="2026-10-03", closure_reason_id=closure_reason(options, "other"), comment="").status_code == 400
    root = command(client, root, "control/close", closed_on="2026-10-03", closure_reason_id=closure_reason(options, "other"), comment="Запрос отозван письмом суда").json()["letter"]
    assert command(client, root, "control/deadline", due_on="2026-11-01", due_basis="Новый срок").status_code == 400
    assert command(client, root, "control/reopen", reopened_on="2026-10-02").status_code == 400


def test_reply_requires_registered_opposite_readable_parent_and_specific_right(employee_factory, grant):
    client, actor, options, journals = command_setup(employee_factory, grant)
    draft = make_letter(client, options)
    assert create_letter(client, direction="outgoing", parent_id=draft["id"]).status_code == 400
    parent = registered(client, draft, journals)
    assert create_letter(client, direction="incoming", parent_id=parent["id"]).status_code == 400
    actor.role_assignments.filter(role__permissions__permission_code="letters.reply").update(is_active=False)
    assert create_letter(client, direction="outgoing", parent_id=parent["id"]).status_code == 403


def test_assignment_revokes_former_owner_replay_and_department_options_are_minimal(employee_factory, grant):
    clerk, clerk_actor, options, journals = command_setup(employee_factory, grant)
    owner_client, owner = letter_setup(employee_factory, grant); new_owner = employee_factory()
    key = str(uuid.uuid4()); created = create_letter(owner_client, key=key); assert created.status_code == 201
    letter = created.json()["letter"]
    assigned = command(clerk, letter, "assign", responsible_id=str(new_owner.pk))
    assert assigned.status_code == 200 and assigned.json()["letter"]["responsible"]["id"] == str(new_owner.pk)
    assert create_letter(owner_client, key=key).status_code == 403
    assert owner_client.get(f"/api/v1/letters/{letter['id']}/").status_code == 403
    assert all(set(p) == {"id", "full_name"} for p in clerk.get("/api/v1/letters/options/").json()["employees"])
    assert str(new_owner.pk) in [p["id"] for p in clerk.get("/api/v1/letters/options/").json()["employees"]]


def test_list_state_and_period_filters_use_actual_facts_and_control_scope(employee_factory, grant):
    client, actor, options, journals = command_setup(employee_factory, grant)
    unknown = registered(client, make_letter(client, options), journals)
    known = registered(client, make_letter(client, options, received="2026-10-01"), journals, number="ВХ-2")
    outgoing = registered(client, make_letter(client, options, direction="outgoing"), journals)
    sent = command(client, outgoing, "mark-sent", sent_on="2026-10-03", channel_id=options["channels"][0]["id"], recipient_ids=[outgoing["content"]["recipients"][0]["id"]]); assert sent.status_code == 200
    assert client.get("/api/v1/letters/", {"state": "partially_sent"}).json()["count"] == 1
    assert client.get("/api/v1/letters/", {"state": "registered"}).json()["count"] == 2
    received = client.get("/api/v1/letters/", {"received_from": "2026-10-01", "received_to": "2026-10-01"}).json()
    assert [r["id"] for r in received["results"]] == [known["id"]]
    assert client.get("/api/v1/letters/", {"registered_from": "2026-10-03"}).json()["count"] == 0
    assert client.get("/api/v1/letters/", {"received_from": "2026-10-03", "received_to": "2026-10-01"}).status_code == 400
    opened = command(client, unknown, "control", opened_on="2026-10-02", due_on="2026-10-03", due_basis="В письме"); assert opened.status_code == 200
    assert client.get("/api/v1/letters/", {"control_status": "overdue"}).json()["count"] == 1
    actor.role_assignments.filter(role__permissions__permission_code="control.view").update(is_active=False)
    assert client.get(f"/api/v1/letters/{unknown['id']}/").json()["control"] is None
    assert client.get("/api/v1/letters/", {"control_status": "open"}).status_code == 403


@pytest.mark.parametrize("has_control", [True, False])
def test_control_read_capability_distinguishes_redaction_without_disclosing_existence(employee_factory, grant, has_control):
    owner, _, options, journals = command_setup(employee_factory, grant)
    letter = registered(owner, make_letter(owner, options), journals)
    if has_control:
        response = command(owner, letter, "control", opened_on="2026-10-02", due_on=None, due_basis="")
        assert response.status_code == 200
    reader = employee_factory()
    grant(reader, "letters.view")
    grant(reader, "control.view", "own")
    client = Client(); client.force_login(reader.user)
    path = f"/api/v1/letters/{letter['id']}/"
    restricted = client.get(path).json()
    assert restricted["control"] is None
    assert "control.view" not in restricted["allowed_actions"]
    grant(reader, "control.view")
    readable = client.get(path).json()
    assert "control.view" in readable["allowed_actions"]
    assert (readable["control"] is not None) is has_control
    listed = client.get("/api/v1/letters/").json()["results"][0]
    assert "control.view" in listed["allowed_actions"]


def test_proof_replay_redacts_revoked_document_and_keeps_pinned_version(employee_factory, grant, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    client, actor, options, journals = command_setup(employee_factory, grant)
    letter = registered(client, make_letter(client, options), journals)
    document = client.post("/api/v1/documents/", {"kind": "letter", "title": "ДЕМО · подтверждение получения", "source_kind": "uploaded_copy"}, content_type="application/json").json()
    v1 = upload(client, document["id"]).json(); key = str(uuid.uuid4())
    values = {"received_on": "2026-10-02", "evidence_document_id": document["id"]}
    received = command(client, letter, "mark-received", key=key, **values); assert received.status_code == 200
    upload(client, document["id"], version=2)
    replay = command(client, letter, "mark-received", key=key, **values)
    assert replay.status_code == 200 and replay.json()["letter"]["receipts"][0]["evidence"]["accepted_version_id"] == v1["id"]
    actor.role_assignments.filter(role__permissions__permission_code="documents.view").update(is_active=False)
    replay = command(client, letter, "mark-received", key=key, **values)
    assert replay.status_code == 200
    assert replay.json()["letter"]["receipts"][0]["evidence"] == {"id": document["id"], "restricted": True}


def test_finishing_expertise_does_not_close_independent_correspondence_control(employee_factory, grant, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    from test_result_completion import completion_setup, ready_result, send
    expert, _, work, _, _, _, _ = completion_setup(employee_factory, grant)
    client, actor, options, journals = command_setup(employee_factory, grant)
    grant(actor, "expertise.view")
    response = create_letter(client, expertise_ids=[work["id"]], subject="Запрос материалов", sender_name="Суд", kind_id=options["kinds"][0]["id"])
    assert response.status_code == 201
    letter = registered(client, response.json()["letter"], journals)
    opened = command(client, letter, "control", opened_on="2026-10-02", due_on=None); assert opened.status_code == 200
    work = ready_result(expert, work)
    completed = send(expert, work, "complete", result_id=work["result"]["id"])
    assert completed.status_code == 200 and completed.json()["expertise"]["state"] == "completed"
    assert client.get(f"/api/v1/letters/{letter['id']}/").json()["control"]["status"] == "open"


def test_registry_does_not_reload_actor_permissions_for_every_row(employee_factory, grant):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext
    client, _ = letter_setup(employee_factory, grant)
    for _ in range(25): assert create_letter(client).status_code == 201
    with CaptureQueriesContext(connection) as queries:
        response = client.get("/api/v1/letters/")
    assert response.status_code == 200 and response.json()["count"] == 25
    assert len(queries) < 90


def test_parent_after_transfer_is_restricted_and_new_reply_does_not_bypass_scope(employee_factory, grant):
    clerk, _, options, journals = command_setup(employee_factory, grant)
    owner_client, owner = letter_setup(employee_factory, grant)
    grant(owner, "letters.reply", "own")
    parent = registered(clerk, make_letter(owner_client, options), journals)
    response = create_letter(owner_client, direction="outgoing", parent_id=parent["id"], reply_completeness="partial")
    assert response.status_code == 201
    child = response.json()["letter"]
    assert command(clerk, parent, "assign", responsible_id=str(employee_factory().pk)).status_code == 200
    detail = owner_client.get(f"/api/v1/letters/{child['id']}/").json()
    assert detail["content"]["parent"] == {"id": parent["id"], "restricted": True}
    assert create_letter(owner_client, direction="outgoing", parent_id=parent["id"]).status_code == 403
