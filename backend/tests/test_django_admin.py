from datetime import date
from io import StringIO

import pytest
from django.core.management import call_command, CommandError
from django.test import Client

from apps.accounts.models import RolePermission
from apps.audit.models import AuditEvent
from apps.expertises.models import Expertise
from apps.intake.models import Material, Receipt
from apps.references.models import Department, Specialty, LetterJournal

pytestmark = pytest.mark.django_db


@pytest.fixture
def administrator(employee_factory, grant):
    employee = employee_factory(full_name='Администратор стенда')
    employee.user.is_staff = employee.user.is_superuser = True
    employee.user.save()
    grant(employee, 'references.manage')
    client = Client()
    client.force_login(employee.user)
    return client, employee


def test_admin_login_and_index_are_available_but_ordinary_accounts_are_denied(employee_factory, administrator):
    assert Client().get('/admin/login/').status_code == 200
    ordinary = employee_factory()
    ordinary.user.is_staff = True
    ordinary.user.save()
    client = Client()
    client.force_login(ordinary.user)
    assert client.get('/admin/').status_code == 302
    client, _ = administrator
    response = client.get('/admin/')
    assert response.status_code == 200
    assert 'Абаканская ЛСЭ' in response.content.decode()
    for path in ('expertises/expertise/', 'personnel/employee/', 'references/department/', 'audit/auditevent/'):
        assert f'/admin/{path}' in response.content.decode()


def test_expertise_can_be_found_but_cannot_be_changed_or_deleted(administrator):
    client, actor = administrator
    department = Department.objects.create(code='4', name='Отдел 4')
    specialty = Specialty.objects.create(code='18.1', name='Стоимость')
    material = Material.objects.create(created_by=actor, title='Материал для проверки')
    receipt = Receipt.objects.create(material=material, created_by=actor, received_at=date(2026, 1, 1))
    work = Expertise.objects.create(material=material, receipt=receipt, registered_by=actor.user,
        registration_number='482/4-1-26', sequence=482, year=2026, category_code='1',
        department=department, specialty=specialty, appointment_nature='primary', state='completed')
    listing = client.get('/admin/expertises/expertise/', {'q': '482/4-1-26'})
    assert listing.status_code == 200 and '482/4-1-26' in listing.content.decode()
    url = f'/admin/expertises/expertise/{work.pk}/change/'
    page = client.get(url)
    assert page.status_code == 200 and f'/expertises/{work.pk}' in page.content.decode()
    assert client.post(url, {'state': 'in_progress', '_save': '1'}).status_code == 403
    assert client.post(f'/admin/expertises/expertise/{work.pk}/delete/', {'post': 'yes'}).status_code == 403
    work.refresh_from_db()
    assert work.state == 'completed'


def test_every_domain_model_has_a_working_list_and_history_cannot_be_written(administrator):
    from django.apps import apps
    from django.contrib import admin
    client, actor = administrator
    # Covers the complete installed catalogue rather than only the menu links.
    for app in apps.get_app_configs():
        if not app.name.startswith('apps.'):
            continue
        for model in app.get_models():
            assert model in admin.site._registry, model._meta.label
            response = client.get(f'/admin/{app.label}/{model._meta.model_name}/')
            assert response.status_code == 200, model._meta.label
    event = AuditEvent.objects.create(actor=actor.user, action='test.original', object_type='test', object_id='1')
    url = f'/admin/audit/auditevent/{event.pk}/change/'
    assert client.get(url).status_code == 200
    assert client.post(url, {'action': 'test.forged'}).status_code == 403
    event.refresh_from_db()
    assert event.action == 'test.original'


def test_reference_create_and_update_use_versions_and_audit(administrator):
    client, actor = administrator
    assert client.post('/admin/references/department/add/', {'code': '9', 'name': 'Новый отдел', '_save': '1'}).status_code == 302
    item = Department.objects.get(code='9')
    assert item.version == 1 and item.is_active
    assert AuditEvent.objects.filter(actor=actor.user, action='reference.create', object_id=str(item.pk)).exists()
    url = f'/admin/references/department/{item.pk}/change/'
    response = client.post(url, {'name': 'Уточнённый отдел', 'expected_version': 1, '_save': '1'})
    assert response.status_code == 302, response.content.decode()[-2000:]
    item.refresh_from_db()
    assert item.code == '9' and item.name == 'Уточнённый отдел' and item.version == 2 and not item.is_active
    event = AuditEvent.objects.get(action='reference.update', object_id=str(item.pk))
    assert event.changes['before']['name'] == 'Новый отдел'
    assert event.changes['after']['name'] == 'Уточнённый отдел'
    assert client.post(f'/admin/references/department/{item.pk}/delete/', {'post': 'yes'}).status_code == 403


