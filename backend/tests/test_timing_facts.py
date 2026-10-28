from copy import deepcopy
from datetime import date
import uuid
import pytest
from django.apps import apps
from django.test import Client
from apps.audit.models import AuditEvent
from apps.documents.models import Document
from apps.expertises.models import HistoricalParticipant
from test_case_details import setup,counts
pytestmark=pytest.mark.django_db

def options(client,work):
 response=client.get(f'/api/v1/expertises/{work.pk}/timing/');assert response.status_code==200,response.content
 return response.json()
def entry(ref,**changes):return {'reason_id':ref['id'],'comment':'По материалам дела','document_id':None,**changes}
def body(work,**changes):return {'expected_version':work.version,'reason':'ДЕМО · сверено с документами срока','reasons_complete':False,'primary_reason_id':None,'reasons':[],
 'notification_sent':None,'notification_on':None,'notification_document_id':None,'extension_requested':None,'request_on':None,'request_document_id':None,
 'deadline_breached':None,'breach_basis':'','breach_document_id':None,**changes}
def send(client,work,data=None,key=None):return client.post(f'/api/v1/expertises/{work.pk}/timing/',data or body(work),content_type='application/json',HTTP_IDEMPOTENCY_KEY=key or str(uuid.uuid4()))
def refs(client,work):return {r['code']:r for r in options(client,work)['delay_reasons']}

def test_read_does_not_invent_negative_facts_or_profile(employee_factory,grant,settings,tmp_path):
 client,_,work,_,_,_=setup(employee_factory,grant,settings,tmp_path)
 data=client.get(f'/api/v1/expertises/{work.pk}/').json();assert 'timing' in data
 facts=data['timing'];assert facts['id'] is None and facts['reasons_complete'] is False and facts['reasons']==[]
 assert facts['notification_sent'] is None and facts['extension_requested'] is None and facts['deadline_breached'] is None
 assert not apps.get_model('expertises','WorkTimingFacts').objects.exists()
 assert set(refs(client,work))=={'research_complexity','large_material_volume','expert_workload','long_research_methods','appointing_party_deadline','other'}

def test_save_facts_documents_history_and_core_identity(employee_factory,grant,settings,tmp_path):
 client,actor,work,h,department,_=setup(employee_factory,grant,settings,tmp_path);reasons=refs(client,work)
 doc=Document.objects.create(kind='letter',source_kind='paper_original',created_by=actor)
 baseline=counts();identity=(work.registration_number,work.state,work.department_id,work.receipt_id,work.appointment_nature);raw=deepcopy(h.source_row.raw)
 data=body(work,reasons_complete=True,reasons=[entry(reasons['research_complexity'])],primary_reason_id=reasons['research_complexity']['id'],notification_sent=True,notification_on='2026-10-03',notification_document_id=str(doc.pk),extension_requested=True,request_on='2026-10-04',request_document_id=str(doc.pk),deadline_breached=False,breach_basis='Установленный срок соблюдён по документу',breach_document_id=str(doc.pk))
 result=send(client,work,data);assert result.status_code==200,result.content
 loaded=result.json()['expertise'];facts=loaded['timing'];assert loaded['version']==2 and facts['deadline_breached'] is False and facts['notification_sent'] is True
 assert facts['reasons'][0]['reason']['report_group']=='research_complexity' and facts['notification_document']['id']==str(doc.pk)
 revision=facts['revisions'][0];assert revision['actor']['id']==str(actor.user_id) and revision['before']['deadline_breached'] is None and revision['after']['deadline_breached'] is False
 assert revision['after']['department_id']==str(department.pk) and revision['after']['registration_number']==work.registration_number
 work.refresh_from_db();h.source_row.refresh_from_db();assert (work.registration_number,work.state,work.department_id,work.receipt_id,work.appointment_nature)==identity and counts()==baseline and h.source_row.raw==raw
 assert AuditEvent.objects.filter(action='expertise.timing.save').count()==1
 assert client.get(f'/api/v1/expertises/{work.pk}/').json()['timing']==facts

@pytest.mark.parametrize('change',[
 {'extra':1},{'reason':''},{'notification_sent':True},{'extension_requested':True},
 {'deadline_breached':True},{'deadline_breached':False,'breach_basis':'Нужен документ'},
 {'notification_sent':False,'notification_on':'2026-10-02'}, {'notification_on':'2099-01-01'}, {'request_on':'2026-09-01'},
 {'reasons_complete':None},
])
def test_invalid_facts_leave_no_partial_profile(employee_factory,grant,settings,tmp_path,change):
 client,_,work,_,_,_=setup(employee_factory,grant,settings,tmp_path)
 result=send(client,work,body(work,**change));assert result.status_code==400,result.content
 work.refresh_from_db();assert work.version==1 and not apps.get_model('expertises','WorkTimingFacts').objects.exists()

