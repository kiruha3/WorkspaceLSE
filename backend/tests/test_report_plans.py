"""Annual plans are real audited records; missing is not zero."""
import uuid
import pytest
from django.apps import apps
from django.test import Client
from apps.audit.models import AuditEvent
from apps.documents.models import Document
from apps.references.models import Specialty,Department
pytestmark=pytest.mark.django_db


def plan_models():return tuple(apps.get_model('reports',name) for name in ('StateAssignmentPlan','StateAssignmentPlanLine','StateAssignmentPlanRevision'))
def client_for(employee):
 client=Client();client.force_login(employee.user);return client
def setup(employee_factory,grant):
 actor=employee_factory()
 for code in ('reports.plans.manage','reports.form151.run','expertise.view','documents.view'):grant(actor,code)
 return client_for(actor),actor
def body(**changes):return {'expected_version':0,'reason':'ДЕМО · сверено с утверждённым планом','total':None,'basis_text':'ДЕМО · контрольное основание','document_id':None,'lines':[],**changes}
def line(specialty,count):return {'specialty_id':str(specialty.pk),'count':count}
def send(client,data=None,*,year=2027,key=None):return client.post(f'/api/v1/report-plans/{year}/',data or body(),content_type='application/json',HTTP_IDEMPOTENCY_KEY=key or str(uuid.uuid4()))
def read(client,year=2027):
 response=client.get(f'/api/v1/report-plans/{year}/');assert response.status_code==200,response.content[:500]
 return response.json()


def test_unknown_year_read_creates_nothing_and_seed_has_no_invented_allocation(employee_factory,grant):
 client,_=setup(employee_factory,grant);unknown=read(client)
 assert unknown['id'] is None and unknown['version']==0 and unknown['year']==2027 and unknown['total'] is None and unknown['lines']==[] and unknown['can_edit']
 Plan,Line,Revision=plan_models();assert Plan.objects.count()==1 and Line.objects.count()==0 and Revision.objects.count()==1
 seeded=read(client,2026);assert seeded['total']==294 and seeded['version']==1 and seeded['lines']==[]
 assert seeded['revisions'][0]['actor'] is None and seeded['revisions'][0]['after']['total']==294


def test_create_edit_keeps_unknown_and_zero_distinct_with_audit_and_full_history(employee_factory,grant):
 client,actor=setup(employee_factory,grant);a=Specialty.objects.create(code='1.1',name='Почерковедческая');b=Specialty.objects.create(code='16.1',name='Строительная')
 response=send(client,body(total=10,lines=[line(a,0),line(b,None)]));assert response.status_code==200,response.content
 saved=response.json();assert saved['year']==2027 and saved['version']==1 and saved['total']==10
 assert {item['specialty']['code']:item['count'] for item in saved['lines']}=={'1.1':0,'16.1':None}
 response=send(client,body(expected_version=1,total=None,lines=[line(a,None),line(b,5)]));assert response.status_code==200,response.content
 edited=response.json();assert edited['id']==saved['id'] and edited['version']==2 and edited['total'] is None
 revision=edited['revisions'][-1];assert revision['actor']['id']==str(actor.user_id) and revision['before']['total']==10 and revision['after']['total'] is None
 assert read(client)==edited and AuditEvent.objects.filter(action='reports.plan.save').count()==2


@pytest.mark.parametrize('change',[{'extra':1},{'reason':''},{'total':-1},{'total':1.5},{'total':2147483648},{'expected_version':-1},{'total':True},{'total':5,'basis_text':''}])
def test_invalid_plan_does_not_leave_an_empty_year_or_revision(employee_factory,grant,change):
 client,_=setup(employee_factory,grant);response=send(client,body(**change));assert response.status_code==400,response.content
 Plan,Line,Revision=plan_models();assert not Plan.objects.filter(year=2027).exists() and Line.objects.count()==0 and Revision.objects.count()==1


@pytest.mark.parametrize('year',[1899,2201])
def test_year_outside_report_range_is_rejected(employee_factory,grant,year):
 client,_=setup(employee_factory,grant);assert send(client,year=year).status_code==400 and client.get(f'/api/v1/report-plans/{year}/').status_code==400


