from copy import deepcopy
from datetime import date
import uuid
import pytest
from django.test import Client
from apps.expertises.models import Expertise,ExpertAssignment,ResultRevision,WorkClosure,Suspension,DeadlineEvent
from apps.references.models import Specialty,Department,SndzReason,ReturnReason,UnresolvedQuestionReason
from apps.references.result_seeds import seed_result_catalogs
from apps.imports.models import ImportApplicationItem
from apps.documents.models import Document
from apps.issuance.models import IssuePackage
from apps.audit.models import AuditEvent
from apps.reports.registry import calculate_registry
from historical_samples import historical_setup
from test_form151_reasons import cell

pytestmark=pytest.mark.django_db


def setup_correction(employee_factory,grant,settings,tmp_path,**options):
    client,actor,work,history,dept,specialty=historical_setup(employee_factory,grant,settings,tmp_path,**options)
    grant(actor,'expertise.closed.correct');seed_result_catalogs()
    return client,actor,work,history,dept,specialty


def body(work,**patch):
    result={'kind':'expert_conclusion','completed_on':'2026-10-08','complexity_level':2,'questions':3,'categorical':2,'probable':0,'unresolved':1,'statistics_complete':True,'sndz_reason_id':None,'sndz_comment':'','unresolved_allocations':[],'allocations_complete':False,'note':'Уточнено по бумажным материалам'}
    return {'expected_version':work.version,'reason':'Сверено с заключением и журналом выдачи','specialty_id':str(work.specialty_id) if work.specialty_id else None,'correction_kind':'result','result':result,**patch}


def send(client,work,payload=None,key=None):
    return client.post(f'/api/v1/expertises/{work.pk}/history-report/',payload or body(work),content_type='application/json',HTTP_IDEMPOTENCY_KEY=key or str(uuid.uuid4()))


def domain_counts():
    return {m.__name__:m.objects.count() for m in (Expertise,ExpertAssignment,ResultRevision,WorkClosure,Suspension,DeadlineEvent,Document)}


def test_correct_current_facts_audit_history_and_calendar_without_native_events(employee_factory,grant,settings,tmp_path):
    client,actor,work,history,_,_=setup_correction(employee_factory,grant,settings,tmp_path)
    source=deepcopy(history.source_row.facts);raw=deepcopy(history.source_row.raw);identity=(work.registration_number,work.department_id,work.receipt_id,history.source_row_id)
    before=domain_counts();original=history.completed_on
    response=send(client,work);assert response.status_code==200,response.content
    data=response.json()['expertise'];history.refresh_from_db();work.refresh_from_db()
    assert history.completed_on==date(2026,10,8) and history.questions==3 and history.unresolved==1 and history.statistics_confirmed
    assert data['production']['calendar_days']==8 and data['historical']['completed_on']=='2026-10-08'
    assert work.version==2 and work.state=='completed' and not history.operational
    assert (work.registration_number,work.department_id,work.receipt_id,history.source_row_id)==identity
    assert domain_counts()==before
    history.source_row.refresh_from_db();assert history.source_row.facts==source and history.source_row.raw==raw
    corrections=data['historical']['corrections'];assert len(corrections)==1
    assert corrections[0]['before']['completed_on']==original.isoformat() and corrections[0]['after']['completed_on']=='2026-10-08'
    assert corrections[0]['actor']['id']==str(actor.user_id) and corrections[0]['reason']==body(work)['reason']
    assert AuditEvent.objects.filter(action='expertise.history.report.correct').count()==1
    assert client.get(f'/api/v1/expertises/{work.pk}/').json()['historical']['corrections']==corrections


def test_sndz_and_return_reasons_feed_registry_without_fictitious_closure(employee_factory,grant,settings,tmp_path,django_assert_num_queries):
    client,_,work,history,_,_=setup_correction(employee_factory,grant,settings,tmp_path)
    data=body(work);data['result'].update(kind='sndz',sndz_reason_id=str(SndzReason.objects.get(code='science_cannot_answer').pk))
    assert send(client,work,data).status_code==200
    with django_assert_num_queries(1):report=calculate_registry(year=2026,month=10)
    assert cell(report,1,'F108')['value']==1 and cell(report,1,'I108')['value']==1
    assert cell(report,1,'J108')['value']==0 and not WorkClosure.objects.exists()
    history.refresh_from_db();assert history.sndz_reason.code=='science_cannot_answer'
    work.state='without_execution';work.save();work.refresh_from_db()
    data=body(work,correction_kind='return',return_data={'decided_on':'2026-10-09','return_reason_id':str(ReturnReason.objects.get(code='appointing_party_request').pk),'comment':'Запрос органа'})
    data.pop('result')
    response=send(client,work,data);assert response.status_code==200,response.content
    history.refresh_from_db();assert history.return_decided_on==date(2026,10,9)
    report=calculate_registry(year=2026,month=10);assert cell(report,4,'S107')['value']==1 and cell(report,1,'F108')['value']==0
    assert len(response.json()['expertise']['historical']['corrections'])==2


