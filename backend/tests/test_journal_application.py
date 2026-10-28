from datetime import date
import uuid
import pytest
from django.test import Client
from apps.expertises.models import Expertise,HistoricalWork,HistoricalParticipant,ExpertAssignment,WorkClosure,ResultRevision,Suspension,DeadlineEvent
from apps.intake.models import Material,Receipt
from apps.documents.models import Document,FileVersion
from apps.personnel.models import EmployeeSpecialty
from apps.accounts.models import CommandReceipt
from apps.audit.models import AuditEvent
from apps.references.models import Department,Specialty
from application_samples import application_setup,source_batch,selection_body,select_row,apply_rows
from journal_samples import row

pytestmark=pytest.mark.django_db


def test_reconciliation_options_are_minimal_and_include_inactive_historical_references(employee_factory,grant,settings,tmp_path):
    client,actor,batch,department,specialty=application_setup(employee_factory,grant,settings,tmp_path)
    department.is_active=False;department.save();specialty.is_active=False;specialty.save()
    response=client.get('/api/v1/imports/reconciliation-options/');assert response.status_code==200
    data=response.json()
    assert data['departments']==[{'id':str(department.pk),'code':'4','name':'ДЕМО · отдел4','is_active':False}]
    assert data['specialties'][0]['is_active'] is False
    assert data['employees']==[{'id':str(actor.pk),'full_name':actor.full_name,'is_active':True}]
    assert client.get(f'/api/v1/imports/{batch.pk}/').json()['apply_available'] is True


def test_saved_selection_is_versioned_idempotent_and_not_a_business_write(employee_factory,grant,settings,tmp_path):
    client,actor,batch,department,specialty=application_setup(employee_factory,grant,settings,tmp_path)
    source=batch.rows.get();raw=source.raw.copy();body=selection_body(department,specialty)
    response=select_row(client,batch,source,body);assert response.status_code==200
    selection=response.json()['selection']
    assert selection['version']==1 and selection['appointment_nature'] is None and selection['is_commission'] is None
    assert selection['employee_ids']==[] and selection['complex_known'] is False
    assert select_row(client,batch,source,body).json()['selection']['id']==selection['id']
    assert select_row(client,batch,source,{**body,'reason':'Другое основание'}).status_code==409
    assert not any(model.objects.exists() for model in (Material,Receipt,Expertise,EmployeeSpecialty,Document,FileVersion))
    assert select_row(client,batch,source,{**body,'expected_version':0},'stale').status_code==409
    response=select_row(client,batch,source,{**body,'expected_version':1,'appointment_nature':'repeated'},'update')
    assert response.status_code==200 and response.json()['selection']['version']==2
    source.refresh_from_db();assert source.raw==raw


@pytest.mark.parametrize('override',[
    {'reason':' '},{'expected_version':-1},{'unexpected':True},{'complex_known':False,'complex_group_key':'complex-a'},
    {'is_commission':True,'employee_ids':[]},{'statistics_confirmed':True},
])
def test_selection_rejects_unconfirmed_or_contradictory_inputs(employee_factory,grant,settings,tmp_path,override):
    client,_,batch,department,specialty=application_setup(employee_factory,grant,settings,tmp_path,rows=[row()])
    response=select_row(client,batch,batch.rows.get(),selection_body(department,specialty,**override))
    assert response.status_code==400
    assert not Expertise.objects.exists()


def test_exact_code_mapping_and_explicit_employees_do_not_create_qualifications(employee_factory,grant,settings,tmp_path):
    client,actor,batch,department,specialty=application_setup(employee_factory,grant,settings,tmp_path)
    source=batch.rows.get();other=Department.objects.create(code='3',name='Отдел3')
    other_specialty=Specialty.objects.create(code='19.1',name='Другая специальность')
    assert select_row(client,batch,source,selection_body(other,specialty)).status_code==400
    assert select_row(client,batch,source,selection_body(department,other_specialty)).status_code==400
    second=employee_factory(active=False)
    department.is_active=False;department.save();specialty.is_active=False;specialty.save()
    body=selection_body(department,specialty,employee_ids=[str(actor.pk),str(second.pk)],is_commission=True,statistics_confirmed=True)
    assert select_row(client,batch,source,body).status_code==200
    assert not EmployeeSpecialty.objects.exists()