def test_line_validation_membership_bounds_and_partial_known_sum(employee_factory,grant):
 client,_=setup(employee_factory,grant);a=Specialty.objects.create(code='16.1',name='Строительная');b=Specialty.objects.create(code='16.2',name='Оценочная')
 for entries,total in (([line(a,1),line(a,1)],5),([line(a,-1)],5),([line(a,1.5)],5),([line(a,2147483648)],None),([line(a,3),line(b,3)],5),([line(a,0)]*1001,None)):
  assert send(client,body(total=total,lines=entries)).status_code==400
 assert send(client,body(total=10,lines=[line(a,3),line(b,None)])).status_code==200
 assert read(client)['total']==10


def test_replay_exact_packet_stale_version_and_revoked_current_right(employee_factory,grant):
 client,actor=setup(employee_factory,grant);data=body(total=10)
 first=send(client,data,key='same-plan');assert first.status_code==200,first.content
 assert send(client,data,key='same-plan').json()['version']==1
 assert send(client,data,key='different-key').status_code==409
 assert send(client,{**data,'total':11},key='same-plan').status_code==409
 actor.role_assignments.filter(role__permissions__permission_code='reports.plans.manage').update(is_active=False)
 assert send(client,data,key='same-plan').status_code==403 and read(client)['can_edit'] is False
 Plan,_,Revision=plan_models();assert Plan.objects.get(year=2027).version==1 and Revision.objects.filter(plan__year=2027).count()==1


def test_reference_restoration_retains_inactive_history_but_rejects_new_inactive(employee_factory,grant):
 client,_=setup(employee_factory,grant);specialty=Specialty.objects.create(code='16.1',name='Строительная')
 assert send(client,body(total=10,lines=[line(specialty,3)])).status_code==200
 Specialty.objects.filter(pk=specialty.pk).update(is_active=False)
 assert send(client,body(expected_version=1,total=10)).status_code==200
 data=read(client);assert str(specialty.pk) in data['retained_specialty_ids'] and any(s['id']==str(specialty.pk) for s in data['specialties'])
 assert send(client,body(expected_version=2,total=10,lines=[line(specialty,3)])).status_code==200
 other=Specialty.objects.create(code='inactive',name='Не использовалась',is_active=False)
 assert send(client,body(expected_version=3,total=10,lines=[line(other,3)])).status_code==400


def test_doc_file_and_permission_are_checked_even_on_replay_and_read_is_restricted(employee_factory,grant,settings,tmp_path):
 from test_basis_documents import upload
 settings.MEDIA_ROOT=tmp_path
 client,actor=setup(employee_factory,grant);grant(actor,'documents.upload');doc=Document.objects.create(kind='letter',source_kind='uploaded_copy',created_by=actor)
 data=body(total=10,basis_text='',document_id=str(doc.pk));assert send(client,data).status_code==400
 assert upload(client,str(doc.pk)).status_code==201
 result=send(client,data,key='document-plan');assert result.status_code==200,result.content
 assert result.json()['document']['versions']
 actor.role_assignments.filter(role__permissions__permission_code='documents.view').update(is_active=False)
 assert send(client,data,key='document-plan').status_code==403
 assert read(client)['document']['restricted'] is True


@pytest.mark.parametrize('permission',['references.view','references.manage','reports.form151.run'])
def test_existing_read_permissions_do_not_grant_write(employee_factory,grant,permission):
 actor=employee_factory();grant(actor,permission);client=client_for(actor)
 assert read(client,2026)['can_edit'] is False and send(client).status_code==403


def test_department_or_own_reporting_scope_cannot_read_institutional_plan(employee_factory,grant):
 department=Department.objects.create(code='3',name='Отдел3')
 for scope in ('own','departments'):
  actor=employee_factory(department=department);grant(actor,'reports.form151.run',scope,departments=[department]);client=client_for(actor)
  assert client.get('/api/v1/report-plans/2026/').status_code==403 and send(client).status_code==403
