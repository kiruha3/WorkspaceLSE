import uuid
import pytest
from django.test import Client
from apps.references.models import Department,Specialty
from apps.audit.models import AuditEvent

pytestmark=pytest.mark.django_db

def access(employee_factory,grant,*codes):
    actor=employee_factory()
    assignments=[grant(actor,code)[1] for code in codes]
    client=Client();client.force_login(actor.user)
    return client,actor,assignments

def test_authority_type_group_is_explicit_and_only_that_catalog_accepts_it(employee_factory,grant):
    client,_,_=access(employee_factory,grant,'references.manage')
    response=client.post('/api/v1/references/authority-types/',{'code':'test_court','name':'Тестовый тип органа','report_group':'court'},content_type='application/json')
    assert response.status_code==201,response.content
    data=response.json();assert data['report_group']=='court'
    assert client.patch(f"/api/v1/references/authority-types/{data['id']}/",{'expected_version':1,'report_group':None},content_type='application/json').json()['report_group'] is None
    assert client.post('/api/v1/references/authority-types/',{'code':'bad','name':'Ошибочная группа','report_group':'guess'},content_type='application/json').status_code==400
    assert client.post('/api/v1/references/specialties/',{'code':'99.1','name':'Не тип органа','report_group':'court'},content_type='application/json').status_code==400

def test_catalogue_create_and_patch_with_keys_are_repeatable_without_duplicate_audit(employee_factory,grant):
    client,actor,_=access(employee_factory,grant,'references.manage')
    body={'code':'99.1','name':'ДЕМО · специальность'};key=str(uuid.uuid4())
    first=client.post('/api/v1/references/specialties/',body,content_type='application/json',HTTP_IDEMPOTENCY_KEY=key)
    second=client.post('/api/v1/references/specialties/',body,content_type='application/json',HTTP_IDEMPOTENCY_KEY=key)
    assert first.status_code==second.status_code==201 and first.json()['id']==second.json()['id']
    assert Specialty.objects.filter(code='99.1').count()==1
    pk=first.json()['id'];url=f'/api/v1/references/specialties/{pk}/';change={'expected_version':1,'name':'Уточнённая специальность','is_active':False};patch_key=str(uuid.uuid4())
    a=client.patch(url,change,content_type='application/json',HTTP_IDEMPOTENCY_KEY=patch_key);b=client.patch(url,change,content_type='application/json',HTTP_IDEMPOTENCY_KEY=patch_key)
    assert a.status_code==b.status_code==200 and b.json()['version']==2 and not b.json()['is_active']
    assert AuditEvent.objects.filter(actor=actor.user,object_id=pk).count()==2
    changed={**change,'name':'Другое значение'}
    assert client.patch(url,changed,content_type='application/json',HTTP_IDEMPOTENCY_KEY=patch_key).status_code==409
    assert client.patch(url,change,content_type='application/json',HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4())).status_code==409

def test_ref_replay_rechecks_manage_permission(employee_factory,grant):
    client,_,assignments=access(employee_factory,grant,'references.manage')
    body={'code':'99.1','name':'ДЕМО · справочник'};key=str(uuid.uuid4());path='/api/v1/references/specialties/'
    assert client.post(path,body,content_type='application/json',HTTP_IDEMPOTENCY_KEY=key).status_code==201
    assignment=assignments[0];assignment.is_active=False;assignment.save()
    assert client.post(path,body,content_type='application/json',HTTP_IDEMPOTENCY_KEY=key).status_code==403
    assert Specialty.objects.filter(code='99.1').count()==1

def test_history_requires_catalogue_rights_not_only_options_and_shows_before_after(employee_factory,grant):
    client,_,_=access(employee_factory,grant,'references.manage')
    item=client.post('/api/v1/references/specialties/',{'code':'99.1','name':'Первое имя'},content_type='application/json').json()
    url=f"/api/v1/references/specialties/{item['id']}/"
    assert client.patch(url,{'expected_version':1,'name':'Второе имя'},content_type='application/json').status_code==200
    history=client.get(url+'history/');assert history.status_code==200,history.content
    assert len(history.json())==2 and history.json()[0]['changes']['before']['name']=='Первое имя'
    assert history.json()[0]['changes']['after']['name']=='Второе имя'
    reader,_,_=access(employee_factory,grant,'expertise.view')
    assert reader.get('/api/v1/references/authority-types/').status_code==200
    assert reader.get(url+'history/').status_code==403
    viewer,_,_=access(employee_factory,grant,'references.view')
    assert viewer.get(url+'history/').status_code==200
    assert viewer.patch(url,{'expected_version':2,'is_active':False},content_type='application/json').status_code==403

def test_successful_journal_receipt_survives_department_deactivation_but_new_selection_does_not(employee_factory,grant):
    client,_,_=access(employee_factory,grant,'references.manage');dept=Department.objects.create(code='3',name='Отдел3')
    data={'code':'IN','name':'Входящие','direction':'incoming','department_id':str(dept.pk)};key=str(uuid.uuid4());path='/api/v1/references/letter-journals/'
    first=client.post(path,data,content_type='application/json',HTTP_IDEMPOTENCY_KEY=key);assert first.status_code==201
    dept.is_active=False;dept.save()
    replay=client.post(path,data,content_type='application/json',HTTP_IDEMPOTENCY_KEY=key)
    assert replay.status_code==201 and replay.json()['id']==first.json()['id']
    assert client.post(path,{**data,'code':'NEW'},content_type='application/json',HTTP_IDEMPOTENCY_KEY='new-journal').status_code==400

def test_legacy_reference_clients_without_keys_still_work_and_codes_remain_immutable(employee_factory,grant):
    client,_,_=access(employee_factory,grant,'references.manage')
    response=client.post('/api/v1/references/specialties/',{'code':'99.1','name':'ДЕМО'},content_type='application/json');assert response.status_code==201
    url=f"/api/v1/references/specialties/{response.json()['id']}/"
    assert client.patch(url,{'expected_version':1,'code':'new'},content_type='application/json').status_code==400
    assert client.delete(url).status_code==405
