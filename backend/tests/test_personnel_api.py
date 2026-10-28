from datetime import timedelta
import pytest
from django.test import Client
from django.utils import timezone
from apps.accounts.models import Role
from apps.personnel.models import Employee, EmployeeOrgAssignment, EmployeeRole, EmployeeSpecialty
from apps.references.models import Department, Position, Specialty

pytestmark = pytest.mark.django_db


def client_for(employee):
    client = Client()
    client.force_login(employee.user)
    return client


def test_employee_list_scopes_current_departments_before_pagination(employee_factory, grant):
    d3 = Department.objects.create(code="3",name="Отдел 3")
    d4 = Department.objects.create(code="4",name="Отдел 4")
    head = employee_factory(department=d3)
    own = employee_factory(department=d3)
    foreign = employee_factory(department=d4)
    EmployeeOrgAssignment.objects.create(employee=foreign,department=d3,position=Position.objects.first(),valid_to=timezone.localdate()-timedelta(days=1))
    grant(head,"employees.view","departments",departments=[d3])
    response = client_for(head).get("/api/v1/employees/")
    assert response.status_code == 200
    assert response.json()["count"] == 2
    assert {row["id"] for row in response.json()["results"]} == {str(head.id),str(own.id)}
    assert client_for(head).get(f"/api/v1/employees/{foreign.id}/").status_code == 403


def test_employee_two_specialties_is_one_row_and_qualify_requires_separate_right(employee_factory, grant):
    actor = employee_factory()
    target = employee_factory()
    grant(actor,"employees.view")
    grant(actor,"specialties.training.manage")
    client = client_for(actor)
    for code in ["18.1","13.1"]:
        specialty = Specialty.objects.create(code=code,name=f"Специальность {code}")
        response = client.post(f"/api/v1/employees/{target.id}/specialties/", {"specialty_id":str(specialty.id),"status":"training"},content_type="application/json")
        assert response.status_code == 201
    rows = client.get("/api/v1/employees/").json()["results"]
    assert len([row for row in rows if row["id"] == str(target.id)]) == 1
    item = EmployeeSpecialty.objects.get(employee=target,specialty__code="18.1")
    url = f"/api/v1/employee-specialties/{item.id}/qualify/"
    payload = {"expected_version":1,"qualified_at":"2026-10-01","basis":"Подтверждение владельца"}
    assert client.post(url,payload,content_type="application/json").status_code == 403
    grant(actor,"specialties.qualify")
    assert client.post(url,payload,content_type="application/json").status_code == 200
    item.refresh_from_db()
    assert item.status == "qualified"
    assert item.version == 2
    assert client.post(url,payload,content_type="application/json").status_code == 409
    assert EmployeeSpecialty.objects.get(employee=target,specialty__code="13.1").status == "training"


def test_training_form_cannot_directly_claim_qualification_or_duplicate(employee_factory, grant):
    actor = employee_factory()
    grant(actor,"specialties.training.manage")
    spec = Specialty.objects.create(code="18.1",name="Транспорт")
    url = f"/api/v1/employees/{actor.id}/specialties/"
    client = client_for(actor)
    assert client.post(url,{"specialty_id":str(spec.id),"status":"qualified"},content_type="application/json").status_code == 403
    payload = {"specialty_id":str(spec.id),"status":"training"}
    assert client.post(url,payload,content_type="application/json").status_code == 201
    assert client.post(url,payload,content_type="application/json").status_code == 400
    assert EmployeeSpecialty.objects.count() == 1


def test_authorized_confirmation_allows_unknown_qualification_date_with_basis(employee_factory,grant):
    from datetime import date
    from apps.personnel.services import qualification_eligibility
    actor = employee_factory()
    target = employee_factory()
    grant(actor,"specialties.qualify")
    specialty = Specialty.objects.create(code="18.1",name="Транспорт")
    item = EmployeeSpecialty.objects.create(employee=target,specialty=specialty,status="unknown_legacy")
    url = f"/api/v1/employee-specialties/{item.id}/qualify/"
    response = client_for(actor).post(url,{"expected_version":1,"qualified_at":None,"basis":"Получение подтверждено ответственным; дата неизвестна"},content_type="application/json")
    assert response.status_code == 200
    item.refresh_from_db()
    assert item.qualified_at is None and item.status == "qualified"
    assert qualification_eligibility(target,specialty,date(2026,10,28))["eligible"] is True


