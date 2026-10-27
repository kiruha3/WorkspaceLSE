import pytest
from django.test import Client
from apps.references.models import Department
from apps.intake.models import Receipt
from test_registration import register
from test_expert_assignments import assignment_setup, qualified, assign

pytestmark=pytest.mark.django_db


def test_institution_view_does_not_expand_department_assign(employee_factory,grant):
    client,_,work,department,specialty=assignment_setup(employee_factory,grant)
    outsider=employee_factory();grant(outsider,"expertise.view")
    other_department=Department.objects.create(code="4",name="Отдел 4")
    grant(outsider,"expertise.assign","departments",departments=[other_department])
    other=Client();other.force_login(outsider.user)
    assert other.get(f"/api/v1/expertises/{work['id']}/").json()["allowed_actions"]==[]
    employee=qualified(employee_factory,specialty)
    assert assign(other,work,[employee]).status_code==403
    assert other.get(f"/api/v1/expertises/{work['id']}/assignment-candidates/").status_code==403


def test_shared_material_does_not_expand_other_work_mutation(employee_factory,grant):
    client,_,work,department,specialty=assignment_setup(employee_factory,grant)
    department4=Department.objects.create(code="4",name="Отдел 4")
    receipt=Receipt.objects.get(pk=work["receipt"]["id"])
    second=register(client,{"id":str(receipt.id)},{"expected_version":2,"registration_number":"152/4-1-26","department_id":str(department4.id),"specialty_id":str(specialty.id),"appointment_nature":"primary","is_commission":False}).json()
    employee=qualified(employee_factory,specialty)
    outsider=employee_factory();grant(outsider,"expertise.view","departments",departments=[department])
    grant(outsider,"expertise.assign","departments",departments=[department])
    other=Client();other.force_login(outsider.user)
    assert other.get("/api/v1/expertises/").json()["count"]==1
    assert other.get(f"/api/v1/expertises/{second['id']}/").status_code==403
    assert assign(other,second,[employee]).status_code==403


def test_assigned_expert_can_read_basis_only_with_document_view(employee_factory,grant):
    client,_,work,_,specialty=assignment_setup(employee_factory,grant)
    employee=qualified(employee_factory,specialty);grant(employee,"expertise.view","own")
    assigned=assign(client,work,[employee])
    assert assigned.status_code==200
    other=Client();other.force_login(employee.user)
    detail=other.get(f"/api/v1/expertises/{work['id']}/").json()
    assert detail["basis_document"]["restricted"] is True
    grant(employee,"documents.view","own")
    detail=other.get(f"/api/v1/expertises/{work['id']}/").json()
    assert detail["basis_document"]["kind"]=="decision"
    assert other.get(f"/api/v1/documents/{detail['basis_document']['id']}/").status_code==200
    assert other.get(f"/api/v1/receipts/{work['receipt']['id']}/").status_code==403


def test_empty_department_grant_denies_assignment(employee_factory,grant):
    client,head,work,_,specialty=assignment_setup(employee_factory,grant)
    for assignment in head.role_assignments.filter(role__permissions__permission_code="expertise.assign"):
        assignment.departments.clear()
    employee=qualified(employee_factory,specialty)
    assert assign(client,work,[employee]).status_code==403
