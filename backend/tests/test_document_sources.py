"""Typed source metadata must not masquerade as a local accepted file."""
import hashlib
import uuid
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.accounts.commands import execute_once
from apps.documents.models import Document, FileVersion
from test_receipts import clerk_client
from test_basis_documents import PNG
from test_work_document_vault import vault

pytestmark = pytest.mark.django_db


def source(client, **changes):
    return client.post('/api/v1/documents/', {
        'kind': 'case_material', 'title': 'Материалы дела', 'source_kind': 'external_link',
        'source_url': 'https://example.org/materials/document.pdf', **changes,
    }, content_type='application/json', HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))


def test_external_source_is_metadata_only_then_accepts_an_archived_copy(employee_factory, grant, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    client, _ = clerk_client(employee_factory, grant)
    response = source(client)
    assert response.status_code == 201, response.content
    doc = response.json()
    assert doc['source_url'] == 'https://example.org/materials/document.pdf' and doc['versions'] == []
    assert not list(tmp_path.rglob('*'))
    uploaded = client.post(f"/api/v1/documents/{doc['id']}/versions/", {
        'expected_version': 1, 'relative_path': 'Дело/Материалы/document.png',
        'file': SimpleUploadedFile('document.png', PNG),
    }, HTTP_IDEMPOTENCY_KEY='copy')
    assert uploaded.status_code == 201, uploaded.content
    assert uploaded.json()['relative_path'] == 'Дело/Материалы/document.png'
    saved = FileVersion.objects.get(pk=uploaded.json()['id'])
    assert saved.file.name.startswith(f"documents/{doc['id']}/") and 'Дело' not in saved.file.name
    fresh = client.get(f"/api/v1/documents/{doc['id']}/").json()
    assert fresh['source_url'] == doc['source_url']
    assert b''.join(client.get(uploaded.json()['download_url']).streaming_content) == PNG


@pytest.mark.parametrize('url', ['', 'file:///C:/secret', 'javascript:alert(1)', 'ftp://example.org/x',
                                  'https://user:pass@example.org/x', 'https://', 'https://example.org/\nsecret'])
def test_invalid_external_url_creates_no_document(employee_factory, grant, url):
    client, _ = clerk_client(employee_factory, grant)
    response = source(client, source_url=url)
    assert response.status_code == 400, response.content
    assert Document.objects.count() == 0


def test_url_on_paper_source_is_rejected_instead_of_silently_dropped(employee_factory, grant):
    client, _ = clerk_client(employee_factory, grant)
    assert source(client, source_kind='paper_original').status_code == 400
    assert Document.objects.count() == 0


@pytest.mark.parametrize('path', ['../document.png', '/document.png', 'C:\\folder\\document.png',
                                   'folder/../document.png', 'folder/other.png', 'folder/\x00document.png'])
def test_folder_path_is_only_safe_metadata_and_invalid_input_writes_nothing(employee_factory, grant, settings, tmp_path, path):
    settings.MEDIA_ROOT = tmp_path
    client, employee = clerk_client(employee_factory, grant)
    doc = Document.objects.create(kind='decision', title='Дело', source_kind='uploaded_copy', created_by=employee)
    response = client.post(f'/api/v1/documents/{doc.pk}/versions/', {
        'expected_version': 1, 'relative_path': path, 'file': SimpleUploadedFile('document.png', PNG),
    }, HTTP_IDEMPOTENCY_KEY='bad-path')
    assert response.status_code == 400, response.content
    assert FileVersion.objects.count() == 0 and not list(tmp_path.rglob('*'))


def test_normalized_folder_path_replays_once_and_does_not_change_storage(employee_factory, grant, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    client, employee = clerk_client(employee_factory, grant)
    doc = Document.objects.create(kind='decision', title='Дело', source_kind='uploaded_copy', created_by=employee)
    def send(path):
        return client.post(f'/api/v1/documents/{doc.pk}/versions/', {
            'expected_version': 1, 'relative_path': path, 'file': SimpleUploadedFile('document.png', PNG),
        }, HTTP_IDEMPOTENCY_KEY='folder-retry')
    first = send('Дело\\document.png')
    assert first.status_code == 201, first.content
    assert first.json()['relative_path'] == 'Дело/document.png'
    assert send('Дело/document.png').json() == first.json()
    assert send('Другая/document.png').status_code == 409
    assert FileVersion.objects.count() == 1


def test_old_successful_upload_receipt_without_relative_path_still_replays(employee_factory, grant, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    client, employee = clerk_client(employee_factory, grant)
    doc = Document.objects.create(kind='decision', title='Старая копия', source_kind='uploaded_copy', created_by=employee)
    version = FileVersion.objects.create(document=doc, number=1, file='old/file.png', original_name='document.png',
        size=len(PNG), content_type='image/png', sha256=hashlib.sha256(PNG).hexdigest(), created_by=employee)
    execute_once(actor=employee.user, action='document.version.add', key='pre-upgrade', payload={
        'document_id': str(doc.pk), 'expected_version': 1, 'original_name': 'document.png',
        'size': len(PNG), 'sha256': hashlib.sha256(PNG).hexdigest(),
    }, operation=lambda: {'id': str(version.pk)})
    doc.version = 2; doc.save(update_fields=['version'])
    response = client.post(f'/api/v1/documents/{doc.pk}/versions/', {
        'expected_version': 1, 'file': SimpleUploadedFile('document.png', PNG),
    }, HTTP_IDEMPOTENCY_KEY='pre-upgrade')
    assert response.status_code == 201 and response.json()['id'] == str(version.pk)
    assert response.json()['relative_path'] == '' and FileVersion.objects.count() == 1


@pytest.mark.parametrize('consumer', ['intake','deadline','decree','previous','timing','plan'])
@pytest.mark.parametrize('archived',[False,True])
def test_url_without_archived_copy_is_not_paper_evidence_for_existing_consumers(vault,grant,consumer,archived):
    from apps.intake.models import Receipt
    from test_case_details import body as case_body
    from test_classification import body as class_body,previous
    from test_timing_facts import body as timing_body
    from test_report_plans import body as plan_body
    client,owner,(work,_),_=vault
    for action in ('receipts.accept','expertise.deadline.record','expertise.work.update','reports.plans.manage'):
        grant(owner,action)
    doc=Document.objects.create(kind='decision' if consumer=='intake' else 'expert_conclusion' if consumer=='previous' else 'deadline_agreement',
        title='Только внешняя ссылка',source_kind='external_link',source_url='https://example.org/evidence.pdf',created_by=owner)
    if archived:
        from test_basis_documents import upload
        assert upload(client,doc.pk).status_code==201
    before=work.version
    if consumer=='intake':
        receipt=Receipt.objects.create(material=work.material,created_by=owner,received_at='2026-10-01',basis_document=doc)
        path=f'/receipts/{receipt.pk}/register/';data={'expected_version':1}
    elif consumer=='deadline':
        path=f'/expertises/{work.pk}/deadline-events/'
        data={'expected_version':1,'kind':'agreement','recorded_on':'2026-10-02','due_on':'2026-11-01','reason':'По согласованию','document_id':str(doc.pk)}
    elif consumer=='decree':
        path=f'/expertises/{work.pk}/case-details/';data=case_body(work,decree3214=True,decree_document_id=str(doc.pk),decree_basis='Указано в документе')
    elif consumer=='previous':
        path=f'/expertises/{work.pk}/classification/';data=class_body(work,previous_conclusions=[previous(document_id=str(doc.pk))])
    elif consumer=='timing':
        path=f'/expertises/{work.pk}/timing/';data=timing_body(work,notification_sent=True,notification_on='2026-10-02',notification_document_id=str(doc.pk))
    else:
        path='/report-plans/2027/';data=plan_body(document_id=str(doc.pk))
    response=client.post('/api/v1'+path,data,content_type='application/json',HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
    assert response.status_code==(200 if archived else 400),response.content
    work.refresh_from_db();assert work.version==before+(1 if archived and consumer not in ('intake','plan') else 0)


def test_correspondence_evidence_requires_archive_not_only_external_reference(employee_factory,grant,settings,tmp_path):
    from test_letter_commands import command_setup,make_letter,registered,command
    from test_basis_documents import upload
    settings.MEDIA_ROOT=tmp_path
    client,actor,options,journals=command_setup(employee_factory,grant)
    letter=registered(client,make_letter(client,options),journals)
    doc=Document.objects.create(kind='letter',title='Подтверждение получения',source_kind='external_link',
        source_url='https://example.org/proof.pdf',created_by=actor)
    response=command(client,letter,'mark-received',received_on='2026-10-02',evidence_document_id=str(doc.pk))
    assert response.status_code==400,response.content
    saved=upload(client,doc.pk);assert saved.status_code==201
    response=command(client,letter,'mark-received',received_on='2026-10-02',evidence_document_id=str(doc.pk))
    assert response.status_code==200,response.content
    assert response.json()['letter']['receipts'][0]['evidence']['accepted_version_id']==saved.json()['id']
