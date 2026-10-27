import uuid
import pytest
from django.core.management import call_command
from apps.accounts.models import CommandReceipt
from apps.audit.models import AuditEvent
from apps.references.models import IssueMethod
from test_issue_drafts import issue_setup, create_package, save_package, package_items
from test_basis_documents import upload
from test_result_completion import result_body, send, ready_result
from test_registration import register

pytestmark = pytest.mark.django_db


def package_command(client, package, endpoint, *, key=None, **values):
    return client.post(f"/api/v1/issue-packages/{package['id']}/{endpoint}/", {
        "expected_version": package["version"], "reason": "ДЕМО · сверка и выдача", **values,
    }, content_type="application/json", HTTP_IDEMPOTENCY_KEY=key or str(uuid.uuid4()))


def ready_package(employee_factory, grant, *, category="1", uploaded=False):
    client, clerk, work, expert, actor, department, specialty = issue_setup(employee_factory, grant, completed=True, category=category)
    kinds = ["expert_subscription", "cover_letter", "notification" if category in ("1", "5") else "invoice"]
    items = package_items(client, work, kinds, source="uploaded_copy" if uploaded else "paper_original")
    if uploaded:
        for item in items: assert upload(client, item["document_id"]).status_code == 201
    created = create_package(client, work["material"]["id"], materials_description="Материалы дела: два тома, опись на одном листе", items=items)
    assert created.status_code == 201
    call_command("seed_issue_catalogs", verbosity=0)
    return client, clerk, work, created.json()["package"], expert, actor, department, specialty


def issue_values(**values):
    return {"issued_on": "2026-10-15", "method_id": str(IssueMethod.objects.get(code="in_person").pk), "recipient_name": "ДЕМО · представитель суда", "recipient_basis": "ДЕМО · доверенность и документ получателя", "tracking": "", "comment": "", "evidence_document_id": None, **values}


def checked(client, package):
    response = package_command(client, package, "check")
    assert response.status_code == 200
    return response.json()["package"]


