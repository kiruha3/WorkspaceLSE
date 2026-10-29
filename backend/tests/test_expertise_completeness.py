import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from apps.accounts.models import CommandReceipt
from apps.audit.models import AuditEvent
from apps.documents.models import Document, WorkDocumentLink
from apps.expertises.models import Expertise, WorkClosure
from test_result_completion import completion_setup, send, ready_result
from test_result_drafts import draft, result_document
from test_basis_documents import upload

pytestmark = pytest.mark.django_db
URL = '/api/v1/expertises/incomplete/'


def sibling(work, number, **fields):
    original = Expertise.objects.get(pk=work['id'])
    return Expertise.objects.create(material=original.material, receipt=original.receipt, department=original.department,
        specialty=original.specialty, registered_by=original.registered_by, registration_number=f'{number}/3-1-26',
        sequence=number, year=2026, category_code='1', appointment_nature='primary', is_commission=False, **fields)


def test_home_reminders_group_work_gaps_without_writing_data(employee_factory, grant):
    client, _, work, _, _, _, _ = completion_setup(employee_factory, grant)
    work = draft(client, work, completed_on='2026-10-10').json()['expertise']
    assert send(client, work, 'complete', result_id=work['result']['id']).status_code == 200
    models = (Expertise, Document, AuditEvent, CommandReceipt, WorkClosure)
    before = [model.objects.count() for model in models]
    response = client.get(URL)
    assert response.status_code == 200
    data = response.json()
    assert data['count'] == 1 and len(data['results']) == 1
    row = data['results'][0]
    assert row['id'] == work['id'] and row['registration_number'] == work['registration_number']
    assert row['state'] == 'completed'
    codes = [item['code'] for item in row['missing']]
    assert 'result_document_missing' in codes and 'statistics_unconfirmed' in codes
    assert len(codes) == len(set(codes))
    assert [model.objects.count() for model in models] == before
    assert 'expertise_completeness' in client.get('/api/v1/me/').json()['supported_modules']


def test_reminders_never_expose_foreign_work_and_recheck_revoked_scope(employee_factory, grant):
    client, actor, work, _, _, _, _ = completion_setup(employee_factory, grant)
    other = sibling(work, 901)
    response = client.get(URL)
    assert response.status_code == 200 and response.json()['count'] == 1
    assert str(other.pk) not in response.content.decode()
    actor.role_assignments.filter(role__permissions__permission_code='expertise.view').update(is_active=False)
    assert client.get(URL).status_code == 403


@pytest.mark.parametrize('scope,want', [('departments', 1), ('institution', 2)])
def test_reminder_department_and_institution_scopes_follow_existing_roles(employee_factory, grant, scope, want):
    from apps.references.models import Department
    client, actor, work, _, _, own_department, _ = completion_setup(employee_factory, grant)
    foreign = sibling(work, 902)
    department = Department.objects.create(code='99', name='Другой отдел')
    Expertise.objects.filter(pk=foreign.pk).update(department=department)
    actor.role_assignments.filter(role__permissions__permission_code='expertise.view').update(is_active=False)
    grant(actor, 'expertise.view', scope, departments=[own_department] if scope == 'departments' else [])
    response = client.get(URL)
    assert response.status_code == 200
    assert response.json()['count'] == want


def test_stored_link_resolves_reference_gap_without_exposing_document_text(employee_factory, grant):
    client, actor, work, _, _, _, _ = completion_setup(employee_factory, grant)
    work = draft(client, work, completed_on='2026-10-10').json()['expertise']
    assert send(client, work, 'complete', result_id=work['result']['id']).status_code == 200
    doc = client.post('/api/v1/documents/', {'kind': 'expert_conclusion', 'title': 'PRIVATE_TITLE_NOT_IN_REMINDERS', 'source_kind': 'external_link', 'source_url': 'https://example.org/result.pdf'}, content_type='application/json')
    assert doc.status_code == 201
    WorkDocumentLink.objects.create(expertise_id=work['id'], document_id=doc.json()['id'], actor=actor.user)
    actor.role_assignments.filter(role__permissions__permission_code='documents.view').update(is_active=False)
    response = client.get(URL)
    assert response.status_code == 200
    assert 'result_document_missing' not in {item['code'] for item in response.json()['results'][0]['missing']}
    assert 'PRIVATE_TITLE_NOT_IN_REMINDERS' not in response.content.decode()
    assert 'https://example.org' not in response.content.decode()


def test_complete_reference_and_zero_statistics_remove_work_from_reminders(employee_factory, grant, settings, tmp_path):
    from test_issue_drafts import issue_setup, create_package, package_items
    settings.MEDIA_ROOT = tmp_path
    clerk, _, work, expert, _, _, _ = issue_setup(employee_factory, grant)
    assert upload(clerk, work['basis_document']['id']).status_code == 201
    work = ready_result(expert, work, questions=0, categorical=0, probable=0, unresolved=0,
                        statistics_complete=True, complexity_level=1)
    assert send(expert, work, 'complete', result_id=work['result']['id']).status_code == 200
    items = package_items(clerk, work, ['expert_subscription', 'cover_letter', 'notification'])
    assert create_package(clerk, work['material']['id'], materials_description='По описи', items=items).status_code == 201
    response = expert.get(URL)
    assert response.status_code == 200
    assert response.json()['count'] == 0 and response.json()['results'] == []


def test_attached_later_result_reference_resolves_gap_without_faking_old_acceptance(employee_factory, grant, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    client, actor, work, _, _, _, _ = completion_setup(employee_factory, grant)
    work = draft(client, work, completed_on='2026-10-10').json()['expertise']
    assert send(client, work, 'complete', result_id=work['result']['id']).status_code == 200
    doc = result_document(client)
    assert upload(client, doc['id']).status_code == 201
    WorkDocumentLink.objects.create(expertise_id=work['id'], document_id=doc['id'], actor=actor.user)
    response = client.get(URL)
    assert response.status_code == 200
    assert 'result_document_missing' not in {item['code'] for item in response.json()['results'][0]['missing']}
    closure = WorkClosure.objects.get(expertise_id=work['id'])
    assert closure.document_id is None and closure.accepted_version_id is None
    detail = client.get(f"/api/v1/expertises/{work['id']}/").json()
    assert detail['result_readiness']['document_gaps'] == []


def test_historical_work_gets_real_missing_fields_without_operational_activation(employee_factory, grant, settings, tmp_path):
    from historical_samples import historical_setup
    client, _, work, history, _, _ = historical_setup(employee_factory, grant, settings, tmp_path)
    response = client.get(URL)
    assert response.status_code == 200
    assert response.json()['results'][0]['id'] == str(work.pk)
    assert 'result_document_missing' in {item['code'] for item in response.json()['results'][0]['missing']}
    history.refresh_from_db()
    assert not history.operational and not work.closures.exists()


def test_reminders_paginate_once_and_avoid_per_work_queries(employee_factory, grant):
    client, actor, work, _, _, _, _ = completion_setup(employee_factory, grant)
    grant(actor, 'expertise.view', 'institution')
    with CaptureQueriesContext(connection) as first:
        assert client.get(URL).status_code == 200
    for number in range(1001, 1031):
        sibling(work, number)
    with CaptureQueriesContext(connection) as many:
        response = client.get(URL)
    assert response.status_code == 200
    first_page = response.json()
    assert first_page['count'] == 31 and len(first_page['results']) == 25
    second_page = client.get(URL, {'page': 2}).json()
    ids = [row['id'] for row in first_page['results'] + second_page['results']]
    assert len(ids) == len(set(ids)) == 31
    assert len(many) <= len(first) + 2
