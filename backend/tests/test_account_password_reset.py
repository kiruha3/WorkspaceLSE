import json

import pytest
from django.test import Client

from apps.audit.models import AuditEvent
from apps.personnel.models import Employee

pytestmark = pytest.mark.django_db
PASSWORD = "Replacement-personal-password9!"


def signed_in(employee, **options):
    client = Client(**options)
    client.force_login(employee.user)
    return client


def reset_url(employee):
    return f"/api/v1/employees/{employee.id}/account/reset-password/"


def test_reset_changes_only_password_and_invalidates_previous_login_and_session(employee_factory, grant):
    actor, target = employee_factory(), employee_factory()
    grant(actor, "users.reset_password")
    grant(target, "expertise.view")
    original_version = target.version
    roles_before = list(target.role_assignments.values_list("id", flat=True))
    old_session = signed_in(target)
    assert old_session.get("/api/v1/me/").status_code == 200

    response = signed_in(actor).post(reset_url(target), {"password": PASSWORD, "reason": "По обращению сотрудника"}, content_type="application/json")
    assert response.status_code == 200
    target.refresh_from_db()
    assert response.json() == {"id": str(target.user_id), "username": target.user.username, "is_active": True}
    assert target.user.check_password(PASSWORD)
    assert target.version == original_version and target.is_active
    assert list(target.role_assignments.values_list("id", flat=True)) == roles_before
    assert old_session.get("/api/v1/me/").status_code == 401
    assert not Client().login(username=target.user.username, password="Test-only-LongPassword9")
    assert Client().login(username=target.user.username, password=PASSWORD)
    event = AuditEvent.objects.get(action="employee.account.password_reset")
    assert event.actor_id == actor.user_id and event.object_id == str(target.pk)
    assert event.reason == "По обращению сотрудника"
    assert PASSWORD not in json.dumps(event.changes)
    assert target.user.password not in json.dumps(event.changes)
    assert "password" not in event.changes


@pytest.mark.parametrize("permission", ["users.create", "users.deactivate", "employees.update"])
def test_reset_requires_its_own_permission(employee_factory, grant, permission):
    actor, target = employee_factory(), employee_factory()
    grant(actor, permission)
    original = target.user.password
    response = signed_in(actor).post(reset_url(target), {"password": PASSWORD}, content_type="application/json")
    assert response.status_code == 403
    target.user.refresh_from_db()
    assert target.user.password == original
    assert not AuditEvent.objects.filter(action="employee.account.password_reset").exists()


def test_reset_right_can_be_revoked_without_restarting_session(employee_factory, grant):
    actor, target = employee_factory(), employee_factory()
    _, assignment = grant(actor, "users.reset_password")
    client = signed_in(actor)
    assert client.get(f"/api/v1/employees/{target.id}/account/").status_code == 200
    assignment.is_active = False
    assignment.save(update_fields=["is_active"])
    assert client.post(reset_url(target), {"password": PASSWORD}, content_type="application/json").status_code == 403
    target.user.refresh_from_db()
    assert target.user.check_password("Test-only-LongPassword9")


@pytest.mark.parametrize("payload", [{"password": "123"}, {"password": ""}, {}, {"password": PASSWORD, "is_superuser": True}])
def test_invalid_reset_preserves_password_and_audit(employee_factory, grant, payload):
    actor, target = employee_factory(), employee_factory()
    grant(actor, "users.reset_password")
    original = target.user.password
    response = signed_in(actor).post(reset_url(target), payload, content_type="application/json")
    assert response.status_code == 400
    target.user.refresh_from_db()
    assert target.user.password == original
    assert not AuditEvent.objects.filter(action="employee.account.password_reset").exists()


def test_reset_does_not_create_missing_account(employee_factory, grant, django_user_model):
    actor = employee_factory()
    target = Employee.objects.create(full_name="Без логина")
    grant(actor, "users.reset_password")
    count = django_user_model.objects.count()
    response = signed_in(actor).post(reset_url(target), {"password": PASSWORD}, content_type="application/json")
    assert response.status_code == 400
    target.refresh_from_db()
    assert target.user_id is None and django_user_model.objects.count() == count


def test_reset_preserves_disabled_account_and_needs_csrf(employee_factory, grant):
    actor, target = employee_factory(), employee_factory()
    grant(actor, "users.reset_password")
    target.user.is_active = False
    target.user.save(update_fields=["is_active"])
    assert signed_in(actor, enforce_csrf_checks=True).post(reset_url(target), {"password": PASSWORD}, content_type="application/json").status_code == 403
    response = signed_in(actor).post(reset_url(target), {"password": PASSWORD}, content_type="application/json")
    assert response.status_code == 200 and response.json()["is_active"] is False
    target.user.refresh_from_db()
    assert target.user.check_password(PASSWORD) and not target.user.is_active


def test_reset_admin_can_read_minimal_directory_and_account_without_personnel_right(employee_factory, grant):
    actor = employee_factory()
    target = employee_factory(full_name="Сотрудник для сброса")
    grant(actor, "users.reset_password")
    client = signed_in(actor)
    directory = client.get("/api/v1/access/employees/?search=для сброса")
    assert directory.status_code == 200
    assert directory.json()["results"] == [{"id": str(target.id), "full_name": target.full_name, "is_active": True}]
    assert client.get(f"/api/v1/employees/{target.id}/account/").json()["username"] == target.user.username
    assert client.get(f"/api/v1/employees/{target.id}/").status_code == 403
