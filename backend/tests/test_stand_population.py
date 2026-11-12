import json
from io import StringIO

import pytest
from django.core.management import call_command, CommandError
from django.test import Client

from apps.accounts.models import User
from apps.personnel.models import Employee
from apps.expertises.models import Expertise, WorkClosure, ExpertAssignment
from apps.intake.models import Material
from apps.imports.models import ImportBatch

pytestmark = pytest.mark.django_db


def test_population_requires_explicit_stand_mode(settings, tmp_path):
    settings.AIS_STAND_MODE = False
    with pytest.raises(CommandError, match='AIS_STAND_MODE'):
        call_command('populate_stand', count=12, credentials_file=str(tmp_path / 'access.json'))
    assert not User.objects.exists()


def test_population_refuses_existing_employee_data(settings, employee_factory, tmp_path):
    settings.AIS_STAND_MODE = True
    settings.JOURNAL_GOOGLE_ID = ''
    employee = employee_factory(full_name='Существующий сотрудник')
    with pytest.raises(CommandError, match='существующ'):
        call_command('populate_stand', count=12, credentials_file=str(tmp_path / 'access.json'))
    assert Employee.objects.count() == 1 and Employee.objects.get().pk == employee.pk
    assert not Expertise.objects.exists()


def test_population_creates_coherent_fictional_records_and_keeps_credentials(settings, tmp_path):
    pytest.importorskip('reportlab')
    settings.AIS_STAND_MODE = True
    settings.JOURNAL_GOOGLE_ID = ''
    settings.MEDIA_ROOT = tmp_path / 'media'
    credentials = tmp_path / 'access.json'
    options = {'count': 48, 'as_of': '2026-11-09', 'credentials_file': str(credentials), 'stdout': StringIO()}
    call_command('populate_stand', **options)
    assert Expertise.objects.count() == 48
    assert not ImportBatch.objects.exists()
    assert not Material.objects.filter(is_demo=True).exists()
    assert set(Expertise.objects.values_list('state', flat=True)) >= {'in_progress', 'completed', 'suspended', 'without_execution'}
    assert not WorkClosure.objects.filter(kind='completed', result__isnull=True).exists()
    assert not ExpertAssignment.objects.filter(employee__specialties__status='training').exists()
    assert Expertise.objects.filter(complex_group__isnull=False).exists()
    from apps.issuance.models import IssuePackage
    assert IssuePackage.objects.count() == 8
    from apps.documents.models import FileVersion
    assert FileVersion.objects.exists()
    assert all((settings.MEDIA_ROOT / item.file.name).exists() for item in FileVersion.objects.all())
    before = credentials.read_bytes()
    call_command('populate_stand', **options)
    assert Expertise.objects.count() == 48 and credentials.read_bytes() == before
    access = json.loads(before)
    admin = User.objects.get(username='admin')
    assert admin.check_password(access['accounts'][0]['password']) and admin.is_superuser
    client = Client()
    client.force_login(admin)
    response = client.get('/api/v1/expertises/registry/')
    assert response.status_code == 200 and response.json()['count'] == 48
    report = client.get('/api/v1/reports/form151/', {'source': 'registry', 'year': 2026, 'month': 11})
    assert report.status_code == 200 and len(report.json()['records']) == 48


def test_population_cannot_use_configured_google_source(settings, tmp_path):
    settings.AIS_STAND_MODE = True
    settings.JOURNAL_GOOGLE_ID = 'configured-working-source'
    with pytest.raises(CommandError, match='Google'):
        call_command('populate_stand', count=12, credentials_file=str(tmp_path / 'access.json'))
    assert not User.objects.exists()
