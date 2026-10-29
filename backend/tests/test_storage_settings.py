import subprocess
import pytest
from django.apps import apps
from django.test import Client
from apps.accounts.models import CommandReceipt
from apps.audit.models import AuditEvent
from test_journal_preview_api import business_counts

pytestmark = pytest.mark.django_db
ROOT = '/api/v1/document-storage/2026/'
CHECK = '/api/v1/document-storage/check/'
PERMISSION = 'documents.storage.manage'
FOLDER = r'\\fileserver.invalid\share\2026'


@pytest.fixture
def manager(employee_factory, grant):
    actor = employee_factory()
    grant(actor, PERMISSION)
    client = Client()
    client.force_login(actor.user)
    return client, actor


def save(client, *, endpoint=ROOT, key='storage-one', **changes):
    headers = {'HTTP_IDEMPOTENCY_KEY': key} if key else {}
    return client.put(endpoint, {'path': FOLDER, 'expected_version': 0, **changes},
                      content_type='application/json', **headers)


def test_empty_get_creates_nothing_and_exposes_storage_capability(manager):
    client, _ = manager
    before = business_counts()
    response = client.get(ROOT)
    assert response.status_code == 200
    assert response.json() == {'year': 2026, 'path': '', 'version': 0, 'read_only': True}
    assert not AuditEvent.objects.exists() and not CommandReceipt.objects.exists()
    assert business_counts() == before
    assert 'document_storage_settings' in client.get('/api/v1/me/').json()['supported_modules']


def test_saving_never_checks_disk_and_years_are_independent(manager, monkeypatch):
    client, _ = manager
    from apps.documents import storage_settings
    monkeypatch.setattr(storage_settings, 'probe_directory', lambda path: pytest.fail('Save must not probe'))
    before = business_counts()
    first = save(client)
    assert first.status_code == 200, first.content
    assert first.json()['path'] == FOLDER and first.json()['version'] == 1
    other = save(client, endpoint='/api/v1/document-storage/2027/', key='storage-next', path=r'\\fileserver.invalid\share\2027')
    assert other.status_code == 200
    assert client.get(ROOT).json() == {'year': 2026, 'path': FOLDER, 'version': 1, 'read_only': True}
    assert business_counts() == before
    assert AuditEvent.objects.filter(action='documents.storage.save').count() == 2


def test_replay_and_stale_versions_cannot_overwrite_saved_root(manager):
    client, _ = manager
    first = save(client)
    assert first.status_code == 200
    assert save(client).json() == first.json()
    assert save(client, path=r'C:\different').status_code == 409
    assert save(client, key='stale', path=r'C:\different').status_code == 409
    assert client.get(ROOT).json()['path'] == FOLDER
    assert save(client, key='new', expected_version=1, path=r'C:\different').json()['version'] == 2
    assert CommandReceipt.objects.filter(action='documents.storage.save').count() == 2


@pytest.mark.parametrize('kind', ['none', 'invalid_scope', 'superuser', 'inactive'])
def test_settings_and_explicit_check_require_role_permission(employee_factory, grant, tmp_path, kind):
    actor = employee_factory()
    if kind == 'invalid_scope':
        grant(actor, PERMISSION, 'own')
    if kind == 'superuser':
        actor.user.is_superuser = True
        actor.user.save()
    if kind == 'inactive':
        role, _ = grant(actor, PERMISSION)
        role.is_active = False
        role.save()
    client = Client()
    client.force_login(actor.user)
    assert client.get(ROOT).status_code == 403
    assert save(client).status_code == 403
    assert client.post(CHECK, {'path': str(tmp_path)}, content_type='application/json').status_code == 403


def test_revocation_denies_replay_and_check(manager, tmp_path):
    client, actor = manager
    assert save(client).status_code == 200
    actor.role_assignments.update(is_active=False)
    assert save(client).status_code == 403
    assert client.get(ROOT).status_code == 403
    assert client.post(CHECK, {'path': str(tmp_path)}, content_type='application/json').status_code == 403


@pytest.mark.parametrize('path', ['relative/folder', '../folder', r'C:relative', r'\\?\C:\folder', r'\\.\C:\folder', r'C:\root\..\folder', 'C:\\bad\nfolder', 'https://host/path', ''])
def test_invalid_paths_do_not_create_configuration(manager, path):
    client, _ = manager
    assert save(client, path=path).status_code == 400
    assert client.post(CHECK, {'path': path}, content_type='application/json').status_code == 400
    assert client.get(ROOT).json()['version'] == 0


def test_audit_failure_rolls_back_new_root(manager, monkeypatch):
    client, _ = manager
    from apps.documents import storage_settings
    def fail(*args, **kwargs):
        raise RuntimeError('audit unavailable')
    monkeypatch.setattr(storage_settings, 'audit', fail)
    with pytest.raises(RuntimeError):
        save(client)
    assert not apps.get_model('documents', 'StorageRoot').objects.exists()
    assert not CommandReceipt.objects.filter(action='documents.storage.save').exists()


def test_missing_key_unknown_fields_and_invalid_year_leave_settings_unchanged(manager):
    client, _ = manager
    assert save(client, key=None).status_code == 400
    assert save(client, read_only=False).status_code == 400
    assert save(client, endpoint='/api/v1/document-storage/99/').status_code == 400
    assert client.get(ROOT).json()['version'] == 0


def test_explicit_probe_reads_real_empty_directory_without_saving_or_changing_files(manager, tmp_path):
    client, _ = manager
    response = client.post(CHECK, {'path': str(tmp_path)}, content_type='application/json')
    assert response.status_code == 200
    assert response.json() == {'status': 'available', 'read_only': True}
    assert list(tmp_path.iterdir()) == []
    assert client.get(ROOT).json()['version'] == 0
    missing = client.post(CHECK, {'path': str(tmp_path / 'missing')}, content_type='application/json')
    assert missing.json()['status'] == 'unavailable'


def test_probe_timeout_has_bounded_child_and_does_not_mark_root_available(manager, tmp_path, monkeypatch):
    client, _ = manager
    from apps.documents import storage_probe
    def timeout(args, **kwargs):
        assert kwargs['timeout'] == 5
        raise subprocess.TimeoutExpired(args, kwargs['timeout'])
    monkeypatch.setattr(storage_probe.subprocess, 'run', timeout)
    response = client.post(CHECK, {'path': str(tmp_path)}, content_type='application/json')
    assert response.status_code == 200
    assert response.json() == {'status': 'timeout', 'read_only': True}


def test_storage_permission_is_assignable_in_existing_role_editor(manager, grant):
    client, actor = manager
    grant(actor, 'access.roles.manage')
    permission = next(item for item in client.get('/api/v1/permissions/').json() if item['code'] == PERMISSION)
    assert permission['scopes'] == ['institution']
    response = client.post('/api/v1/roles/', {'name': 'Хранилище', 'permissions': [{'permission_code': PERMISSION, 'scope': 'institution'}]}, content_type='application/json')
    assert response.status_code == 201
