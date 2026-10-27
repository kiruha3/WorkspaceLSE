from datetime import date
import pytest


@pytest.mark.django_db
def test_trainee_for_one_specialty_remains_eligible_for_another(employee_factory, grant):
    from apps.personnel.models import EmployeeSpecialty
    from apps.personnel.services import qualification_eligibility
    from apps.references.models import Specialty
    employee = employee_factory()
    vehicle = Specialty.objects.create(code="18.1", name="Транспорт")
    road = Specialty.objects.create(code="13.1", name="ДТП")
    EmployeeSpecialty.objects.create(employee=employee, specialty=vehicle, status="qualified", qualified_at=date(2026, 1, 1))
    EmployeeSpecialty.objects.create(employee=employee, specialty=road, status="training")
    grant(employee, "expertise.assign", "institution")
    assert qualification_eligibility(employee, vehicle, date(2026,10,27))["eligible"] is True
    denied = qualification_eligibility(employee, road, date(2026,10,27))
    assert denied["eligible"] is False
    assert denied["code"] == "specialty_training"


@pytest.mark.django_db
def test_unknown_or_expired_qualification_cannot_be_used_for_new_assignment(employee_factory):
    from apps.personnel.models import EmployeeSpecialty
    from apps.personnel.services import qualification_eligibility
    from apps.references.models import Specialty
    employee = employee_factory()
    specialty = Specialty.objects.create(code="18.1", name="Транспорт")
    item = EmployeeSpecialty.objects.create(employee=employee, specialty=specialty, status="unknown_legacy")
    assert qualification_eligibility(employee,specialty,date(2026,10,27))["eligible"] is False
    item.status = "qualified"
    item.qualified_at = date(2026,1,1)
    item.valid_until = date(2026,10,26)
    item.save()
    assert qualification_eligibility(employee,specialty,date(2026,10,27))["eligible"] is False
    item.valid_until = date(2026,10,27)
    item.save()
    assert qualification_eligibility(employee,specialty,date(2026,10,27))["eligible"] is True