def test_apply_creates_main_work_with_known_facts_and_no_forged_workflow(employee_factory,grant,settings,tmp_path):
    client,actor,batch,department,specialty=application_setup(employee_factory,grant,settings,tmp_path)
    source=batch.rows.get()
    body=selection_body(department,specialty,employee_ids=[str(actor.pk)],statistics_confirmed=True)
    assert select_row(client,batch,source,body).status_code==200
    response=apply_rows(client,batch,[source]);assert response.status_code==201
    protocol=response.json()['application'];assert protocol['created_count']==1 and protocol['existing_count']==0
    work=Expertise.objects.get();history=HistoricalWork.objects.get()
    assert protocol['items']==[{'row_id':str(source.pk),'expertise_id':str(work.pk),'action':'created'}]
    assert work.origin_kind=='historical' and work.state=='completed' and work.specialty_id==specialty.pk
    assert work.appointment_nature is None and work.is_commission is None and work.receipt.status=='historical'
    assert work.receipt.received_at==date(2026,2,12) and history.completed_on==date(2026,3,6)
    assert history.source_row_id==source.pk and history.questions==2 and history.statistics_confirmed is True and not history.operational
    assert list(history.participants.values_list('employee_id',flat=True))==[actor.pk]
    assert not any(model.objects.exists() for model in (Document,FileVersion,ExpertAssignment,WorkClosure,ResultRevision,Suspension,DeadlineEvent,EmployeeSpecialty))
    assert client.get(f"/api/v1/expertises/{work.pk}/").status_code==200
    assert client.get(f"/api/v1/imports/applications/{protocol['id']}/").json()==protocol
    assert apply_rows(client,batch,[source]).json()['application']['id']==protocol['id']
    assert AuditEvent.objects.filter(action='imports.apply').count()==1
    assert apply_rows(client,batch,[source],reason='Иное основание').status_code==409
    again=apply_rows(client,batch,[source],key='acknowledge-prior');assert again.status_code==201
    assert again.json()['application']['created_count']==0 and again.json()['application']['existing_count']==1
    assert Expertise.objects.count()==1
    assert select_row(client,batch,source,{**body,'expected_version':1},'after-apply').status_code==409


@pytest.mark.parametrize('overrides,unknown',[
    ({'M':''},'specialty'),({'T':'1НПВ'},'unresolved'),({'P':'01.01.2026'},'completed_on'),({'O':'Акт экспертного исследования'},'result_kind'),
])
def test_invalid_nonidentity_field_does_not_drop_whole_registration(employee_factory,grant,settings,tmp_path,overrides,unknown):
    client,_,batch,department,specialty=application_setup(employee_factory,grant,settings,tmp_path,rows=[row(**overrides)])
    source=batch.rows.get();assert select_row(client,batch,source,selection_body(department,None if unknown=='specialty' else specialty)).status_code==200
    response=apply_rows(client,batch,[source]);assert response.status_code==201
    work=Expertise.objects.get();history=HistoricalWork.objects.get()
    assert (work.specialty_id if unknown=='specialty' else getattr(history,unknown)) is None
    assert history.source_row.diagnostics and work.registration_number=='151/4-1-26'


@pytest.mark.parametrize('bad', [{'B':'номер неясен'},{'C':''},{'C':'31.02.2026'},{'D':'неясно'}])
def test_bad_identity_or_arrival_or_state_blocks_the_whole_selected_package(employee_factory,grant,settings,tmp_path,bad):
    client,_,batch,department,specialty=application_setup(employee_factory,grant,settings,tmp_path,rows=[row(),row(B='152/4-1-26',**bad) if 'B' not in bad else row(**bad)])
    sources=list(batch.rows.all())
    for index,source in enumerate(sources):assert select_row(client,batch,source,selection_body(department,specialty),key=f'select-{index}').status_code==200
    response=apply_rows(client,batch,sources);assert response.status_code in (400,409)
    assert not Expertise.objects.exists() and not Material.objects.exists() and not CommandReceipt.objects.filter(action='imports.apply').exists()


