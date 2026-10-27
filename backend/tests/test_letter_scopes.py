import uuid
import pytest
from django.test import Client
from apps.references.models import Department
from test_letter_drafts import letter_setup, create_letter, save_draft
from test_production import production_setup
from test_basis_documents import upload, PNG
from test_expert_assignments import assign, qualified
from test_registration import register

pytestmark = pytest.mark.django_db


def test_previous_responsible_cannot_read_or_replay_even_as_creator(employee_factory, grant):
    client, _ = letter_setup(employee_factory, grant); key = str(uuid.uuid4())
    response = create_letter(client, key=key); assert response.status_code == 201
    letter = response.json()["letter"]
    from apps.correspondence.models import Letter
    other = employee_factory()
    Letter.objects.filter(pk=letter["id"]).update(responsible=other)
    assert client.get(f"/api/v1/letters/{letter['id']}/").status_code == 403
    assert client.get("/api/v1/letters/").json()["count"] == 0
    assert create_letter(client, key=key).status_code == 403
    assert save_draft(client, letter).status_code == 403


def test_file_access_through_standalone_letter_needs_view_not_expertise_and_never_upload(employee_factory, grant, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    client, actor = letter_setup(employee_factory, grant)
    owner_client, owner = letter_setup(employee_factory, grant)
    grant(owner, "letters.view"); grant(owner, "letters.attach")
    response = create_letter(client); assert response.status_code == 201
    letter = response.json()["letter"]
    document = owner_client.post("/api/v1/documents/", {"kind": "letter", "title": "Запрос", "source_kind": "uploaded_copy"}, content_type="application/json").json()
    version = upload(owner_client, document["id"]).json()
    assert client.get(version["preview_url"]).status_code == 403
    path = f"/api/v1/letters/{letter['id']}/attachments/"
    attached = owner_client.post(path, {"expected_version": 1, "reason": "К запросу", "document_id": document["id"]}, content_type="application/json", HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
    assert attached.status_code == 200
    downloaded = client.get(version["download_url"])
    assert downloaded.status_code == 200 and b"".join(downloaded.streaming_content) == PNG
    assert upload(client, document["id"]).status_code == 403
    actor.role_assignments.filter(role__permissions__permission_code="documents.view").update(is_active=False)
    detail = client.get(f"/api/v1/letters/{letter['id']}/").json()
    assert detail["attachments"][0]["document"] == {"id": document["id"], "restricted": True}
    assert client.get(version["preview_url"]).status_code == 403


def test_linked_participant_can_read_not_mutate_shared_letter_and_loses_access_on_transfer(employee_factory, grant):
    client, actor, work, clerk, head, department, specialty = production_setup(employee_factory, grant)
    grant(actor, "letters.view", "own"); grant(actor, "letters.draft", "own")
    for action in ("letters.view", "letters.draft"): grant(head, action)
    response = create_letter(clerk, expertise_ids=[work["id"]], department_id=str(department.pk))
    assert response.status_code == 201
    letter = response.json()["letter"]; path = f"/api/v1/letters/{letter['id']}/"
    assert client.get(path).status_code == 200
    assert save_draft(client, letter).status_code == 403
    related = client.get(f"/api/v1/expertises/{work['id']}/letters/")
    assert related.status_code == 200 and related.json()["count"] == 1
    assert assign(clerk, work, [qualified(employee_factory, specialty)], reassign=True).status_code == 200
    assert client.get(path).status_code == 403


def test_mixed_wide_view_cannot_link_foreign_work_or_choose_arbitrary_department(employee_factory, grant):
    client, actor, work, clerk, head, department, specialty = production_setup(employee_factory, grant)
    grant(actor, "letters.view"); grant(actor, "letters.draft", "own")
    foreign = Department.objects.create(code="foreign", name="Другой отдел")
    assert create_letter(client, department_id=str(foreign.pk)).status_code == 403
    from apps.intake.models import Receipt
    receipt = Receipt.objects.get(pk=work["receipt"]["id"])
    sibling = register(clerk, {"id": str(receipt.pk)}, {"expected_version": receipt.version, "registration_number": "152/3-1-26", "department_id": str(department.pk), "specialty_id": str(specialty.pk), "appointment_nature": "primary", "is_commission": False})
    assert sibling.status_code == 201
    grant(actor, "expertise.view")
    assert create_letter(client, expertise_ids=[work["id"], sibling.json()["id"]]).status_code == 403
    for action in ("letters.view", "letters.draft"): grant(head, action)
    shared = create_letter(clerk, expertise_ids=[work["id"], sibling.json()["id"]])
    assert shared.status_code == 201
    actor.role_assignments.filter(role__permissions__permission_code="expertise.view", role__permissions__scope="institution").update(is_active=False)
    detail = client.get(f"/api/v1/letters/{shared.json()['letter']['id']}/").json()
    assert [w["id"] for w in detail["content"]["expertises"]] == [work["id"]]
    assert client.get("/api/v1/letters/", {"expertise_id": sibling.json()["id"]}).json()["count"] == 0


def test_material_links_and_options_require_a_visible_receipt_or_work(employee_factory, grant):
    client, actor, work, _, _, _, _ = production_setup(employee_factory, grant)
    for action in ("letters.view", "letters.draft"): grant(actor, action, "own")
    from apps.intake.models import Material
    private = Material.objects.create(title="Скрытый материал", created_by=employee_factory())
    assert create_letter(client, material_id=str(private.pk)).status_code == 403
    allowed = create_letter(client, material_id=work["material"]["id"], expertise_ids=[work["id"]])
    assert allowed.status_code == 201
    result = client.get("/api/v1/letters/material-options/")
    assert result.status_code == 200
    assert [m["id"] for m in result.json()["results"]] == [work["material"]["id"]]
    assert client.get("/api/v1/letters/work-options/").json()["results"][0]["id"] == work["id"]
    actor.role_assignments.filter(role__permissions__permission_code="expertise.view").update(is_active=False)
    detail = client.get(f"/api/v1/letters/{allowed.json()['letter']['id']}/").json()
    assert detail["content"]["material"] is None and detail["content"]["expertises"] == []


@pytest.mark.parametrize("hide_links", [True, False])
def test_draft_roundtrip_preserves_hidden_links_but_can_remove_visible_links(employee_factory, grant, hide_links):
    from apps.correspondence.models import Letter
    client, actor, work, _, _, _, _ = production_setup(employee_factory, grant)
    for action in ("letters.view", "letters.draft"): grant(actor, action, "own")
    created = create_letter(client, material_id=work["material"]["id"], expertise_ids=[work["id"]])
    assert created.status_code == 201
    letter = created.json()["letter"]
    if hide_links:
        actor.role_assignments.filter(role__permissions__permission_code="expertise.view").update(is_active=False)
    projected = client.get(f"/api/v1/letters/{letter['id']}/").json()
    if hide_links:
        assert projected["content"]["material"] is None and projected["content"]["expertises"] == []
    saved = save_draft(client, projected, subject="Изменена только тема", material_id=None, expertise_ids=[])
    assert saved.status_code == 200
    revision = Letter.objects.get(pk=letter["id"]).current_revision
    assert (str(revision.material_id) if revision.material_id else None) == (work["material"]["id"] if hide_links else None)
    assert list(map(str, revision.expertises.values_list("pk", flat=True))) == ([work["id"]] if hide_links else [])
    assert saved.json()["letter"]["content"]["material"] is None
    assert saved.json()["letter"]["content"]["expertises"] == []


def test_draft_cannot_replace_an_inaccessible_existing_material(employee_factory, grant):
    from datetime import date
    from apps.correspondence.models import Letter
    from apps.intake.models import Material, Receipt
    client, actor, work, _, _, _, _ = production_setup(employee_factory, grant)
    for action in ("letters.view", "letters.draft", "receipts.view"): grant(actor, action, "own")
    created = create_letter(client, material_id=work["material"]["id"])
    assert created.status_code == 201
    letter = created.json()["letter"]
    actor.role_assignments.filter(role__permissions__permission_code="expertise.view").update(is_active=False)
    other = Material.objects.create(title="Другой доступный материал", created_by=actor)
    Receipt.objects.create(material=other, received_at=date(2026, 10, 1), created_by=actor)
    response = save_draft(client, letter, material_id=str(other.pk))
    assert response.status_code == 403
    current = Letter.objects.get(pk=letter["id"])
    assert current.version == 1 and current.revisions.count() == 1
    assert str(current.current_revision.material_id) == work["material"]["id"]


def test_department_mutation_scope_is_independent_of_institution_view(employee_factory, grant):
    department = Department.objects.create(code="3", name="Отдел 3")
    other_department = Department.objects.create(code="4", name="Отдел 4")
    owner, _ = letter_setup(employee_factory, grant, department=department)
    created = create_letter(owner, department_id=str(department.pk)); assert created.status_code == 201
    actor = employee_factory(department=other_department); client = Client(); client.force_login(actor.user)
    grant(actor, "letters.view"); grant(actor, "letters.draft", "departments", departments=[other_department])
    letter = created.json()["letter"]
    assert client.get(f"/api/v1/letters/{letter['id']}/").status_code == 200
    assert save_draft(client, letter).status_code == 403
