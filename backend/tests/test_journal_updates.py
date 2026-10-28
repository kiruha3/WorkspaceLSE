from datetime import date,datetime,timezone as dt_timezone
from copy import deepcopy
import uuid
import pytest
from apps.expertises.models import Expertise,HistoricalWork,ResultRevision,WorkClosure,ExpertAssignment
from apps.imports.models import ImportApplication,ImportApplicationItem,ImportRow
from apps.audit.models import AuditEvent
from apps.references.models import Specialty
from application_samples import application_setup,source_batch,selection_body,select_row,apply_rows
from journal_samples import row

pytestmark=pytest.mark.django_db


def prepare(employee_factory,grant,settings,tmp_path,old=None,new=None):
    original=old or [row(N='1',Q='2',R='2',S='0',T='0')]
    client,actor,batch,department,specialty=application_setup(employee_factory,grant,settings,tmp_path,original)
    for i,source in enumerate(batch.rows.all()):
        assert select_row(client,batch,source,selection_body(department,specialty,employee_ids=[str(actor.pk)]),f'old-{i}').status_code==200
    assert apply_rows(client,batch,list(batch.rows.all())).status_code==201
    newer=source_batch(actor,new or [row(N='2',Q='2',R='2',S='0',T='0')])
    for i,source in enumerate(newer.rows.all()):
        assert select_row(client,newer,source,selection_body(department,specialty,employee_ids=[str(actor.pk)]),f'new-{i}').status_code==200
    return client,actor,batch,newer,department,specialty


def packet(batch):
    return {'reason':'Подтверждено исправление источника','updates':[
        {'row_id':str(source.pk),'expected_selection_version':source.selection.version,
         'expected_work_version':work.version,'expected_source_row_id':str(work.historical.source_row_id)}
        for source in batch.rows.all()
        for work in [Expertise.objects.get(registration_number=source.facts['registration_number'])]]}


def update(client,batch,body=None,key='update-journal'):
    return client.post(f'/api/v1/imports/{batch.pk}/updates/',body or packet(batch),content_type='application/json',HTTP_IDEMPOTENCY_KEY=key)


def preview(client,batch):
    item=client.get(f'/api/v1/imports/{batch.pk}/reconciliation/?classification=changed').json()['results'][0]
    assert 'update_preview' in item,'Changed rows need a typed, nonmutating update preview'
    return item['update_preview']


def test_preview_and_update_keep_identity_source_history_and_no_native_events(employee_factory,grant,settings,tmp_path):
    client,actor,old,new,department,specialty=prepare(employee_factory,grant,settings,tmp_path)
    work=Expertise.objects.get();history=work.historical
    original={str(r.pk):(r.raw,r.facts) for r in ImportRow.objects.all()}
    before_audit=AuditEvent.objects.count()
    info=preview(client,new)
    assert info['eligible'] and info['expected_source_row_id']==str(old.rows.get().pk)
    assert {'field':'complexity_level','before':1,'after':2} in info['changes']
    assert info['previous_selection']['employee_ids']==[str(actor.pk)]
    assert AuditEvent.objects.count()==before_audit
    response=update(client,new);assert response.status_code==201,response.content
    protocol=response.json()['application'];assert protocol['updated_count']==1 and protocol['created_count']==0
    item=protocol['items'][0];assert item['action']=='updated' and item['previous_source_row_id']==str(old.rows.get().pk)
    assert item['before']['complexity_level']==1 and item['after']['complexity_level']==2
    work.refresh_from_db();history.refresh_from_db()
    assert work.registration_number=='151/4-1-26' and work.department_id==department.pk and work.specialty_id==specialty.pk
    assert work.version==2 and history.source_row_id==new.rows.get().pk and history.complexity_level==2
    assert list(history.participants.values_list('employee_id',flat=True))==[actor.pk]
    assert {str(r.pk):(r.raw,r.facts) for r in ImportRow.objects.all()}==original
    assert Expertise.objects.count()==1 and ImportApplication.objects.count()==2 and ImportApplicationItem.objects.count()==2
    assert not any(m.objects.exists() for m in (ResultRevision,WorkClosure,ExpertAssignment))
    assert AuditEvent.objects.filter(action='imports.update').count()==1
    assert select_row(client,new,new.rows.get(),selection_body(department,specialty,expected_version=1),'frozen').status_code==409
    assert client.get(f'/api/v1/imports/applications/{protocol["id"]}/').json()==protocol