def test_reference_stale_or_missing_version_does_not_overwrite(administrator):
    client, _ = administrator
    item = Department.objects.create(code='3', name='Актуальный отдел', version=2)
    url = f'/admin/references/department/{item.pk}/change/'
    for payload in ({'name': 'Старое имя', 'expected_version': 1}, {'name': 'Без версии'}):
        response = client.post(url, {**payload, '_save': '1'})
        assert response.status_code == 200
        assert response.context['adminform'].form.errors
    item.refresh_from_db()
    assert item.name == 'Актуальный отдел' and item.version == 2
    assert not AuditEvent.objects.filter(object_id=str(item.pk)).exists()


def test_reference_edit_requires_business_permission_even_for_django_superuser(administrator):
    client, actor = administrator
    RolePermission.objects.all().delete()
    response = client.post('/admin/references/department/add/', {'code': '9', 'name': 'Запрещено', '_save': '1'})
    assert response.status_code == 403
    assert not Department.objects.exists()
    # The separate Django access must not silently grant API rights.
    assert client.get('/api/v1/expertises/registry/').status_code == 403


def test_reference_journal_rejects_inactive_department_without_partial_record(administrator):
    client, _ = administrator
    department = Department.objects.create(code='1', name='Исторический', is_active=False)
    response = client.post('/admin/references/letterjournal/add/', {
        'code': 'IN', 'name': 'Входящие', 'direction': 'incoming', 'department': str(department.pk), '_save': '1'})
    assert response.status_code == 200
    assert response.context['adminform'].form.errors
    assert not LetterJournal.objects.exists()


def test_admin_password_change_is_audited_without_password_or_hash(administrator, django_user_model):
    client, actor = administrator
    target = django_user_model.objects.create_user(username='new.operator', password='Initial-only-secret91')
    response = client.post(f'/admin/accounts/user/{target.pk}/password/', {
        'password1': 'Changed-only-secret92', 'password2': 'Changed-only-secret92',
    })
    assert response.status_code == 302
    target.refresh_from_db()
    assert target.check_password('Changed-only-secret92')
    event = AuditEvent.objects.get(actor=actor.user, object_id=str(target.pk), action='admin.user.password')
    assert event.changes == {'password_changed': True}
    assert 'secret' not in str(event.changes) and target.password not in str(event.changes)


def test_user_edit_records_actor_and_changes(administrator, django_user_model):
    client, actor = administrator
    target = django_user_model.objects.create_user(username='operator')
    response = client.post(f'/admin/accounts/user/{target.pk}/change/', {
        'username': 'operator', 'first_name': 'Иван', 'last_name': '', 'email': '', 'is_active': 'on',
        'date_joined_0': target.date_joined.strftime('%Y-%m-%d'), 'date_joined_1': target.date_joined.strftime('%H:%M:%S'),
        '_save': '1',
    })
    assert response.status_code == 302, response.content.decode()[-1500:]
    target.refresh_from_db()
    assert target.first_name == 'Иван'
    event = AuditEvent.objects.get(actor=actor.user, action='admin.user.update', object_id=str(target.pk))
    assert event.changes['after']['first_name'] == 'Иван'
    assert 'password' not in event.changes['after']


def test_explicit_access_command_preserves_password_roles_and_is_idempotent(employee_factory, grant):
    actor = employee_factory()
    grant(actor, 'expertise.view', 'own')
    before = actor.user.password
    roles = list(actor.role_assignments.values_list('pk', flat=True))
    for _ in range(2):
        call_command('django_admin_access', actor.user.username, stdout=StringIO())
    actor.user.refresh_from_db()
    assert actor.user.is_superuser and actor.user.is_staff and actor.user.password == before
    assert list(actor.role_assignments.values_list('pk', flat=True)) == roles
    assert AuditEvent.objects.filter(action='admin.access.grant', object_id=str(actor.user.pk)).count() == 1
    call_command('django_admin_access', actor.user.username, revoke=True, stdout=StringIO())
    actor.user.refresh_from_db()
    assert not actor.user.is_staff and not actor.user.is_superuser and actor.user.password == before
    assert AuditEvent.objects.filter(action='admin.access.revoke', object_id=str(actor.user.pk)).count() == 1


