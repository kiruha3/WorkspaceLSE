from datetime import date
import pytest
from apps.expertises.models import Expertise,ExpertAssignment,WorkClosure,ResultRevision,Suspension,DeadlineEvent,HistoricalParticipant,ComplexGroup
from apps.intake.models import Material
from apps.personnel.models import EmployeeSpecialty
from apps.accounts.models import CommandReceipt
from apps.audit.models import AuditEvent
from activation_samples import activation_setup,activation_body,activate,evidence

pytestmark=pytest.mark.django_db


def test_open_history_activation_requires_evidence_but_never_creates_qualification_or_assignment(employee_factory,grant,settings,tmp_path):
    client,actor,work,history,_,specialty,basis=activation_setup(employee_factory,grant,settings,tmp_path,state='in_progress',ended=None)
    grant(actor,'expertise.assign')
    response=activate(client,work,activation_body(basis,specialty));assert response.status_code==200
    data=response.json()['expertise'];assert data['historical']['operational'] is True and data['version']==2
    assert data['receipt']['status']=='accepted' and data['basis_document']['id']==str(basis.pk)
    assert not any(model.objects.exists() for model in (EmployeeSpecialty,ExpertAssignment,ResultRevision,WorkClosure,Suspension,DeadlineEvent))
    from test_expert_assignments import assign,qualified
    trainee=employee_factory();EmployeeSpecialty.objects.create(employee=trainee,specialty=specialty,status='training',basis='ДЕМО · обучение')
    assert assign(client,data,[trainee]).status_code==400
    expert=qualified(employee_factory,specialty)
    assert assign(client,data,[expert]).status_code==200 and ExpertAssignment.objects.count()==1
    history.refresh_from_db();assert history.completed_on is None


@pytest.mark.parametrize('change',[{'basis_document_id':None},{'appointment_nature':None},{'is_commission':None},{'complex_known':False},{'reason':' '},{'unexpected':True}])
def test_activation_rejects_unknown_required_confirmation_without_partial_write(employee_factory,grant,settings,tmp_path,change):
    client,_,work,history,_,specialty,basis=activation_setup(employee_factory,grant,settings,tmp_path,state='in_progress',ended=None)
    response=activate(client,work,activation_body(basis,specialty,**change));assert response.status_code==400
    history.refresh_from_db();work.receipt.refresh_from_db()
    assert not history.operational and work.receipt.status=='historical' and not CommandReceipt.objects.filter(action='imports.history.activate').exists()


def test_unknown_specialty_requires_explicit_confirmation_and_known_specialty_cannot_be_replaced(employee_factory,grant,settings,tmp_path):
    client,_,work,_,_,specialty,basis=activation_setup(employee_factory,grant,settings,tmp_path,state='in_progress',ended=None,specialty_known=False)
    assert activate(client,work,activation_body(basis,None)).status_code==400
    assert activate(client,work,activation_body(basis,specialty),key='known-now').status_code==200
    from apps.references.models import Specialty
    other=Specialty.objects.create(code='19.1',name='ДЕМО · другая')
    # A new operation cannot replace a confirmed reference or activate twice.
    response=activate(client,work,activation_body(basis,other,expected_version=2),key='replace')
    assert response.status_code in (400,409)
    work.refresh_from_db();assert work.specialty_id==specialty.pk


@pytest.mark.parametrize('issued',[date(2026,10,7)])
def test_known_historical_issue_blocks_activation_and_receipt_rewrite(employee_factory,grant,settings,tmp_path,issued):
    client,_,work,history,_,specialty,basis=activation_setup(employee_factory,grant,settings,tmp_path,issued=issued)
    doc=evidence(client,work.receipt.created_by,'expert_conclusion')
    response=activate(client,work,activation_body(basis,specialty,result={'kind':'expert_conclusion','completed_on':'2026-10-08','document_id':str(doc.pk)}))
    assert response.status_code==400
    work.receipt.refresh_from_db();history.refresh_from_db()
    assert work.receipt.status=='historical' and not history.operational and not WorkClosure.objects.exists()
    assert 'imports.history.activate' not in client.get(f'/api/v1/expertises/{work.pk}/').json()['allowed_actions']


