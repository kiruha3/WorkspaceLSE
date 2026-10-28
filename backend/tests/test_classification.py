from copy import deepcopy
import uuid
import pytest
from django.test import Client
from apps.accounts.models import CommandReceipt
from apps.audit.models import AuditEvent
from apps.documents.models import Document
from apps.expertises.models import Expertise,HistoricalParticipant
from test_case_details import setup,counts

pytestmark=pytest.mark.django_db
def previous(**changes):return {'reference':'ДЕМО №12 от известной даты','organization_name':'ДЕМО · учреждение','organization_group':'ministry','same_input_data':True,'confirms_previous':False,'document_id':None,**changes}
def body(work,**changes):return {'expected_version':work.version,'reason':'Подтверждено назначением и предыдущими заключениями','appointment_nature':'repeated','previous_complete':True,'previous_conclusions':[previous()],**changes}
def send(client,work,data=None,key=None):return client.post(f'/api/v1/expertises/{work.pk}/classification/',data or body(work),content_type='application/json',HTTP_IDEMPOTENCY_KEY=key or str(uuid.uuid4()))
def state(work):return client_state(work)
def client_state(work):
 work.refresh_from_db();return (work.registration_number,work.department_id,work.is_commission,work.complex_group_id,work.state,work.receipt_id,work.historical.source_row_id)

def test_read_does_not_invent_primary_or_create_profile(employee_factory,grant,settings,tmp_path):
 client,_,work,_,_,_=setup(employee_factory,grant,settings,tmp_path)
 result=client.get(f'/api/v1/expertises/{work.pk}/');assert result.status_code==200
 data=result.json()['classification'];assert data['previous_complete'] is False and data['previous_conclusions']==[] and data['revisions']==[] and data['can_edit']
 assert result.json()['appointment_nature'] is None
 options=client.get(f'/api/v1/expertises/{work.pk}/classification/');assert options.status_code==200
 assert [g['code'] for g in options.json()['organization_groups']]==['ministry','other_state','other']

def test_atomic_nature_previous_facts_history_and_registration_identity(employee_factory,grant,settings,tmp_path):
 client,actor,work,h,dept,_=setup(employee_factory,grant,settings,tmp_path)
 baseline=state(work);before=counts();raw=deepcopy(h.source_row.raw);facts=deepcopy(h.source_row.facts)
 result=send(client,work);assert result.status_code==200,result.content
 value=result.json()['expertise'];profile=value['classification'];assert value['appointment_nature']=='repeated' and value['version']==2
 assert profile['previous_complete'] and len(profile['previous_conclusions'])==1 and profile['previous_conclusions'][0]['confirms_previous'] is False
 revision=profile['revisions'][0];assert revision['actor']['id']==str(actor.user_id) and revision['before']['appointment_nature'] is None and revision['after']['appointment_nature']=='repeated'
 assert revision['after']['department_id']==str(dept.pk) and revision['after']['department_code']=='4' and revision['after']['registration_department_code']=='4'
 assert state(work)==baseline and counts()==before and h.source_row.raw==raw and h.source_row.facts==facts
 assert AuditEvent.objects.filter(action='expertise.classification.save').count()==1
 assert client.get(f'/api/v1/expertises/{work.pk}/').json()['classification']==profile

@pytest.mark.parametrize('change',[
 {'appointment_nature':'unknown'}, {'extra':'rejected'}, {'previous_complete':True,'previous_conclusions':[]},
 {'previous_conclusions':[previous(reference='')]}, {'previous_conclusions':[previous(organization_group='court')]},
 {'previous_conclusions':[previous(confirms_previous='nonsense')]}, {'previous_conclusions':[previous(extra=1)]},
 {'previous_conclusions':[previous()]*101}, {'previous_complete':None}, {'reason':''},
])
def test_strict_invalid_data_rolls_back(employee_factory,grant,settings,tmp_path,change):
 client,_,work,_,_,_=setup(employee_factory,grant,settings,tmp_path);before=counts()
 response=send(client,work,body(work,**change));assert response.status_code==400,response.content
 work.refresh_from_db();assert work.version==1 and work.appointment_nature is None and counts()==before
 assert not AuditEvent.objects.filter(action='expertise.classification.save').exists()