def test_complex_group_is_explicit_batch_local_and_shared_only_when_selected(employee_factory,grant,settings,tmp_path):
    client,actor,batch,department,specialty=application_setup(employee_factory,grant,settings,tmp_path,rows=[row(),row(B='152/4-1-26',M='19.1.')])
    second=Specialty.objects.create(code='19.1',name='ДЕМО · 19.1')
    sources=list(batch.rows.all())
    for index,(source,ref) in enumerate(zip(sources,[specialty,second])):
        assert select_row(client,batch,source,selection_body(department,ref,complex_known=True,complex_group_key='complex-a'),f'select-{index}').status_code==200
    assert apply_rows(client,batch,sources).status_code==201
    works=list(Expertise.objects.order_by('sequence'))
    assert works[0].material_id==works[1].material_id and works[0].complex_group_id==works[1].complex_group_id
    other=source_batch(actor,[row(B='153/4-1-26')]);source=other.rows.get()
    assert select_row(client,other,source,selection_body(department,specialty,complex_known=True,complex_group_key='complex-a'),'select-other').status_code==200
    assert apply_rows(client,other,[source],key='apply-other').status_code==201
    third=Expertise.objects.get(sequence=153)
    assert third.material_id!=works[0].material_id and third.complex_group_id!=works[0].complex_group_id


def test_duplicate_specialty_complex_and_stale_selection_roll_back(employee_factory,grant,settings,tmp_path):
    client,_,batch,department,specialty=application_setup(employee_factory,grant,settings,tmp_path,rows=[row(),row(B='152/4-1-26')])
    sources=list(batch.rows.all())
    for index,source in enumerate(sources):assert select_row(client,batch,source,selection_body(department,specialty,complex_known=True,complex_group_key='same'),f'select-{index}').status_code==200
    assert apply_rows(client,batch,sources).status_code in (400,409)
    assert not Expertise.objects.exists()
    assert select_row(client,batch,sources[0],selection_body(department,specialty,expected_version=1),'change-selection').status_code==200
    assert apply_rows(client,batch,[sources[0]],key='stale').status_code==409
    assert not Expertise.objects.exists()


def test_new_snapshot_with_same_number_is_classified_not_silently_updated(employee_factory,grant,settings,tmp_path):
    client,actor,batch,department,specialty=application_setup(employee_factory,grant,settings,tmp_path)
    original=batch.rows.get();assert select_row(client,batch,original,selection_body(department,specialty)).status_code==200
    assert apply_rows(client,batch,[original]).status_code==201
    for index,change in enumerate([{}, {'J':'Изменённое описание'}]):
        newer=source_batch(actor,[row(Q='2',R='2',S='0',T='0',**change)]);source=newer.rows.get()
        response=client.get(f'/api/v1/imports/{newer.pk}/reconciliation/');assert response.status_code==200
        data=response.json();assert data['summary']['unchanged' if not change else 'changed']==1
        assert data['results'][0]['existing_work']['id']==str(Expertise.objects.get().pk)
        assert select_row(client,newer,source,selection_body(department,specialty),f'select-newer-{index}').status_code==200
        assert apply_rows(client,newer,[source],key=f'apply-newer-{index}').status_code==409
    assert Expertise.objects.count()==1 and HistoricalWork.objects.get().source_row_id==original.pk