def test_suspended_activation_needs_real_open_interval_and_keeps_unknown_prior_pauses_unknown(employee_factory,grant,settings,tmp_path):
    client,actor,work,_,_,specialty,basis=activation_setup(employee_factory,grant,settings,tmp_path,state='suspended',ended=None)
    body=activation_body(basis,specialty)
    assert activate(client,work,body).status_code==400
    response=activate(client,work,{**body,'suspended_on':'2026-10-03'},key='with-date');assert response.status_code==200
    assert Suspension.objects.count()==1 and Suspension.objects.get().suspended_on==date(2026,10,3)
    grant(actor,'expertise.resume')
    data=response.json()['expertise']
    response=client.post(f'/api/v1/expertises/{work.pk}/resume/',{'expected_version':data['version'],'resumed_on':'2026-10-06','reason':'ДЕМО · фактическое возобновление'},content_type='application/json',HTTP_IDEMPOTENCY_KEY='resume-after-confirmation')
    assert response.status_code==200 and response.json()['expertise']['production']['paused_days'] is None


@pytest.mark.parametrize('intervals',[
    [{'suspended_on':'2026-09-30','resumed_on':'2026-10-02','reason':'ДЕМО'}],
    [{'suspended_on':'2026-10-04','resumed_on':'2026-10-02','reason':'ДЕМО'}],
    [{'suspended_on':'2027-01-01','resumed_on':'2027-01-02','reason':'ДЕМО'}],
    [{'suspended_on':'2026-10-02','resumed_on':'2026-10-05','reason':'ДЕМО'},{'suspended_on':'2026-10-04','resumed_on':'2026-10-06','reason':'ДЕМО'}],
])
def test_activation_rejects_invalid_or_overlapping_past_intervals(employee_factory,grant,settings,tmp_path,intervals):
    client,_,work,history,_,specialty,basis=activation_setup(employee_factory,grant,settings,tmp_path,state='in_progress',ended=None)
    assert activate(client,work,activation_body(basis,specialty,past_suspensions=intervals,suspension_history_complete=True)).status_code==400
    history.refresh_from_db();assert not history.operational and not Suspension.objects.exists()


def test_confirmed_pause_history_produces_known_days_without_replacing_source_participant(employee_factory,grant,settings,tmp_path):
    client,actor,work,history,_,specialty,basis=activation_setup(employee_factory,grant,settings,tmp_path,state='in_progress',ended=None)
    HistoricalParticipant.objects.create(history=history,employee=actor)
    response=activate(client,work,activation_body(basis,specialty,past_suspensions=[{'suspended_on':'2026-10-02','resumed_on':'2026-10-04','reason':'ДЕМО · подтверждено'}],suspension_history_complete=True))
    assert response.status_code==200 and HistoricalParticipant.objects.count()==1 and not ExpertAssignment.objects.exists()
    from apps.expertises.production import production_summary
    days=production_summary(Expertise.objects.get(pk=work.pk),as_of=date(2026,10,10))
    assert days['calendar_days']==10 and days['paused_days']==2 and days['active_calendar_days']==8


@pytest.mark.parametrize('state,kind',[('completed','expert_conclusion'),('without_execution','return_decision')])
@pytest.mark.parametrize('has_file',[False,True])
def test_closed_history_accepts_missing_file_and_preserves_actual_acceptance_and_source(employee_factory,grant,settings,tmp_path,state,kind,has_file):
    client,actor,work,history,_,specialty,basis=activation_setup(employee_factory,grant,settings,tmp_path,state=state)
    from apps.documents.models import Document
    document=Document.objects.create(kind=kind,title='ДЕМО · без файла',source_kind='paper_original',created_by=actor)
    payload={'result':{'kind':'expert_conclusion','completed_on':'2026-10-08','document_id':str(document.pk)}} if state=='completed' else {'return_data':{'decided_on':'2026-10-08','document_id':str(document.pk)}}
    from test_basis_documents import upload
    if has_file:assert upload(client,str(document.pk)).status_code==201
    response=activate(client,work,activation_body(basis,specialty,**payload),key='with-real-file');assert response.status_code==200
    closure=WorkClosure.objects.get();assert closure.kind==state and closure.ended_on==date(2026,10,8)
    assert (closure.accepted_version_id is not None)==has_file
    if not has_file:
        assert response.json()['expertise']['result_readiness']['document_gaps']
        assert upload(client,str(document.pk)).status_code==201
        closure.refresh_from_db();assert closure.accepted_version_id is None
    history.refresh_from_db();assert history.completed_on==(date(2026,10,6) if state=='completed' else None) and history.return_decided_on is None
    from apps.expertises.history import historical_facts
    facts=historical_facts(Expertise.objects.get(pk=work.pk));assert facts['completed_on' if state=='completed' else 'return_decided_on']==date(2026,10,8)
    if state=='completed':
        grant(actor,'expertise.closed.correct')
        corrected=client.post(f'/api/v1/expertises/{work.pk}/correct/',{'expected_version':response.json()['expertise']['version'],'reason':'ДЕМО · уточнение','correction_kind':'result','result':{**payload['result'],'completed_on':'2026-10-09'}},content_type='application/json',HTTP_IDEMPOTENCY_KEY='correct-confirmed-history')
        assert corrected.status_code==200 and WorkClosure.objects.count()==2


