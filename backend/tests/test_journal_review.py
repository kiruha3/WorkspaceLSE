"""Breaks caught: missing review, silent overwrite, guessed links, stale or duplicate apply."""
from copy import deepcopy
import pytest
from apps.audit.models import AuditEvent
from apps.expertises.models import Expertise, HistoricalWork, HistoricalCorrection
from apps.imports.models import ImportApplication, ImportSelection
from apps.references.models import Specialty
from application_samples import application_setup, source_batch, selection_body, select_row, apply_rows
from journal_samples import row

pytestmark = pytest.mark.django_db


def setup_review(employee_factory, grant, settings, tmp_path, *, old=None, new=None, statistics=False):
    original = old or [row(N='1', L='', M='')]
    client, actor, batch, department, specialty = application_setup(employee_factory, grant, settings, tmp_path, original)
    source = batch.rows.get()
    assert select_row(client, batch, source, selection_body(department, specialty if source.facts['specialty_code'] else None, statistics_confirmed=statistics)).status_code == 200
    assert apply_rows(client, batch, [source]).status_code == 201
    newer = source_batch(actor, new or [row(N='2', L='', M='18.1')])
    return client, actor, newer, specialty


def review(client, batch):
    response = client.get(f'/api/v1/imports/{batch.pk}/review/')
    assert response.status_code == 200, response.content
    return response.json()


def entry(info, fields=None):
    return {key: info[key] for key in ('row_id', 'action', 'expected_work_version', 'expected_source_row_id', 'expected_selection_version', 'proposal_hash')} | {'accepted_fields': fields or []}


def apply(client, batch, entries, *, key='review-apply'):
    return client.post(f'/api/v1/imports/{batch.pk}/review/', {'selections': entries}, content_type='application/json', HTTP_IDEMPOTENCY_KEY=key)


def test_review_is_nonmutating_and_specialty_can_be_accepted_alone(employee_factory, grant, settings, tmp_path):
    client, actor, batch, specialty = setup_review(employee_factory, grant, settings, tmp_path)
    before = (ImportSelection.objects.count(), ImportApplication.objects.count(), AuditEvent.objects.count())
    data = review(client, batch)
    assert data['summary'] == {'new': 0, 'changed': 1, 'unchanged': 0, 'invalid': 0}
    info = data['results'][0]
    assert info['eligible'] and info['action'] == 'update'
    change = next(change for change in info['changes'] if change['field'] == 'specialty_id')
    assert change['before'] is None and change['after'] == str(specialty.pk) and not change['conflict']
    assert change['after_label'].startswith('18.1')
    assert before == (ImportSelection.objects.count(), ImportApplication.objects.count(), AuditEvent.objects.count())
    response = apply(client, batch, [entry(info, ['specialty_id'])])
    assert response.status_code == 201, response.content
    assert response.json()['updated_count'] == 1 and response.json()['created_count'] == 0
    work = Expertise.objects.get()
    assert work.specialty_id == specialty.pk and work.historical.complexity_level == 1
    assert Expertise.objects.count() == 1


def test_review_marks_manual_conflict_and_keeps_unselected_manual_edit(employee_factory, grant, settings, tmp_path):
    client, actor, batch, specialty = setup_review(employee_factory, grant, settings, tmp_path)
    history = HistoricalWork.objects.get()
    HistoricalWork.objects.filter(pk=history.pk).update(complexity_level=3, notes='Ручная отметка')
    HistoricalCorrection.objects.create(history=history, number=1, actor=actor.user, reason='Ручное уточнение', before={}, after={})
    info = review(client, batch)['results'][0]
    assert info['eligible']
    change = next(change for change in info['changes'] if change['field'] == 'complexity_level')
    assert (change['before'], change['after'], change['conflict']) == (3, 2, True)
    assert 'notes' not in {change['field'] for change in info['changes']}
    assert apply(client, batch, [entry(info, ['specialty_id'])]).status_code == 201
    history.refresh_from_db()
    assert history.notes == 'Ручная отметка' and history.complexity_level == 3


def test_explicit_conflict_acceptance_changes_only_chosen_field(employee_factory, grant, settings, tmp_path):
    client, actor, batch, specialty = setup_review(employee_factory, grant, settings, tmp_path)
    HistoricalWork.objects.update(complexity_level=3)
    info = review(client, batch)['results'][0]
    assert apply(client, batch, [entry(info, ['complexity_level'])]).status_code == 201
    work = Expertise.objects.get()
    assert work.specialty_id is None and work.historical.complexity_level == 2


def test_exact_executor_is_linked_but_unknown_name_is_not_guessed(employee_factory, grant, settings, tmp_path):
    client, actor, batch, specialty = setup_review(employee_factory, grant, settings, tmp_path)
    person = employee_factory(full_name='Иванов И.И.')
    other = source_batch(actor, [row(N='1', L='Иванов И.И.', M='18.1')])
    info = review(client, other)['results'][0]
    change = next(change for change in info['changes'] if change['field'] == 'employee_ids')
    assert info['eligible'] and change['after'] == [str(person.pk)]
    assert apply(client, other, [entry(info, ['employee_ids'])]).status_code == 201
    assert list(Expertise.objects.get().historical.participants.values_list('employee_id', flat=True)) == [person.pk]
    unknown = source_batch(actor, [row(N='1', L='Иванов И.И. и кто-то ещё', M='18.1')])
    blocked = review(client, unknown)['results'][0]
    assert not blocked['eligible'] and blocked['blockers']
    assert apply(client, unknown, [entry(blocked, ['employee_ids'])], key='unknown').status_code == 409


