from datetime import date

import pytest

from apps.audit.models import AuditEvent
from apps.personnel.models import EmployeeSpecialty
from apps.personnel.services import qualification_eligibility
from apps.references.models import Specialty
from test_personnel_api import client_for
from test_expert_assignments import assignment_setup, assign

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("status", ["training", "qualified"])
def test_create_checks_scoped_right_before_resolving_any_mentor(employee_factory, status):
    from uuid import uuid4
    actor = employee_factory()
    active_mentor = employee_factory()
    inactive_mentor = employee_factory(active=False)
    specialty = Specialty.objects.create(code="18.1",name="Транспорт")
    client = client_for(actor)
    responses = [client.post(f"/api/v1/employees/{actor.id}/specialties/", {
        "status":status,"specialty_id":str(specialty.pk),"mentor_id":str(mentor_id),
    },content_type="application/json") for mentor_id in (active_mentor.pk,inactive_mentor.pk,uuid4())]
    assert [r.status_code for r in responses] == [403,403,403]
    assert responses[0].json() == responses[1].json() == responses[2].json()
    assert not EmployeeSpecialty.objects.exists()


@pytest.mark.parametrize("payload", [[], "not an object"])
def test_malformed_create_is_a_validation_error_without_creating_a_specialty(employee_factory, grant, payload):
    actor = employee_factory()
    grant(actor, "specialties.qualify")
    response = client_for(actor).post(f"/api/v1/employees/{actor.id}/specialties/", payload, content_type="application/json")
    assert response.status_code == 400
    assert not EmployeeSpecialty.objects.exists()


def test_malformed_reference_patch_returns_a_validation_error_and_keeps_existing_data(employee_factory, grant):
    actor = employee_factory()
    grant(actor,"specialties.qualify")
    specialty = Specialty.objects.create(code="18.1",name="Транспорт")
    item = EmployeeSpecialty.objects.create(employee=actor,specialty=specialty,status="qualified")
    response = client_for(actor).patch(f"/api/v1/employee-specialties/{item.id}/",[],content_type="application/json")
    assert response.status_code == 400
    item.refresh_from_db()
    assert item.version == 1 and item.basis == ""


def test_obtained_specialty_can_be_added_directly_without_confirmation_dates_or_basis(employee_factory, grant):
    actor = employee_factory()
    target = employee_factory()
    grant(actor, "specialties.qualify")
    specialty = Specialty.objects.create(code="18.1", name="Транспорт")
    response = client_for(actor).post(f"/api/v1/employees/{target.id}/specialties/", {
        "specialty_id": str(specialty.id), "status": "qualified",
    }, content_type="application/json")
    assert response.status_code == 201
    item = EmployeeSpecialty.objects.get(employee=target, specialty=specialty)
    assert item.status == "qualified" and item.qualified_at is None and item.valid_until is None and item.basis == ""
    assert qualification_eligibility(target, specialty, date(2026, 10, 28))["eligible"] is True
    assert AuditEvent.objects.filter(action="employee.specialty.add", object_id=str(item.pk)).count() == 1


def test_training_right_does_not_allow_direct_obtained_status(employee_factory, grant):
    actor = employee_factory()
    grant(actor, "specialties.training.manage")
    specialty = Specialty.objects.create(code="18.1", name="Транспорт")
    response = client_for(actor).post(f"/api/v1/employees/{actor.id}/specialties/", {
        "specialty_id": str(specialty.id), "status": "qualified",
    }, content_type="application/json")
    assert response.status_code == 403
    assert EmployeeSpecialty.objects.count() == 0


@pytest.mark.parametrize("extra", [{}, {"basis": "", "qualified_at": None}])
def test_marking_existing_specialty_obtained_does_not_require_proof(employee_factory, grant, extra):
    actor = employee_factory()
    grant(actor, "specialties.qualify")
    specialty = Specialty.objects.create(code="18.1", name="Транспорт")
    item = EmployeeSpecialty.objects.create(employee=actor, specialty=specialty, status="training")
    response = client_for(actor).post(f"/api/v1/employee-specialties/{item.id}/qualify/", {
        "expected_version": 1, **extra,
    }, content_type="application/json")
    assert response.status_code == 200
    item.refresh_from_db()
    assert item.status == "qualified" and item.basis == "" and item.qualified_at is None and item.version == 2


