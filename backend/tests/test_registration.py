import uuid
import pytest
from django.test import Client
from apps.references.models import Department, Specialty
from apps.audit.models import AuditEvent
from test_receipts import clerk_client, create_basis

pytestmark = pytest.mark.django_db


def registration_setup(employee_factory, grant):
    client, employee = clerk_client(employee_factory, grant)
    for action in ("expertise.register", "expertise.view"):
        grant(employee, action)
    department = Department.objects.create(code="3", name="Отдел 3")
    specialty = Specialty.objects.create(code="1.1", name="Почерковедческая")
    basis = create_basis(client)
    receipt = client.post("/api/v1/receipts/", {"received_at":"2026-10-28", "basis_document_id":basis["id"]}, content_type="application/json").json()
    receipt = client.post(f"/api/v1/receipts/{receipt['id']}/register/", {"expected_version":1}, content_type="application/json").json()
    data = {"expected_version":2, "registration_number":"151/3-1-26", "department_id":str(department.id), "specialty_id":str(specialty.id), "appointment_nature":"primary", "is_commission":False}
    return client, employee, receipt, department, specialty, data


def register(client, receipt, data, key=None):
    return client.post(f"/api/v1/receipts/{receipt['id']}/expertises/", data, content_type="application/json", HTTP_IDEMPOTENCY_KEY=key or str(uuid.uuid4()))


def test_manual_number_creates_unassigned_work_with_original_basis(employee_factory, grant):
    client, _, receipt, _, _, data = registration_setup(employee_factory, grant)
    response = register(client, receipt, data)
    assert response.status_code == 201
    work = response.json()
    assert work["category_code"] == "1" and work["year"] == 2026
    assert work["registration_number"] == "151/3-1-26"
    assert work["state"] == "in_progress" and work["current_assignments"] == []
    assert work["basis_document"]["id"] == receipt["basis_document"]["id"]
    assert client.get(f"/api/v1/expertises/{work['id']}/").json()["id"] == work["id"]


def test_number_151_1_1_26_category_criminal():
    from apps.expertises.numbering import parse_current_number
    parsed = parse_current_number("151/1-1-26")
    assert (parsed.sequence, parsed.department_code, parsed.category_code, parsed.year, parsed.normalized) == (151,"1","1",2026,"151/1-1-26")


def test_parenthesized_historical_number_is_not_current_category(employee_factory, grant):
    client, _, receipt, _, _, data = registration_setup(employee_factory, grant)
    data.update(registration_number="151/3-5-26", historical_number="22/10-1-25")
    response = register(client, receipt, data)
    assert response.status_code == 201 and response.json()["category_code"] == "5"
    data["registration_number"] = "152/3-5-26 (22/10-1-25)"
    assert register(client, receipt, data).status_code == 400


def test_retry_returns_same_registration(employee_factory, grant):
    client, _, receipt, _, _, data = registration_setup(employee_factory, grant)
    key = str(uuid.uuid4())
    first = register(client, receipt, data, key)
    second = register(client, receipt, data, key)
    assert first.status_code == second.status_code == 201
    assert first.json() == second.json()
    assert AuditEvent.objects.filter(action="expertise.register").count() == 1


def test_same_key_different_payload_conflicts(employee_factory, grant):
    client, _, receipt, _, _, data = registration_setup(employee_factory, grant)
    key = str(uuid.uuid4())
    assert register(client, receipt, data, key).status_code == 201
    data["registration_number"] = "152/3-1-26"
    assert register(client, receipt, data, key).status_code == 409


def test_replay_rechecks_revoked_authority(employee_factory, grant):
    client, employee, receipt, _, _, data = registration_setup(employee_factory, grant)
    key = str(uuid.uuid4())
    assert register(client, receipt, data, key).status_code == 201
    employee.role_assignments.filter(role__permissions__permission_code="expertise.register").update(is_active=False)
    assert register(client, receipt, data, key).status_code == 403


def test_failed_command_can_be_retried_after_receipt_is_accepted(employee_factory, grant):
    client, _, receipt, _, _, data = registration_setup(employee_factory, grant)
    from apps.intake.models import Receipt
    Receipt.objects.filter(pk=receipt["id"]).update(status="draft")
    key = str(uuid.uuid4())
    assert register(client, receipt, data, key).status_code == 400
    Receipt.objects.filter(pk=receipt["id"]).update(status="accepted")
    assert register(client, receipt, data, key).status_code == 201