def test_question_allocation_and_explicit_specialty_change_are_consistent(employee_factory,grant,settings,tmp_path):
    client,_,work,history,_,_=setup_correction(employee_factory,grant,settings,tmp_path)
    ref=UnresolvedQuestionReason.objects.get(code='materials_insufficient');specialty=Specialty.objects.create(code='1.1',name='Почерковедческая')
    data=body(work,specialty_id=str(specialty.pk));data['result'].update(allocations_complete=True,unresolved_allocations=[{'reason_id':str(ref.pk),'count':1,'comment':'Недостающие материалы'}])
    response=send(client,work,data);assert response.status_code==200,response.content
    report=calculate_registry(year=2026,month=10)
    assert cell(report,2,'J107')['value']==1 and cell(report,2,'J10')['value']==1 and cell(report,1,'J11')['value']==1
    work.refresh_from_db();assert work.specialty_id==specialty.pk
    details=response.json()['expertise']['historical']['report_details']
    assert details['allocations_complete'] and details['unresolved_allocations'][0]['reason']['code']=='materials_insufficient'
    correction=response.json()['expertise']['historical']['corrections'][0]
    assert correction['after']['specialty']['code']=='1.1' and correction['before']['specialty']['code']=='18.1'


def test_explicit_unknowns_stay_unknown_and_zero_does_not_become_blank(employee_factory,grant,settings,tmp_path):
    client,_,work,history,_,_=setup_correction(employee_factory,grant,settings,tmp_path)
    data=body(work,specialty_id=None);data['result'].update(completed_on=None,questions=None,categorical=0,probable=None,unresolved=None,statistics_complete=False,complexity_level=None)
    response=send(client,work,data);assert response.status_code==200,response.content
    history.refresh_from_db();work.refresh_from_db()
    assert history.completed_on is None and history.questions is None and history.categorical==0 and history.probable is None and work.specialty is None
    assert response.json()['expertise']['historical']['corrections'][0]['after']['categorical']==0


@pytest.mark.parametrize('variant',['balance','future','before_receipt','wrong_kind','other_without_comment','duplicate_allocation','incomplete_distribution','unknown_field','identity','missing_reason','mixed_kind'])
def test_invalid_input_is_atomic(employee_factory,grant,settings,tmp_path,variant):
    client,_,work,history,_,_=setup_correction(employee_factory,grant,settings,tmp_path);data=body(work)
    if variant=='balance':data['result']['questions']=0
    if variant=='future':data['result']['completed_on']='2099-01-01'
    if variant=='before_receipt':data['result']['completed_on']='2026-09-30'
    if variant=='wrong_kind':data['result']['kind']='research_act'
    if variant=='other_without_comment':data.update(correction_kind='return',return_data={'decided_on':None,'return_reason_id':str(ReturnReason.objects.get(code='other').pk),'comment':''});data.pop('result');work.state='without_execution';work.save()
    if variant in ('duplicate_allocation','incomplete_distribution'):
        entry={'reason_id':str(UnresolvedQuestionReason.objects.get(code='materials_insufficient').pk),'count':1}
        data['result'].update(allocations_complete=True,unresolved_allocations=[entry,entry] if variant=='duplicate_allocation' else [])
    if variant=='unknown_field':data['result']['unexpected']=1
    if variant=='identity':data['registration_number']='999/4-1-26'
    if variant=='missing_reason':data['reason']=' '
    if variant=='mixed_kind':data['return_data']={'decided_on':None,'return_reason_id':None,'comment':''}
    before=deepcopy(history.__dict__);counts=domain_counts()
    response=send(client,work,data);assert response.status_code==400,response.content
    history.refresh_from_db();work.refresh_from_db();assert history.completed_on==before['completed_on'] and work.version==1
    assert domain_counts()==counts and not AuditEvent.objects.filter(action='expertise.history.report.correct').exists()