def test_checked_package_pins_facts_and_issue_is_separate_from_completion(employee_factory, grant, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    client, _, work, package, _, _, _, _ = ready_package(employee_factory, grant)
    assert package["issuance"] is None and not package["readiness"]["can_issue"]
    key = str(uuid.uuid4())
    check = package_command(client, package, "check", key=key)
    assert check.status_code == 200
    current = check.json()["package"]
    assert current["state"] == "checked" and current["version"] == package["version"] + 1
    assert current["readiness"]["check_current"] and current["readiness"]["can_issue"]
    assert current["checks"][0]["works"] == [{"expertise_id": work["id"], "closure_id": work["closure"]["id"]}]
    assert len(current["checks"][0]["files"]) == 4
    paper = [item["document"] for item in current["checks"][0]["files"] if item["item_id"]]
    assert all(item["accepted_version_id"] is None and item["versions"] == [] for item in paper)
    issue_key = str(uuid.uuid4())
    issued = package_command(client, current, "issue", key=issue_key, **issue_values())
    assert issued.status_code == 200
    result = issued.json()["package"]
    assert result["state"] == "issued" and result["issuance"]["issued_on"] == "2026-10-15"
    assert result["issuance"]["recipient_name"] == "ДЕМО · представитель суда"
    assert result["allowed_actions"] == []
    replay = package_command(client, current, "issue", key=issue_key, **issue_values())
    assert replay.status_code == 200 and replay.json()["event"] == issued.json()["event"]
    assert package_command(client, package, "check", key=key).json()["package"]["state"] == "issued"
    assert package_command(client, result, "issue", **issue_values()).status_code == 400
    assert save_package(client, result, materials_description="Не переписать выдачу").status_code == 400
    assert AuditEvent.objects.filter(action="issue.confirm").count() == 1
    assert client.get("/api/v1/issue-packages/", {"state": "issued", "issued_from": "2026-10-15", "issued_to": "2026-10-15"}).json()["count"] == 1
    assert client.get("/api/v1/issue-packages/", {"issued_from": "2026-10-16"}).json()["count"] == 0


@pytest.mark.parametrize("variant", ["no_check", "future", "before_end", "recipient", "basis", "inactive", "wrong_version", "missing_key"])
def test_invalid_issue_is_atomic_and_does_not_mark_material_issued(employee_factory, grant, settings, tmp_path, variant):
    settings.MEDIA_ROOT = tmp_path
    client, _, _, package, _, _, _, _ = ready_package(employee_factory, grant)
    if variant != "no_check": package = checked(client, package)
    values = issue_values()
    if variant == "future": values["issued_on"] = "2099-01-01"
    if variant == "before_end": values["issued_on"] = "2026-10-09"
    if variant in ("recipient", "basis"): values["recipient_name" if variant == "recipient" else "recipient_basis"] = " "
    if variant == "inactive": IssueMethod.objects.filter(pk=values["method_id"]).update(is_active=False)
    if variant == "wrong_version": values["expected_version"] = 999
    key = " " if variant == "missing_key" else str(uuid.uuid4())
    response = package_command(client, package, "issue", key=key, **values)
    assert response.status_code == (409 if variant == "wrong_version" else 400)
    assert not CommandReceipt.objects.filter(action__startswith="issue.confirm", key=key).exists()
    assert not AuditEvent.objects.filter(action="issue.confirm").exists()
    assert client.get(f"/api/v1/issue-packages/{package['id']}/").json()["issuance"] is None


@pytest.mark.parametrize("change", ["draft", "closure", "new_work", "supplement", "result_file"])
def test_check_snapshot_requires_recheck_for_changed_composition_not_unaccepted_result_bytes(employee_factory, grant, settings, tmp_path, change):
    settings.MEDIA_ROOT = tmp_path
    client, _, work, package, expert, actor, department, specialty = ready_package(employee_factory, grant, uploaded=True)
    package = checked(client, package)
    if change == "draft":
        items = [{"kind": item["kind"], "expertise_id": item["expertise_id"], "document_id": item["document"]["id"], "note": item["note"]} for item in package["content"]["items"]]
        response = save_package(client, package, materials_description="Уточнена опись материалов", items=items)
        assert response.status_code == 200; package = response.json()["package"]
    elif change == "closure":
        grant(actor, "expertise.closed.correct", "own")
        response = send(expert, work, "correct", correction_kind="result", result=result_body(work, note="Уточнён итог"))
        assert response.status_code == 200
    elif change == "new_work":
        assert register(client, work["receipt"], {"expected_version": 2, "registration_number": "152/3-1-26", "department_id": str(department.pk), "specialty_id": str(specialty.pk), "appointment_nature": "primary", "is_commission": False}).status_code == 201
    elif change == "supplement": assert upload(client, package["content"]["items"][0]["document"]["id"], version=2).status_code == 201
    else: assert upload(expert, work["closure"]["document"]["id"], version=2).status_code == 201
    current = client.get(f"/api/v1/issue-packages/{package['id']}/").json()
    assert current["readiness"]["check_current"] is (change == "result_file")
    response = package_command(client, current, "issue", **issue_values())
    assert response.status_code == (200 if change == "result_file" else 400)
    if change == "result_file":
        accepted = next(file["document"] for file in response.json()["package"]["checks"][0]["files"] if file["closure_id"])
        assert accepted["accepted_version_id"] == work["closure"]["document"]["accepted_version_id"]


def test_issued_material_blocks_registration_receipt_amendment_and_closed_correction(employee_factory, grant, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    client, clerk, work, package, expert, actor, department, specialty = ready_package(employee_factory, grant)
    package = checked(client, package)
    assert package_command(client, package, "issue", **issue_values()).status_code == 200
    values = {"expected_version": 2, "registration_number": "152/3-1-26", "department_id": str(department.pk), "specialty_id": str(specialty.pk), "appointment_nature": "primary", "is_commission": False}
    assert register(client, work["receipt"], values).status_code == 400
    grant(clerk, "receipts.amend")
    assert client.post(f"/api/v1/receipts/{work['receipt']['id']}/amend/", {"expected_version": 2, "received_at": "2026-10-02", "reason": "Не переписать выданный факт"}, content_type="application/json").status_code == 400
    grant(actor, "expertise.closed.correct", "own")
    assert send(expert, work, "correct", correction_kind="result", result=result_body(work)).status_code == 400
    assert "expertise.closed.correct" not in expert.get(f"/api/v1/expertises/{work['id']}/").json()["allowed_actions"]
    original = CommandReceipt.objects.get(action="expertise.register", result__id=work["id"])
    values["registration_number"] = work["registration_number"]
    assert register(client, work["receipt"], values, key=original.key).status_code == 201


def test_current_expert_reads_issue_status_but_cannot_issue_and_old_keys_recheck_rights(employee_factory, grant, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    client, clerk, work, package, expert, actor, _, _ = ready_package(employee_factory, grant)
    path = f"/api/v1/expertises/{work['id']}/issue-status/"
    assert expert.get(path).json()["status"] == "unavailable"
    grant(actor, "issue.view", "own")
    assert expert.get(path).json()["status"] == "not_issued"
    package = checked(client, package); key = str(uuid.uuid4())
    assert package_command(expert, package, "issue", **issue_values()).status_code == 403
    issued = package_command(client, package, "issue", key=key, **issue_values())
    assert issued.status_code == 200
    status = expert.get(path).json()
    assert status["status"] == "issued" and status["issued_on"] == "2026-10-15"
    assert status["package"] == {"id": package["id"]}
    clerk.role_assignments.filter(role__permissions__permission_code="issue.confirm").update(is_active=False)
    assert package_command(client, package, "issue", key=key, **issue_values()).status_code == 403


def test_issue_replay_redacts_revoked_proof_and_keeps_checked_file_versions(employee_factory, grant, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    client, clerk, _, package, _, _, _, _ = ready_package(employee_factory, grant, uploaded=True)
    package = checked(client, package)
    from test_issue_drafts import item_document
    evidence = item_document(client, "letter", source="uploaded_copy")
    proof = upload(client, evidence["id"]).json(); key = str(uuid.uuid4())
    values = issue_values(evidence_document_id=evidence["id"])
    issued = package_command(client, package, "issue", key=key, **values)
    assert issued.status_code == 200
    assert issued.json()["package"]["issuance"]["evidence"]["accepted_version_id"] == proof["id"]
    assert upload(client, evidence["id"], version=2).status_code == 201
    visible_replay = package_command(client, package, "issue", key=key, **values)
    assert visible_replay.json()["package"]["issuance"]["evidence"]["accepted_version_id"] == proof["id"]
    clerk.role_assignments.filter(role__permissions__permission_code="documents.view").update(is_active=False)
    replay = package_command(client, package, "issue", key=key, **values)
    assert replay.status_code == 200
    assert replay.json()["package"]["issuance"]["evidence"] == {"id": evidence["id"], "restricted": True}
    assert client.get(proof["preview_url"]).status_code == 403


def test_incomplete_package_cannot_be_checked(employee_factory, grant):
    client, _, work, _, _, _, _ = issue_setup(employee_factory, grant)
    package = create_package(client, work["material"]["id"]).json()["package"]
    assert package_command(client, package, "check").status_code == 400
    assert client.get(f"/api/v1/issue-packages/{package['id']}/").json()["checks"] == []


def test_unknown_package_policy_cannot_be_checked(employee_factory, grant, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    client, _, _, package, _, _, _, _ = ready_package(employee_factory, grant, category="4")
    assert package_command(client, package, "check").status_code == 400
    assert not AuditEvent.objects.filter(action="issue.check").exists()


def test_wide_read_never_expands_check_or_issue_department(employee_factory, grant, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    from django.test import Client
    from apps.references.models import Department
    client, _, _, package, _, _, _, _ = ready_package(employee_factory, grant)
    package = checked(client, package)
    other = Department.objects.create(code="4", name="Отдел 4")
    actor = employee_factory(department=other)
    for action in ("expertise.view", "issue.view", "documents.view"): grant(actor, action)
    for action in ("issue.check", "issue.confirm"): grant(actor, action, "departments", departments=[other])
    scoped = Client(); scoped.force_login(actor.user)
    detail = scoped.get(f"/api/v1/issue-packages/{package['id']}/")
    assert detail.status_code == 200
    assert "issue.confirm" not in detail.json()["allowed_actions"]
    assert package_command(scoped, package, "check").status_code == 403
    assert package_command(scoped, package, "issue", **issue_values()).status_code == 403


def test_completion_replay_remains_available_after_issue_without_second_ending(employee_factory, grant, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    from apps.expertises.models import WorkClosure
    client, _, work, expert, _, _, _ = issue_setup(employee_factory, grant)
    pending = ready_result(expert, work); key = str(uuid.uuid4())
    completed = send(expert, pending, "complete", key=key, result_id=pending["result"]["id"])
    assert completed.status_code == 200
    work = completed.json()["expertise"]
    items = package_items(client, work, ["expert_subscription", "cover_letter", "notification"])
    package = create_package(client, work["material"]["id"], materials_description="Материалы", items=items).json()["package"]
    call_command("seed_issue_catalogs", verbosity=0)
    package = checked(client, package)
    assert package_command(client, package, "issue", **issue_values()).status_code == 200
    replay = send(expert, pending, "complete", key=key, result_id=pending["result"]["id"])
    assert replay.status_code == 200 and replay.json()["event"] == completed.json()["event"]
    assert WorkClosure.objects.filter(expertise_id=work["id"]).count() == 1
