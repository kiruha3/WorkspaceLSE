from copy import deepcopy
from datetime import date
from io import BytesIO
from zipfile import ZipFile
from xml.etree import ElementTree as ET
import uuid
import pytest
from django.test import Client
from apps.accounts.models import CommandReceipt
from apps.audit.models import AuditEvent
from apps.documents.models import Document
from apps.expertises.models import Expertise,HistoricalParticipant,ResultRevision,WorkClosure,ExpertAssignment,Suspension,DeadlineEvent
from apps.references.models import Department
from apps.reports.registry import calculate_registry
from historical_samples import historical_setup
from test_form151 import value

pytestmark=pytest.mark.django_db

def setup(employee_factory,grant,settings,tmp_path,**options):
    client,actor,work,history,dept,specialty=historical_setup(employee_factory,grant,settings,tmp_path,**options)
    grant(actor,'expertise.closed.correct');grant(actor,'expertise.work.update');grant(actor,'documents.view')
    return client,actor,work,history,dept,specialty

def body(work,**changes):
    return {'expected_version':work.version,'reason':'Сверено с постановлением и материалами','authority_type_id':None,'authority_name':'ДЕМО · назначивший орган','official':'ДЕМО · уполномоченное лицо','contact':'ДЕМО · служебный контакт','case_number':'ДЕМО-123','case_description':'ДЕМО · обстоятельства дела','basis_text':'ДЕМО · постановление','inventory':'ДЕМО · опись материалов','questions_text':'1. ДЕМО · поставленный вопрос','decree3214':None,'decree_document_id':None,'decree_basis':'',**changes}

def send(client,work,data=None,key=None):
    return client.post(f'/api/v1/expertises/{work.pk}/case-details/',data or body(work),content_type='application/json',HTTP_IDEMPOTENCY_KEY=key or str(uuid.uuid4()))

def counts():return {m.__name__:m.objects.count() for m in (Expertise,ResultRevision,WorkClosure,ExpertAssignment,Suspension,DeadlineEvent,Document)}

def authority(client,work,code='mvd'):
    response=client.get(f'/api/v1/expertises/{work.pk}/case-details/');assert response.status_code==200,response.content
    return next(item for item in response.json()['authority_types'] if item['code']==code)

def test_legacy_facts_are_read_without_implicitly_creating_a_profile(employee_factory,grant,settings,tmp_path):
    client,_,work,history,_,_=setup(employee_factory,grant,settings,tmp_path)
    history.authority_type='Органы МВД России';history.authority_name='Из исходного журнала';history.official='Исходное должностное лицо';history.save()
    response=client.get(f'/api/v1/expertises/{work.pk}/');assert response.status_code==200
    details=response.json()['case_details'];assert details['source']=='history' and details['authority_type'] is None and details['authority_type_raw']=='Органы МВД России'
    assert details['authority_name']=='Из исходного журнала' and details['case_number']=='' and details['decree3214'] is None and details['can_edit']
    options=client.get(f'/api/v1/expertises/{work.pk}/case-details/').json()
    assert options['initial_authority_type_id']==next(r['id'] for r in options['authority_types'] if r['code']=='mvd')
    from apps.expertises.models import WorkCaseDetails
    assert not WorkCaseDetails.objects.exists()

def test_save_current_case_facts_and_history_without_identity_or_native_event_changes(employee_factory,grant,settings,tmp_path):
    client,actor,work,history,_,_=setup(employee_factory,grant,settings,tmp_path)
    raw=deepcopy(history.source_row.raw);facts=deepcopy(history.source_row.facts);before=counts();identity=(work.registration_number,work.state,work.department_id,work.receipt_id,history.source_row_id)
    response=send(client,work,body(work,authority_type_id=authority(client,work)['id'],decree3214=False));assert response.status_code==200,response.content
    loaded=response.json()['expertise'];details=loaded['case_details'];assert details['source']=='typed' and details['authority_type']['report_group']=='mvd' and details['decree3214'] is False
    assert details['case_number']=='ДЕМО-123' and details['questions_text']=='1. ДЕМО · поставленный вопрос'
    assert details['revisions'][0]['actor']['id']==str(actor.user_id) and details['revisions'][0]['before']['decree3214'] is None and details['revisions'][0]['after']['decree3214'] is False
    work.refresh_from_db();history.source_row.refresh_from_db();assert work.version==2 and (work.registration_number,work.state,work.department_id,work.receipt_id,history.source_row_id)==identity
    assert counts()==before and history.source_row.raw==raw and history.source_row.facts==facts
    assert AuditEvent.objects.filter(action='expertise.case_details.save').count()==1
    assert client.get(f'/api/v1/expertises/{work.pk}/').json()['case_details']==details