def test_mixed_packet_rolls_back_if_one_work_changed_and_replay_does_not_duplicate(employee_factory, grant, settings, tmp_path):
    client, actor, batch, specialty = setup_review(employee_factory, grant, settings, tmp_path)
    mixed = source_batch(actor, [row(N='2', L='', M='18.1'), row(B='152/4-1-26', L='', M='18.1')])
    items = review(client, mixed)['results']
    entries = [entry(item, ['specialty_id'] if item['action'] == 'update' else []) for item in items]
    bad = deepcopy(entries)
    next(item for item in bad if item['action'] == 'update')['expected_work_version'] = 99
    response = apply(client, mixed, bad, key='stale')
    assert response.status_code == 409, response.content
    assert Expertise.objects.count() == 1 and Expertise.objects.get().specialty_id is None
    assert not ImportSelection.objects.filter(row__batch=mixed).exists()
    good = apply(client, mixed, entries)
    assert good.status_code == 201, good.content
    assert (good.json()['created_count'], good.json()['updated_count']) == (1, 1)
    assert apply(client, mixed, entries).json() == good.json()
    assert Expertise.objects.count() == 2


@pytest.mark.parametrize('bad', ['empty', 'field', 'hash', 'duplicate', 'no_fields'])
def test_no_unreviewed_or_empty_choice_can_change_the_database(employee_factory, grant, settings, tmp_path, bad):
    client, actor, batch, specialty = setup_review(employee_factory, grant, settings, tmp_path)
    selected = entry(review(client, batch)['results'][0], ['specialty_id'])
    if bad == 'field': selected['accepted_fields'] = ['registration_number']
    if bad == 'hash': selected['proposal_hash'] = '0' * 64
    if bad == 'no_fields': selected['accepted_fields'] = []
    entries = [] if bad == 'empty' else [selected, selected] if bad == 'duplicate' else [selected]
    assert apply(client, batch, entries).status_code in (400, 409)
    assert Expertise.objects.get().specialty_id is None


def test_native_activity_and_revoked_permission_still_block_review_apply(employee_factory, grant, settings, tmp_path):
    client, actor, batch, specialty = setup_review(employee_factory, grant, settings, tmp_path)
    info = review(client, batch)['results'][0]
    HistoricalWork.objects.update(operational=True)
    blocked = review(client, batch)['results'][0]
    assert not blocked['eligible']
    assert apply(client, batch, [entry(info, ['specialty_id'])]).status_code == 409
    actor.role_assignments.filter(role__permissions__permission_code='imports.apply').update(is_active=False)
    assert apply(client, batch, [entry(info, ['specialty_id'])], key='revoked').status_code == 403


def test_pending_field_can_be_accepted_later_from_the_same_snapshot(employee_factory, grant, settings, tmp_path):
    client, actor, batch, specialty = setup_review(employee_factory, grant, settings, tmp_path)
    info = review(client, batch)['results'][0]
    assert apply(client, batch, [entry(info, ['specialty_id'])]).status_code == 201
    remaining = review(client, batch)
    assert remaining['summary']['changed'] == 1
    info = remaining['results'][0]
    assert {change['field'] for change in info['changes']} == {'complexity_level'}
    response = apply(client, batch, [entry(info, ['complexity_level'])], key='accept-rest')
    assert response.status_code == 201, response.content
    assert HistoricalWork.objects.get().complexity_level == 2
    assert review(client, batch)['results'] == []


def test_preserved_manual_conflict_stays_manual_across_multiple_partial_syncs(employee_factory, grant, settings, tmp_path):
    client, actor, batch, specialty = setup_review(employee_factory, grant, settings, tmp_path)
    HistoricalWork.objects.update(complexity_level=3)
    info = review(client, batch)['results'][0]
    assert apply(client, batch, [entry(info, ['specialty_id'])]).status_code == 201
    newer = source_batch(actor, [row(N='4', L='', M='18.1')])
    change = next(change for change in review(client, newer)['results'][0]['changes'] if change['field']=='complexity_level')
    assert (change['before'], change['after'], change['conflict']) == (3, 4, True)


def test_an_identical_fresh_snapshot_keeps_unaccepted_proposals(employee_factory, grant, settings, tmp_path):
    client, actor, batch, specialty = setup_review(employee_factory, grant, settings, tmp_path)
    assert apply(client, batch, [entry(review(client, batch)['results'][0], ['specialty_id'])]).status_code == 201
    newer = source_batch(actor, [row(N='2', L='', M='18.1')])
    pending = review(client, newer)
    assert pending['summary']['changed'] == 1
    assert pending['results'][0]['changes'] == [{'field':'complexity_level','before':1,'after':2,'conflict':False}]


