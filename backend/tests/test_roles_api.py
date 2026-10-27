import pytest
from django.test import Client
from apps.accounts.models import Role, RolePermission
from apps.audit.models import AuditEvent

pytestmark = pytest.mark.django_db


def editor(employee_factory, grant):
    employee = employee_factory()
    grant(employee, "access.roles.manage")
    grant(employee, "access.roles.view")
    client = Client()
    client.force_login(employee.user)
    return client, employee


def test_role_persists_permission_and_versioned_atomic_replacement(employee_factory, grant):
    client, employee = editor(employee_factory, grant)
    response = client.post("/api/v1/roles/", {"name":"Эксперт отдела", "description":"Описание", "permissions":[{"permission_code":"expertise.view","scope":"own"}]}, content_type="application/json")
    assert response.status_code == 201
    role_id = response.json()["id"]
    url = f"/api/v1/roles/{role_id}/permissions/"
    response = client.put(url, {"expected_version":1,"permissions":[{"permission_code":"expertise.complete","scope":"own"}]}, content_type="application/json")
    assert response.status_code == 200
    assert response.json()["version"] == 2
    assert list(RolePermission.objects.filter(role_id=role_id).values_list("permission_code", "scope")) == [("expertise.complete","own")]
    assert AuditEvent.objects.filter(actor=employee.user,object_id=role_id,action="role.permissions.replace").exists()
    stale = client.put(url, {"expected_version":1,"permissions":[]}, content_type="application/json")
    assert stale.status_code == 409
    assert stale.json()["code"] == "version_conflict"
    assert RolePermission.objects.filter(role_id=role_id).count() == 1


@pytest.mark.parametrize("permissions", [
    [{"permission_code":"imaginary.superpower","scope":"institution"}],
    [{"permission_code":"access.roles.manage","scope":"own"}],
    [{"permission_code":"expertise.view","scope":"own"},{"permission_code":"expertise.view","scope":"institution"}],
])
def test_invalid_permissions_do_not_partially_replace_role(employee_factory, grant, permissions):
    client, _ = editor(employee_factory,grant)
    role = Role.objects.create(name="Не испортить")
    RolePermission.objects.create(role=role,permission_code="employees.view",scope="own")
    response = client.put(f"/api/v1/roles/{role.id}/permissions/", {"expected_version":1,"permissions":permissions},content_type="application/json")
    assert response.status_code == 400
    role.refresh_from_db()
    assert role.version == 1
    assert list(role.permissions.values_list("permission_code",flat=True)) == ["employees.view"]


def test_role_permission_revoke_is_effective_in_already_open_session(employee_factory, grant):
    employee = employee_factory()
    role, _ = grant(employee,"access.roles.manage")
    client = Client()
    client.force_login(employee.user)
    assert client.post("/api/v1/roles/",{"name":"До отзыва","permissions":[]},content_type="application/json").status_code == 201
    role.permissions.all().delete()
    assert client.post("/api/v1/roles/",{"name":"После отзыва","permissions":[]},content_type="application/json").status_code == 403
    assert not Role.objects.filter(name="После отзыва").exists()


def test_role_read_is_separate_from_manage_and_references_unknown_fields_rejected(employee_factory, grant):
    employee = employee_factory()
    grant(employee,"access.roles.view")
    client = Client()
    client.force_login(employee.user)
    assert client.get("/api/v1/roles/").status_code == 200
    assert client.post("/api/v1/roles/",{"name":"Нет"},content_type="application/json").status_code == 403
    grant(employee,"access.roles.manage")
    response = client.post("/api/v1/roles/",{"name":"Неявная эскалация","permissions":[],"is_superuser":True},content_type="application/json")
    assert response.status_code == 400


def test_role_assignment_only_can_read_options_not_edit_them(employee_factory, grant):
    employee = employee_factory()
    grant(employee,"access.roles.assign")
    client = Client()
    client.force_login(employee.user)
    assert client.get("/api/v1/roles/").status_code == 200
    assert client.get("/api/v1/references/departments/").status_code == 200
    assert client.post("/api/v1/roles/",{"name":"Нет"},content_type="application/json").status_code == 403