def test_partial_list_and_unknown_flags_stay_unknown_and_can_be_cleared(employee_factory,grant,settings,tmp_path):
 client,_,work,_,_,_=setup(employee_factory,grant,settings,tmp_path)
 response=send(client,work,body(work,previous_complete=False,previous_conclusions=[previous(organization_group=None,same_input_data=None,confirms_previous=None)]));assert response.status_code==200,response.content
 entry=response.json()['expertise']['classification']['previous_conclusions'][0];assert entry['organization_group'] is None and entry['same_input_data'] is None and entry['confirms_previous'] is None
 work.refresh_from_db();response=send(client,work,body(work,appointment_nature=None,previous_complete=False,previous_conclusions=[]));assert response.status_code==200
 data=response.json()['expertise'];assert data['appointment_nature'] is None and data['classification']['previous_conclusions']==[] and len(data['classification']['revisions'])==2

def test_native_cannot_become_unknown_and_preserves_accepted_result(employee_factory,grant,settings,tmp_path):
 client,_,work,_,_,_=setup(employee_factory,grant,settings,tmp_path)
 work.origin_kind='native';work.appointment_nature='primary';work.is_commission=False;work.save()
 assert send(client,work,body(work,appointment_nature=None,previous_complete=False)).status_code==400
 assert send(client,work).status_code==200

def test_idempotence_current_rights_conflicts_and_key_body_identity(employee_factory,grant,settings,tmp_path):
 client,actor,work,_,_,_=setup(employee_factory,grant,settings,tmp_path);data=body(work)
 first=send(client,work,data,'same');assert first.status_code==200,first.content
 assert send(client,work,data,'same').json()['event']==first.json()['event']
 assert send(client,work,data,'different').status_code==409
 assert send(client,work,{**data,'reason':'Другой пакет'},'same').status_code==409
 from apps.accounts.models import RolePermission
 actor.role_assignments.filter(role__permissions__permission_code='expertise.closed.correct').update(is_active=False)
 assert send(client,work,data,'same').status_code==403
 assert AuditEvent.objects.filter(action='expertise.classification.save').count()==1

def test_current_document_permission_is_checked_on_replay(employee_factory,grant,settings,tmp_path):
 client,actor,work,_,_,_=setup(employee_factory,grant,settings,tmp_path)
 document=Document.objects.create(kind='expert_conclusion',title='ДЕМО · предыдущее',source_kind='paper_original',created_by=actor)
 data=body(work,previous_conclusions=[previous(document_id=str(document.pk))]);first=send(client,work,data,'evidence');assert first.status_code==200,first.content
 from apps.accounts.models import RolePermission
 RolePermission.objects.filter(permission_code='documents.view').delete()
 assert send(client,work,data,'evidence').status_code==403

def test_copy_requires_file_and_foreign_document_is_denied(employee_factory,grant,settings,tmp_path):
 client,actor,work,_,dept,_=setup(employee_factory,grant,settings,tmp_path)
 document=Document.objects.create(kind='expert_conclusion',source_kind='uploaded_copy',created_by=actor)
 assert send(client,work,body(work,previous_conclusions=[previous(document_id=str(document.pk))])).status_code==400
 other=employee_factory();foreign=Document.objects.create(kind='expert_conclusion',source_kind='paper_original',created_by=other)
 from apps.accounts.models import RolePermission
 RolePermission.objects.filter(permission_code='documents.view').delete();grant(actor,'documents.view',scope='own')
 assert send(client,work,body(work,previous_conclusions=[previous(document_id=str(foreign.pk))])).status_code==403

def test_exact_previous_document_is_shared_with_historical_participant_only(employee_factory,grant,settings,tmp_path):
 client,actor,work,history,_,_=setup(employee_factory,grant,settings,tmp_path)
 document=Document.objects.create(kind='expert_conclusion',source_kind='paper_original',created_by=actor)
 unrelated=Document.objects.create(kind='expert_conclusion',source_kind='paper_original',created_by=actor)
 assert send(client,work,body(work,previous_conclusions=[previous(document_id=str(document.pk))])).status_code==200
 participant=employee_factory();HistoricalParticipant.objects.create(history=history,employee=participant)
 grant(participant,'expertise.view',scope='own');grant(participant,'documents.view',scope='own');viewer=Client();viewer.force_login(participant.user)
 data=viewer.get(f'/api/v1/expertises/{work.pk}/').json()['classification'];assert 'restricted' not in data['previous_conclusions'][0]['document']
 assert viewer.get(f'/api/v1/documents/{unrelated.pk}/').status_code==403

