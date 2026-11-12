from datetime import date

import pytest
from django.test import Client
from django.utils.html import strip_tags

from apps.expertises.models import Expertise
from apps.intake.models import Material, Receipt
from apps.references.models import Department, Specialty

pytestmark = pytest.mark.django_db


@pytest.fixture
def russian_admin(employee_factory, grant):
    employee = employee_factory(full_name='Логинов Д.Л.')
    employee.user.is_staff = employee.user.is_superuser = True
    employee.user.save()
    grant(employee, 'references.manage')
    department = Department.objects.create(code='4', name='Отдел 4')
    specialty = Specialty.objects.create(code='18.1', name='Исследование стоимости')
    material = Material.objects.create(created_by=employee, title='Материалы дела')
    receipt = Receipt.objects.create(material=material, created_by=employee, received_at=date(2026, 1, 1))
    work = Expertise.objects.create(material=material, receipt=receipt, registered_by=employee.user,
        registration_number='482/4-1-26', sequence=482, year=2026, category_code='1',
        department=department, specialty=specialty, appointment_nature='primary', state='completed')
    client = Client()
    client.force_login(employee.user)
    return client, employee, work


def test_expertise_columns_filters_and_card_are_readable_in_russian(russian_admin):
    client, _, work = russian_admin
    page = client.get('/admin/expertises/expertise/')
    assert page.status_code == 200
    text = strip_tags(page.content.decode())
    for label in ('Регистрационный номер', 'Год', 'Состояние', 'Завершена', 'Первичная'):
        assert label in text
    assert 'Registration number' not in text
    filtered = client.get('/admin/expertises/expertise/', {'state__exact': 'completed', 'o': '1'})
    assert filtered.status_code == 200 and work.registration_number in filtered.content.decode()
    card = client.get(f'/admin/expertises/expertise/{work.pk}/change/')
    assert card.status_code == 200
    text = strip_tags(card.content.decode())
    for label in ('Исторический номер', 'Специальность', 'Первичная', 'Завершена', 'Уголовное дело', 'Экспертиза'):
        assert label in text
    assert 'in_progress' not in text and 'completed' not in text
    assert 'Expertise object (' not in text


def test_related_records_show_names_instead_of_model_object_uuid(russian_admin):
    client, employee, _ = russian_admin
    from apps.personnel.models import EmployeeOrgAssignment
    from apps.references.models import Position
    department = Department.objects.get(code='4')
    position = Position.objects.create(code='expert', name='Эксперт')
    assignment = EmployeeOrgAssignment.objects.create(employee=employee, department=department, position=position)
    response = client.get(f'/admin/personnel/employeeorgassignment/{assignment.pk}/change/')
    assert response.status_code == 200
    text = strip_tags(response.content.decode())
    assert 'Логинов Д.Л.' in text and 'Отдел 4' in text and 'Эксперт' in text
    assert 'Employee object (' not in text
    assert f'/admin/personnel/employee/{employee.pk}/change/' in response.content.decode()


def test_reference_readonly_labels_and_form_submission_still_work(russian_admin):
    client, _, _ = russian_admin
    department = Department.objects.get(code='4')
    path = f'/admin/references/department/{department.pk}/change/'
    response = client.get(path)
    assert response.status_code == 200
    text = strip_tags(response.content.decode())
    assert 'Код' in text and 'Версия' in text and 'Отдел' in text
    response = client.post(path, {'name': 'Новое название отдела', 'is_active': 'on', 'expected_version': 1, '_save': '1'})
    assert response.status_code == 302
    department.refresh_from_db()
    assert department.name == 'Новое название отдела' and department.code == '4' and department.version == 2


def test_translation_does_not_change_model_metadata_or_api_codes(russian_admin):
    from django.apps import apps
    models = [m for app in apps.get_app_configs() if app.name.startswith('apps.') for m in app.get_models()]
    def metadata():
        return [(m._meta.label, str(m._meta.verbose_name), str(m._meta.verbose_name_plural),
                 [(f.name, str(f.verbose_name), list(f.flatchoices) if f.choices else None) for f in m._meta.fields]) for m in models]
    before = metadata()
    client, _, work = russian_admin
    assert client.get('/admin/expertises/expertise/').status_code == 200
    assert client.get(f'/admin/expertises/expertise/{work.pk}/change/').status_code == 200
    assert metadata() == before
    work.refresh_from_db()
    assert work.state == 'completed' and work.appointment_nature == 'primary' and work.category_code == '1'