def test_activation_replay_is_idempotent_and_current_rights_are_not_cached(employee_factory,grant,settings,tmp_path):
    client,actor,work,_,_,specialty,basis=activation_setup(employee_factory,grant,settings,tmp_path,state='in_progress',ended=None)
    body=activation_body(basis,specialty)
    response=activate(client,work,body);assert response.status_code==200
    assert activate(client,work,body).json()['event']==response.json()['event']
    assert AuditEvent.objects.filter(action='imports.history.activate').count()==1
    assert activate(client,work,{**body,'reason':'Иная причина'}).status_code==409
    actor.role_assignments.filter(role__permissions__permission_code='imports.history.activate').update(is_active=False)
    assert activate(client,work,body).status_code==403


def test_activation_cannot_remove_explicit_group_or_adopt_another_material_group(employee_factory,grant,settings,tmp_path):
    client,actor,work,history,_,specialty,basis=activation_setup(employee_factory,grant,settings,tmp_path,state='in_progress',ended=None)
    group=ComplexGroup.objects.create(material=work.material,title='ДЕМО · явный комплекс')
    work.complex_group=group;work.save();history.complex_known=True;history.save()
    assert activate(client,work,activation_body(basis,specialty)).status_code==400
    other=ComplexGroup.objects.create(material=Material.objects.create(created_by=actor),title='ДЕМО · другой материал')
    assert activate(client,work,activation_body(basis,specialty,complex_group_id=str(other.pk)),key='foreign-group').status_code==400
    assert activate(client,work,activation_body(basis,specialty,complex_group_id=str(group.pk)),key='same-group').status_code==200


@pytest.mark.parametrize('permission',['imports.history.activate','expertise.register','expertise.view','documents.view'])
def test_activation_requires_current_command_work_and_evidence_rights(employee_factory,grant,settings,tmp_path,permission):
    client,actor,work,history,_,specialty,basis=activation_setup(employee_factory,grant,settings,tmp_path,state='in_progress',ended=None)
    actor.role_assignments.filter(role__permissions__permission_code=permission).update(is_active=False)
    assert activate(client,work,activation_body(basis,specialty)).status_code==403
    history.refresh_from_db();assert not history.operational
    assert not CommandReceipt.objects.filter(action='imports.history.activate').exists()


def test_evidence_permission_is_rechecked_on_replay_and_card_is_redacted(employee_factory,grant,settings,tmp_path):
    client,actor,work,_,_,specialty,basis=activation_setup(employee_factory,grant,settings,tmp_path,state='in_progress',ended=None)
    body=activation_body(basis,specialty);assert activate(client,work,body).status_code==200
    actor.role_assignments.filter(role__permissions__permission_code='documents.view').update(is_active=False)
    assert activate(client,work,body).status_code==403
    assert client.get(f'/api/v1/expertises/{work.pk}/').json()['basis_document']=={'id':str(basis.pk),'restricted':True}


def test_closed_history_cannot_change_closure_type_through_activation(employee_factory,grant,settings,tmp_path):
    client,actor,work,history,_,specialty,basis=activation_setup(employee_factory,grant,settings,tmp_path,state='without_execution')
    document=evidence(client,actor,'expert_conclusion')
    response=activate(client,work,activation_body(basis,specialty,result={'kind':'expert_conclusion','completed_on':'2026-10-08','document_id':str(document.pk)}))
    assert response.status_code==400 and not WorkClosure.objects.exists()
    history.refresh_from_db();assert not history.operational
