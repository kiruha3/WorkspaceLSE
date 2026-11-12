from datetime import date
import pytest
from django.utils import timezone
from apps.expertises.models import ExpertAssignment, HistoricalParticipant, Expertise
from apps.personnel.models import EmployeeSpecialty, EmployeeRole
from historical_samples import historical_setup
from activation_samples import activation_body, activate

pytestmark = pytest.mark.django_db
URL = '/api/v1/imports/historical-assignments/'


@pytest.fixture
def sample(employee_factory, grant, settings, tmp_path):
    client, actor, work, history, department, specialty = historical_setup(
        employee_factory, grant, settings, tmp_path, state='in_progress', ended=None)
    for code in ('imports.apply', 'expertise.assign'):
        grant(actor, code)
    expert = employee_factory(department=department)
    HistoricalParticipant.objects.create(history=history, employee=expert)
    qualification = EmployeeSpecialty.objects.create(employee=expert, specialty=specialty, status='qualified')
    return client, actor, work, history, expert, qualification


def choice(client, work):
    response = client.get(URL)
    assert response.status_code == 200, response.content
    return next(row for row in response.json()['results'] if row['expertise_id'] == str(work.pk))


def apply(client, rows, key='historical-transfer'):
    return client.post(URL, {'selections': [
        {field: row[field] for field in ('expertise_id', 'expected_version', 'proposal_hash')}
        for row in rows], 'reason': 'Подтверждённый перенос исполнителей'},
        content_type='application/json', HTTP_IDEMPOTENCY_KEY=key)


def test_preview_and_explicit_transfer_preserve_history_and_retry(sample):
    client, actor, work, history, expert, qualification = sample
    row = choice(client, work)
    assert row['eligible'] and row['employees'][0]['id'] == str(expert.pk)
    assert not ExpertAssignment.objects.exists()
    before = timezone.now()
    result = apply(client, [row])
    assert result.status_code == 201, result.content
    assignment = ExpertAssignment.objects.get()
    assert assignment.employee_id == expert.pk and assignment.started_at >= before
    assert assignment.qualification_snapshot['historical_import']['history_id'] == str(history.pk)
    work.refresh_from_db(); history.refresh_from_db(); qualification.refresh_from_db()
    assert work.registration_number == '151/4-1-26' and work.state == 'in_progress'
    assert work.version == 2 and work.is_commission is None and not history.operational
    assert history.executor_raw == 'ДЕМО · имя в журнале' and qualification.version == 1
    assert apply(client, [row]).json() == result.json()
    assert ExpertAssignment.objects.count() == 1
    assert not choice(client, work)['eligible']
    assert apply(client, [row], 'different-key').status_code == 409


@pytest.mark.parametrize('change', ['training', 'unknown_legacy', 'inactive', 'missing', 'closed', 'issued', 'unmatched', 'previous_assignment', 'composition'])
def test_blocks_unsafe_transfers(sample, change):
    client, actor, work, history, expert, qualification = sample
    if change in ('training', 'unknown_legacy'):
        qualification.status = change; qualification.save()
    elif change == 'missing': qualification.delete()
    elif change == 'inactive': expert.is_active = False; expert.save()
    elif change == 'closed': work.state = 'completed'; work.save()
    elif change == 'issued': history.issued_on = date(2026, 10, 6); history.save()
    elif change == 'unmatched': history.participants.all().delete()
    elif change == 'composition': work.is_commission = True; work.save()
    else: ExpertAssignment.objects.create(expertise=work, employee=expert, started_at=timezone.now(), ended_at=timezone.now(), actor=actor.user)
    count = ExpertAssignment.objects.count()
    row = choice(client, work)
    assert not row['eligible'] and row['blockers']
    assert apply(client, [row]).status_code == 409
    assert ExpertAssignment.objects.count() == count


@pytest.mark.parametrize('change', ['match', 'version', 'qualification'])
def test_stale_proposal_is_rejected(sample, employee_factory, change):
    client, actor, work, history, expert, qualification = sample
    row = choice(client, work)
    if change == 'match': HistoricalParticipant.objects.create(history=history, employee=employee_factory())
    elif change == 'version': work.version += 1; work.save()
    else: qualification.basis = 'Изменённое основание'; qualification.save()
    assert apply(client, [row]).status_code == 409
    assert not ExpertAssignment.objects.exists()


def test_revoked_right_and_department_scope_apply_on_replay(sample, grant):
    client, actor, work, history, expert, qualification = sample
    row = choice(client, work)
    assert apply(client, [row]).status_code == 201
    EmployeeRole.objects.filter(employee=actor, role__permissions__permission_code='expertise.assign').delete()
    assert apply(client, [row]).status_code == 403
    grant(actor, 'expertise.assign', scope='departments', departments=[])
    assert apply(client, [row]).status_code == 403