def test_versions_idempotency_revoke_and_no_duplicate_history(employee_factory,grant,settings,tmp_path):
    client,actor,work,history,_,_=setup_correction(employee_factory,grant,settings,tmp_path);payload=body(work);key=str(uuid.uuid4())
    first=send(client,work,payload,key);assert first.status_code==200,first.content
    assert send(client,work,payload,key).json()['event']==first.json()['event']
    assert len(client.get(f'/api/v1/expertises/{work.pk}/').json()['historical']['corrections'])==1
    assert send(client,work,payload).status_code==409
    changed=deepcopy(payload);changed['reason']='Другая причина';assert send(client,work,changed,key).status_code==409
    actor.role_assignments.filter(role__permissions__permission_code='expertise.closed.correct').update(is_active=False)
    assert send(client,work,payload,key).status_code==403


@pytest.mark.parametrize('scope',['own','departments','institution'])
def test_explicit_scopes_and_unrelated_historical_participant(employee_factory,grant,settings,tmp_path,scope):
    client,actor,work,history,dept,_=historical_setup(employee_factory,grant,settings,tmp_path)
    from apps.expertises.models import HistoricalParticipant
    grant(actor,'expertise.closed.correct',scope,departments=[dept])
    HistoricalParticipant.objects.create(history=history,employee=actor)
    detail=client.get(f'/api/v1/expertises/{work.pk}/').json();assert 'expertise.closed.correct' in detail['allowed_actions']
    options=client.get(f'/api/v1/expertises/{work.pk}/history-report/');assert options.status_code==200
    assert send(client,work).status_code==200
    other=employee_factory();grant(other,'expertise.view');grant(other,'expertise.closed.correct','own')
    outsider=Client();outsider.force_login(other.user)
    work.refresh_from_db();assert send(outsider,work).status_code==403
    assert 'expertise.closed.correct' not in outsider.get(f'/api/v1/expertises/{work.pk}/').json()['allowed_actions']


@pytest.mark.parametrize('variant',['open','operational','native','package','assignment','suspension','deadline','result','closure'])
def test_nonhistorical_or_operational_continuation_is_blocked(employee_factory,grant,settings,tmp_path,variant):
    client,actor,work,history,_,_=setup_correction(employee_factory,grant,settings,tmp_path)
    if variant=='open':work.state='in_progress';work.save()
    if variant=='operational':history.operational=True;history.save()
    if variant=='native':work.origin_kind='native';work.appointment_nature='primary';work.is_commission=False;work.save()
    if variant=='package':IssuePackage.objects.create(material=work.material,created_by=actor.user)
    if variant=='assignment':ExpertAssignment.objects.create(expertise=work,employee=actor,actor=actor.user,reason='Нативное назначение',started_at='2026-10-02T00:00:00Z')
    if variant=='suspension':Suspension.objects.create(expertise=work,actor=actor.user,suspended_on='2026-10-02',reason='Нативная пауза')
    if variant=='deadline':DeadlineEvent.objects.create(expertise=work,actor=actor.user,kind='initial',recorded_on='2026-10-02',due_on='2026-10-05',reason='Нативный срок')
    if variant in ('result','closure'):
        result=ResultRevision.objects.create(expertise=work,number=1,kind='expert_conclusion',actor=actor.user,reason='Нативная редакция')
        if variant=='closure':
            doc=Document.objects.create(kind='expert_conclusion',source_kind='paper_original',created_by=actor)
            WorkClosure.objects.create(expertise=work,number=1,kind='completed',ended_on='2026-10-06',result=result,document=doc,actor=actor.user,reason='Нативное окончание')
    response=send(client,work);assert response.status_code in (400,409),response.content
    work.refresh_from_db();assert work.version==1


def test_historical_issue_metadata_does_not_block_and_source_sync_cannot_erase_manual_reasons(employee_factory,grant,settings,tmp_path):
    client,_,work,history,_,_=setup_correction(employee_factory,grant,settings,tmp_path,issued=date(2026,10,10))
    data=body(work);assert send(client,work,data).status_code==200
    history.refresh_from_db();assert history.issued_on==date(2026,10,10)
    from apps.imports.updates import update_preview
    # Eligibility explicitly explains a manual historical correction even
    # if the source row itself is old; it must not rely only on scalar drift.
    preview=update_preview(history.source_row,work)
    assert any('уточнен' in b.lower() or 'корректиров' in b.lower() for b in preview['blockers'])