def test_selected_receipt_date_cannot_overtake_retained_completion(employee_factory, grant, settings, tmp_path):
    client, actor, batch, specialty = setup_review(employee_factory, grant, settings, tmp_path,
        old=[row(L='',M='18.1')], new=[row(L='',M='18.1',C='10.03.2026',P='20.03.2026')])
    info = review(client, batch)['results'][0]
    response = apply(client, batch, [entry(info, ['received_on'])])
    assert response.status_code in (400,409), response.content
    assert Expertise.objects.get().receipt.received_at.isoformat() == '2026-02-12'
    response = apply(client, batch, [entry(info, ['received_on','completed_on'])], key='dates-together')
    assert response.status_code == 201, response.content


def test_selected_count_cannot_invalidate_retained_confirmed_statistics(employee_factory, grant, settings, tmp_path):
    client, actor, batch, specialty = setup_review(employee_factory, grant, settings, tmp_path, statistics=True,
        old=[row(L='',M='18.1',Q='10',R='10',S='0',T='0')],new=[row(L='',M='18.1',Q='12',R='12',S='0',T='0')])
    info = review(client, batch)['results'][0]
    response = apply(client, batch, [entry(info, ['questions'])])
    assert response.status_code in (400,409), response.content
    assert HistoricalWork.objects.get().questions == 10
    assert apply(client, batch, [entry(info, ['questions','categorical'])], key='counts-together').status_code == 201


def test_selected_status_does_not_keep_an_impossible_completion_date(employee_factory, grant, settings, tmp_path):
    client, actor, batch, specialty = setup_review(employee_factory, grant, settings, tmp_path,
        old=[row(L='',M='18.1')],new=[row(L='',M='18.1',D='В работе',P='',O='')])
    info = review(client, batch)['results'][0]
    response = apply(client, batch, [entry(info, ['state'])])
    assert response.status_code in (400,409), response.content
    assert Expertise.objects.get().state == 'completed'
    assert apply(client, batch, [entry(info, ['state','completed_on','result_kind'])], key='status-together').status_code == 201


def test_changed_unresolved_count_preserves_validated_reason_allocations(employee_factory, grant, settings, tmp_path):
    from apps.references.models import UnresolvedQuestionReason
    client, actor, batch, specialty = setup_review(employee_factory, grant, settings, tmp_path, statistics=True,
        old=[row(L='',M='18.1',Q='10',R='9',S='0',T='1')],new=[row(L='',M='18.1',Q='12',R='10',S='0',T='2')])
    history = HistoricalWork.objects.get()
    reason = UnresolvedQuestionReason.objects.create(code='test',name='Причина')
    history.unresolved_allocations.create(reason=reason,count=1)
    history.allocations_complete=True;history.save()
    response = apply(client, batch, [entry(review(client, batch)['results'][0], ['questions','categorical','unresolved'])])
    assert response.status_code in (400,409), response.content
    history.refresh_from_db();assert history.unresolved == 1 and history.allocations_complete


@pytest.mark.django_db(transaction=True)
def test_reusing_complex_material_cannot_deadlock_with_material_first_correction(employee_factory, grant, settings, tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from django.db import close_old_connections,connection,transaction
    from apps.intake.models import Material
    from apps.imports.review import apply_review
    from apps.imports.review_api import ReviewInput
    client, actor, batch, department, specialty = application_setup(employee_factory, grant, settings, tmp_path,
        [row(B='151/4-1-26',L='',M='18.1'),row(B='152/4-1-26',L='',M='1.1')])
    other = Specialty.objects.create(code='1.1',name='Почерковедение')
    first, second = list(batch.rows.all())
    assert select_row(client,batch,first,selection_body(department,specialty,complex_known=True,complex_group_key='complex-1')).status_code == 200
    assert apply_rows(client,batch,[first]).status_code == 201
    assert select_row(client,batch,second,selection_body(department,other,complex_known=True,complex_group_key='complex-1'),key='second-choice').status_code == 200
    info=review(client,batch)['results'][0]
    body={'selections':[entry(info)]};form=ReviewInput(data=body);form.is_valid(raise_exception=True)
    material_id=Expertise.objects.get().material_id
    held=Event();material_attempt=Event()
    def correction():
        close_old_connections()
        try:
            with transaction.atomic():
                Material.objects.select_for_update().get(pk=material_id)
                held.set();assert material_attempt.wait(8)
                Specialty.objects.select_for_update().get(pk=specialty.pk)
        finally:connection.close()
    def importing():
        close_old_connections();assert held.wait(8)
        def trace(execute,query,params,many,context):
            if 'FOR UPDATE' in query and '"intake_material"' in query:material_attempt.set()
            return execute(query,params,many,context)
        try:
            with connection.execute_wrapper(trace):
                return apply_review(actor=actor.user,batch_id=batch.pk,key='complex-reviewed',payload=body,**form.validated_data)
        finally:connection.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        correction_job=pool.submit(correction);import_job=pool.submit(importing)
        correction_job.result(timeout=15);result=import_job.result(timeout=15)
    assert result['created_count']==1 and Expertise.objects.count()==2
