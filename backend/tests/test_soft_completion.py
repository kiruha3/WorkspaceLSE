import uuid
import pytest
from apps.documents.models import Document
from apps.expertises.models import Expertise, WorkClosure
from test_result_completion import completion_setup, send
from test_result_drafts import draft, result_document
from test_basis_documents import upload

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize('kind', ['expert_conclusion', 'sndz', 'research_act'])
@pytest.mark.parametrize('has_document', [False, True])
def test_complete_without_file_keeps_gap_and_does_not_create_fake_document(employee_factory, grant, kind, has_document):
    client, _, work, _, _, _, _ = completion_setup(employee_factory, grant)
    if kind == 'research_act':
        Expertise.objects.filter(pk=work['id']).update(category_code='6')
    doc = result_document(client, kind) if has_document else None
    before = Document.objects.count()
    work = draft(client, work, kind=kind, completed_on='2026-10-10', document_id=doc['id'] if doc else None).json()['expertise']
    assert not work['result_readiness']['completion_blockers']
    assert any(g['code'] == 'file_missing' for g in work['result_readiness']['document_gaps'])
    key = str(uuid.uuid4())
    response = send(client, work, 'complete', key=key, result_id=work['result']['id'])
    assert response.status_code == 200, response.content
    done = response.json()['expertise']
    closure = WorkClosure.objects.get(pk=done['closure']['id'])
    assert done['state'] == 'completed' and done['closure']['ended_on'] == '2026-10-10'
    assert closure.document_id == (uuid.UUID(doc['id']) if doc else None)
    assert closure.accepted_version_id is None and Document.objects.count() == before
    assert done['result']['questions'] is None
    assert send(client, work, 'complete', key=key, result_id=work['result']['id']).json()['event'] == response.json()['event']
    assert client.get(f"/api/v1/expertises/{work['id']}/documents/").status_code == 200


@pytest.mark.parametrize('has_document', [False, True])
def test_return_and_correct_without_file_preserve_real_decision(employee_factory, grant, has_document):
    client, actor, work, _, _, _, _ = completion_setup(employee_factory, grant)
    doc = result_document(client, 'return_decision') if has_document else None
    fields = {'decided_on': '2026-10-10', 'document_id': doc['id'] if doc else None}
    response = send(client, work, 'return-without-execution', **fields)
    assert response.status_code == 200, response.content
    done = response.json()['expertise']
    assert done['state'] == 'without_execution' and done['result'] is None
    assert any(g['code'] == 'file_missing' for g in done['result_readiness']['document_gaps'])
    grant(actor, 'expertise.closed.correct', 'own')
    corrected = send(client, done, 'correct', correction_kind='return', decided_on='2026-10-11', document_id=None)
    assert corrected.status_code == 200, corrected.content
    assert corrected.json()['expertise']['closure']['document'] is None
    assert len(corrected.json()['expertise']['closure_history']) == 2


def test_later_file_resolves_current_gap_without_rewriting_closure_snapshot(employee_factory, grant, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    client, _, work, _, _, _, _ = completion_setup(employee_factory, grant)
    doc = result_document(client)
    work = draft(client, work, completed_on='2026-10-10', document_id=doc['id']).json()['expertise']
    response = send(client, work, 'complete', result_id=work['result']['id'])
    assert response.status_code == 200, response.content
    assert upload(client, doc['id']).status_code == 201
    detail = client.get(f"/api/v1/expertises/{work['id']}/").json()
    assert not detail['result_readiness']['document_gaps']
    assert detail['closure']['document']['accepted_version_id'] is None
    assert WorkClosure.objects.get(pk=detail['closure']['id']).accepted_version_id is None


def test_soft_completion_still_rejects_missing_kind_date_and_unauthorised_actor(employee_factory, grant):
    client, actor, work, clerk, _, _, _ = completion_setup(employee_factory, grant)
    work = draft(client, work, kind=None, completed_on=None).json()['expertise']
    assert send(client, work, 'complete', result_id=work['result']['id']).status_code == 400
    work = draft(client, work, kind='sndz', completed_on='2026-10-10').json()['expertise']
    assert send(clerk, work, 'complete', result_id=work['result']['id']).status_code == 403
    actor.role_assignments.filter(role__permissions__permission_code='expertise.complete').update(is_active=False)
    assert send(client, work, 'complete', result_id=work['result']['id']).status_code == 403