def test_inactive_values_are_not_new_choices_and_prior_ones_can_be_restored(employee_factory,grant,settings,tmp_path):
    client,_,work,history,_,_=setup_correction(employee_factory,grant,settings,tmp_path)
    ref=SndzReason.objects.get(code='science_cannot_answer');ref.is_active=False;ref.save()
    data=body(work);data['result'].update(kind='sndz',sndz_reason_id=str(ref.pk))
    assert send(client,work,data).status_code==400
    ref.is_active=True;ref.save();assert send(client,work,data).status_code==200
    work.refresh_from_db();ref.is_active=False;ref.save();data=body(work);data['result'].update(kind='sndz',sndz_reason_id=str(ref.pk))
    assert send(client,work,data).status_code==200


def test_foreign_allocation_document_cannot_be_linked(employee_factory,grant,settings,tmp_path):
    client,actor,work,history,dept,_=setup_correction(employee_factory,grant,settings,tmp_path)
    other=employee_factory();doc=Document.objects.create(kind='other',source_kind='paper_original',created_by=other)
    grant(actor,'documents.view','own');data=body(work)
    data['result']['unresolved_allocations']=[{'reason_id':str(UnresolvedQuestionReason.objects.get(code='materials_insufficient').pk),'count':1,'document_id':str(doc.pk)}]
    assert send(client,work,data).status_code==403


def test_document_view_is_rechecked_even_on_a_successful_key_replay(employee_factory,grant,settings,tmp_path):
    client,actor,work,history,_,_=setup_correction(employee_factory,grant,settings,tmp_path)
    _,assignment=grant(actor,'documents.view','own')
    doc=Document.objects.create(kind='other',source_kind='paper_original',created_by=actor)
    data=body(work);data['result']['unresolved_allocations']=[{'reason_id':str(UnresolvedQuestionReason.objects.get(code='materials_insufficient').pk),'count':1,'document_id':str(doc.pk)}]
    key=str(uuid.uuid4());assert send(client,work,data,key).status_code==200
    assignment.is_active=False;assignment.save(update_fields=['is_active'])
    assert send(client,work,data,key).status_code==403
    history.refresh_from_db();work.refresh_from_db()
    assert history.corrections.count()==1 and work.version==2


@pytest.mark.parametrize('kind',['sndz','expert_conclusion','return'])
@pytest.mark.parametrize('inactive',[False,True])
def test_corrected_reasons_survive_explicit_native_activation(employee_factory,grant,settings,tmp_path,kind,inactive):
    from activation_samples import activation_setup,activation_body,activate,evidence
    client,actor,work,history,_,specialty,basis=activation_setup(employee_factory,grant,settings,tmp_path,state='without_execution' if kind=='return' else 'completed')
    grant(actor,'expertise.closed.correct');seed_result_catalogs()
    ref=(ReturnReason.objects.get(code='appointing_party_request') if kind=='return' else SndzReason.objects.get(code='science_cannot_answer') if kind=='sndz' else UnresolvedQuestionReason.objects.get(code='materials_insufficient'))
    if kind=='return':data={'expected_version':1,'reason':'Уточнено решение','specialty_id':str(specialty.pk),'correction_kind':'return','return_data':{'decided_on':'2026-10-08','return_reason_id':str(ref.pk),'comment':'Подтверждённая причина'}}
    else:
        data=body(work);data['result']['kind']=kind
        if kind=='sndz':data['result'].update(sndz_reason_id=str(ref.pk),sndz_comment='Подтверждённая причина')
        else:data['result'].update(unresolved_allocations=[{'reason_id':str(ref.pk),'count':1,'comment':'Подтверждённый вопрос','document_id':None}],allocations_complete=True)
    assert send(client,work,data).status_code==200
    before=calculate_registry(year=2026,month=10)
    if inactive:ref.is_active=False;ref.save(update_fields=['is_active'])
    doc=evidence(client,actor,'return_decision' if kind=='return' else kind)
    values=deepcopy(data['return_data' if kind=='return' else 'result']);values['document_id']=str(doc.pk)
    response=activate(client,work,activation_body(basis,specialty,expected_version=2,**{'return_data' if kind=='return' else 'result':values}))
    assert response.status_code==200,response.content
    after=calculate_registry(year=2026,month=10)
    # This activation explicitly confirms primary nature, formerly unknown.
    # Preserve all earlier816 cells AND provenance; separately assert the
    # intended transition in the84 new repeat cells instead of ignoring them.
    def original_cells(report):
        return [c for c in report['cells'] if not(c['sheet']=='Раздел 4' and c['address'][0] in 'HIJKLMN' or c['sheet']=='Раздел 3' and c['address'][0] in 'GHIJKLMN')]
    assert len(original_cells(before))==len(original_cells(after))==816
    assert original_cells(before)==original_cells(after)
    timing_cells=lambda report:[c for c in report['cells'] if c['sheet']=='Раздел 3' and c['address'][0] in 'GHIJKLMN']
    assert len(timing_cells(before))==96 and timing_cells(before)==timing_cells(after)
    for address in [f'{column}{row}' for column in 'HIJKLMN' for row in (64,107)]:
        old=next(c for c in before['cells'] if c['sheet']=='Раздел 4' and c['address']==address)
        new=next(c for c in after['cells'] if c['sheet']=='Раздел 4' and c['address']==address)
        assert old['value']==(0 if kind=='return' else None)
        assert old['rows']==([] if kind=='return' else [str(work.pk)])
        assert new['value']==0 and new['rows']==[]
    assert response.json()['expertise']['appointment_nature']=='primary'
    loaded=response.json()['expertise'];assert loaded['historical']['operational'] and len(loaded['historical']['corrections'])==1
    closure=WorkClosure.objects.get(expertise=work)
    if kind=='return':assert closure.return_reason_id==ref.pk and closure.comment=='Подтверждённая причина'
    elif kind=='sndz':assert closure.result.sndz_reason_id==ref.pk and closure.result.sndz_comment=='Подтверждённая причина'
    else:assert closure.result.allocations_complete and closure.result.unresolved_allocations.get().reason_id==ref.pk