def test_typed_unknown_does_not_fall_back_to_the_old_authority(employee_factory,grant,settings,tmp_path,django_assert_num_queries):
    client,_,work,history,_,_=setup(employee_factory,grant,settings,tmp_path)
    history.authority_type='Органы МВД России';history.save()
    assert value(calculate_registry(year=2026,month=10),5,'G108')==1
    assert send(client,work,body(work,authority_name='',decree3214=False)).status_code==200
    with django_assert_num_queries(1):report=calculate_registry(year=2026,month=10)
    assert value(report,5,'G108') is None and value(report,1,'P108')==0
    assert any(str(work.pk) in g['rows'] for g in report['gaps'] if g['code']=='authority')
    assert client.get(f'/api/v1/expertises/{work.pk}/').json()['case_details']['authority_name']==''

def test_native_authority_and_3214_feed_report_and_real_xlsx(employee_factory,grant):
    from test_registration import registration_setup,register
    from apps.reports.xlsx import export_xlsx
    client,actor,receipt,dept,specialty,data=registration_setup(employee_factory,grant);grant(actor,'expertise.work.update');grant(actor,'expertise.closed.correct');grant(actor,'documents.view')
    specialty.code='16.1';specialty.save()
    work=Expertise.objects.get(pk=register(client,receipt,data).json()['id'])
    doc=Document.objects.create(kind='expert_conclusion',source_kind='paper_original',created_by=actor)
    result=ResultRevision.objects.create(expertise=work,number=1,kind='expert_conclusion',actor=actor.user,reason='Принятый итог',completed_on=date(2026,10,28),document=doc)
    WorkClosure.objects.create(expertise=work,number=1,kind='completed',ended_on=date(2026,10,28),result=result,document=doc,actor=actor.user,reason='Окончание');work.state='completed';work.save()
    before=calculate_registry(year=2026,month=10);assert value(before,1,'P108')==0
    evidence=Document.objects.create(kind='resolution',source_kind='paper_original',created_by=actor)
    response=send(client,work,body(work,authority_type_id=authority(client,work,'sk')['id'],decree3214=True,decree_document_id=str(evidence.pk),decree_basis='ДЕМО · документированное основание3214'));assert response.status_code==200,response.content
    report=calculate_registry(year=2026,month=10)
    assert value(report,5,'F108')==1 and value(report,5,'G108')==0 and value(report,1,'P108')==1 and value(report,1,'P59')==1
    assert value(report,1,'J108')==1 and value(report,1,'K108')==1 and len(report['cells'])==996 and report['data_revision']!=before['data_revision']
    with ZipFile(BytesIO(export_xlsx(report))) as archive:
        root=ET.fromstring(archive.read('xl/worksheets/sheet2.xml'));ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
        assert root.find(".//s:c[@r='P108']/s:v",ns).text=='1'

@pytest.mark.parametrize('patch',[{'reason':' '},{'registration_number':'999/3-1-26'},{'state':'in_progress'},{'authority_group':'mvd'},{'decree3214':True},{'decree3214':False,'decree_basis':'Лишнее основание'},{'decree3214':'unknown'},{'case_number':'x'*501}])
def test_strict_invalid_fields_are_atomic(employee_factory,grant,settings,tmp_path,patch):
    client,_,work,_,_,_=setup(employee_factory,grant,settings,tmp_path)
    assert send(client,work,body(work,**patch)).status_code==400
    from apps.expertises.models import WorkCaseDetails,CaseDetailsRevision
    work.refresh_from_db();assert work.version==1 and not WorkCaseDetails.objects.exists() and not CaseDetailsRevision.objects.exists()