def test_unknown_date_of_confirmed_sending_is_retained_not_invented(employee_factory,grant,settings,tmp_path):
 client,actor,work,_,_,_=setup(employee_factory,grant,settings,tmp_path)
 doc=Document.objects.create(kind='letter',source_kind='paper_original',created_by=actor)
 result=send(client,work,body(work,notification_sent=True,notification_document_id=str(doc.pk)));assert result.status_code==200,result.content
 facts=result.json()['expertise']['timing'];assert facts['notification_sent'] is True and facts['notification_on'] is None

def test_reason_membership_duplicate_bounds_and_long_complete_list(employee_factory,grant,settings,tmp_path):
 client,_,work,_,_,_=setup(employee_factory,grant,settings,tmp_path);reasons=refs(client,work);one=reasons['research_complexity'];other=reasons['other']
 for change in ({'primary_reason_id':other['id'],'reasons':[entry(one)]},{'reasons':[entry(one)]*2},{'reasons':[entry(one)]*101}):
  assert send(client,work,body(work,**change)).status_code==400
 work.receipt.received_at=date(2026,8,1);work.receipt.save(update_fields=['received_at'])
 assert send(client,work,body(work,reasons_complete=True)).status_code==400
 assert send(client,work,body(work,reasons_complete=True,reasons=[entry(one)])).status_code==200

def test_replay_stale_body_identity_and_current_work_rights(employee_factory,grant,settings,tmp_path):
 client,actor,work,_,_,_=setup(employee_factory,grant,settings,tmp_path);data=body(work)
 first=send(client,work,data,'timing-same');assert first.status_code==200,first.content
 assert send(client,work,data,'timing-same').json()['event']==first.json()['event']
 assert send(client,work,data,'new-key').status_code==409
 assert send(client,work,{**data,'reason':'Другой пакет'},'timing-same').status_code==409
 actor.role_assignments.filter(role__permissions__permission_code='expertise.closed.correct').update(is_active=False)
 assert send(client,work,data,'timing-same').status_code==403
 assert AuditEvent.objects.filter(action='expertise.timing.save').count()==1

def test_inactive_reasons_are_retained_and_restorable_but_not_newly_selectable(employee_factory,grant,settings,tmp_path):
 client,_,work,_,_,_=setup(employee_factory,grant,settings,tmp_path);reasons=refs(client,work);reason=reasons['expert_workload']
 assert send(client,work,body(work,reasons=[entry(reason)])).status_code==200
 model=apps.get_model('references','DelayReason');model.objects.filter(pk=reason['id']).update(is_active=False)
 work.refresh_from_db();assert send(client,work,body(work)).status_code==200
 work.refresh_from_db();assert reason['id'] in options(client,work)['retained_reason_ids']
 assert send(client,work,body(work,reasons=[entry(reason)])).status_code==200
 forbidden=model.objects.create(code='not-used',name='Не использовалась',is_active=False,report_group=None);work.refresh_from_db()
 assert send(client,work,body(work,reasons=[entry({'id':str(forbidden.pk)})])).status_code==400

def test_document_permission_rechecked_on_replay_and_copy_requires_a_file(employee_factory,grant,settings,tmp_path):
 client,actor,work,_,_,_=setup(employee_factory,grant,settings,tmp_path)
 doc=Document.objects.create(kind='letter',source_kind='uploaded_copy',created_by=actor)
 data=body(work,notification_sent=True,notification_document_id=str(doc.pk));assert send(client,work,data).status_code==400
 from test_basis_documents import upload
 grant(actor,'documents.upload');assert upload(client,str(doc.pk)).status_code==201
 assert send(client,work,data,'doc-key').status_code==200
 actor.role_assignments.filter(role__permissions__permission_code='documents.view').update(is_active=False)
 assert send(client,work,data,'doc-key').status_code==403