def test_completion_specialty_people_and_next_update_drive_live_report(employee_factory,grant,settings,tmp_path):
    old_rows=[row(D='В работе',P='',O='',N='',Q='',R='',S='',T='')]
    new_rows=[row(N='1',Q='2',R='2',S='0',T='0',M='1.1.',L='Новый А.А.')]
    client,actor,old,new,department,_=prepare(employee_factory,grant,settings,tmp_path,old_rows,old_rows)
    # Replace this unused saved snapshot with an actual newer source and explicit mapping.
    new=source_batch(actor,new_rows);specialty=Specialty.objects.create(code='1.1',name='Почерк')
    other=employee_factory()
    assert select_row(client,new,new.rows.get(),selection_body(department,specialty,employee_ids=[str(other.pk)]),'people').status_code==200
    from apps.reports.registry import calculate_registry
    from test_form151 import value
    before=calculate_registry(year=2026,month=10)
    assert value(before,1,'J108')==0
    assert update(client,new).status_code==201
    work=Expertise.objects.get();assert work.specialty_id==specialty.pk and work.state=='completed'
    assert work.historical.completed_on==date(2026,3,6)
    assert list(work.historical.participants.values_list('employee_id',flat=True))==[other.pk]
    after=calculate_registry(year=2026,month=10)
    assert value(after,1,'J108')==1 and value(after,1,'J11')==1 and after['data_revision']!=before['data_revision']
    newest=source_batch(actor,[row(N='2',Q='2',R='2',S='0',T='0',M='1.1.',L='Новый А.А.')])
    assert select_row(client,newest,newest.rows.get(),selection_body(department,specialty,employee_ids=[str(other.pk)]),'third').status_code==200
    assert preview(client,newest)['eligible']
    assert update(client,newest,key='third').status_code==201
    work.refresh_from_db();assert work.historical.complexity_level==2 and work.version==3


@pytest.mark.parametrize('field',['history','receipt','state','participants','operational','draft','native_package'])
def test_manual_or_native_activity_blocks_without_partial_changes(employee_factory,grant,settings,tmp_path,field):
    client,actor,old,new,department,specialty=prepare(employee_factory,grant,settings,tmp_path)
    work=Expertise.objects.get();body=packet(new)
    if field=='history':HistoricalWork.objects.filter(expertise=work).update(questions=7)
    if field=='receipt':work.receipt.sender_name='Ручное изменение';work.receipt.save()
    if field=='state':Expertise.objects.filter(pk=work.pk).update(state='in_progress')
    if field=='participants':work.historical.participants.all().delete()
    if field=='operational':HistoricalWork.objects.filter(expertise=work).update(operational=True)
    if field=='draft':ResultRevision.objects.create(expertise=work,number=1,kind='expert_conclusion',actor=actor.user,reason='Собственный черновик')
    if field=='native_package':
        from apps.issuance.models import IssuePackage
        IssuePackage.objects.create(material=work.material,created_by=actor.user)
    info=preview(client,new);assert not info['eligible'] and info['blockers']
    response=update(client,new,body);assert response.status_code==409,response.content
    assert ImportApplication.objects.count()==1 and not ImportApplicationItem.objects.filter(row__batch=new).exists()
    assert HistoricalWork.objects.get().complexity_level==1


def test_explicit_historical_issue_metadata_is_not_a_native_package_edit(employee_factory,grant,settings,tmp_path):
    original=[row(N='1',Q='2',R='2',S='0',T='0',W='Выдано 07.03.2026')]
    changed=[{**original[0],'N':'2'}]
    client,actor,old,new,_,_=prepare(employee_factory,grant,settings,tmp_path,original,changed)
    assert preview(client,new)['eligible'] and update(client,new).status_code==201
    assert HistoricalWork.objects.get().issued_on==date(2026,3,7)