def test_current_rights_checked_on_replay_and_cannot_be_replaced_by_preview_right(employee_factory,grant,settings,tmp_path):
    client,actor,batch,department,specialty=application_setup(employee_factory,grant,settings,tmp_path)
    source=batch.rows.get();body=selection_body(department,specialty)
    assert select_row(client,batch,source,body).status_code==200
    assert apply_rows(client,batch,[source]).status_code==201
    actor.role_assignments.filter(role__permissions__permission_code='imports.apply').update(is_active=False)
    assert apply_rows(client,batch,[source]).status_code==403
    assert client.get(f'/api/v1/imports/{batch.pk}/').json()['apply_available'] is False
    actor.role_assignments.filter(role__permissions__permission_code='imports.reconcile').update(is_active=False)
    assert select_row(client,batch,source,body).status_code==403
    assert client.get('/api/v1/imports/reconciliation-options/').status_code==403
    assert client.get(f'/api/v1/imports/{batch.pk}/reconciliation/').status_code==200


@pytest.mark.parametrize('case',['empty','duplicate','too_many','unknown_field','no_reason'])
def test_apply_strict_packet_bounds_are_checked_before_any_creation(employee_factory,grant,settings,tmp_path,case):
    client,_,batch,_,_=application_setup(employee_factory,grant,settings,tmp_path)
    source=batch.rows.get();one={'row_id':str(source.pk),'expected_selection_version':1}
    overrides={'selections':[] if case=='empty' else [one,one] if case=='duplicate' else [{'row_id':str(uuid.uuid4()),'expected_selection_version':1} for _ in range(1001)] if case=='too_many' else [one]}
    if case=='unknown_field':overrides['automatic']=True
    if case=='no_reason':overrides['reason']=' '
    assert apply_rows(client,batch,[source],**overrides).status_code==400
    assert not Expertise.objects.exists()


def test_reconciliation_keeps_global_counts_when_filtering_and_does_not_block_missing_specialty(employee_factory,grant,settings,tmp_path):
    client,_,batch,_,_=application_setup(employee_factory,grant,settings,tmp_path,rows=[row(),row(B='152/4-1-26',M=''),row(B='неясно')])
    response=client.get(f'/api/v1/imports/{batch.pk}/reconciliation/',{'classification':'new','search':'152'})
    assert response.status_code==200
    data=response.json();assert data['summary']=={'new':2,'unchanged':0,'changed':0,'invalid':1}
    assert data['count']==1 and data['results'][0]['row']['facts']['registration_number']=='152/4-1-26'
    assert data['results'][0]['suggested_specialty'] is None and data['results'][0]['blockers']==[]


def test_current_reference_code_change_invalidates_saved_mapping_without_creating_work(employee_factory,grant,settings,tmp_path):
    client,_,batch,department,specialty=application_setup(employee_factory,grant,settings,tmp_path)
    source=batch.rows.get();assert select_row(client,batch,source,selection_body(department,specialty)).status_code==200
    specialty.code='18.2';specialty.save()
    assert apply_rows(client,batch,[source]).status_code==400
    assert not Expertise.objects.exists() and not Material.objects.exists()


def test_later_packet_can_extend_only_its_explicit_complex_group(employee_factory,grant,settings,tmp_path):
    client,_,batch,department,specialty=application_setup(employee_factory,grant,settings,tmp_path,rows=[row(),row(B='152/4-1-26',M='19.1.')])
    other=Specialty.objects.create(code='19.1',name='ДЕМО ·19.1')
    sources=list(batch.rows.all())
    for index,(source,ref) in enumerate(zip(sources,[specialty,other])):
        assert select_row(client,batch,source,selection_body(department,ref,complex_known=True,complex_group_key='same'),f'select-{index}').status_code==200
        assert apply_rows(client,batch,[source],key=f'apply-{index}').status_code==201
    assert Expertise.objects.values('material_id').distinct().count()==1