@pytest.mark.parametrize('field',['specialty','sndz_reason','return_reason','unresolved_allocations'])
def test_a_removed_inactive_reference_can_be_explicitly_restored_from_this_history(employee_factory,grant,settings,tmp_path,field):
    client,_,work,history,_,specialty=setup_correction(employee_factory,grant,settings,tmp_path,state='without_execution' if field=='return_reason' else 'completed')
    ref={'specialty':specialty,'sndz_reason':SndzReason.objects.get(code='science_cannot_answer'),'return_reason':ReturnReason.objects.get(code='appointing_party_request'),'unresolved_allocations':UnresolvedQuestionReason.objects.get(code='materials_insufficient')}[field]
    def selected(enabled):
        data=body(work)
        if field=='specialty':data['specialty_id']=str(ref.pk) if enabled else None
        if field=='sndz_reason':data['result'].update(kind='sndz' if enabled else 'expert_conclusion',sndz_reason_id=str(ref.pk) if enabled else None)
        if field=='unresolved_allocations':data['result']['unresolved_allocations']=[{'reason_id':str(ref.pk),'count':1}] if enabled else []
        if field=='return_reason':
            data.pop('result');data.update(correction_kind='return',return_data={'decided_on':None,'return_reason_id':str(ref.pk) if enabled else None,'comment':''})
        return data
    assert send(client,work,selected(True)).status_code==200;work.refresh_from_db()
    assert send(client,work,selected(False)).status_code==200;work.refresh_from_db()
    ref.is_active=False;ref.save(update_fields=['is_active'])
    response=send(client,work,selected(True));assert response.status_code==200,response.content
    assert response.json()['expertise']['historical']['corrections'][-1]['after'][field]


def test_complex_specialty_conflict_rolls_back_facts_allocations_and_correction(employee_factory,grant,settings,tmp_path):
    from apps.expertises.models import ComplexGroup
    client,actor,work,history,dept,specialty=setup_correction(employee_factory,grant,settings,tmp_path)
    other=Specialty.objects.create(code='1.1',name='ДЕМО · другая специальность')
    group=ComplexGroup.objects.create(material=work.material,title='ДЕМО · комплекс')
    work.complex_group=group;work.save(update_fields=['complex_group'])
    Expertise.objects.create(material=work.material,receipt=work.receipt,registration_number='152/4-1-26',sequence=152,year=2026,category_code='1',department=dept,specialty=other,origin_kind='historical',complex_group=group,registered_by=actor.user)
    original=(history.completed_on,history.questions,history.categorical)
    data=body(work);data['specialty_id']=str(other.pk);data['result']['unresolved_allocations']=[{'reason_id':str(UnresolvedQuestionReason.objects.get(code='materials_insufficient').pk),'count':1}]
    assert send(client,work,data).status_code==409
    work.refresh_from_db();history.refresh_from_db()
    assert work.specialty_id==specialty.pk and work.version==1
    assert (history.completed_on,history.questions,history.categorical)==original
    assert not history.corrections.exists() and not history.unresolved_allocations.exists()
