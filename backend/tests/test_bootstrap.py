from io import StringIO
import pytest
from django.core.management import call_command, CommandError
from apps.accounts.models import Role, RolePermission
from apps.personnel.models import Employee, EmployeeSpecialty
from apps.references.models import Department

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


def test_fresh_bootstrap_allows_old_department_journal_without_changing_employee_departments(monkeypatch, grant):
    from django.test import Client
    from apps.expertises.models import Expertise, ExpertAssignment
    from application_samples import source_batch
    from journal_samples import row

    monkeypatch.setenv("AIS_BOOTSTRAP_PASSWORD", "Long-unique-bootstrap-password9")
    call_command("bootstrap_access", username="setup", full_name="Настройка", seed_staff=True, no_input=True, stdout=StringIO())
    historical = Department.objects.filter(code="1").first()
    assert historical is not None, "Fresh installations must include historical department 1"
    assert not historical.is_active
    actor = Employee.objects.get(user__username="setup")
    for code in ("imports.preview", "imports.results.view", "imports.reconcile", "imports.apply", "expertise.view"):
        grant(actor, code)
    rows = [row(B="1/1-1-26", L="Логинов Д.Л."),
            row(B="2/1-3-26", L="Арыштаев А.С.", M="16.1"),
            row(B="3/4-1-26", L="Логинов Д.Л.")]
    batch = source_batch(actor, rows)
    client = Client()
    client.force_login(actor.user)
    result = client.get(f"/api/v1/imports/{batch.pk}/review/")
    assert result.status_code == 200, result.content
    data = result.json()
    assert data["summary"] == {"new": 3, "changed": 0, "unchanged": 0, "invalid": 0}
    assert all(item["eligible"] and not item["blockers"] for item in data["results"])
    keys = ("row_id", "action", "expected_work_version", "expected_source_row_id", "expected_selection_version", "proposal_hash")
    selections = [{**{key: item[key] for key in keys}, "accepted_fields": []} for item in data["results"]]
    applied = client.post(f"/api/v1/imports/{batch.pk}/review/", {"selections": selections},
                          content_type="application/json", HTTP_IDEMPOTENCY_KEY="fresh-bootstrap-journal")
    assert applied.status_code == 201, applied.content
    assert set(Expertise.objects.values_list("registration_number", "department__code")) == {
        ("1/1-1-26", "1"), ("2/1-3-26", "1"), ("3/4-1-26", "4")}
    person = Employee.objects.get(full_name="Логинов Д.Л.")
    assert person.org_assignments.get().department.code == "4"
    assert Expertise.objects.get(registration_number="1/1-1-26").historical.participants.get().employee_id == person.pk
    assert not ExpertAssignment.objects.exists()


@pytest.mark.parametrize("active", [True, False])
def test_bootstrap_preserves_existing_historical_department_details(monkeypatch, active):
    historical = Department.objects.create(code="1", name="Название учреждения", is_active=active, version=7)
    monkeypatch.setenv("AIS_BOOTSTRAP_PASSWORD", "Long-unique-bootstrap-password9")
    call_command("bootstrap_access", username="setup", full_name="Настройка", no_input=True, stdout=StringIO())
    historical.refresh_from_db()
    assert (historical.name, historical.is_active, historical.version) == ("Название учреждения", active, 7)
    assert Department.objects.filter(code="1").count() == 1
