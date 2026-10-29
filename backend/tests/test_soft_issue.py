import pytest
from django.core.management import call_command
from apps.expertises.models import Expertise
from test_issue_drafts import issue_setup, create_package, package_items, save_package
from test_issue_commands import package_command, issue_values
from test_result_completion import send
from test_result_drafts import draft

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize('variant', ['conclusion', 'research', 'sndz', 'return', 'commission', 'paid'])
def test_missing_digital_pack_warns_but_allows_checked_actual_issue(employee_factory, grant, variant):
    kind = 'research_act' if variant == 'research' else 'sndz' if variant == 'sndz' else 'expert_conclusion'
    client, _, work, expert, _, _, _ = issue_setup(employee_factory, grant, category='6' if variant == 'research' else '1')
    if variant == 'commission':
        Expertise.objects.filter(pk=work['id']).update(is_commission=True)
    if variant == 'return':
        response = send(expert, work, 'return-without-execution', decided_on='2026-10-10', document_id=None)
    else:
        work = draft(expert, work, kind=kind, completed_on='2026-10-10').json()['expertise']
        response = send(expert, work, 'complete', result_id=work['result']['id'])
    assert response.status_code == 200, response.content
    package = create_package(client, work['material']['id'], materials_description='Материалы по описи',
                             billing=[{'expertise_id': work['id'], 'is_paid': True if variant == 'paid' else None}]).json()['package']
    assert package['readiness']['can_check'], package['readiness']
    assert package['readiness']['blockers'] == []
    warnings = package['readiness']['warnings']
    assert any(item['code'] == 'file_missing' and item['expertise_id'] == work['id'] for item in warnings)
    assert any(item['code'] == 'item_missing' and item['field'] == 'cover_letter' for item in warnings)
    if variant == 'return':
        assert 'expert_subscription' not in package['works'][0]['required_items']
    if variant == 'sndz':
        assert 'notification' not in package['works'][0]['required_items']
    if variant == 'paid':
        assert any(item['field'] == 'invoice' for item in warnings)
    checked = package_command(client, package, 'check')
    assert checked.status_code == 200, checked.content
    package = checked.json()['package']
    assert package['checks'][0]['files'] == []
    assert package['works'][0]['closure']['document'] is None
    call_command('seed_issue_catalogs', verbosity=0)
    issued = package_command(client, package, 'issue', **issue_values())
    assert issued.status_code == 200, issued.content
    assert issued.json()['package']['issuance']['issued_on'] == '2026-10-15'


def test_missing_copy_bytes_are_warnings_and_resolve_after_upload(employee_factory, grant, settings, tmp_path):
    from test_basis_documents import upload
    settings.MEDIA_ROOT = tmp_path
    client, _, work, _, _, _, _ = issue_setup(employee_factory, grant, completed=True)
    items = package_items(client, work, ['expert_subscription', 'cover_letter', 'notification'], source='uploaded_copy')
    package = create_package(client, work['material']['id'], materials_description='Два тома', items=items).json()['package']
    assert package['readiness']['can_check']
    assert any(item['code'] == 'file_missing' for item in package['readiness']['warnings'])
    for item in items:
        assert upload(client, item['document_id']).status_code == 201
    refreshed = client.get(f"/api/v1/issue-packages/{package['id']}/").json()
    assert not any(item['code'] == 'file_missing' for item in refreshed['readiness']['warnings'])


def test_optional_issue_evidence_without_file_does_not_block_actual_issue(employee_factory, grant, settings, tmp_path):
    from test_issue_commands import ready_package, checked
    from test_issue_drafts import item_document
    settings.MEDIA_ROOT = tmp_path
    client, _, _, package, _, _, _, _ = ready_package(employee_factory, grant)
    package = checked(client, package)
    evidence = item_document(client, 'letter', source='uploaded_copy')
    response = package_command(client, package, 'issue', **issue_values(evidence_document_id=evidence['id']))
    assert response.status_code == 200, response.content
    assert response.json()['package']['issuance']['evidence']['accepted_version_id'] is None
