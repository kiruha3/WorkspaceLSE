"""Explicit, one-time transfer of confirmed historical participants.

This creates assignments dated today, never historical production facts. The
normal journal refresh deliberately does not call this command.
"""
import hashlib
import json
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from apps.accounts.commands import CommandConflict, execute_once
from apps.accounts.policies import AccessScope, permission_scopes, require
from apps.accounts.services import audit
from apps.expertises.models import Expertise, HistoricalWork, HistoricalParticipant, ExpertAssignment
from apps.expertises.policies import expertise_scope_queryset, require_work
from apps.intake.models import Material, Receipt
from apps.issuance.models import MaterialIssue
from apps.personnel.models import Employee, EmployeeSpecialty
from apps.personnel.services import qualification_eligibility
from apps.references.models import Specialty
from .policies import require_preview_read

ACTION = 'imports.historical_assignments.apply'


def works_for(actor, scopes):
    return expertise_scope_queryset(actor, 'expertise.view', scopes).filter(origin_kind='historical', historical__isnull=False)


def hydrated(works):
    return works.select_related('historical__source_row', 'specialty').prefetch_related('assignments', 'historical__participants__employee')


def qualifications_for(works, lock=False):
    employees = {p.employee_id for work in works for p in work.historical.participants.all()}
    rows = EmployeeSpecialty.objects.filter(employee_id__in=employees, specialty_id__in={w.specialty_id for w in works}).order_by('employee_id', 'specialty_id')
    if lock: rows = rows.select_for_update()
    return {(q.employee_id, q.specialty_id): q for q in rows}


def qualification_snapshot(q):
    return {'qualification_id': str(q.pk), 'specialty_id': str(q.specialty_id),
            'status': q.status, 'qualified_at': q.qualified_at.isoformat() if q.qualified_at else None,
            'valid_until': q.valid_until.isoformat() if q.valid_until else None, 'basis': q.basis, 'version': q.version}


def issued_materials(works):
    ids = {work.material_id for work in works}
    return set(MaterialIssue.objects.filter(package__material_id__in=ids).values_list('package__material_id', flat=True)) | set(
        HistoricalWork.objects.filter(expertise__material_id__in=ids, issued_on__isnull=False).values_list('expertise__material_id', flat=True))


