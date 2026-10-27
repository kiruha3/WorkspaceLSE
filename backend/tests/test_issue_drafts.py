import uuid
import pytest
from django.core.management import call_command
from apps.accounts.models import CommandReceipt
from apps.audit.models import AuditEvent
from apps.expertises.models import Expertise
from apps.personnel.models import Employee
from test_result_completion import completion_setup, ready_result, send

pytestmark = pytest.mark.django_db


def issue_setup(employee_factory, grant, *, completed=False, category="1", kind="expert_conclusion"):
    expert, actor, work, clerk, head, department, specialty = completion_setup(employee_factory, grant)
    employee = Employee.objects.get(user_id=clerk.session["_auth_user_id"])
    for action in ("issue.view", "issue.prepare", "issue.check", "issue.confirm", "documents.view", "documents.upload"):
        grant(employee, action)
    Expertise.objects.filter(pk=work["id"]).update(category_code=category)
    if completed:
        work = ready_result(expert, work, kind=kind)
        response = send(expert, work, "complete", result_id=work["result"]["id"])
        assert response.status_code == 200
        work = response.json()["expertise"]
    return clerk, employee, work, expert, actor, department, specialty


def create_package(client, material_id, *, key=None, **values):
    return client.post(f"/api/v1/materials/{material_id}/issue-packages/", {
        "reason": "ДЕМО · подготовка выдачи", **values,
    }, content_type="application/json", HTTP_IDEMPOTENCY_KEY=key or str(uuid.uuid4()))


def save_package(client, package, *, key=None, **values):
    return client.post(f"/api/v1/issue-packages/{package['id']}/draft/", {
        "expected_version": package["version"], "reason": "Уточнение комплекта", **values,
    }, content_type="application/json", HTTP_IDEMPOTENCY_KEY=key or str(uuid.uuid4()))


def item_document(client, kind, *, source="paper_original"):
    response = client.post("/api/v1/documents/", {"kind": kind, "title": "ДЕМО · документ выдачи", "source_kind": source}, content_type="application/json")
    assert response.status_code == 201
    return response.json()


def package_items(client, work, kinds, *, source="paper_original"):
    return [{"kind": kind, "expertise_id": work["id"], "document_id": item_document(client, kind, source=source)["id"], "note": ""} for kind in kinds]


def test_incomplete_issue_package_appends_revisions_without_inventing_issue(employee_factory, grant):
    client, _, work, _, _, _, _ = issue_setup(employee_factory, grant)
    material_id = work["material"]["id"]
    empty = client.get(f"/api/v1/materials/{material_id}/issue-packages/")
    assert empty.status_code == 200 and empty.json()["package"] is None
    response = create_package(client, material_id)
    assert response.status_code == 201
    package = response.json()["package"]
    assert package["version"] == 1 and package["state"] == "draft"
    assert package["issuance"] is None and package["checks"] == []
    assert package["content"]["materials_description"] == "" and package["content"]["items"] == []
    assert "issue.confirm" not in package["allowed_actions"] and "issue.check" not in package["allowed_actions"]
    codes = {item["code"] for item in package["readiness"]["blockers"]}
    assert {"materials_missing", "work_open"} <= codes
    second = save_package(client, package, materials_description="Дело в двух томах", note="Ожидаем заключение")
    assert second.status_code == 200
    current = second.json()["package"]
    assert current["version"] == 2 and len(current["content_history"]) == 2
    assert current["content_history"][0]["materials_description"] == ""
    assert current["content"]["materials_description"] == "Дело в двух томах"
    assert client.get(f"/api/v1/issue-packages/{package['id']}/").json() == current
    assert client.get("/api/v1/issue-packages/").json()["count"] == 1


def test_issue_draft_replays_project_current_revision_and_recheck_authority(employee_factory, grant):
    client, actor, work, _, _, _, _ = issue_setup(employee_factory, grant)
    key = str(uuid.uuid4())
    response = create_package(client, work["material"]["id"], key=key)
    assert response.status_code == 201
    first = response.json()["package"]
    save_key = str(uuid.uuid4())
    second = save_package(client, first, key=save_key, note="Ожидаем")
    assert second.status_code == 200
    current = save_package(client, second.json()["package"], note="Уточнено").json()["package"]
    replay = save_package(client, first, key=save_key, note="Ожидаем")
    assert replay.status_code == 200 and replay.json()["event"] == second.json()["event"]
    assert replay.json()["package"] == current
    assert create_package(client, work["material"]["id"], key=key).json()["package"] == current
    assert create_package(client, work["material"]["id"]).status_code == 409
    assert save_package(client, first).status_code == 409
    assert save_package(client, first, key=save_key, note="Другой ввод").status_code == 409
    actor.role_assignments.filter(role__permissions__permission_code="issue.prepare").update(is_active=False)
    assert save_package(client, first, key=save_key, note="Ожидаем").status_code == 403
    assert create_package(client, work["material"]["id"], key=key).status_code == 403


def test_issue_package_requires_command_key(employee_factory, grant):
    client, _, work, _, _, _, _ = issue_setup(employee_factory, grant)
    assert create_package(client, work["material"]["id"], key=" ").status_code == 400
    assert client.get(f"/api/v1/materials/{work['material']['id']}/issue-packages/").json()["package"] is None