def test_historical_participant_reads_only_exact_timing_evidence_and_profile_blocks_source(employee_factory,grant,settings,tmp_path):
 client,actor,work,history,_,_=setup(employee_factory,grant,settings,tmp_path)
 doc=Document.objects.create(kind='letter',source_kind='paper_original',created_by=actor);unrelated=Document.objects.create(kind='letter',source_kind='paper_original',created_by=actor)
 assert send(client,work,body(work,notification_sent=True,notification_document_id=str(doc.pk))).status_code==200
 reader=employee_factory();HistoricalParticipant.objects.create(history=history,employee=reader)
 grant(reader,'expertise.view','own');grant(reader,'documents.view','own');browser=Client();browser.force_login(reader.user)
 facts=browser.get(f'/api/v1/expertises/{work.pk}/').json()['timing'];assert 'restricted' not in facts['notification_document']
 assert browser.get(f'/api/v1/documents/{unrelated.pk}/').status_code==403
 from apps.imports.updates import update_preview
 work.refresh_from_db();assert any('срок' in b.lower() for b in update_preview(history.source_row,work)['blockers'])

def test_delay_reason_catalogue_supports_explicit_and_unknown_mapping(employee_factory,grant):
 actor=employee_factory();grant(actor,'references.manage');client=Client();client.force_login(actor.user)
 response=client.post('/api/v1/references/delay-reasons/',{'code':'custom','name':'Особая причина','report_group':'expert_workload'},content_type='application/json');assert response.status_code==201,response.content
 data=response.json();assert data['report_group']=='expert_workload'
 assert client.patch(f"/api/v1/references/delay-reasons/{data['id']}/",{'expected_version':1,'report_group':None},content_type='application/json').json()['report_group'] is None
 assert client.post('/api/v1/references/delay-reasons/',{'code':'bad','name':'Неизвестная группа','report_group':'guess'},content_type='application/json').status_code==400

@pytest.mark.parametrize('scope',['own','departments','institution'])
def test_open_scopes_and_unrelated_historical_employee(employee_factory,grant,settings,tmp_path,scope):
 from historical_samples import historical_setup
 client,actor,work,history,department,_=historical_setup(employee_factory,grant,settings,tmp_path,state='in_progress',ended=None)
 grant(actor,'expertise.work.update',scope,departments=[department]);HistoricalParticipant.objects.create(history=history,employee=actor)
 assert send(client,work).status_code==200
 outsider=employee_factory();grant(outsider,'expertise.view');grant(outsider,'expertise.work.update','own');browser=Client();browser.force_login(outsider.user);work.refresh_from_db()
 assert send(browser,work).status_code==403 and browser.get(f'/api/v1/expertises/{work.pk}/').json()['timing']['can_edit'] is False

def test_timing_facts_survive_history_activation_without_native_deadline_events(employee_factory,grant,settings,tmp_path):
 from activation_samples import activation_setup,activation_body,activate
 from apps.expertises.models import DeadlineEvent
 client,actor,work,_,_,specialty,basis=activation_setup(employee_factory,grant,settings,tmp_path,state='in_progress',ended=None);grant(actor,'expertise.work.update')
 assert send(client,work,body(work,notification_sent=False,extension_requested=False)).status_code==200
 response=activate(client,work,activation_body(basis,specialty,expected_version=2));assert response.status_code==200,response.content
 assert response.json()['expertise']['timing']['notification_sent'] is False and len(response.json()['expertise']['timing']['revisions'])==1
 assert not DeadlineEvent.objects.exists()

def test_metadata_after_physical_issue_does_not_issue_or_replace_accepted_result(employee_factory,grant,settings,tmp_path):
 from apps.issuance.models import IssuePackage,PackageRevision,PackageCheck,MaterialIssue
 from apps.references.models import IssueMethod
 client,actor,work,history,_,_=setup(employee_factory,grant,settings,tmp_path)
 package=IssuePackage.objects.create(material=work.material,created_by=actor.user)
 revision=PackageRevision.objects.create(package=package,number=1,actor=actor.user,reason='ДЕМО · комплект')
 check=PackageCheck.objects.create(package=package,revision=revision,actor=actor.user,reason='ДЕМО · проверка')
 method=IssueMethod.objects.create(code='demo',name='ДЕМО · передача')
 issue=MaterialIssue.objects.create(package=package,package_check=check,issued_on='2026-10-09',method=method,recipient_name='ДЕМО',recipient_basis='ДЕМО',actor=actor.user,reason='ДЕМО · выдача')
 assert send(client,work).status_code==200
 issue.refresh_from_db();work.refresh_from_db();history.refresh_from_db()
 assert issue.issued_on==date(2026,10,9) and MaterialIssue.objects.count()==1 and work.state=='completed' and history.completed_on==date(2026,10,6)
