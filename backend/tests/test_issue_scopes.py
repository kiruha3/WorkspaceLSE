import uuid
import pytest
from django.test import Client
from apps.expertises.models import Expertise
from apps.references.models import Department
from test_issue_drafts import issue_setup, create_package, save_package, item_document
from test_registration import register

pytestmark = pytest.mark.django_db


def test_wide_view_does_not_expand_issue_prepare_scope(employee_factory, grant):
    owner, _, work, _, _, _, _ = issue_setup(employee_factory, grant)
    package = create_package(owner, work["material"]["id"]).json()["package"]
    other = Department.objects.create(code="4", name="Отдел 4")
    actor = employee_factory(department=other)
    grant(actor, "expertise.view"); grant(actor, "issue.view")
    grant(actor, "issue.prepare", "departments", departments=[other])
    client = Client(); client.force_login(actor.user)
    assert client.get(f"/api/v1/issue-packages/{package['id']}/").status_code == 200
    assert save_package(client, package).status_code == 403


def test_material_requires_all_work_scopes_and_does_not_disclose_hidden_work_counts(employee_factory, grant):
    owner, _, work, expert, actor, department, specialty = issue_setup(employee_factory, grant)
    grant(actor, "issue.view", "own")
    package = create_package(owner, work["material"]["id"]).json()["package"]
    assert expert.get(f"/api/v1/issue-packages/{package['id']}/").status_code == 200
    other = Department.objects.create(code="4", name="Отдел 4")
    sibling = register(owner, work["receipt"], {"expected_version": work["receipt"]["version"] if "version" in work["receipt"] else 2, "registration_number": "152/4-1-26", "department_id": str(other.pk), "specialty_id": str(specialty.pk), "appointment_nature": "primary", "is_commission": False})
    assert sibling.status_code == 201
    detail = expert.get(f"/api/v1/issue-packages/{package['id']}/")
    assert detail.status_code == 403 and sibling.json()["registration_number"] not in detail.content.decode()
    assert expert.get("/api/v1/issue-packages/").json()["count"] == 0
    readiness = owner.get(f"/api/v1/issue-packages/{package['id']}/readiness/").json()
    assert any(item["code"] == "work_open" and item["expertise_id"] == sibling.json()["id"] for item in readiness["blockers"])


def test_package_items_cannot_adopt_foreign_work_or_wrong_kind(employee_factory, grant):
    client, _, work, _, _, _, _ = issue_setup(employee_factory, grant)
    package = create_package(client, work["material"]["id"]).json()["package"]
    doc = item_document(client, "invoice")
    assert save_package(client, package, items=[{"kind": "invoice", "expertise_id": str(uuid.uuid4()), "document_id": doc["id"]}]).status_code in (400, 403)
    assert save_package(client, package, items=[{"kind": "expert_subscription", "expertise_id": work["id"], "document_id": doc["id"]}]).status_code == 400
    assert save_package(client, package, items=[{"kind": "invoice", "expertise_id": work["id"], "document_id": doc["id"]}] * 2).status_code == 400
    current = client.get(f"/api/v1/issue-packages/{package['id']}/").json()
    assert current["version"] == 1 and len(current["content_history"]) == 1


def test_document_options_only_offer_readable_compatible_documents(employee_factory, grant):
    client, actor, work, _, _, _, _ = issue_setup(employee_factory, grant)
    package = create_package(client, work["material"]["id"]).json()["package"]
    visible = item_document(client, "invoice")
    from apps.documents.models import Document
    private = Document.objects.create(kind="invoice", source_kind="paper_original", title="Чужой счёт", created_by=employee_factory())
    actor.role_assignments.filter(role__permissions__permission_code="documents.view").update(is_active=False)
    grant(actor, "documents.view", "own")
    response = client.get(f"/api/v1/issue-packages/{package['id']}/document-options/", {"kind": "invoice"})
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()["results"]]
    assert visible["id"] in ids and str(private.pk) not in ids
    assert save_package(client, package, items=[{"kind": "invoice", "expertise_id": work["id"], "document_id": str(private.pk)}]).status_code == 403


def test_package_document_fallback_needs_both_current_scopes_and_never_grants_upload(employee_factory, grant, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    from test_basis_documents import upload, PNG
    client, _, work, expert, actor, _, _ = issue_setup(employee_factory, grant)
    grant(actor, "issue.view", "own")
    document = item_document(client, "invoice", source="uploaded_copy")
    uploaded = upload(client, document["id"])
    assert uploaded.status_code == 201
    version = uploaded.json()
    assert expert.get(version["download_url"]).status_code == 403
    created = create_package(client, work["material"]["id"], items=[{"kind": "invoice", "expertise_id": work["id"], "document_id": document["id"]}])
    assert created.status_code == 201
    response = expert.get(version["download_url"])
    assert response.status_code == 200 and b"".join(response.streaming_content) == PNG
    assert upload(expert, document["id"], version=2).status_code == 403
    actor.role_assignments.filter(role__permissions__permission_code="issue.view").update(is_active=False)
    assert expert.get(version["download_url"]).status_code == 403
