"""Test-only runtime must never point a browser exercise at working data."""
import io
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from infra.acceptance import checked_database_name, prepare, runtime_env
from infra.acceptance_static import spa_application


@pytest.mark.parametrize('name',['ais_lse','test_ais_lse','postgres','ais_lse_acceptance_','ais_lse_acceptance_bad;drop','../ais_lse_acceptance_x'])
def test_database_guard_rejects_live_or_unscoped_names(name):
    with pytest.raises(ValueError):checked_database_name(name)


def test_runtime_environment_selects_only_isolated_database_and_no_google(monkeypatch):
    monkeypatch.setenv('AIS_JOURNAL_GOOGLE_ID','working-source')
    config={'host':'127.0.0.1','port':55432,'dbname':'ais_lse','user':'owner','password':'local-db-secret',
        'django_secret':'working-django-secret','journal_source':{'spreadsheet_id':'working-source'}}
    state={'database':'ais_lse_acceptance_example','django_secret':'isolated-secret'}
    env=runtime_env(config,state)
    assert env['PGDATABASE']=='ais_lse_acceptance_example' and env['PGHOST']=='127.0.0.1'
    assert env['DJANGO_SECRET_KEY']=='isolated-secret'
    assert env['AIS_JOURNAL_GOOGLE_ID']==''
    assert env['AIS_JOURNAL_GOOGLE_GID']=='' and env['AIS_JOURNAL_GOOGLE_SHEET_NAME']==''
    assert config['dbname']=='ais_lse' and config['journal_source']['spreadsheet_id']=='working-source'
    with pytest.raises(ValueError):runtime_env(config,dict(state,database='ais_lse'))
    with pytest.raises(ValueError):runtime_env(dict(config,host='remote.example'),state)


def test_prepare_refuses_existing_state_before_reading_credentials(tmp_path):
    state=tmp_path/'state.json';state.write_bytes(b'original-state')
    with pytest.raises(FileExistsError):prepare(state_path=state,config_path=tmp_path/'absent-config.json')
    assert state.read_bytes()==b'original-state'


def test_prepare_cannot_overwrite_state_created_between_check_and_write(tmp_path,monkeypatch):
    import json
    import psycopg
    from infra import acceptance
    monkeypatch.setattr(acceptance,'ROOT',tmp_path)
    state=tmp_path/'.runtime/cross-role-acceptance-race/state.json'
    config=tmp_path/'config.json';config.write_text(json.dumps({'host':'127.0.0.1','port':55432,'user':'fixture','password':'fixture'}))
    mkdir=Path.mkdir
    def concurrent_create(path,*args,**kwargs):
        result=mkdir(path,*args,**kwargs)
        if path==state.parent:state.write_bytes(b'other-operator-state')
        return result
    monkeypatch.setattr(Path,'mkdir',concurrent_create)
    def unexpected_connection(**kwargs):raise AssertionError('Must reject existing state before connecting')
    monkeypatch.setattr(psycopg,'connect',unexpected_connection)
    with pytest.raises(FileExistsError):prepare(state_path=state,config_path=config)
    assert state.read_bytes()==b'other-operator-state'


def test_serve_refuses_media_redirect_before_reading_database_credentials(tmp_path,monkeypatch):
    import json
    from infra import acceptance
    monkeypatch.setattr(acceptance,'ROOT',tmp_path)
    state=tmp_path/'.runtime/cross-role-acceptance-media/state.json';state.parent.mkdir(parents=True)
    state.write_text(json.dumps({'database':'ais_lse_acceptance_fixture','status':'ready','media':str(tmp_path/'media')}))
    with pytest.raises(ValueError):acceptance.serve(state)


def call(app,path,method='GET'):
    response={}
    def start(status,headers,exc_info=None):response.update(status=status,headers=dict(headers))
    output=app({'PATH_INFO':path,'REQUEST_METHOD':method,'wsgi.input':io.BytesIO()},start)
    try:response['body']=b''.join(output)
    finally:
        if hasattr(output,'close'):output.close()
    return response