def test_factual_department_snapshot_is_independent_of_number(employee_factory,grant,settings,tmp_path):
 client,_,work,_,_,_=setup(employee_factory,grant,settings,tmp_path)
 from apps.references.models import Department
 actual=Department.objects.create(code='3',name='Текущий фактический');work.department=actual;work.save(update_fields=['department'])
 response=send(client,work);assert response.status_code==200,response.content
 snapshot=response.json()['expertise']['classification']['revisions'][0]['after'];assert snapshot['department_code']=='3' and snapshot['registration_department_code']=='4'

def test_profile_blocks_new_source_even_without_scalar_difference(employee_factory,grant,settings,tmp_path):
 # Covered using the same real update-preview boundary below, no mocked policy.
 from apps.imports.updates import update_preview
 client,_,work,history,_,_=setup(employee_factory,grant,settings,tmp_path)
 response=send(client,work,body(work,appointment_nature=None,previous_complete=False,previous_conclusions=[]));assert response.status_code==200,response.content
 preview=update_preview(history.source_row,work)
 assert any('классификац' in blocker.lower() for blocker in preview['blockers'])

@pytest.mark.parametrize('scope',['own','departments','institution'])
def test_open_update_scope_does_not_make_an_unrelated_employee_an_executor(employee_factory,grant,settings,tmp_path,scope):
 from historical_samples import historical_setup
 client,actor,work,history,department,_=historical_setup(employee_factory,grant,settings,tmp_path,state='in_progress',ended=None)
 grant(actor,'expertise.work.update',scope,departments=[department]);HistoricalParticipant.objects.create(history=history,employee=actor)
 assert send(client,work).status_code==200
 outsider=employee_factory();grant(outsider,'expertise.view');grant(outsider,'expertise.work.update','own');other=Client();other.force_login(outsider.user);work.refresh_from_db()
 assert send(other,work).status_code==403
 assert other.get(f'/api/v1/expertises/{work.pk}/').json()['classification']['can_edit'] is False

def test_activation_preserves_classification_and_does_not_silently_replace_nature(employee_factory,grant,settings,tmp_path):
 from activation_samples import activation_setup,activation_body,activate
 client,actor,work,_,_,specialty,basis=activation_setup(employee_factory,grant,settings,tmp_path,state='in_progress',ended=None);grant(actor,'expertise.work.update')
 assert send(client,work).status_code==200
 assert activate(client,work,activation_body(basis,specialty,expected_version=2)).status_code==400
 accepted=activate(client,work,activation_body(basis,specialty,expected_version=2,appointment_nature='repeated'),key='retain-repeat');assert accepted.status_code==200,accepted.content
 data=accepted.json()['expertise'];assert data['appointment_nature']=='repeated' and len(data['classification']['previous_conclusions'])==1 and len(data['classification']['revisions'])==1

def test_classification_after_physical_issue_does_not_reissue_or_create_closure(employee_factory,grant,settings,tmp_path):
 from datetime import date
 from apps.issuance.models import IssuePackage,PackageRevision,PackageCheck,MaterialIssue
 from apps.references.models import IssueMethod
 from apps.expertises.models import WorkClosure
 client,actor,work,history,_,_=setup(employee_factory,grant,settings,tmp_path)
 package=IssuePackage.objects.create(material=work.material,created_by=actor.user)
 revision=PackageRevision.objects.create(package=package,number=1,actor=actor.user,reason='ДЕМО · комплект')
 check=PackageCheck.objects.create(package=package,revision=revision,actor=actor.user,reason='ДЕМО · проверка')
 method=IssueMethod.objects.create(code='demo',name='ДЕМО · передача')
 issue=MaterialIssue.objects.create(package=package,package_check=check,issued_on='2026-10-09',method=method,recipient_name='ДЕМО',recipient_basis='ДЕМО',actor=actor.user,reason='ДЕМО · выдача')
 assert send(client,work).status_code==200
 issue.refresh_from_db();work.refresh_from_db();history.refresh_from_db()
 assert issue.issued_on==date(2026,10,9) and MaterialIssue.objects.count()==1
 assert work.state=='completed' and history.completed_on==date(2026,10,6) and not WorkClosure.objects.exists()