def test_replay_stale_version_and_revocation(employee_factory,grant,settings,tmp_path):
    client,actor,work,_,_,_=setup(employee_factory,grant,settings,tmp_path)
    data=body(work);key=str(uuid.uuid4());first=send(client,work,data,key);assert first.status_code==200
    assert send(client,work,data,key).json()['event']==first.json()['event']
    assert send(client,work,data).status_code==409
    assert send(client,work,{**data,'reason':'Другое основание'},key).status_code==409
    actor.role_assignments.filter(role__permissions__permission_code='expertise.closed.correct').update(is_active=False)
    assert send(client,work,data,key).status_code==403
    from apps.expertises.models import CaseDetailsRevision
    assert CaseDetailsRevision.objects.count()==1

@pytest.mark.parametrize('scope',['own','departments','institution'])
def test_case_update_scopes_and_unrelated_historical_actor(employee_factory,grant,settings,tmp_path,scope):
    client,actor,work,history,dept,_=historical_setup(employee_factory,grant,settings,tmp_path,state='in_progress',ended=None)
    grant(actor,'expertise.work.update',scope,departments=[dept]);HistoricalParticipant.objects.create(history=history,employee=actor)
    assert send(client,work).status_code==200
    outsider=employee_factory();grant(outsider,'expertise.view');grant(outsider,'expertise.work.update','own')
    other=Client();other.force_login(outsider.user);work.refresh_from_db()
    assert send(other,work).status_code==403
    assert not other.get(f'/api/v1/expertises/{work.pk}/').json()['case_details']['can_edit']

def test_document_access_is_rechecked_on_replay_and_uploaded_copy_requires_file(employee_factory,grant,settings,tmp_path):
    client,actor,work,_,_,_=setup(employee_factory,grant,settings,tmp_path)
    work.specialty.code='16.1';work.specialty.save()
    doc=Document.objects.create(kind='other',source_kind='uploaded_copy',created_by=actor)
    data=body(work,decree3214=True,decree_document_id=str(doc.pk),decree_basis='Подтверждено документом')
    assert send(client,work,data).status_code==400
    from test_basis_documents import upload
    grant(actor,'documents.upload');assert upload(client,str(doc.pk)).status_code==201
    key=str(uuid.uuid4());assert send(client,work,data,key).status_code==200
    actor.role_assignments.filter(role__permissions__permission_code='documents.view').update(is_active=False)
    assert send(client,work,data,key).status_code==403

def test_manual_case_profile_blocks_source_update_even_when_old_scalar_fields_match(employee_factory,grant,settings,tmp_path):
    from apps.imports.updates import current_values,update_preview
    client,_,work,history,_,_=setup(employee_factory,grant,settings,tmp_path)
    before=current_values(work);assert send(client,work).status_code==200;work.refresh_from_db()
    assert current_values(work)==before
    assert any('дела' in item or 'карточк' in item for item in update_preview(history.source_row,work)['blockers'])

def test_current_and_removed_inactive_authority_can_be_restored_but_foreign_inactive_cannot(employee_factory,grant,settings,tmp_path):
    client,_,work,_,_,_=setup(employee_factory,grant,settings,tmp_path)
    selected=authority(client,work);data=body(work,authority_type_id=selected['id']);assert send(client,work,data).status_code==200;work.refresh_from_db()
    assert send(client,work,body(work)).status_code==200;work.refresh_from_db()
    from apps.references.models import AuthorityType
    AuthorityType.objects.filter(pk=selected['id']).update(is_active=False)
    assert send(client,work,body(work,authority_type_id=selected['id'])).status_code==200;work.refresh_from_db()
    unrelated=AuthorityType.objects.create(code='inactive_other',name='Не использовался',report_group='other',is_active=False)
    assert send(client,work,body(work,authority_type_id=str(unrelated.pk))).status_code==400

def test_authority_group_changes_fingerprint_and_old_download_cannot_be_reused(employee_factory,grant,settings,tmp_path):
    client,actor,work,_,_,_=setup(employee_factory,grant,settings,tmp_path)
    grant(actor,'references.manage');grant(actor,'reports.form151.run');grant(actor,'reports.form151.download')
    selected=authority(client,work);assert send(client,work,body(work,authority_type_id=selected['id'])).status_code==200
    before=client.get('/api/v1/reports/form151/',{'source':'registry','year':2026,'month':10}).json()
    assert client.patch(f"/api/v1/references/authority-types/{selected['id']}/",{'expected_version':selected['version'],'report_group':'sk'},content_type='application/json').status_code==200
    assert client.get(before['download_url']).status_code==409
    after=calculate_registry(year=2026,month=10);assert value(after,5,'F108')==1 and value(after,5,'G108')==0