@pytest.mark.parametrize("qualified_at,valid_until", [(None, None), (date(2027, 1, 1), None), (date(2020, 1, 1), date(2021, 1, 1))])
def test_reference_dates_do_not_block_candidate_or_actual_assignment(employee_factory, grant, qualified_at, valid_until):
    client, head, work, _, specialty = assignment_setup(employee_factory, grant)
    item = EmployeeSpecialty.objects.create(employee=head, specialty=specialty, status="qualified", qualified_at=qualified_at, valid_until=valid_until)
    candidate = next(c for c in client.get(f"/api/v1/expertises/{work['id']}/assignment-candidates/").json() if c["id"] == str(head.id))
    assert candidate["eligible"] is True
    response = assign(client, work, [head])
    assert response.status_code == 200
    from apps.expertises.models import ExpertAssignment
    before = ExpertAssignment.objects.get(employee=head).qualification_snapshot
    grant(head, "specialties.qualify")
    changed = client_for(head).patch(f"/api/v1/employee-specialties/{item.id}/", {
        "expected_version": 1, "qualified_at": None, "valid_until": None, "basis": "Справочное уточнение",
    }, content_type="application/json")
    assert changed.status_code == 200
    assert ExpertAssignment.objects.get(employee=head).qualification_snapshot == before


@pytest.mark.parametrize("status,permission", [("qualified", "specialties.qualify"), ("training", "specialties.training.manage"), ("unknown_legacy", "specialties.training.manage")])
def test_reference_metadata_update_is_versioned_preserves_status_and_omitted_values(employee_factory, grant, status, permission):
    actor = employee_factory()
    grant(actor, permission)
    specialty = Specialty.objects.create(code="18.1", name="Транспорт")
    item = EmployeeSpecialty.objects.create(employee=actor, specialty=specialty, status=status,
        training_started_at=date(2020, 1, 1), qualified_at=date(2021, 1, 1), valid_until=date(2027, 1, 1), basis="Исходные сведения")
    client = client_for(actor)
    url = f"/api/v1/employee-specialties/{item.id}/"
    response = client.patch(url, {"expected_version": 1, "qualified_at": None, "basis": ""}, content_type="application/json")
    assert response.status_code == 200
    item.refresh_from_db()
    assert item.status == status and item.version == 2 and item.qualified_at is None and item.basis == ""
    assert item.training_started_at == date(2020, 1, 1) and item.valid_until == date(2027, 1, 1)
    event = AuditEvent.objects.get(action="employee.specialty.update", object_id=str(item.pk))
    assert event.changes["before"]["qualified_at"] == "2021-01-01" and event.changes["after"]["qualified_at"] is None
    assert client.patch(url, {"expected_version": 1, "basis": "Устарело"}, content_type="application/json").status_code == 409
    assert AuditEvent.objects.filter(action="employee.specialty.update", object_id=str(item.pk)).count() == 1


@pytest.mark.parametrize("values", [{}, {"status": "qualified"}, {"specialty_id": "x"}, {"qualified_at": "wrong"}, {"qualified_at": "2028-01-01"}, {"valid_until": "2020-01-01"}])
def test_invalid_metadata_patch_leaves_version_values_and_audit_unchanged(employee_factory, grant, values):
    actor = employee_factory()
    grant(actor, "specialties.qualify")
    specialty = Specialty.objects.create(code="18.1", name="Транспорт")
    item = EmployeeSpecialty.objects.create(employee=actor, specialty=specialty, status="qualified", qualified_at=date(2021, 1, 1), valid_until=date(2027, 1, 1))
    response = client_for(actor).patch(f"/api/v1/employee-specialties/{item.id}/", {"expected_version": 1, **values}, content_type="application/json")
    assert response.status_code == 400
    item.refresh_from_db()
    assert item.version == 1 and item.qualified_at == date(2021, 1, 1) and item.valid_until == date(2027, 1, 1)
    assert not AuditEvent.objects.filter(action="employee.specialty.update").exists()


def test_reference_metadata_requires_the_right_for_the_specific_employee_and_status(employee_factory, grant):
    from apps.references.models import Department
    d3 = Department.objects.create(code="3", name="Отдел3")
    d4 = Department.objects.create(code="4", name="Отдел4")
    actor = employee_factory(department=d3)
    target = employee_factory(department=d4)
    grant(actor, "specialties.qualify", "departments", departments=[d3])
    grant(actor, "specialties.training.manage")
    specialty = Specialty.objects.create(code="18.1", name="Транспорт")
    item = EmployeeSpecialty.objects.create(employee=target, specialty=specialty, status="qualified")
    response = client_for(actor).patch(f"/api/v1/employee-specialties/{item.id}/", {"expected_version": 1, "basis": "Нет доступа"}, content_type="application/json")
    assert response.status_code == 403
    item.refresh_from_db()
    assert item.version == 1 and item.basis == ""
