import itertools
import pytest


@pytest.fixture
def employee_factory(db, django_user_model):
    from apps.personnel.models import Employee, EmployeeOrgAssignment
    from apps.references.models import Position
    count = itertools.count(1)

    def create(*, department=None, active=True, full_name=None):
        n = next(count)
        user = django_user_model.objects.create_user(username=f"employee{n}", password="Test-only-LongPassword9")
        employee = Employee.objects.create(user=user, full_name=full_name or f"Тестовый сотрудник {n}", is_active=active)
        if department:
            position, _ = Position.objects.get_or_create(code="expert",defaults={"name":"Эксперт"})
            EmployeeOrgAssignment.objects.create(employee=employee, department=department, position=position)
        return employee
    return create


@pytest.fixture
def grant(db):
    from apps.accounts.models import Role, RolePermission
    from apps.personnel.models import EmployeeRole
    count = itertools.count(1)

    def create(employee, action, scope="institution", *, departments=(), limit="institution", role=None):
        role = role or Role.objects.create(name=f"Тестовая роль {next(count)}")
        RolePermission.objects.create(role=role, permission_code=action, scope=scope)
        assignment = EmployeeRole.objects.create(employee=employee, role=role, scope_limit=limit)
        assignment.departments.set(departments)
        return role, assignment
    return create
