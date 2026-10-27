import pytest
from django.test import Client
from apps.accounts.models import Role
from apps.personnel.models import EmployeeOrgAssignment, EmployeeRole
from apps.references.models import Department, Position

pytestmark = pytest.mark.django_db


def client_for(employee):
    client = Client()
    client.force_login(employee.user)
    return client


def test_org_assignment_is_explicit_multiple_and_dates_versioned(employee_factory,grant):
    actor = employee_factory()
    target = employee_factory()
    grant(actor,"employees.org_assignments.manage")
    d3 = Department.objects.create(code="3",name="Отдел 3")
    d4 = Department.objects.create(code="4",name="Отдел 4")
    position = Position.objects.create(code="head",name="Начальник отдела")
    client = client_for(actor)
    url = f"/api/v1/employees/{target.id}/org-assignments/"
    first = client.post(url,{"department_id":str(d3.id),"position_id":str(position.id),"valid_from":"2026-10-01","reason":"Приказ"},content_type="application/json")
    assert first.status_code == 201
    assert client.post(url,{"department_id":str(d4.id),"position_id":str(position.id),"reason":"Совмещение"},content_type="application/json").status_code == 201
    end = f"/api/v1/employee-org-assignments/{first.json()['id']}/"
    assert client.patch(end,{"expected_version":1,"valid_to":"2026-10-20","reason":"Перевод"},content_type="application/json").status_code == 200
    assert client.patch(end,{"expected_version":1,"valid_to":"2026-10-21","reason":"Старый редактор"},content_type="application/json").status_code == 409
    assert EmployeeOrgAssignment.objects.filter(employee=target).count() == 2
    assert not target.role_assignments.exists()


def test_individual_role_revocation_applies_next_request_and_preserves_history(employee_factory,grant):
    actor = employee_factory()
    grant(actor,"access.roles.assign")
    target = employee_factory()
    _, assignment = grant(target,"employees.view")
    target_client = client_for(target)
    assert target_client.get("/api/v1/employees/").status_code == 200
    url = f"/api/v1/employee-roles/{assignment.id}/"
    response = client_for(actor).patch(url,{"expected_version":1,"is_active":False,"reason":"Прекращение полномочий"},content_type="application/json")
    assert response.status_code == 200
    assert target_client.get("/api/v1/employees/").status_code == 403
    assert EmployeeRole.objects.filter(pk=assignment.id,is_active=False).exists()
    assert client_for(actor).patch(url,{"expected_version":1,"is_active":False,"reason":"Устарело"},content_type="application/json").status_code == 409


def test_personal_login_is_created_for_existing_employee_without_granting_roles(employee_factory,grant,django_user_model):
    from apps.personnel.models import Employee
    actor = employee_factory()
    grant(actor,"users.create")
    grant(actor,"users.view")
    grant(actor,"users.deactivate")
    target = Employee.objects.create(full_name="Новый эксперт")
    client = client_for(actor)
    url = f"/api/v1/employees/{target.id}/account/"
    response = client.post(url,{"username":"new-expert","password":"Unique-personal-test-password9"},content_type="application/json")
    assert response.status_code == 201
    assert "password" not in response.json()
    target.refresh_from_db()
    assert target.user.check_password("Unique-personal-test-password9")
    assert not target.user.is_superuser
    assert not target.role_assignments.exists()
    assert client.post(url,{"username":"other","password":"Unique-personal-test-password9"},content_type="application/json").status_code == 400
    assert client.patch(url,{"is_active":False,"reason":"Блокировка входа"},content_type="application/json").status_code == 200
    assert not django_user_model.objects.get(pk=target.user_id).is_active


def test_dept_edit_right_does_not_spread_from_institution_view(employee_factory,grant):
    d3 = Department.objects.create(code="3",name="Отдел 3")
    d4 = Department.objects.create(code="4",name="Отдел 4")
    actor = employee_factory(department=d3)
    target = employee_factory(department=d4)
    grant(actor,"employees.view","institution")
    grant(actor,"employees.update","departments",departments=[d3])
    response = client_for(actor).patch(f"/api/v1/employees/{target.id}/",{"expected_version":1,"full_name":"Чужой отдел"},content_type="application/json")
    assert response.status_code == 403
    target.refresh_from_db()
    assert target.full_name != "Чужой отдел"
