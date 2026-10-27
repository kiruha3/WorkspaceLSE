from django.core.management import call_command
from apps.accounts.models import RolePermission,User
from apps.personnel.models import Employee, EmployeeSpecialty
import pytest

pytestmark=pytest.mark.django_db


def test_demo_profiles_are_explicit_and_rerun_preserves_edits(monkeypatch):
    monkeypatch.setenv("AIS_DEMO_PASSWORD","Only-local-DemoPassword75")
    call_command("bootstrap_workflow_demo")
    assert User.objects.filter(username__startswith="demo.").count()==5
    assert Employee.objects.count()==5
    expert=Employee.objects.get(user__username="demo.expert")
    assert expert.full_name.startswith("ДЕМО")
    assert expert.specialties.get().qualified_at is None
    assert expert.specialties.get().basis
    assert EmployeeSpecialty.objects.get(employee__user__username="demo.trainee").status=="training"
    permission=RolePermission.objects.get(role__name="ДЕМО · Делопроизводитель",permission_code="receipts.accept")
    permission.delete()
    specialty=expert.specialties.get();specialty.basis="Ручная правка";specialty.save()
    monkeypatch.setenv("AIS_DEMO_PASSWORD","Different-local-DemoPassword75")
    call_command("bootstrap_workflow_demo")
    assert User.objects.filter(username__startswith="demo.").count()==5
    expert.refresh_from_db()
    assert expert.user.check_password("Only-local-DemoPassword75")
    assert expert.specialties.get().basis=="Ручная правка"
    assert not RolePermission.objects.filter(role__name="ДЕМО · Делопроизводитель",permission_code="receipts.accept").exists()
    from apps.expertises.models import Expertise
    assert Expertise.objects.count()==0
