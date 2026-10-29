import pytest
from django.apps import apps
from django.test import Client
from apps.accounts.models import CommandReceipt
from apps.audit.models import AuditEvent
from test_journal_preview_api import business_counts

pytestmark=pytest.mark.django_db
PATH='/api/v1/imports/google-source/settings/'
PERMISSION='imports.source.manage'


@pytest.fixture
def manager(employee_factory,grant,settings,monkeypatch):
    settings.JOURNAL_GOOGLE_ID='DEMO_old_sheet_123';settings.JOURNAL_GOOGLE_GID='0';settings.JOURNAL_GOOGLE_SHEET_NAME='Лист1'
    actor=employee_factory();grant(actor,PERMISSION)
    client=Client();client.force_login(actor.user)
    from apps.imports import google_source
    monkeypatch.setattr(google_source,'fetch_google_csv',lambda source:pytest.fail('Saving source settings must not read Google'))
    return client,actor


def save(client,*,key='settings-one',**changes):
    data={'url':'https://docs.google.com/spreadsheets/d/DEMO_new_sheet_123/edit?usp=sharing#gid=9',
          'gid':'17','sheet_name':'Журнал 2026','expected_version':0,**changes}
    headers={'HTTP_IDEMPOTENCY_KEY':key} if key is not None else {}
    return client.put(PATH,data,content_type='application/json',**headers)


def test_settings_read_falls_back_without_creating_database_records(manager):
    client,_=manager;before=business_counts()
    response=client.get(PATH)
    assert response.status_code==200
    assert response.json()=={'url':'https://docs.google.com/spreadsheets/d/DEMO_old_sheet_123/edit#gid=0','gid':'0','sheet_name':'Лист1','version':0}
    assert not AuditEvent.objects.exists() and not CommandReceipt.objects.exists()
    assert business_counts()==before


def test_save_settings_uses_explicit_gid_and_takes_effect_without_restart_or_import(manager):
    client,_=manager;before=business_counts()
    response=save(client);assert response.status_code==200,response.content
    saved=response.json()
    assert saved['version']==1 and saved['gid']=='17' and saved['sheet_name']=='Журнал 2026'
    assert saved['url']=='https://docs.google.com/spreadsheets/d/DEMO_new_sheet_123/edit#gid=17'
    assert saved['event']['id']
    assert client.get(PATH).json()=={name:saved[name] for name in ('url','gid','sheet_name','version')}
    public=client.get('/api/v1/imports/google-source/');assert public.status_code==200
    assert public.json()['spreadsheet_id']=='DEMO_new_sheet_123' and public.json()['gid']=='17'
    assert business_counts()==before
    assert AuditEvent.objects.filter(action='imports.source.save').count()==1
    assert 'journal_source_settings' in client.get('/api/v1/me/').json()['supported_modules']
    assert client.post('/api/v1/imports/google-preview/',{},content_type='application/json').status_code==403


@pytest.mark.parametrize('kind',['none','preview','invalid_scope','inactive_role','superuser'])
def test_settings_and_command_require_an_active_institution_role(employee_factory,grant,kind):
    actor=employee_factory()
    if kind=='preview':
        grant(actor,'imports.results.view');grant(actor,'imports.preview')
    if kind=='invalid_scope':grant(actor,PERMISSION,'own')
    if kind=='inactive_role':
        role,_=grant(actor,PERMISSION);role.is_active=False;role.save()
    if kind=='superuser':
        actor.user.is_superuser=True;actor.user.is_staff=True;actor.user.save()
    client=Client();client.force_login(actor.user)
    assert client.get(PATH).status_code==403
    assert save(client).status_code==403
    assert not AuditEvent.objects.filter(action='imports.source.save').exists()


def test_revoking_role_denies_an_idempotent_settings_replay(manager):
    client,actor=manager;assert save(client).status_code==200
    actor.role_assignments.update(is_active=False)
    assert save(client).status_code==403
    assert AuditEvent.objects.filter(action='imports.source.save').count()==1


def test_settings_replay_is_exact_and_stale_version_cannot_overwrite(manager):
    client,_=manager;first=save(client);assert first.status_code==200
    assert save(client).json()==first.json()
    assert save(client,sheet_name='Иное').status_code==409
    assert save(client,key='stale',sheet_name='Иное').status_code==409
    second=save(client,key='new',expected_version=1,sheet_name='Обновлённый журнал')
    assert second.status_code==200 and second.json()['version']==2
    assert client.get(PATH).json()['sheet_name']=='Обновлённый журнал'
    assert AuditEvent.objects.filter(action='imports.source.save').count()==2
    assert CommandReceipt.objects.filter(action='imports.source.save').count()==2


@pytest.mark.parametrize('changes',[
    {'url':'http://docs.google.com/spreadsheets/d/DEMO_new_sheet_123/edit'},
    {'url':'https://docs.google.com.other.invalid/spreadsheets/d/DEMO_new_sheet_123/edit'},
    {'url':'https://docs.google.com/spreadsheets/d/short/edit'},
    {'gid':'1&other=2'},{'sheet_name':' '},{'expected_version':-1},{'unexpected':True},
])
def test_invalid_source_settings_never_change_configuration(manager,changes):
    client,_=manager
    assert save(client,**changes).status_code==400
    assert client.get(PATH).json()['version']==0
    assert not AuditEvent.objects.filter(action='imports.source.save').exists()
    assert not CommandReceipt.objects.filter(action='imports.source.save').exists()


def test_settings_need_an_idempotency_key(manager):
    client,_=manager
    assert save(client,key=None).status_code==400
    assert client.get(PATH).json()['version']==0


def test_audit_failure_rolls_back_the_first_setting(manager,monkeypatch):
    client,_=manager
    from apps.imports import source_settings
    def fail(*args,**kwargs):raise RuntimeError('Audit unavailable')
    monkeypatch.setattr(source_settings,'audit',fail)
    with pytest.raises(RuntimeError):save(client)
    assert not apps.get_model('imports','JournalSourceSettings').objects.exists()
    assert not CommandReceipt.objects.filter(action='imports.source.save').exists()


def test_saved_source_rejects_prepared_preview_from_previous_table(manager,grant):
    client,actor=manager;grant(actor,'imports.results.view');grant(actor,'imports.preview')
    assert save(client).status_code==200
    response=client.post('/api/v1/imports/google-preview/',{'spreadsheet_id':'DEMO_old_sheet_123','gid':'0','reason':'Old prepared request'},content_type='application/json',HTTP_IDEMPOTENCY_KEY='old-preview')
    assert response.status_code==409


def test_source_permission_is_available_in_role_editor(manager,grant):
    client,actor=manager;grant(actor,'access.roles.manage')
    catalogue=client.get('/api/v1/permissions/');assert catalogue.status_code==200
    permission=next(item for item in catalogue.json() if item['code']==PERMISSION)
    assert permission['scopes']==['institution']
    response=client.post('/api/v1/roles/',{'name':'Источник журнала','permissions':[{'permission_code':PERMISSION,'scope':'institution'}]},content_type='application/json')
    assert response.status_code==201
    assert response.json()['permissions']==[{'permission_code':PERMISSION,'scope':'institution'}]