def test_unknown_date_obtained_status_does_not_require_basis(employee_factory,grant):
    actor = employee_factory()
    grant(actor,"specialties.qualify")
    specialty = Specialty.objects.create(code="18.1",name="Транспорт")
    item = EmployeeSpecialty.objects.create(employee=actor,specialty=specialty,status="training")
    response = client_for(actor).post(f"/api/v1/employee-specialties/{item.id}/qualify/",{"expected_version":1,"qualified_at":None,"basis":""},content_type="application/json")
    assert response.status_code == 200
    item.refresh_from_db()
    assert item.status == "qualified"


def test_employee_updates_cannot_self_assign_roles_or_deactivate_without_right(employee_factory, grant):
    actor = employee_factory()
    grant(actor,"employees.update")
    url = f"/api/v1/employees/{actor.id}/"
    client = client_for(actor)
    assert client.patch(url,{"expected_version":1,"full_name":"Исправлено","roles":["admin"]},content_type="application/json").status_code == 400
    assert client.patch(url,{"expected_version":1,"is_active":False},content_type="application/json").status_code == 403
    assert client.patch(url,{"expected_version":1,"full_name":"Исправлено"},content_type="application/json").status_code == 200
    assert client.patch(url,{"expected_version":1,"full_name":"Устарело"},content_type="application/json").status_code == 409
    grant(actor,"employees.deactivate")
    assert client.patch(url,{"expected_version":2,"is_active":False},content_type="application/json").status_code == 200
    actor.refresh_from_db()
    assert not actor.is_active
    assert actor.full_name == "Исправлено"


def test_role_assignment_is_explicit_scoped_and_audited(employee_factory, grant):
    actor = employee_factory()
    target = employee_factory()
    grant(actor,"access.roles.assign")
    role = Role.objects.create(name="Руководитель")
    department = Department.objects.create(code="3",name="Отдел 3")
    client = client_for(actor)
    url = f"/api/v1/employees/{target.id}/roles/"
    payload = {"role_id":str(role.id),"scope_limit":"departments","department_ids":[],"reason":"Назначение"}
    assert client.post(url,payload,content_type="application/json").status_code == 400
    payload["department_ids"] = [str(department.id)]
    assert client.post(url,payload,content_type="application/json").status_code == 201
    rows = client.get(url).json()
    assert len(rows) == 1 and rows[0]["department_ids"] == [str(department.id)]
    assert EmployeeRole.objects.get(employee=target).role_id == role.id


def test_reference_extension_is_versioned_and_deactivation_not_deletion(employee_factory, grant):
    actor = employee_factory()
    grant(actor,"references.manage")
    client = client_for(actor)
    response = client.post("/api/v1/references/specialties/",{"code":"99.1","name":"Новая специальность"},content_type="application/json")
    assert response.status_code == 201
    item_id = response.json()["id"]
    url = f"/api/v1/references/specialties/{item_id}/"
    assert client.patch(url,{"expected_version":1,"is_active":False},content_type="application/json").status_code == 200
    assert not Specialty.objects.get(id=item_id).is_active
    assert client.delete(url).status_code == 405


def test_department_training_right_can_read_options_without_global_reference_right(employee_factory,grant):
    department = Department.objects.create(code="3",name="Отдел 3")
    actor = employee_factory(department=department)
    grant(actor,"specialties.training.manage","departments",departments=[department])
    Specialty.objects.create(code="18.1",name="Транспорт")
    client = client_for(actor)
    assert client.get("/api/v1/references/specialties/").status_code == 200
    assert client.get("/api/v1/references/positions/").status_code == 403
    assert client.post("/api/v1/references/specialties/",{"code":"99.1","name":"Нет"},content_type="application/json").status_code == 403


def test_qualification_validates_retained_expiry_before_database_write(employee_factory,grant):
    from datetime import date
    actor = employee_factory()
    grant(actor,"specialties.qualify")
    specialty = Specialty.objects.create(code="18.1",name="Транспорт")
    item = EmployeeSpecialty.objects.create(employee=actor,specialty=specialty,status="training",valid_until=date(2026,9,30))
    url = f"/api/v1/employee-specialties/{item.id}/qualify/"
    client = client_for(actor)
    response = client.post(url,{"expected_version":1,"qualified_at":"2026-10-01","basis":"Подтверждение"},content_type="application/json")
    assert response.status_code == 400
    assert "valid_until" in response.json()["field_errors"]
    item.refresh_from_db()
    assert item.version == 1 and item.status == "training"
    response = client.post(url,{"expected_version":1,"qualified_at":"2026-10-01","valid_until":None,"basis":"Подтверждение без ограничения срока"},content_type="application/json")
    assert response.status_code == 200
    item.refresh_from_db()
    assert item.valid_until is None