@pytest.fixture
def spa(tmp_path):
    dist=tmp_path/'dist';dist.mkdir();(dist/'index.html').write_bytes(b'<html>Real compiled app</html>')
    (dist/'assets').mkdir();(dist/'assets/app.js').write_bytes(b'console.log("real asset")')
    (tmp_path/'private.txt').write_bytes(b'private outside dist')
    def api(env,start):start('404 Not Found',[('Content-Type','application/json')]);return [b'{"code":"not_found"}']
    return spa_application(api,dist)


@pytest.mark.parametrize('path',['/api','/api/v1/unknown/'])
def test_spa_fallback_never_masks_api_404(spa,path):
    value=call(spa,path)
    assert value['status']=='404 Not Found' and value['body']==b'{"code":"not_found"}'
    assert value['headers']['Content-Type']=='application/json'


def test_deep_client_route_and_existing_asset_are_served(spa):
    page=call(spa,'/expertises/example/documents')
    assert page['status']=='200 OK' and page['body']==b'<html>Real compiled app</html>'
    assert page['headers']['Content-Type'].startswith('text/html')
    asset=call(spa,'/assets/app.js')
    assert asset['status']=='200 OK' and asset['body']==b'console.log("real asset")'
    assert 'javascript' in asset['headers']['Content-Type']
    assert call(spa,'/assets/app.js','HEAD')['body']==b''


@pytest.mark.parametrize('path',['/assets/missing.js','/assets/../../private.txt','/assets/%2e%2e/%2e%2e/private.txt','/assets/..\\..\\private.txt','/assets/%00file'])
def test_missing_asset_and_path_escape_are_not_spa_or_private_file(spa,path):
    value=call(spa,path)
    assert value['status']=='404 Not Found'
    assert b'private outside dist' not in value['body'] and b'Real compiled app' not in value['body']


def test_missing_compiled_frontend_is_explicit(tmp_path):
    with pytest.raises(FileNotFoundError):spa_application(lambda e,s:[],tmp_path)


@pytest.mark.django_db
def test_identity_fixtures_do_not_create_ready_business_facts():
    from full_workflow_support import create_people
    from apps.intake.models import Receipt,Material
    from apps.expertises.models import Expertise,WorkClosure
    from apps.documents.models import Document
    from apps.personnel.models import EmployeeSpecialty
    from apps.correspondence.models import Letter
    from apps.issuance.models import IssuePackage
    models=(Receipt,Material,Expertise,WorkClosure,Document,Letter,IssuePackage)
    before=[model.objects.count() for model in models]
    world=create_people('Test-only-LongPassword9')
    assert [model.objects.count() for model in models]==before
    assert set(world['profiles'])=={'clerk','head','expert','expert2','trainee','hr','access','director'}
    assert EmployeeSpecialty.objects.get(employee_id=world['profiles']['trainee']['employee_id'],specialty_id=world['specialty']['id']).status=='training'
    assert EmployeeSpecialty.objects.get(employee_id=world['profiles']['head']['employee_id'],specialty_id=world['specialty']['id']).status=='qualified'


@pytest.mark.django_db
def test_identity_seeding_refuses_a_working_database_name(monkeypatch):
    from django.db import connection
    from full_workflow_support import create_people
    with monkeypatch.context() as patch:
        patch.setitem(connection.settings_dict,'NAME','ais_lse')
        with pytest.raises(ValueError):create_people('Test-only-LongPassword9')


@pytest.mark.django_db
def test_runtime_cookie_names_keep_working_browser_sessions_separate(settings,tmp_path,employee_factory):
    from infra.acceptance import apply_acceptance_settings
    from django.test import Client
    person=employee_factory()
    apply_acceptance_settings(settings,{'media':str(tmp_path)})
    browser=Client(enforce_csrf_checks=True)
    csrf=browser.get('/api/v1/auth/csrf/')
    assert 'acceptance_csrftoken' in csrf.cookies and 'csrftoken' not in csrf.cookies
    response=browser.post('/api/v1/auth/login/',{'username':person.user.username,'password':'Test-only-LongPassword9'},
        content_type='application/json',HTTP_X_CSRFTOKEN=csrf.json()['csrf_token'])
    assert response.status_code==200
    assert 'acceptance_sessionid' in response.cookies and 'sessionid' not in response.cookies
