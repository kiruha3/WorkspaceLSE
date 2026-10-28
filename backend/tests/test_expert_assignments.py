from datetime import date
import pytest
from django.test import Client
from apps.personnel.models import EmployeeSpecialty
from apps.references.models import Specialty
from test_registration import registration_setup, register

pytestmark = pytest.mark.django_db


def assignment_setup(employee_factory, grant, *, commission=False):
    client, head, receipt, department, specialty, data = registration_setup(employee_factory,grant)
    data["is_commission"] = commission
    for action in ("expertise.assign","expertise.reassign"):grant(head,action,"departments",departments=[department])
    response = register(client,receipt,data)
    assert response.status_code == 201
    return client,head,response.json(),department,specialty


def qualified(employee_factory, specialty, *, department=None, status="qualified", qualified_at=None, valid_until=None):
    employee = employee_factory(department=department)
    EmployeeSpecialty.objects.create(employee=employee,specialty=specialty,status=status,qualified_at=qualified_at,valid_until=valid_until,basis="Подтверждено ответственным, архивное свидетельство")
    return employee


def assign(client,work,employees,*,reassign=False,version=None):
    return client.post(f"/api/v1/expertises/{work['id']}/{'reassign' if reassign else 'assignments'}/",{"expected_version":version or work["version"],"employee_ids":[str(e.id) for e in employees],"reason":"Назначение состава исполнителей"},content_type="application/json")


def test_training_13_1_does_not_block_qualified_18_1(employee_factory,grant):
    client,_,work,_,specialty=assignment_setup(employee_factory,grant)
    employee=qualified(employee_factory,specialty)
    other=Specialty.objects.create(code="13.1",name="ДТП")
    EmployeeSpecialty.objects.create(employee=employee,specialty=other,status="training")
    response=assign(client,work,[employee])
    assert response.status_code==200
    assert response.json()["current_assignments"][0]["employee"]["id"]==str(employee.id)


def test_head_role_does_not_override_training(employee_factory,grant):
    client,head,work,department,specialty=assignment_setup(employee_factory,grant)
    EmployeeSpecialty.objects.create(employee=head,specialty=specialty,status="training")
    candidates=client.get(f"/api/v1/expertises/{work['id']}/assignment-candidates/")
    assert candidates.status_code==200
    candidate=next(c for c in candidates.json() if c["id"]==str(head.id))
    assert candidate["eligible"] is False and candidate["code"]=="specialty_training"
    assert assign(client,work,[head]).status_code==400


def test_unknown_date_confirmed_basis_allowed(employee_factory,grant):
    client,head,work,_,specialty=assignment_setup(employee_factory,grant)
    item=EmployeeSpecialty.objects.create(employee=head,specialty=specialty,status="qualified",basis="Явно подтверждённая квалификация")
    assert assign(client,work,[head]).status_code==200
    from apps.expertises.models import ExpertAssignment
    snapshot=ExpertAssignment.objects.get(employee=head).qualification_snapshot
    assert snapshot["qualified_at"] is None and snapshot["basis"]==item.basis
    item.basis="Позднее изменение";item.save()
    assert ExpertAssignment.objects.get(employee=head).qualification_snapshot==snapshot


@pytest.mark.parametrize("change",["inactive","training","unconfirmed"])
def test_inactive_or_unqualified_candidate_rechecked(employee_factory,grant,change):
    client,_,work,_,specialty=assignment_setup(employee_factory,grant)
    employee=qualified(employee_factory,specialty)
    assert next(c for c in client.get(f"/api/v1/expertises/{work['id']}/assignment-candidates/").json() if c["id"]==str(employee.id))["eligible"]
    if change=="inactive":employee.is_active=False;employee.save()
    else:
        item=employee.specialties.get()
        if change=="training":item.status="training"
        else:item.status="unknown_legacy"
        item.save()
    assert assign(client,work,[employee]).status_code==400
    from apps.expertises.models import ExpertAssignment
    assert ExpertAssignment.objects.count()==0


def test_commission_one_number_two_qualified_participants(employee_factory,grant):
    client,_,work,_,specialty=assignment_setup(employee_factory,grant,commission=True)
    first=qualified(employee_factory,specialty);second=qualified(employee_factory,specialty)
    assert assign(client,work,[first]).status_code==400
    response=assign(client,work,[first,second])
    assert response.status_code==200 and len(response.json()["current_assignments"])==2
    assert response.json()["registration_number"]=="151/3-1-26"
    from apps.expertises.models import Expertise
    assert Expertise.objects.count()==1


def test_commission_reassignment_keeps_unchanged_participant(employee_factory,grant):
    client,_,work,_,specialty=assignment_setup(employee_factory,grant,commission=True)
    first,second,third=[qualified(employee_factory,specialty) for _ in range(3)]
    assigned=assign(client,work,[first,second]).json()
    first_id=next(a["id"] for a in assigned["current_assignments"] if a["employee"]["id"]==str(first.id))
    response=assign(client,assigned,[first,third],reassign=True)
    assert response.status_code==200
    result=response.json()
    assert len(result["assignment_history"])==3
    assert next(a["id"] for a in result["current_assignments"] if a["employee"]["id"]==str(first.id))==first_id
    assert next(a for a in result["assignment_history"] if a["employee"]["id"]==str(second.id))["ended_at"] is not None


def test_reassignment_moves_current_list_preserves_history(employee_factory,grant):
    client,_,work,_,specialty=assignment_setup(employee_factory,grant)
    first=qualified(employee_factory,specialty);second=qualified(employee_factory,specialty)
    for e in (first,second):grant(e,"expertise.view","own")
    assigned=assign(client,work,[first]).json()
    response=assign(client,assigned,[second],reassign=True)
    assert response.status_code==200
    result=response.json()
    assert result["registration_number"]==work["registration_number"] and len(result["assignment_history"])==2
    own=Client();own.force_login(first.user)
    assert own.get("/api/v1/expertises/").json()["count"]==0
    own.force_login(second.user)
    assert own.get("/api/v1/expertises/").json()["count"]==1
    assert own.get("/api/v1/expertises/filter-options/").json()=={"employees":[{"id":str(second.id),"full_name":second.full_name}]}
    assert assign(client,work,[first],reassign=True).status_code==409


def test_ordinary_work_rejects_multiple_or_duplicate_experts(employee_factory,grant):
    client,_,work,_,specialty=assignment_setup(employee_factory,grant)
    first=qualified(employee_factory,specialty);second=qualified(employee_factory,specialty)
    assert assign(client,work,[first,second]).status_code==400
    assert assign(client,work,[first,first]).status_code==400


def test_revocation_is_rechecked_in_open_assignment_form(employee_factory,grant):
    client,head,work,_,specialty=assignment_setup(employee_factory,grant)
    employee=qualified(employee_factory,specialty)
    assert client.get(f"/api/v1/expertises/{work['id']}/assignment-candidates/").status_code==200
    head.role_assignments.filter(role__permissions__permission_code="expertise.assign").update(is_active=False)
    assert assign(client,work,[employee]).status_code==403
