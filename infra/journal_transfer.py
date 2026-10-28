"""Recovery checks for the explicitly approved, one-off journal transfer.

Not an HTTP endpoint or an automatic department/identity inference service.
The caller saves a durable baseline and database backup before any mutation.
"""
import hashlib
import json
from pathlib import Path

from django.db import transaction
from apps.documents.models import Document, FileVersion
from apps.expertises.models import ExpertAssignment, WorkClosure, Suspension, DeadlineEvent
from apps.imports.models import ImportApplicationItem
from apps.personnel.models import Employee, EmployeeSpecialty
from apps.references.models import Department


@transaction.atomic
def ensure_historical_department(client):
    name = 'Отдел 1 (исторический код)'
    ref = Department.objects.filter(code='1').first()
    if ref is None:
        response = client.post('/api/v1/references/departments/',
                               {'code': '1', 'name': name}, content_type='application/json')
        assert response.status_code == 201, response.content
        ref = Department.objects.get(pk=response.json()['id'])
    # Never deactivate an unrelated reference silently on recovery.
    assert ref.name == name, 'Historical department 1 needs manual review'
    if ref.is_active:
        response = client.patch(f'/api/v1/references/departments/{ref.pk}/',
                                {'expected_version': ref.version, 'is_active': False},
                                content_type='application/json')
        assert response.status_code == 200, response.content
        ref.refresh_from_db()
    assert not ref.is_active
    return ref


def workflow_counts():
    return {model.__name__: model.objects.count() for model in
            (ExpertAssignment, WorkClosure, Suspension, DeadlineEvent,
             Document, FileVersion, EmployeeSpecialty, Employee)}


def source_digest(batch):
    rows = [(str(row.pk), row.raw, row.facts) for row in batch.rows.order_by('source_row')]
    return hashlib.sha256(json.dumps(rows, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def verify_transfer(batch, expected_names_by_row, baseline):
    """Verify the same invariants after normal apply AND after interruption.

    A matching count alone is not a receipt. Recover the original application
    and backup association only after checking each real work and its people.
    """
    assert baseline['batch_id'] == str(batch.pk)
    assert baseline['source_sha256'] == batch.source_sha256
    backup = Path(baseline['backup'])
    with backup.open('rb') as stream:
        assert stream.read(5) == b'PGDMP', 'Missing or invalid pre-transfer backup'
    assert source_digest(batch) == baseline['source_digest'], 'Source changed'
    links = list(ImportApplicationItem.objects.filter(row__batch=batch).select_related(
        'row', 'work__department', 'work__receipt', 'work__historical', 'application__actor'
    ).prefetch_related('work__historical__participants__employee'))
    assert {str(link.row_id) for link in links} == set(expected_names_by_row), 'Applied row set differs'
    assert len({link.work_id for link in links}) == len(links), 'Work linked more than once'
    assert len({link.application_id for link in links}) == 1, 'Expected one original application'
    for link in links:
        work, facts = link.work, link.row.facts
        assert work.registration_number == facts['registration_number'], 'Registration number changed'
        assert work.department.code == facts['department_code'], 'Work department differs'
        assert work.receipt.department_id == work.department_id, 'Receipt department differs'
        assert work.origin_kind == 'historical' and work.receipt.status == 'historical'
        assert work.historical.source_row_id == link.row_id and not work.historical.operational
        actual = {p.employee.full_name for p in work.historical.participants.all()}
        assert actual == set(expected_names_by_row[str(link.row_id)]), 'Participant links differ'
    counts = workflow_counts()
    assert counts == baseline['before_counts'], ('Unexpected workflow/personnel writes', counts)
    application = links[0].application
    return {'application_id': str(application.pk), 'import_actor': application.actor.username,
            'applied_at': application.created_at.isoformat(), 'verified_rows': len(links),
            'backup': str(backup), 'source_sha256': batch.source_sha256,
            'uncreated_workflow_counts': counts}