def test_unselected_work_unchanged_and_batch_rolls_back(sample):
    client, actor, work, history, expert, qualification = sample
    other = Expertise.objects.create(material=work.material, receipt=work.receipt,
        registration_number='152/4-1-26', sequence=152, year=2026, category_code='1',
        department=work.department, specialty=work.specialty, state='in_progress', origin_kind='historical', registered_by=actor.user)
    from apps.expertises.models import HistoricalWork
    second = HistoricalWork.objects.create(expertise=other, source_row=history.source_row, actor=actor.user)
    HistoricalParticipant.objects.create(history=second, employee=expert)
    first, last = choice(client, work), choice(client, other)
    other.version += 1; other.save()
    assert apply(client, [first, last]).status_code == 409
    assert not ExpertAssignment.objects.exists()
    assert apply(client, [first], 'only-one').status_code == 201
    assert not other.assignments.exists()


def test_imported_assignments_allow_later_activation(sample, grant):
    client, actor, work, history, expert, qualification = sample
    for code in ('imports.history.activate', 'expertise.register', 'documents.view'): grant(actor, code)
    from apps.documents.models import Document
    basis = Document.objects.create(kind='resolution', title='Основание', source_kind='paper_original', created_by=actor, department=work.department)
    assert apply(client, [choice(client, work)]).status_code == 201
    result = activate(client, work, activation_body(basis, work.specialty, expected_version=2))
    assert result.status_code == 200, result.content
    history.refresh_from_db()
    assert history.operational and work.assignments.count() == 1


def test_preview_needs_import_read_and_apply_needs_import_permission(sample):
    client, actor, work, history, expert, qualification = sample
    row = choice(client, work)
    EmployeeRole.objects.filter(employee=actor, role__permissions__permission_code='imports.apply').delete()
    assert client.get(URL).status_code == 200
    assert apply(client, [row]).status_code == 403
    EmployeeRole.objects.filter(employee=actor, role__permissions__permission_code='imports.results.view').delete()
    assert client.get(URL).status_code == 403


def test_activation_preserves_assignment_snapshot_when_qualification_later_changes(sample, grant):
    client, actor, work, history, expert, qualification = sample
    for code in ('imports.history.activate', 'expertise.register', 'documents.view'): grant(actor, code)
    from apps.documents.models import Document
    basis = Document.objects.create(kind='resolution', title='Основание', source_kind='paper_original', created_by=actor, department=work.department)
    assert apply(client, [choice(client, work)]).status_code == 201
    expert.is_active = False; expert.save()
    qualification.status = 'unknown_legacy'; qualification.save()
    result = activate(client, work, activation_body(basis, work.specialty, expected_version=2))
    assert result.status_code == 200, result.content
    assert work.assignments.get().qualification_snapshot['status'] == 'qualified'


def test_commission_composition_must_be_confirmed_consistently_at_activation(sample, employee_factory, grant):
    client, actor, work, history, expert, qualification = sample
    other = employee_factory()
    HistoricalParticipant.objects.create(history=history, employee=other)
    EmployeeSpecialty.objects.create(employee=other, specialty=work.specialty, status='qualified')
    assert apply(client, [choice(client, work)]).status_code == 201
    for code in ('imports.history.activate', 'expertise.register', 'documents.view'): grant(actor, code)
    from apps.documents.models import Document
    basis = Document.objects.create(kind='resolution', title='Основание', source_kind='paper_original', created_by=actor, department=work.department)
    assert activate(client, work, activation_body(basis, work.specialty, expected_version=2)).status_code == 400
    result = activate(client, work, activation_body(basis, work.specialty, expected_version=2, is_commission=True), key='commission')
    assert result.status_code == 200, result.content


@pytest.mark.parametrize('permission', ['imports.apply', 'imports.results.view', 'expertise.view', 'expertise.assign'])
def test_right_revoked_while_acquiring_locks_cancels_the_whole_command(sample, monkeypatch, permission):
    client, actor, work, history, expert, qualification = sample
    row = choice(client, work)
    from apps.imports import historical_assignments as service
    original = service.qualifications_for

    def revoke_after_locks(works, lock=False):
        values = original(works, lock=lock)
        if lock:
            EmployeeRole.objects.filter(employee=actor, role__permissions__permission_code=permission).update(is_active=False)
        return values

    monkeypatch.setattr(service, 'qualifications_for', revoke_after_locks)
    assert apply(client, [row]).status_code == 403
    assert not ExpertAssignment.objects.exists()