def proposal(work, qualifications, issued, scopes):
    history = work.historical
    participants = list(history.participants.all())
    blockers = []
    if work.state not in ('in_progress', 'suspended'): blockers.append('Работа закрыта. Перенос нужен только для незавершённых экспертиз.')
    if work.material_id in issued: blockers.append('Материалы уже выданы.')
    if list(work.assignments.all()): blockers.append('Назначения уже есть или были ранее. Используйте обычное перепоручение в карточке.')
    if not participants: blockers.append('Нет подтверждённого соответствия сотруднику. Сначала сопоставьте исполнителя при сверке источника.')
    if work.is_commission is True and len(participants) < 2 or work.is_commission is False and len(participants) != 1:
        blockers.append('Исторические участники не соответствуют подтверждённому составу работы.')
    if not scopes.get('expertise.assign', AccessScope()).allows(department_ids=[work.department_id]):
        blockers.append('Нет права «Назначать экспертов» в отделе этой работы.')
    if not work.specialty_id: blockers.append('Специальность работы не сопоставлена.')
    snapshots = []
    for participant in participants:
        employee = participant.employee
        q = qualifications.get((employee.pk, work.specialty_id))
        if work.specialty_id:
            eligibility = qualification_eligibility(employee, work.specialty, timezone.localdate(), qualification=q)
            if not eligibility['eligible']: blockers.append(f'{employee.full_name}: {eligibility["message"]}')
        snapshots.append({'id': str(employee.pk), 'active': employee.is_active, 'version': employee.version,
                          'qualification': qualification_snapshot(q) if q else None})
    item = {'expertise_id': str(work.pk), 'number': work.registration_number, 'state': work.state,
            'expected_version': work.version, 'history_id': str(history.pk), 'source_row_id': str(history.source_row_id),
            'batch_id': str(history.source_row.batch_id), 'source_row': history.source_row.source_row,
            'executor_raw': history.executor_raw, 'operational': history.operational,
            'specialty': work.specialty.code if work.specialty_id else None,
            'employees': [{'id': str(p.employee_id), 'full_name': p.employee.full_name} for p in participants],
            'eligible': not blockers, 'blockers': blockers}
    digest = {**item, 'qualifications': snapshots, 'commission': work.is_commission}
    item['proposal_hash'] = hashlib.sha256(json.dumps(digest, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return item


def preview(actor):
    require_preview_read(actor)
    scopes = permission_scopes(actor)
    works = list(hydrated(works_for(actor, scopes)).order_by('year', 'sequence', 'id'))
    qualifications, issued = qualifications_for(works), issued_materials(works)
    rows = [proposal(work, qualifications, issued, scopes) for work in works]
    return {'results': rows, 'eligible_count': sum(row['eligible'] for row in rows)}


@transaction.atomic
def apply_assignments(*, actor, selections, reason, key, payload):
    require_preview_read(actor)
    require(actor, 'imports.apply')
    scopes = permission_scopes(actor)
    ids = [row['expertise_id'] for row in selections]
    visible = list(works_for(actor, scopes).filter(pk__in=ids))
    if len(visible) != len(ids): raise PermissionDenied('Одна из выбранных исторических работ недоступна.')
    # Check today's rights before returning even a previously saved response.
    for work in visible: require_work(actor, 'expertise.assign', work, scopes)

    def operation():
        # Consistent lock order with issue/activation: material -> receipt -> work.
        list(Material.objects.select_for_update().filter(pk__in={w.material_id for w in visible}).order_by('pk'))
        list(Receipt.objects.select_for_update().filter(pk__in={w.receipt_id for w in visible}).order_by('pk'))
        list(Expertise.objects.select_for_update().filter(pk__in=ids).order_by('pk'))
        histories = list(HistoricalWork.objects.select_for_update().filter(expertise_id__in=ids).order_by('pk'))
        participants = list(HistoricalParticipant.objects.select_for_update().filter(history__in=histories).order_by('pk'))
        list(Specialty.objects.select_for_update().filter(pk__in={w.specialty_id for w in visible}).order_by('pk'))
        list(Employee.objects.select_for_update().filter(pk__in={p.employee_id for p in participants}).order_by('pk'))
        works = list(hydrated(works_for(actor, scopes).filter(pk__in=ids)).order_by('pk'))
        if len(works) != len(ids): raise CommandConflict('Состав исторических работ изменился. Обновите перечень.')
        qualifications, issued = qualifications_for(works, lock=True), issued_materials(works)
        # Locks above can wait. A role revoked during that wait must cancel the
        # command too, rather than authorizing it with a saved AccessScope.
        require_preview_read(actor)
        require(actor, 'imports.apply')
        current_scopes = permission_scopes(actor)
        expected = {row['expertise_id']: row for row in selections}
        for work in works:
            require_work(actor, 'expertise.view', work, current_scopes)
            require_work(actor, 'expertise.assign', work, current_scopes)
            current = proposal(work, qualifications, issued, current_scopes)
            old = expected[work.pk]
            if not current['eligible'] or work.version != old['expected_version'] or current['proposal_hash'] != old['proposal_hash']:
                raise CommandConflict(f'{work.registration_number}: данные изменились или перенос недоступен. Обновите перечень; пакет не применён.')
        now = timezone.now()
        events = []
        for work in works:
            history = work.historical
            employee_ids = []
            for participant in history.participants.all():
                snapshot = qualification_snapshot(qualifications[(participant.employee_id, work.specialty_id)])
                snapshot['historical_import'] = {'history_id': str(history.pk), 'source_row_id': str(history.source_row_id)}
                ExpertAssignment.objects.create(expertise=work, employee=participant.employee, started_at=now,
                                               actor=actor, reason=reason, qualification_snapshot=snapshot)
                employee_ids.append(str(participant.employee_id))
            work.version += 1
            work.save(update_fields=['version'])
            event = audit(actor, ACTION, work, {'employee_ids': employee_ids, 'historical_id': str(history.pk),
                'source_row_id': str(history.source_row_id), 'version': work.version}, reason)
            events.append(str(event.pk))
        return {'applied_count': len(works), 'expertise_ids': [str(w.pk) for w in works], 'event_ids': events}

    result = execute_once(actor=actor, action=ACTION, key=key, payload=payload, operation=operation)
    # execute_once can itself wait for an earlier request with the same key.
    require_preview_read(actor)
    require(actor, 'imports.apply')
    current_scopes = permission_scopes(actor)
    for work in Expertise.objects.filter(pk__in=ids).prefetch_related('assignments'):
        require_work(actor, 'expertise.view', work, current_scopes)
        require_work(actor, 'expertise.assign', work, current_scopes)
    return result
