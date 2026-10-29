"""Extra associations never replace strong provenance or confer upload authority."""
import hashlib
import uuid
import pytest
from django.test import Client
from django.utils import timezone
from apps.accounts.models import CommandReceipt
from apps.audit.models import AuditEvent
from apps.documents.models import Document
from apps.expertises.models import Expertise, ExpertAssignment, WorkClosure, ResultRevision
from apps.intake.models import Material, Receipt
from apps.references.models import Department, Specialty
from test_basis_documents import upload, PNG

pytestmark = pytest.mark.django_db


@pytest.fixture
def vault(employee_factory, grant, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    department = Department.objects.create(code='3', name='Отдел 3')
    specialty = Specialty.objects.create(code='1.1', name='Почерковедческая')
    owner = employee_factory(department=department)
    for action in ('expertise.view', 'documents.view', 'documents.upload', 'documents.link', 'documents.unlink'):
        grant(owner, action)
    basis = Document.objects.create(kind='decision', title='Определение', source_kind='paper_original', created_by=owner)
    material = Material.objects.create(created_by=owner)
    receipt = Receipt.objects.create(material=material, created_by=owner, basis_document=basis,
                                     received_at='2026-10-01', status='accepted', department=department)
    works = [Expertise.objects.create(receipt=receipt, material=material, department=department, specialty=specialty,
        registration_number=f'{n}/3-1-26', sequence=n, year=2026, category_code='1', appointment_nature='primary',
        is_commission=False, registered_by=owner.user) for n in (1, 2)]
    client = Client(); client.force_login(owner.user)
    return client, owner, works, basis


def library_url(work): return f'/api/v1/expertises/{work.pk}/documents/'


def make_complex(works):
    from apps.expertises.models import ComplexGroup
    one,two=works
    specialty=Specialty.objects.create(code='18.1',name='Оценка транспортных средств')
    two.specialty=specialty;two.save(update_fields=['specialty'])
    group=ComplexGroup.objects.create(material=one.material,title='Комплексная экспертиза')
    Expertise.objects.filter(pk__in=[one.pk,two.pk]).update(complex_group=group)
    for work in works:work.refresh_from_db()


def test_one_document_can_be_linked_to_all_complex_numbers_without_copying_file(vault):
    from apps.documents.models import WorkDocumentLink,FileVersion
    client,owner,works,_=vault
    make_complex(works)
    doc=Document.objects.create(kind='expert_conclusion',title='Общее заключение',source_kind='uploaded_copy',created_by=owner)
    saved=upload(client,doc.pk).json()
    key=str(uuid.uuid4())
    body={'expected_version':1,'document_id':str(doc.pk),'reason':'Общее заключение комплекса','share_with_complex':True}
    for _ in range(2):
        response=client.post(library_url(works[0]),body,content_type='application/json',HTTP_IDEMPOTENCY_KEY=key)
        assert response.status_code==200,response.content
    assert WorkDocumentLink.objects.filter(document=doc,detached_at__isnull=True).count()==2
    assert FileVersion.objects.filter(document=doc).count()==1
    for work in works:
        row=entry(client.get(library_url(work)).json(),doc)
        assert row['document']['versions'][0]['id']==saved['id']
        work.refresh_from_db();assert work.state=='in_progress'


def test_shared_document_link_requires_authority_for_every_work_and_is_atomic(vault,employee_factory,grant):
    from apps.documents.models import WorkDocumentLink
    _,owner,works,_=vault
    make_complex(works)
    other=Department.objects.create(code='4',name='Отдел 4')
    works[1].department=other;works[1].save(update_fields=['department'])
    doc=Document.objects.create(kind='expert_conclusion',title='Общее заключение',source_kind='paper_original',created_by=owner)
    employee=employee_factory()
    grant(employee,'expertise.view');grant(employee,'documents.view')
    grant(employee,'documents.link','departments',departments=[works[0].department])
    client=Client();client.force_login(employee.user)
    body={'expected_version':1,'document_id':str(doc.pk),'reason':'Общий документ','share_with_complex':True}
    response=client.post(library_url(works[0]),body,content_type='application/json',HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
    assert response.status_code==403,response.content
    assert WorkDocumentLink.objects.count()==0


def link(client, work, document, *, version=None, key=None):
    work.refresh_from_db()
    return client.post(library_url(work), {'expected_version': work.version if version is None else version,
        'document_id': str(document.pk), 'note': 'Общий документ', 'reason': 'Досланы материалы'},
        content_type='application/json', HTTP_IDEMPOTENCY_KEY=key or str(uuid.uuid4()))


def detach(client, work, link_id, *, version=None, key=None):
    work.refresh_from_db()
    return client.post(f'{library_url(work)}{link_id}/detach/', {
        'expected_version': work.version if version is None else version, 'reason': 'Ошибочная связь'},
        content_type='application/json', HTTP_IDEMPOTENCY_KEY=key or str(uuid.uuid4()))


def entry(data, document):
    return next(item for item in data['results'] if item['document']['id'] == str(document.pk))


def test_existing_paper_basis_is_aggregated_without_creating_extra_links(vault):
    client, _, (work, _), basis = vault
    response = client.get(library_url(work))
    assert response.status_code == 200, response.content
    data = response.json()
    assert data['context']['registration_number'] == '1/3-1-26'
    assert data['count'] == 1 and data['can_link'] and data['can_unlink']
    row = entry(data, basis)
    assert row['origins'][0]['kind'] == 'receipt_basis' and row['extra_links'] == []
    assert row['document']['versions'] == []


def test_shared_file_two_works_detach_one_preserves_bytes_and_other_link(vault):
    from apps.documents.models import WorkDocumentLink
    client, owner, (one, two), _ = vault
    doc = Document.objects.create(kind='letter', title='Общий файл', source_kind='uploaded_copy', created_by=owner)
    saved = upload(client, doc.pk).json()
    first = link(client, one, doc); assert first.status_code == 200, first.content
    second = link(client, two, doc); assert second.status_code == 200, second.content
    link_id = entry(first.json()['library'], doc)['extra_links'][0]['id']
    removed = detach(client, one, link_id); assert removed.status_code == 200, removed.content
    assert str(doc.pk) not in [item['document']['id'] for item in removed.json()['library']['results']]
    assert entry(client.get(library_url(two)).json(), doc)['document']['versions'][0]['id'] == saved['id']
    body = b''.join(client.get(saved['download_url']).streaming_content)
    assert hashlib.sha256(body).hexdigest() == hashlib.sha256(PNG).hexdigest()
    assert WorkDocumentLink.objects.filter(detached_at__isnull=True).count() == 1
    assert WorkDocumentLink.objects.count() == 2 and doc.versions.count() == 1


def test_accepted_closure_pins_v1_and_explicit_null_never_substitutes_latest(vault):
    client, owner, (work, _), _ = vault
    doc = Document.objects.create(kind='expert_conclusion', title='Заключение', source_kind='paper_original', created_by=owner)
    v1 = upload(client, doc.pk).json(); upload(client, doc.pk, version=2)
    result = ResultRevision.objects.create(expertise=work, number=1, document=doc,
        kind='expert_conclusion', completed_on='2026-10-10', actor=owner.user, reason='Итог')
    old = WorkClosure.objects.create(expertise=work, number=1, kind='completed', ended_on='2026-10-10',
        result=result, document=doc, accepted_version_id=v1['id'], actor=owner.user, reason='Первое окончание')
    new = WorkClosure.objects.create(expertise=work, number=2, kind='completed', ended_on='2026-10-11',
        result=result, document=doc, accepted_version=None, actor=owner.user, reason='Бумажный оригинал')
    response = client.get(library_url(work)); assert response.status_code == 200, response.content
    origins = {item['id']: item for item in entry(response.json(), doc)['origins']}
    assert origins[str(old.pk)]['accepted_version_id'] == v1['id']
    assert 'accepted_version_id' in origins[str(new.pk)] and origins[str(new.pk)]['accepted_version_id'] is None


def test_link_and_detach_replay_do_not_reactivate_removed_association(vault):
    from apps.documents.models import WorkDocumentLink
    client, owner, (work, _), _ = vault
    doc = Document.objects.create(kind='letter', title='Архив', source_kind='paper_original', created_by=owner)
    first = link(client, work, doc, key='link-once', version=1)
    assert first.status_code == 200, first.content
    link_id = entry(first.json()['library'], doc)['extra_links'][0]['id']
    removed = detach(client, work, link_id, key='detach-once', version=2)
    assert removed.status_code == 200
    repeated = link(client, work, doc, key='link-once', version=1)
    assert repeated.status_code == 200 and repeated.json()['event'] == first.json()['event']
    assert not WorkDocumentLink.objects.filter(detached_at__isnull=True).exists()
    assert detach(client, work, link_id, key='detach-once', version=2).json()['event'] == removed.json()['event']
    assert WorkDocumentLink.objects.count() == 1
    assert link(client, work, doc).status_code == 200
    assert WorkDocumentLink.objects.count() == 2


def test_duplicate_foreign_stale_and_revoked_commands_are_atomic(vault):
    from apps.documents.models import WorkDocumentLink
    client, owner, (one, two), _ = vault
    doc = Document.objects.create(kind='letter', title='Архив', source_kind='paper_original', created_by=owner)
    first = link(client, one, doc, key='original', version=1)
    assert first.status_code == 200, first.content
    link_id = entry(first.json()['library'], doc)['extra_links'][0]['id']
    before = (CommandReceipt.objects.count(), AuditEvent.objects.count())
    assert link(client, one, doc).status_code == 409
    assert detach(client, two, link_id).status_code == 404
    assert detach(client, one, link_id, version=1).status_code == 409
    owner.role_assignments.filter(role__permissions__permission_code='documents.link').update(is_active=False)
    assert link(client, one, doc, key='original', version=1).status_code == 403
    assert (CommandReceipt.objects.count(), AuditEvent.objects.count()) == before
    assert WorkDocumentLink.objects.count() == 1


def test_own_reader_loses_extra_file_after_detach_without_upload_escalation(vault, employee_factory, grant):
    client, owner, (work, _), _ = vault
    doc = Document.objects.create(kind='letter', title='Чужой исходный файл', source_kind='uploaded_copy', created_by=owner)
    saved = upload(client, doc.pk).json()
    linked = link(client, work, doc); assert linked.status_code == 200, linked.content
    link_id = entry(linked.json()['library'], doc)['extra_links'][0]['id']
    reader = employee_factory()
    for action in ('expertise.view', 'documents.view', 'documents.upload'): grant(reader, action, 'own')
    assignment = ExpertAssignment.objects.create(expertise=work, employee=reader, started_at=timezone.now(), actor=owner.user, reason='Назначен')
    other = Client(); other.force_login(reader.user)
    assert other.get(saved['download_url']).status_code == 200
    assert upload(other, doc.pk, version=2).status_code == 403
    removed = detach(client, work, link_id); assert removed.status_code == 200
    assert other.get(saved['download_url']).status_code == 403
    history = other.get(library_url(work)).json()['detached_links']
    assert history[0]['document'] == {'id': str(doc.pk), 'restricted': True}
    assignment.ended_at = timezone.now(); assignment.save(update_fields=['ended_at'])
    assert other.get(library_url(work)).status_code in (403, 404)


def test_read_only_archive_and_picker_do_not_leak_closed_document_titles(vault, employee_factory, grant):
    client, owner, (work, _), _ = vault
    reader = employee_factory()
    for action in ('expertise.view', 'documents.view'): grant(reader, action, 'own')
    ExpertAssignment.objects.create(expertise=work, employee=reader, started_at=timezone.now(), actor=owner.user, reason='Назначен')
    other = Client(); other.force_login(reader.user)
    response = other.get(library_url(work)); assert response.status_code == 200, response.content
    assert not response.json()['can_link'] and not response.json()['can_unlink']
    assert other.get(library_url(work) + 'options/').status_code == 403
    secret = Document.objects.create(kind='letter', title='Секретное название', source_kind='paper_original', created_by=owner)
    assert other.get(library_url(work), {'search': secret.title}).json()['count'] == 0
    assert link(other, work, secret).status_code == 403


def test_registered_clerk_can_use_own_extra_links_but_not_without_work_read(vault, grant):
    client, owner, (work, _), basis = vault
    owner.role_assignments.filter(role__permissions__permission_code__in=['documents.link', 'documents.unlink']).update(is_active=False)
    grant(owner, 'documents.link', 'own'); grant(owner, 'documents.unlink', 'own')
    assert link(client, work, basis).status_code == 200
    owner.role_assignments.filter(role__permissions__permission_code='expertise.view').update(is_active=False)
    assert client.get(library_url(work)).status_code == 403


def test_picker_requires_document_view_even_when_work_link_right_is_present(vault):
    client,owner,(work,_),_=vault
    owner.role_assignments.filter(role__permissions__permission_code='documents.view').update(is_active=False)
    response=client.get(library_url(work)+'options/')
    assert response.status_code==403,response.content


def test_scoped_link_permission_cannot_be_used_in_another_department(vault,employee_factory,grant):
    client,owner,(one,two),basis=vault
    department=Department.objects.create(code='4',name='Отдел 4')
    two.department=department;two.save(update_fields=['department'])
    operator=employee_factory(department=one.department)
    grant(operator,'expertise.view');grant(operator,'documents.view')
    grant(operator,'documents.link','departments',departments=[one.department])
    other=Client();other.force_login(operator.user)
    assert link(other,one,basis).status_code==200
    assert link(other,two,basis).status_code==403
    assert other.get(library_url(two)+'options/').status_code==403


def test_current_history_participant_not_bulk_import_actor_owns_extra_link(employee_factory,grant,settings,tmp_path):
    from historical_samples import historical_setup
    from apps.expertises.models import HistoricalParticipant
    client,importer,work,history,_,_=historical_setup(employee_factory,grant,settings,tmp_path)
    grant(importer,'documents.view');grant(importer,'documents.link','own')
    doc=Document.objects.create(kind='letter',title='Архив',source_kind='paper_original',created_by=importer)
    assert link(client,work,doc).status_code==403
    expert=employee_factory()
    for action in ('expertise.view','documents.view','documents.link'):grant(expert,action,'own')
    HistoricalParticipant.objects.create(history=history,employee=expert)
    owned=Document.objects.create(kind='letter',title='Документ эксперта',source_kind='paper_original',created_by=expert)
    other=Client();other.force_login(expert.user)
    assert link(other,work,owned).status_code==200


def test_filters_pagination_and_search_only_see_documents_in_current_work(vault):
    from apps.documents.models import WorkDocumentLink
    client,owner,(work,_),basis=vault
    for number in range(27):
        doc=Document.objects.create(kind='letter',title=f'Письмо {number:02}',source_kind='paper_original',created_by=owner)
        WorkDocumentLink.objects.create(expertise=work,document=doc,actor=owner.user)
    first=client.get(library_url(work),{'kind':'letter'}).json()
    assert first['count']==27 and len(first['results'])==25 and first['next']
    second=client.get(library_url(work),{'kind':'letter','page':2}).json()
    assert len(second['results'])==2 and second['previous'] and second['next'] is None
    found=client.get(library_url(work),{'search':'Письмо 03'}).json()
    assert found['count']==1 and found['results'][0]['document']['title']=='Письмо 03'
    assert client.get(library_url(work),{'kind':'unknown'}).status_code==400


def test_letter_archive_uses_only_accessible_current_work_context(vault,employee_factory,grant):
    from apps.correspondence.models import Letter,LetterRevision,LetterAttachment
    client,owner,(one,two),_=vault
    grant(owner,'letters.view')
    shared=Document.objects.create(kind='letter',title='Файл письма',source_kind='paper_original',created_by=owner)
    letter=Letter.objects.create(direction='incoming',department=one.department,created_by=owner,responsible=owner)
    old=LetterRevision.objects.create(letter=letter,number=1,subject='Старое письмо',actor=owner,reason='Черновик')
    old.expertises.add(one)
    new=LetterRevision.objects.create(letter=letter,number=2,subject='Только другая работа',actor=owner,reason='Уточнено')
    new.expertises.add(two);letter.current_revision=new;letter.save(update_fields=['current_revision'])
    LetterAttachment.objects.create(letter=letter,document=shared,actor=owner,reason='Приложение')
    assert str(shared.pk) not in [row['document']['id'] for row in client.get(library_url(one)).json()['results']]
    assert entry(client.get(library_url(two)).json(),shared)['origins'][0]['kind']=='letter_attachment'
    viewer=employee_factory()
    for action in ('expertise.view','documents.view','letters.view'):grant(viewer,action,'own')
    ExpertAssignment.objects.create(expertise=one,employee=viewer,started_at=timezone.now(),actor=owner.user,reason='Назначение')
    other=Client();other.force_login(viewer.user)
    assert other.get(library_url(one),{'search':shared.title}).json()['count']==0


def test_all_typed_strong_origins_collapse_to_one_document_without_extra_links(vault,grant):
    from apps.expertises.models import DeadlineEvent,WorkCaseDetails,WorkClassification,PreviousConclusion,WorkTimingFacts,TimingReason
    from apps.references.models import DelayReason
    client,owner,(work,_),basis=vault
    DeadlineEvent.objects.create(expertise=work,kind='agreement',recorded_on='2026-10-02',due_on='2026-11-01',document=basis,actor=owner.user,reason='Согласовано')
    WorkCaseDetails.objects.create(expertise=work,created_by=owner.user,decree3214=True,decree_document=basis,decree_basis='Подтверждено')
    classification=WorkClassification.objects.create(expertise=work,created_by=owner.user)
    PreviousConclusion.objects.create(classification=classification,ordinal=1,reference='ДЕМО №1',document=basis)
    timing=WorkTimingFacts.objects.create(expertise=work,created_by=owner.user,notification_document=basis)
    reason=DelayReason.objects.first()
    TimingReason.objects.create(timing=timing,reason=reason,document=basis)
    response=client.get(library_url(work));assert response.status_code==200,response.content
    assert response.json()['count']==1
    row=entry(response.json(),basis)
    assert {origin['kind'] for origin in row['origins']}=={'receipt_basis','deadline','decree3214','previous_conclusion','timing_notification','timing_reason'}
    assert row['extra_links']==[]


def test_document_picker_does_not_reload_roles_for_every_visible_document(vault):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext
    client,owner,(work,_),_=vault
    Document.objects.bulk_create([Document(kind='letter',title=f'Документ {n}',source_kind='paper_original',created_by=owner) for n in range(30)])
    with CaptureQueriesContext(connection) as queries:
        response=client.get(library_url(work)+'options/')
    assert response.status_code==200,response.content
    assert response.json()['count']==31
    assert len(queries)<=40,f'{len(queries)} SQL queries for31 documents; rights should share the current request snapshot'


def test_failed_command_response_pagination_does_not_commit_an_invisible_link(vault):
    from apps.documents.models import WorkDocumentLink
    client,owner,(work,_),basis=vault
    response=client.post(library_url(work)+'?page=999',{'expected_version':1,'document_id':str(basis.pk),'reason':'Дослано'},
        content_type='application/json',HTTP_IDEMPOTENCY_KEY='bad-response-page')
    assert response.status_code==404
    assert WorkDocumentLink.objects.count()==0
    work.refresh_from_db();assert work.version==1
    assert not CommandReceipt.objects.filter(key='bad-response-page').exists()


def test_issued_files_remain_pinned_and_extra_archive_does_not_rewrite_issuance(employee_factory,grant,settings,tmp_path):
    from django.core.management import call_command
    from apps.issuance.models import MaterialIssue
    from test_issue_billing import prepare
    from test_issue_commands import checked,package_command,issue_values
    settings.MEDIA_ROOT=tmp_path
    client,clerk,work_data,package,*_=prepare(employee_factory,grant)
    grant(clerk,'documents.link')
    call_command('seed_issue_catalogs',verbosity=0)
    proof=Document.objects.create(kind='letter',title='Подтверждение выдачи',source_kind='paper_original',created_by=clerk)
    package=checked(client,package)
    issued=package_command(client,package,'issue',**issue_values(evidence_document_id=str(proof.pk)))
    assert issued.status_code==200,issued.content
    issue=MaterialIssue.objects.get();issue_id=issue.pk
    assert issue.accepted_evidence_version_id is None
    assert upload(client,proof.pk).status_code==201
    work=Expertise.objects.get(pk=work_data['id'])
    data=client.get(library_url(work)).json()
    origin=next(item for item in entry(data,proof)['origins'] if item['kind']=='issue_evidence')
    assert 'accepted_version_id' in origin and origin['accepted_version_id'] is None
    extra=Document.objects.create(kind='letter',title='Досланная архивная копия',source_kind='paper_original',created_by=clerk)
    assert link(client,work,extra).status_code==200
    work.refresh_from_db();issue.refresh_from_db()
    assert work.state=='completed' and issue.pk==issue_id and issue.accepted_evidence_version_id is None
    assert MaterialIssue.objects.count()==1