@pytest.mark.parametrize('bad',['work_version','source','selection','older','same','duplicate','unknown'])
def test_stale_or_ambiguous_packet_is_rejected(employee_factory,grant,settings,tmp_path,bad):
    client,actor,old,new,_,_=prepare(employee_factory,grant,settings,tmp_path)
    body=packet(new)
    if bad=='work_version':body['updates'][0]['expected_work_version']=9
    if bad=='source':body['updates'][0]['expected_source_row_id']=str(uuid.uuid4())
    if bad=='selection':body['updates'][0]['expected_selection_version']=9
    if bad=='older':type(new).objects.filter(pk=new.pk).update(created_at=old.created_at)
    if bad=='same':ImportRow.objects.filter(batch=new).update(facts=old.rows.get().facts)
    if bad=='duplicate':body['updates']*=2
    if bad=='unknown':body['updates'][0]['unexpected']=True
    response=update(client,new,body);assert response.status_code in (400,409),response.content
    assert HistoricalWork.objects.get().complexity_level==1 and ImportApplication.objects.count()==1


def test_packet_is_atomic_and_replay_is_idempotent_but_still_checks_rights(employee_factory,grant,settings,tmp_path):
    originals=[row(B=f'{n}/4-1-26',N='1',Q='2',R='2',S='0',T='0') for n in (151,152)]
    client,actor,old,new,_,_=prepare(employee_factory,grant,settings,tmp_path,originals,[{**r,'N':'2'} for r in originals])
    body=packet(new);bad=deepcopy(body);bad['updates'][1]['expected_work_version']=9
    assert update(client,new,bad,key='bad').status_code==409
    assert list(HistoricalWork.objects.values_list('complexity_level',flat=True))==[1,1]
    good=update(client,new,body);assert good.status_code==201
    assert update(client,new,body).json()==good.json()
    assert update(client,new,{**body,'reason':'Другое'}).status_code==409
    actor.role_assignments.filter(role__permissions__permission_code='imports.apply').update(is_active=False)
    assert update(client,new,body).status_code==403
    assert ImportApplication.objects.count()==2 and AuditEvent.objects.filter(action='imports.update').count()==1


def test_future_at_original_import_stays_unknown_in_baseline(employee_factory,grant,settings,tmp_path):
    from unittest.mock import patch
    old=[row(N='1',P='27.10.2026',Q='2',R='2',S='0',T='0')]
    with patch('apps.imports.application.timezone.localdate',return_value=date(2026,10,26)):
        client,actor,batch,new,_,_=prepare(employee_factory,grant,settings,tmp_path,old,[{**old[0],'N':'2'}])
    # Reproduce the real original import date, without changing the source dates.
    HistoricalWork.objects.update(created_at=datetime(2026,10,26,0,tzinfo=dt_timezone.utc))
    assert HistoricalWork.objects.get().completed_on is None
    assert preview(client,new)['eligible']
    assert update(client,new).status_code==201
    assert HistoricalWork.objects.get().completed_on==date(2026,10,27)


def test_apply_only_reader_can_see_meaningful_specialty_and_participant_changes(employee_factory,grant,settings,tmp_path):
    client,actor,old,_,department,_=prepare(employee_factory,grant,settings,tmp_path)
    actor.full_name='Эксперт А.А.';actor.save()
    other=employee_factory(full_name='Эксперт Б.Б.')
    specialty=Specialty.objects.create(code='1.1',name='Почерк')
    newest=source_batch(actor,[row(M='1.1.',L='Эксперт Б.Б.',N='1',Q='2',R='2',S='0',T='0')])
    assert select_row(client,newest,newest.rows.get(),selection_body(department,specialty,employee_ids=[str(other.pk)]),'labels').status_code==200
    actor.role_assignments.filter(role__permissions__permission_code='imports.reconcile').update(is_active=False)
    assert client.get('/api/v1/imports/reconciliation-options/').status_code==403
    changes={c['field']:c for c in preview(client,newest)['changes']}
    assert changes['specialty_id'].get('before_label')=='18.1 · ДЕМО · специальность'
    assert changes['specialty_id'].get('after_label')=='1.1 · Почерк'
    assert changes['employee_ids'].get('before_label')=='Эксперт А.А.'
    assert changes['employee_ids'].get('after_label')=='Эксперт Б.Б.'
