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


def test_demo_results_opt_in_restores_only_new_rights_and_refuses_real_members(monkeypatch,employee_factory):
    from django.core.management.base import CommandError
    from apps.accounts.models import Role
    from apps.personnel.models import EmployeeRole
    monkeypatch.setenv("AIS_DEMO_PASSWORD","Only-local-DemoPassword75")
    call_command("bootstrap_workflow_demo")
    role=Role.objects.get(name="ДЕМО · Эксперт")
    RolePermission.objects.filter(role=role,permission_code__in=["expertise.result.draft","expertise.return_without_execution","expertise.complete"]).delete()
    call_command("bootstrap_workflow_demo")
    assert not RolePermission.objects.filter(role=role,permission_code="expertise.result.draft").exists()
    call_command("bootstrap_workflow_demo",enable_results=True)
    assert RolePermission.objects.filter(role=role,permission_code="expertise.result.draft",scope="own").exists()
    assert RolePermission.objects.filter(role=role,permission_code="expertise.return_without_execution",scope="own").exists()
    assert not RolePermission.objects.filter(role=role,permission_code="expertise.complete").exists()
    EmployeeRole.objects.create(employee=employee_factory(),role=role,reason="Ручное назначение")
    with pytest.raises(CommandError):call_command("bootstrap_workflow_demo",enable_results=True)


def test_demo_correspondence_opt_in_adds_only_new_rights_and_refuses_real_members(monkeypatch, employee_factory):
    from django.core.management.base import CommandError
    from apps.accounts.models import Role
    from apps.personnel.models import EmployeeRole
    monkeypatch.setenv("AIS_DEMO_PASSWORD", "Only-local-DemoPassword75")
    call_command("bootstrap_workflow_demo")
    expert = Role.objects.get(name="ДЕМО · Эксперт")
    clerk = Role.objects.get(name="ДЕМО · Делопроизводитель")
    RolePermission.objects.filter(role__in=[expert, clerk], permission_code__in=["letters.attach", "control.view", "letters.draft"]).delete()
    call_command("bootstrap_workflow_demo")
    assert not RolePermission.objects.filter(role=expert, permission_code="letters.attach").exists()
    call_command("bootstrap_workflow_demo", enable_correspondence=True)
    assert RolePermission.objects.filter(role=expert, permission_code="letters.attach", scope="own").exists()
    assert RolePermission.objects.filter(role=clerk, permission_code="control.assign", scope="institution").exists()
    assert not RolePermission.objects.filter(role__in=[expert, clerk], permission_code="letters.draft").exists()
    EmployeeRole.objects.create(employee=employee_factory(), role=clerk, reason="Реальный сотрудник")
    with pytest.raises(CommandError): call_command("bootstrap_workflow_demo", enable_correspondence=True)


def test_demo_issuance_opt_in_preserves_other_revocations_and_refuses_real_members(monkeypatch, employee_factory):
    from django.core.management.base import CommandError
    from apps.accounts.models import Role
    from apps.personnel.models import EmployeeRole
    monkeypatch.setenv("AIS_DEMO_PASSWORD", "Only-local-DemoPassword75")
    call_command("bootstrap_workflow_demo")
    clerk = Role.objects.get(name="ДЕМО · Делопроизводитель")
    expert = Role.objects.get(name="ДЕМО · Эксперт")
    RolePermission.objects.filter(role__in=[clerk, expert], permission_code__in=["issue.view", "issue.prepare", "issue.check", "issue.confirm"]).delete()
    call_command("bootstrap_workflow_demo")
    assert not RolePermission.objects.filter(role=clerk, permission_code="issue.prepare").exists()
    call_command("bootstrap_workflow_demo", enable_issuance=True)
    assert RolePermission.objects.filter(role=clerk, permission_code="issue.prepare", scope="institution").exists()
    assert RolePermission.objects.filter(role=expert, permission_code="issue.view", scope="own").exists()
    assert not RolePermission.objects.filter(role=clerk, permission_code="issue.confirm").exists()
    EmployeeRole.objects.create(employee=employee_factory(), role=clerk, reason="Неучебный сотрудник")
    with pytest.raises(CommandError): call_command("bootstrap_workflow_demo", enable_issuance=True)


def test_demo_import_preview_opt_in_preserves_edits_and_refuses_real_members(monkeypatch,employee_factory):
    from django.core.management.base import CommandError
    from apps.accounts.models import Role
    from apps.personnel.models import EmployeeRole
    monkeypatch.setenv("AIS_DEMO_PASSWORD","Only-local-DemoPassword75")
    call_command("bootstrap_workflow_demo")
    role=Role.objects.get(name="ДЕМО · Делопроизводитель")
    RolePermission.objects.filter(role=role,permission_code__in=["imports.preview","imports.results.view","expertise.register"]).delete()
    call_command("bootstrap_workflow_demo")
    assert not RolePermission.objects.filter(role=role,permission_code="imports.preview").exists()
    call_command("bootstrap_workflow_demo",enable_import_preview=True)
    assert RolePermission.objects.filter(role=role,permission_code="imports.preview",scope="institution").exists()
    assert RolePermission.objects.filter(role=role,permission_code="imports.results.view",scope="institution").exists()
    assert not RolePermission.objects.filter(role=role,permission_code="expertise.register").exists()
    EmployeeRole.objects.create(employee=employee_factory(),role=role,reason="Реальный сотрудник")
    with pytest.raises(CommandError):call_command("bootstrap_workflow_demo",enable_import_preview=True)


def test_demo_application_opt_in_restores_only_new_rights_and_refuses_non_demo_role_member(monkeypatch,employee_factory):
    from django.core.management.base import CommandError
    from apps.accounts.models import Role
    from apps.personnel.models import EmployeeRole
    monkeypatch.setenv('AIS_DEMO_PASSWORD','Only-local-DemoPassword75')
    call_command('bootstrap_workflow_demo')
    role=Role.objects.get(name='ДЕМО · Делопроизводитель')
    codes=['imports.reconcile','imports.apply','imports.history.activate']
    RolePermission.objects.filter(role=role,permission_code__in=[*codes,'expertise.register']).delete()
    call_command('bootstrap_workflow_demo')
    assert not RolePermission.objects.filter(role=role,permission_code__in=codes).exists()
    call_command('bootstrap_workflow_demo',enable_journal_application=True)
    assert RolePermission.objects.filter(role=role,permission_code__in=codes,scope='institution').count()==3
    assert not RolePermission.objects.filter(role=role,permission_code='expertise.register').exists()
    EmployeeRole.objects.create(employee=employee_factory(),role=role,reason='Реальное назначение')
    with pytest.raises(CommandError):call_command('bootstrap_workflow_demo',enable_journal_application=True)