@pytest.mark.parametrize("values", [{"reason": " "}, {"items": [{"kind": "result", "expertise_id": str(uuid.uuid4()), "document_id": str(uuid.uuid4())}]}, {"issued_on": "2026-10-28"}])
def test_invalid_issue_draft_has_no_command_audit_or_package(employee_factory, grant, values):
    client, _, work, _, _, _, _ = issue_setup(employee_factory, grant)
    key = str(uuid.uuid4())
    assert create_package(client, work["material"]["id"], key=key, **values).status_code == 400
    assert not CommandReceipt.objects.filter(key=key).exists()
    assert not AuditEvent.objects.filter(action="issue.prepare").exists()


@pytest.mark.parametrize("category,extra", [("1", "notification"), ("5", "notification"), ("2", "invoice"), ("3", "invoice")])
def test_readiness_requires_correct_category_documents_without_payment_assumption(employee_factory, grant, settings, tmp_path, category, extra):
    settings.MEDIA_ROOT = tmp_path
    client, _, work, _, _, _, _ = issue_setup(employee_factory, grant, completed=True, category=category)
    kinds = ["expert_subscription", "cover_letter", extra]
    items = package_items(client, work, kinds)
    response = create_package(client, work["material"]["id"], materials_description="Материалы дела: два тома", items=items)
    assert response.status_code == 201
    package = response.json()["package"]
    assert package["works"][0]["required_items"] == kinds
    assert package["readiness"]["can_check"] and package["readiness"]["blockers"] == []
    assert package["works"][0]["closure"]["document"]["accepted_version_id"] == work["closure"]["document"]["accepted_version_id"]
    assert not package["readiness"]["can_issue"]
    missing = save_package(client, package, materials_description="Два тома", items=items[:-1]).json()["package"]
    assert any(item["code"] == "item_missing" and item["field"] == extra for item in missing["readiness"]["blockers"])


@pytest.mark.parametrize("variant", ["4", "6", "sndz", "commission", "return"])
def test_unconfirmed_issue_policy_is_explicit_not_ordinary_conclusion_default(employee_factory, grant, settings, tmp_path, variant):
    settings.MEDIA_ROOT = tmp_path
    category = variant if variant in ("4", "6") else "1"
    kind = "research_act" if variant == "6" else "sndz" if variant == "sndz" else "expert_conclusion"
    client, _, work, expert, _, _, _ = issue_setup(employee_factory, grant, completed=variant != "return", category=category, kind=kind)
    if variant == "commission": Expertise.objects.filter(pk=work["id"]).update(is_commission=True)
    if variant == "return":
        from test_result_drafts import result_document
        from test_basis_documents import upload
        document = result_document(expert, "return_decision"); assert upload(expert, document["id"]).status_code == 201
        response = send(expert, work, "return-without-execution", decided_on="2026-10-10", document_id=document["id"], return_reason_id=None, comment="Уточнить состав возврата")
        assert response.status_code == 200
    response = create_package(client, work["material"]["id"], materials_description="Два тома")
    assert response.status_code == 201
    readiness = response.json()["package"]["readiness"]
    assert not readiness["can_check"]
    assert any(item["code"] == ("commission_policy_unconfirmed" if variant == "commission" else "policy_unconfirmed") for item in readiness["blockers"])


def test_uploaded_supplement_needs_bytes_while_paper_original_does_not(employee_factory, grant, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    client, actor, work, _, _, _, _ = issue_setup(employee_factory, grant, completed=True)
    items = package_items(client, work, ["expert_subscription", "cover_letter", "notification"], source="uploaded_copy")
    response = create_package(client, work["material"]["id"], materials_description="Материалы", items=items)
    assert response.status_code == 201
    package = response.json()["package"]
    assert any(item["code"] == "file_missing" for item in package["readiness"]["blockers"])
    from test_basis_documents import upload
    for item in items: assert upload(client, item["document_id"]).status_code == 201
    path = f"/api/v1/issue-packages/{package['id']}/"
    assert client.get(path).json()["readiness"]["can_check"]
    actor.role_assignments.filter(role__permissions__permission_code="documents.view").update(is_active=False)
    projected = client.get(path).json()
    assert projected["content"]["items"][0]["document"]["restricted"]
    assert any(item["code"] == "document_unavailable" for item in projected["readiness"]["blockers"])
    assert save_package(client, package, materials_description="Не удалять скрытые приложения", items=[]).status_code == 403


def test_issue_method_seed_preserves_edited_and_inactive_values(employee_factory, grant):
    client, actor, _, _, _, _, _ = issue_setup(employee_factory, grant)
    call_command("seed_issue_catalogs", verbosity=0)
    methods = client.get("/api/v1/issue-packages/options/").json()["methods"]
    grant(actor, "references.manage")
    method = methods[0]
    response = client.patch(f"/api/v1/references/issue-methods/{method['id']}/", {"expected_version": 1, "name": "Наш способ", "is_active": False}, content_type="application/json")
    assert response.status_code == 200
    call_command("seed_issue_catalogs", verbosity=0)
    retained = next(item for item in client.get("/api/v1/issue-packages/options/").json()["methods"] if item["id"] == method["id"])
    assert retained["name"] == "Наш способ" and not retained["is_active"] and retained["version"] == 2