def test_registration_department_number_and_version_are_checked(employee_factory, grant):
    client, _, receipt, _, _, data = registration_setup(employee_factory, grant)
    data["registration_number"] = "151/4-1-26"
    assert register(client, receipt, data).status_code == 400
    data["registration_number"] = "151/3-1-26"; data["expected_version"] = 1
    assert register(client, receipt, data).status_code == 409
    data["expected_version"] = 2
    assert client.post(f"/api/v1/receipts/{receipt['id']}/expertises/", data, content_type="application/json").status_code == 400


def test_complex_two_specialties_two_numbers_not_per_person(employee_factory, grant):
    client, _, receipt, _, _, data = registration_setup(employee_factory, grant)
    group = client.post("/api/v1/complex-groups/", {"receipt_id":receipt["id"], "title":"Комплексная работа"}, content_type="application/json")
    assert group.status_code == 201
    data["complex_group_id"] = group.json()["id"]
    assert register(client, receipt, data).status_code == 201
    data["registration_number"] = "152/3-1-26"
    assert register(client, receipt, data).status_code == 409
    other = Specialty.objects.create(code="3.1", name="Трасологическая")
    data["specialty_id"] = str(other.id)
    assert register(client, receipt, data).status_code == 201
    assert client.get("/api/v1/expertises/").json()["count"] == 2
    assert client.get(f"/api/v1/complex-groups/?receipt_id={receipt['id']}").json()["count"] == 1


@pytest.mark.parametrize("title", [None, "", "   "])
def test_complex_group_requires_a_name(employee_factory, grant, title):
    from apps.expertises.models import ComplexGroup
    client, _, receipt, _, _, _ = registration_setup(employee_factory, grant)
    payload={"receipt_id":receipt["id"]}
    if title is not None:payload["title"]=title
    response=client.post("/api/v1/complex-groups/",payload,content_type="application/json")
    assert response.status_code == 400
    assert ComplexGroup.objects.count() == 0


def test_complex_group_retries_and_repeated_clicks_return_one_named_group(employee_factory, grant):
    from apps.expertises.models import ComplexGroup
    client, _, receipt, _, _, _ = registration_setup(employee_factory, grant)
    payload={"receipt_id":receipt["id"],"title":"Исследование по делу № 12"}
    key=str(uuid.uuid4())
    first=client.post("/api/v1/complex-groups/",payload,content_type="application/json",HTTP_IDEMPOTENCY_KEY=key)
    assert first.status_code == 201
    for request_key in (key,str(uuid.uuid4()),None):
        headers={"HTTP_IDEMPOTENCY_KEY":request_key} if request_key else {}
        response=client.post("/api/v1/complex-groups/",payload,content_type="application/json",**headers)
        assert response.status_code in (200,201)
        assert response.json()["id"] == first.json()["id"]
    assert ComplexGroup.objects.count() == 1
    assert AuditEvent.objects.filter(action="complex_group.create").count() == 1
    changed=client.post("/api/v1/complex-groups/",{**payload,"title":"Другое исследование"},content_type="application/json",HTTP_IDEMPOTENCY_KEY=key)
    assert changed.status_code == 409
    assert ComplexGroup.objects.count() == 1


def test_hint_is_only_last_number_and_does_not_reserve(employee_factory, grant):
    client, _, receipt, department, _, data = registration_setup(employee_factory, grant)
    assert register(client, receipt, data).status_code == 201
    url = f"/api/v1/expertises/number-hint/?department_id={department.id}&year=2026"
    assert client.get(url).json() == {"last_number":"151/3-1-26","next_sequence":152}
    assert client.get(url).json() == {"last_number":"151/3-1-26","next_sequence":152}
    assert client.get("/api/v1/expertises/").json()["count"] == 1


def test_hint_uses_institution_year_maximum_across_departments_and_categories(employee_factory, grant):
    from apps.expertises.models import Expertise
    from apps.intake.models import Material
    client, employee, receipt, department, _, data = registration_setup(employee_factory, grant)
    assert register(client, receipt, data).status_code == 201
    other = Department.objects.create(code="4", name="Отдел 4")
    for number in ("482/4-6-26", "999/4-1-25", "900001/4-1-26"):
        response = register(client, receipt, {**data, "department_id":str(other.id), "registration_number":number})
        assert response.status_code == 201
        if number.startswith("900001/"):
            demo_material=Material.objects.create(title="Учебный материал",is_demo=True,created_by=employee)
            Expertise.objects.filter(pk=response.json()["id"]).update(material=demo_material)
    # Insertion order must not override the greatest sequence for this year.
    assert register(client, receipt, {**data,"registration_number":"2/3-2-26"}).status_code == 201
    for selected in (department, other):
        response=client.get(f"/api/v1/expertises/number-hint/?department_id={selected.id}&year=2026")
        assert response.status_code == 200
        assert response.json() == {"last_number":"482/4-6-26","next_sequence":483}