@pytest.mark.parametrize('issue_origin',['historical','native'])
def test_later_complex_packet_cannot_change_issued_material_and_rolls_back_all_rows(employee_factory,grant,settings,tmp_path,issue_origin):
    from apps.issuance.models import IssuePackage,PackageRevision,PackageCheck,MaterialIssue
    from apps.references.models import IssueMethod
    client,actor,batch,department,specialty=application_setup(employee_factory,grant,settings,tmp_path,rows=[row(),row(B='152/4-1-26',M='19.1.'),row(B='153/4-1-26')])
    other=Specialty.objects.create(code='19.1',name='ДЕМО ·19.1')
    sources=list(batch.rows.all())
    for index,(source,ref) in enumerate(zip(sources,[specialty,other,specialty])):
        assert select_row(client,batch,source,selection_body(department,ref,complex_known=index<2,complex_group_key='same' if index<2 else None),f'select-{index}').status_code==200
    assert apply_rows(client,batch,[sources[0]]).status_code==201
    work=Expertise.objects.get()
    if issue_origin=='historical':HistoricalWork.objects.filter(expertise=work).update(issued_on=date(2026,3,7))
    else:
        package=IssuePackage.objects.create(material=work.material,created_by=actor.user)
        revision=PackageRevision.objects.create(package=package,number=1,actor=actor.user,reason='ДЕМО · ранее принятый комплект')
        check=PackageCheck.objects.create(package=package,revision=revision,actor=actor.user,reason='ДЕМО · проверка')
        MaterialIssue.objects.create(package=package,package_check=check,issued_on=date(2026,3,7),method=IssueMethod.objects.create(code='demo',name='ДЕМО'),recipient_name='ДЕМО',recipient_basis='ДЕМО',actor=actor.user,reason='ДЕМО · зафиксированная выдача')
    response=apply_rows(client,batch,sources[1:],key='late-after-issue')
    assert response.status_code==400
    assert Expertise.objects.count()==1 and Receipt.objects.count()==1 and Material.objects.count()==1
    assert AuditEvent.objects.filter(action='imports.apply').count()==1
    # Acknowledge the existing link without adding anything to the material.
    assert apply_rows(client,batch,[sources[0]],key='ack-issued').status_code==201


@pytest.mark.parametrize('overrides,field',[
    ({'P':'01.11.2026'},'completed_on'),
    ({'W':'Выдано 01.11.2026'},'issued_on'),
])
def test_invalid_factual_source_date_remains_unknown_without_dropping_registration(employee_factory,grant,settings,tmp_path,monkeypatch,overrides,field):
    monkeypatch.setattr('django.utils.timezone.localdate',lambda:date(2026,10,28))
    client,_,batch,department,specialty=application_setup(employee_factory,grant,settings,tmp_path,rows=[row(**overrides)])
    source=batch.rows.get();raw=source.raw.copy()
    assert source.facts[field] is not None
    assert select_row(client,batch,source,selection_body(department,specialty)).status_code==200
    assert apply_rows(client,batch,[source]).status_code==201
    history=HistoricalWork.objects.get();assert getattr(history,field) is None
    source.refresh_from_db();assert source.raw==raw
    from apps.expertises.history import historical_facts
    assert historical_facts(history.expertise)[field] is None
    if field=='completed_on':
        data=client.get(f'/api/v1/expertises/{history.expertise_id}/').json()
        assert data['production']['calendar_days'] is None
        assert client.get('/api/v1/expertises/',{'calendar_days_min':1}).json()['count']==0


def test_noncommission_selection_cannot_confirm_two_current_people(employee_factory,grant,settings,tmp_path):
    client,actor,batch,department,specialty=application_setup(employee_factory,grant,settings,tmp_path)
    other=employee_factory()
    response=select_row(client,batch,batch.rows.get(),selection_body(department,specialty,is_commission=False,employee_ids=[str(actor.pk),str(other.pk)]))
    assert response.status_code==400 and 'employee_ids' in response.json()['field_errors']


def test_ready_application_module_is_advertised_but_activation_is_not_a_card_action_yet(employee_factory,grant,settings,tmp_path):
    client,_,_,_,_=application_setup(employee_factory,grant,settings,tmp_path)
    response=client.get('/api/v1/me/');assert response.status_code==200
    assert 'journal_application' in response.json()['supported_modules']
