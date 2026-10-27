from io import StringIO
import pytest
from django.core.management import call_command, CommandError
from apps.accounts.models import Role, RolePermission
from apps.personnel.models import Employee, EmployeeSpecialty

pytestmark = pytest.mark.django_db


def test_bootstrap_is_idempotent_does_not_reset_roles_password_or_confirm_legacy_qualifications(monkeypatch, django_user_model):
    monkeypatch.setenv("AIS_BOOTSTRAP_PASSWORD","Long-unique-bootstrap-password9")
    output = StringIO()
    args = {"username":"setup","full_name":"Ответственный за настройку","seed_staff":True,"stdout":output}
    call_command("bootstrap_access",**args)
    user = django_user_model.objects.get(username="setup")
    assert user.check_password("Long-unique-bootstrap-password9")
    assert not user.is_superuser
    assert Employee.objects.count() == 11
    assert django_user_model.objects.count() == 1
    assert not EmployeeSpecialty.objects.exclude(status="unknown_legacy").exists()
    role = Role.objects.get(name="Администратор доступа")
    RolePermission.objects.filter(role=role,permission_code="access.roles.manage").delete()
    monkeypatch.setenv("AIS_BOOTSTRAP_PASSWORD","Do-not-reset-password9")
    call_command("bootstrap_access",**args)
    user.refresh_from_db()
    assert user.check_password("Long-unique-bootstrap-password9")
    assert Employee.objects.count() == 11
    assert not RolePermission.objects.filter(role=role,permission_code="access.roles.manage").exists()
    assert "Long-unique-bootstrap-password9" not in output.getvalue()


def test_bootstrap_requires_explicit_password_without_partial_user_creation(monkeypatch, django_user_model):
    monkeypatch.delenv("AIS_BOOTSTRAP_PASSWORD",raising=False)
    with pytest.raises(CommandError):
        call_command("bootstrap_access",username="setup",full_name="Настройка",no_input=True)
    assert not django_user_model.objects.exists()


def test_new_clerk_template_supports_intake_but_rerun_does_not_restore_removed_right(monkeypatch):
    monkeypatch.setenv("AIS_BOOTSTRAP_PASSWORD","Long-unique-bootstrap-password9")
    call_command("bootstrap_access",username="setup",full_name="Настройка",no_input=True,stdout=StringIO())
    role=Role.objects.get(name="Делопроизводитель")
    assert set(role.permissions.filter(permission_code__startswith="receipts.").values_list("permission_code",flat=True))=={"receipts.view","receipts.create","receipts.accept","receipts.amend"}
    role.permissions.filter(permission_code="receipts.accept").delete()
    call_command("bootstrap_access",username="setup",full_name="Настройка",no_input=True,stdout=StringIO())
    assert not role.permissions.filter(permission_code="receipts.accept").exists()