def test_empty_year_hint_starts_at_one_and_preserves_department_permission(employee_factory, grant):
    client, _, _, department, _, _ = registration_setup(employee_factory, grant)
    reader=employee_factory()
    grant(reader,"expertise.register","departments",departments=[department])
    scoped=Client();scoped.force_login(reader.user)
    url=f"/api/v1/expertises/number-hint/?department_id={department.id}&year=2027"
    assert scoped.get(url).json() == {"last_number":None,"next_sequence":1}
    other=Department.objects.create(code="4",name="Отдел 4")
    assert scoped.get(f"/api/v1/expertises/number-hint/?department_id={other.id}&year=2027").status_code == 403


def test_scopes_filter_before_pagination_and_do_not_broaden_registration(employee_factory, grant):
    client, _, receipt, department, _, data = registration_setup(employee_factory, grant)
    work = register(client, receipt, data)
    assert work.status_code == 201
    outsider = employee_factory(); grant(outsider, "expertise.view", "own")
    other = Client(); other.force_login(outsider.user)
    assert other.get("/api/v1/expertises/").json()["count"] == 0
    assert other.get(f"/api/v1/expertises/{work.json()['id']}/").status_code == 403
    assert other.get("/api/v1/references/departments/").status_code == 200
    assert other.get("/api/v1/references/specialties/").status_code == 200
    grant(outsider,"expertise.register","departments",departments=[department])
    assert other.get("/api/v1/references/departments/").status_code == 200
    assert other.get("/api/v1/references/specialties/").status_code == 200
    denied = Department.objects.create(code="4",name="Отдел 4")
    data.update(department_id=str(denied.id), registration_number="152/4-1-26")
    assert register(other, receipt, data).status_code == 403


@pytest.mark.parametrize("query", ["department_id=no", "received_from=no", "received_from=2026-10-29&received_to=2026-10-28", "employee_id=no"])
def test_invalid_work_filters_are_controlled(employee_factory, grant, query):
    client, _, _, _, _, _ = registration_setup(employee_factory, grant)
    assert client.get("/api/v1/expertises/?" + query).status_code == 400


def test_replay_redacts_document_after_granular_revocation(employee_factory,grant):
    client,employee,receipt,_,_,data=registration_setup(employee_factory,grant)
    key=str(uuid.uuid4());first=register(client,receipt,data,key)
    assert first.status_code==201 and first.json()["basis_document"]["title"]
    employee.role_assignments.filter(role__permissions__permission_code="documents.view").update(is_active=False)
    replay=register(client,receipt,data,key)
    assert replay.status_code==201
    assert replay.json()["basis_document"]=={"id":receipt["basis_document"]["id"],"restricted":True}


def test_replay_recomputes_actions_without_changing_business_result(employee_factory,grant):
    client,employee,receipt,_,_,data=registration_setup(employee_factory,grant)
    _,assignment=grant(employee,"expertise.assign")
    key=str(uuid.uuid4());first=register(client,receipt,data,key)
    assert first.json()["allowed_actions"]==["expertise.assign"]
    assignment.is_active=False;assignment.save()
    replay=register(client,receipt,data,key)
    assert replay.json()["id"]==first.json()["id"] and replay.json()["version"]==1
    assert replay.json()["allowed_actions"]==[]


def test_replay_survives_reference_deactivation_but_new_work_does_not(employee_factory,grant):
    client,_,receipt,_,specialty,data=registration_setup(employee_factory,grant)
    key=str(uuid.uuid4());first=register(client,receipt,data,key)
    assert first.status_code==201
    specialty.is_active=False;specialty.save()
    replay=register(client,receipt,data,key)
    assert replay.status_code==201 and replay.json()["id"]==first.json()["id"]
    data["registration_number"]="152/3-1-26"
    assert register(client,receipt,data).status_code==400