def test_case_evidence_is_shared_only_through_the_allowed_work_not_its_creator(employee_factory,grant,settings,tmp_path):
    client,actor,work,history,_,_=setup(employee_factory,grant,settings,tmp_path)
    work.specialty.code='16.1';work.specialty.save()
    doc=Document.objects.create(kind='other',source_kind='paper_original',created_by=actor)
    unrelated=Document.objects.create(kind='other',source_kind='paper_original',created_by=actor)
    assert send(client,work,body(work,decree3214=True,decree_document_id=str(doc.pk),decree_basis='ДЕМО · подтверждено')).status_code==200
    participant=employee_factory();HistoricalParticipant.objects.create(history=history,employee=participant)
    grant(participant,'expertise.view','own');grant(participant,'documents.view','own')
    reader=Client();reader.force_login(participant.user)
    details=reader.get(f'/api/v1/expertises/{work.pk}/').json()['case_details']
    assert 'restricted' not in details['decree_document']
    assert reader.get(f'/api/v1/documents/{doc.pk}/').status_code==200
    assert reader.get(f'/api/v1/documents/{unrelated.pk}/').status_code==403


def test_closed_metadata_edit_after_issue_does_not_reissue_or_replace_the_result(employee_factory,grant,settings,tmp_path):
    from apps.issuance.models import IssuePackage,PackageRevision,PackageCheck,MaterialIssue
    from apps.references.models import IssueMethod
    client,actor,work,history,_,_=setup(employee_factory,grant,settings,tmp_path)
    package=IssuePackage.objects.create(material=work.material,created_by=actor.user)
    revision=PackageRevision.objects.create(package=package,number=1,actor=actor.user,reason='ДЕМО · комплект')
    check=PackageCheck.objects.create(package=package,revision=revision,actor=actor.user,reason='ДЕМО · проверка')
    method=IssueMethod.objects.create(code='demo',name='ДЕМО · передача')
    issued=MaterialIssue.objects.create(package=package,package_check=check,issued_on='2026-10-09',method=method,recipient_name='ДЕМО',recipient_basis='ДЕМО',actor=actor.user,reason='ДЕМО · выдача')
    response=send(client,work);assert response.status_code==200,response.content
    issued.refresh_from_db();work.refresh_from_db();history.refresh_from_db()
    assert issued.issued_on==date(2026,10,9) and MaterialIssue.objects.count()==1
    assert work.state=='completed' and history.completed_on==date(2026,10,6) and not WorkClosure.objects.exists()


def test_assigned_native_expert_can_enter_case_details_but_a_role_alone_is_not_assignment(employee_factory,grant):
    from test_expert_assignments import assignment_setup,qualified,assign
    client,_,registration,_,specialty=assignment_setup(employee_factory,grant)
    actor=qualified(employee_factory,specialty);assert assign(client,registration,[actor]).status_code==200
    grant(actor,'expertise.view','own');grant(actor,'expertise.work.update','own')
    worker=Client();worker.force_login(actor.user);work=Expertise.objects.get(pk=registration['id'])
    assert send(worker,work).status_code==200
    other=employee_factory();grant(other,'expertise.view');grant(other,'expertise.work.update','own')
    outsider=Client();outsider.force_login(other.user);work.refresh_from_db()
    assert send(outsider,work).status_code==403


def test_unknown_free_text_authority_is_not_guessed_and_a_foreign_document_is_not_linkable(employee_factory,grant,settings,tmp_path):
    client,actor,work,history,_,_=historical_setup(employee_factory,grant,settings,tmp_path)
    grant(actor,'expertise.closed.correct');grant(actor,'documents.view','own')
    history.authority_type='ДЕМО · организация с буквами МВД в названии';history.save()
    options=client.get(f'/api/v1/expertises/{work.pk}/case-details/');assert options.status_code==200 and options.json()['initial_authority_type_id'] is None
    other=employee_factory();doc=Document.objects.create(kind='other',source_kind='paper_original',created_by=other)
    assert send(client,work,body(work,decree3214=True,decree_document_id=str(doc.pk),decree_basis='Не даёт доступа к чужому документу')).status_code==403
    work.refresh_from_db();assert work.version==1
