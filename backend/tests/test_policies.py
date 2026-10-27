from datetime import date, timedelta
import pytest


@pytest.mark.django_db
def test_union_of_roles_does_not_expand_another_actions_scope(employee_factory, grant):
    from apps.accounts.policies import can
    from apps.references.models import Department
    d3 = Department.objects.create(code="3", name="Отдел 3")
    d4 = Department.objects.create(code="4", name="Отдел 4")
    head = employee_factory(department=d3)
    other = employee_factory(department=d4)
    grant(head, "expertise.view", "institution")
    grant(head, "expertise.complete", "own")
    assert can(head.user, "expertise.view", employee_id=other.id, department_ids=[d4.id])
    assert can(head.user, "expertise.complete", employee_id=head.id, department_ids=[d3.id])
    assert not can(head.user, "expertise.complete", employee_id=other.id, department_ids=[d4.id])


@pytest.mark.django_db
def test_department_scope_with_no_departments_grants_nothing(employee_factory, grant):
    from apps.accounts.policies import can
    from apps.references.models import Department
    d3 = Department.objects.create(code="3", name="Отдел 3")
    employee = employee_factory(department=d3)
    grant(employee, "expertise.assign", "departments")
    assert not can(employee.user, "expertise.assign", department_ids=[d3.id])


@pytest.mark.django_db
def test_role_assignment_limit_intersects_rather_than_widens_permission(employee_factory, grant):
    from apps.accounts.policies import can
    from apps.references.models import Department
    d3 = Department.objects.create(code="3", name="Отдел 3")
    d4 = Department.objects.create(code="4", name="Отдел 4")
    employee = employee_factory(department=d3)
    grant(employee, "employees.update", "institution", departments=[d3], limit="departments")
    assert can(employee.user, "employees.update", department_ids=[d3.id])
    assert not can(employee.user, "employees.update", department_ids=[d4.id])


@pytest.mark.django_db
def test_revoked_role_is_not_cached_on_user_or_open_session(employee_factory, grant):
    from apps.accounts.policies import can
    employee = employee_factory()
    role, _ = grant(employee, "access.roles.manage")
    assert can(employee.user, "access.roles.manage")
    role.permissions.all().delete()
    assert not can(employee.user, "access.roles.manage")


@pytest.mark.django_db
def test_future_expired_and_inactive_role_grants_do_not_apply(employee_factory, grant):
    from django.utils import timezone
    from apps.accounts.policies import can
    employee = employee_factory()
    role, assignment = grant(employee, "employees.view")
    today = timezone.localdate()
    assignment.valid_from = today + timedelta(days=1)
    assignment.save()
    assert not can(employee.user, "employees.view")
    assignment.valid_from = None
    assignment.valid_to = today - timedelta(days=1)
    assignment.save()
    assert not can(employee.user, "employees.view")
    assignment.valid_to = today
    assignment.save()
    assert can(employee.user, "employees.view")
    role.is_active = False
    role.save()
    assert not can(employee.user, "employees.view")


@pytest.mark.django_db
def test_inactive_employee_has_no_business_permissions(employee_factory, grant):
    from apps.accounts.policies import can
    employee = employee_factory(active=False)
    grant(employee, "employees.view")
    assert not can(employee.user, "employees.view")