def test_access_command_does_not_create_or_reactivate_accounts(employee_factory):
    actor = employee_factory()
    actor.user.is_active = False
    actor.user.save()
    for username in ('missing', actor.user.username):
        with pytest.raises(CommandError):
            call_command('django_admin_access', username, stdout=StringIO())


def test_admin_real_login_uses_csrf_and_existing_password(administrator):
    _, actor = administrator
    client = Client(enforce_csrf_checks=True)
    assert client.post('/admin/login/', {'username': actor.user.username, 'password': 'Test-only-LongPassword9'}).status_code == 403
    login = client.get('/admin/login/')
    assert login.status_code == 200
    response = client.post('/admin/login/', {
        'username': actor.user.username, 'password': 'Test-only-LongPassword9', 'next': '/admin/',
        'csrfmiddlewaretoken': client.cookies['csrftoken'].value,
    })
    assert response.status_code == 302 and response['Location'] == '/admin/'
    assert client.get('/admin/').status_code == 200


def test_admin_user_creation_is_hashed_and_audited_without_creating_employee_or_roles(administrator, django_user_model):
    from apps.personnel.models import Employee
    client, actor = administrator
    response = client.post('/admin/accounts/user/add/', {
        'username': 'new.account', 'password1': 'New-account-only-secret93',
        'password2': 'New-account-only-secret93', 'usable_password': 'true', '_save': '1',
    })
    assert response.status_code == 302, response.content.decode()[-1500:]
    user = django_user_model.objects.get(username='new.account')
    assert user.check_password('New-account-only-secret93')
    assert not user.is_staff and not user.is_superuser
    assert not Employee.objects.filter(user=user).exists()
    event = AuditEvent.objects.get(action='admin.user.create', actor=actor.user, object_id=str(user.pk))
    assert 'password' not in str(event.changes) and 'secret93' not in str(event.changes)


def test_report_catalogue_special_fields_use_the_same_commands(administrator):
    from apps.references.models import AuthorityType
    client, _ = administrator
    response = client.post('/admin/references/authoritytype/add/', {
        'code': 'court', 'name': 'Суд', 'report_group': 'court', '_save': '1',
    })
    assert response.status_code == 302
    item = AuthorityType.objects.get(code='court')
    response = client.post(f'/admin/references/authoritytype/{item.pk}/change/', {
        'name': 'Суды', 'is_active': 'on', 'report_group': 'other', 'expected_version': 1, '_save': '1',
    })
    assert response.status_code == 302
    item.refresh_from_db()
    assert item.report_group == 'other' and item.version == 2


def test_file_version_uses_protected_download_instead_of_direct_media_link(administrator):
    from apps.documents.models import Document, FileVersion
    client, actor = administrator
    document = Document.objects.create(kind='case_material', title='Файл для проверки',
                                       source_kind='uploaded_copy', created_by=actor)
    version = FileVersion.objects.create(document=document, number=1, file='documents/test.pdf',
        original_name='test.pdf', content_type='application/pdf', size=10, sha256='0' * 64, created_by=actor)
    response = client.get(f'/admin/documents/fileversion/{version.pk}/change/')
    assert response.status_code == 200
    assert f'/api/v1/file-versions/{version.pk}/download/' in response.content.decode()
    assert '/media/documents/test.pdf' not in response.content.decode()


def test_staff_without_service_access_gets_explanation_instead_of_login_loop(employee_factory):
    actor = employee_factory()
    actor.user.is_staff = True
    actor.user.save()
    client = Client()
    response = client.post('/admin/login/', {
        'username': actor.user.username, 'password': 'Test-only-LongPassword9', 'next': '/admin/',
    })
    assert response.status_code == 200
    assert 'служебный доступ' in response.content.decode()
    assert '_auth_user_id' not in client.session
