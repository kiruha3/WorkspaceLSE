from types import SimpleNamespace
import uuid
import pytest

from apps.accounts.models import CommandReceipt
from apps.expertises.models import Expertise, WorkCaseDetails, CaseDetailsRevision
from apps.reports.calculation import calculate
from test_registration import registration_setup, register
from test_case_details import body, send

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize('code', ['16.1', '16.2'])
@pytest.mark.parametrize('marked', [True, False])
def test_registration_persists_optional_construction_flag_without_extra_file(employee_factory, grant, code, marked):
    client, actor, receipt, _, specialty, values = registration_setup(employee_factory, grant)
    specialty.code = code
    specialty.save()
    values['decree3214'] = marked
    key = str(uuid.uuid4())
    response = register(client, receipt, values, key)
    assert response.status_code == 201, response.content
    work = response.json()
    assert work['case_details']['decree3214'] is marked
    assert work['case_details']['decree_document'] is None
    assert WorkCaseDetails.objects.count() == 1 and CaseDetailsRevision.objects.count() == 1
    assert register(client, receipt, values, key).status_code == 201
    assert Expertise.objects.count() == 1 and CaseDetailsRevision.objects.count() == 1
    saved = client.get(f"/api/v1/expertises/{work['id']}/").json()
    assert saved['case_details']['decree3214'] is marked
    assert saved['case_details']['revisions'][0]['after']['decree3214'] is marked


def test_other_specialty_rejects_new_mark_atomically_but_old_registration_payload_works(employee_factory, grant):
    client, _, receipt, _, _, values = registration_setup(employee_factory, grant)
    key = str(uuid.uuid4())
    response = register(client, receipt, {**values, 'decree3214': True}, key)
    assert response.status_code == 400
    assert not Expertise.objects.exists() and not WorkCaseDetails.objects.exists()
    assert not CommandReceipt.objects.filter(key=key).exists()
    assert register(client, receipt, values).status_code == 201


def test_edit_flag_without_document_can_be_cleared_with_history_and_version_guard(employee_factory, grant):
    client, actor, receipt, _, specialty, values = registration_setup(employee_factory, grant)
    specialty.code = '16.1'
    specialty.save()
    response = register(client, receipt, values)
    assert response.status_code == 201
    work = Expertise.objects.get(pk=response.json()['id'])
    grant(actor, 'expertise.work.update')
    key = str(uuid.uuid4())
    marked_body = body(work, decree3214=True)
    marked = send(client, work, marked_body, key)
    assert marked.status_code == 200, marked.content
    assert marked.json()['expertise']['case_details']['decree3214'] is True
    assert send(client, work, marked_body, key).status_code == 200
    assert send(client, work, marked_body).status_code == 409
    work.refresh_from_db()
    cleared = send(client, work, body(work, decree3214=False))
    assert cleared.status_code == 200
    details = cleared.json()['expertise']['case_details']
    assert details['decree3214'] is False and len(details['revisions']) == 2
    assert details['revisions'][0]['after']['decree3214'] is True
    assert details['revisions'][1]['before']['decree3214'] is True


def test_other_specialty_cannot_be_newly_marked_but_legacy_mark_is_retained(employee_factory, grant):
    from apps.documents.models import Document
    client, actor, receipt, _, _, values = registration_setup(employee_factory, grant)
    work = Expertise.objects.get(pk=register(client, receipt, values).json()['id'])
    grant(actor, 'expertise.work.update')
    assert send(client, work, body(work, decree3214=True)).status_code == 400
    assert not WorkCaseDetails.objects.exists() and not CaseDetailsRevision.objects.exists()
    evidence = Document.objects.create(kind='resolution', source_kind='paper_original', created_by=actor)
    WorkCaseDetails.objects.create(expertise=work, created_by=actor.user, decree3214=True,
                                  decree_document=evidence, decree_basis='Старое основание')
    grant(actor, 'documents.view')
    response = send(client, work, body(work, decree3214=True, decree_document_id=str(evidence.pk), decree_basis='Старое основание'))
    assert response.status_code == 200, response.content
    assert response.json()['expertise']['case_details']['decree3214'] is True


def test_unresolved_historical_specialty_rejects_new_mark_without_server_error(employee_factory, grant, settings, tmp_path):
    from test_case_details import setup
    client, _, work, _, _, _ = setup(employee_factory, grant, settings, tmp_path, specialty_known=False)
    response = send(client, work, body(work, decree3214=True))
    assert response.status_code == 400
    assert not WorkCaseDetails.objects.exists() and not CaseDetailsRevision.objects.exists()


@pytest.mark.parametrize('code,marked,want', [
    ('16.1', True, 1), ('16.2', True, 1), ('16.1', False, 0), ('16.2', None, 0),
    ('18.1', True, 0), ('1.1', None, 0),
])
def test_report_3214_counts_only_marked_construction_specialties(code, marked, want):
    facts = {'registration_number': '1/3-1-26', 'received_on': '2026-01-01', 'source_end_on': '2026-10-10',
             'state': 'completed', 'category_code': '1', 'result_kind': 'expert_conclusion',
             'specialty_code': code, 'decree3214': marked, 'questions': 1, 'categorical': 1, 'probable': 0,
             'unresolved': 0, 'complexity_level': 1, 'authority_group': 'mvd'}
    report = calculate([SimpleNamespace(facts=facts, raw={}, source_row='work')], 2026, 10, mode='registry')
    assert next(cell for cell in report['cells'] if cell['sheet'] == 'Раздел 1' and cell['address'] == 'P108')['value'] == want
    assert not any(gap['code'] == 'decree3214' for gap in report['gaps'])
