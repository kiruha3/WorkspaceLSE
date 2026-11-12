"""Populate a separate, empty stand from invented cases. No source imports."""
import hashlib
import json
import os
from datetime import date, datetime, time, timedelta
from pathlib import Path
import secrets

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management import BaseCommand, CommandError, call_command
from django.db import transaction
from django.utils import timezone

from apps.accounts.catalog import PERMISSIONS
from apps.accounts.models import User, Role, RolePermission
from apps.accounts.services import audit
from apps.audit.models import AuditEvent
from apps.personnel.models import Employee, EmployeeOrgAssignment, EmployeeRole, EmployeeSpecialty
from apps.references.models import (Department, Position, Specialty, AuthorityType, DelayReason,
    SndzReason, ReturnReason, UnresolvedQuestionReason, LetterKind, LetterJournal)
from apps.references.result_seeds import seed_result_catalogs
from apps.references.correspondence_seeds import seed_correspondence_catalogs
from apps.documents.models import Document, FileVersion, WorkDocumentLink
from apps.intake.models import Material, Receipt
from apps.imports.models import ImportBatch, JournalSourceSettings
from apps.expertises.models import (Expertise, ExpertAssignment, Suspension, DeadlineEvent,
    ResultRevision, UnresolvedAllocation, WorkClosure, WorkCaseDetails, WorkClassification,
    WorkTimingFacts, TimingReason, ComplexGroup, PreviousConclusion)
from apps.correspondence.models import Letter, LetterRevision, LetterRegistration, LetterRecipient, ControlTask, ControlEvent
from apps.issuance.models import IssuePackage, PackageRevision, PackageItem, PackageWorkBilling
from apps.reports.models import StateAssignmentPlan, StateAssignmentPlanLine


PROFILES = (
    ('head3', 'Соколов И.А.', '3', 'head', ('1.1', '3.1', '16.1', '16.2')),
    ('head4', 'Громова Н.В.', '4', 'head', ('13.1', '18.1', '19.1')),
    ('expert.kuznetsova', 'Кузнецова Е.В.', '3', 'expert', ('1.1', '3.1')),
    ('expert.orlova', 'Орлова М.С.', '3', 'expert', ('16.1',)),
    ('expert.belov', 'Белов П.Н.', '3', 'expert', ('16.2',)),
    ('expert.ilina', 'Ильина О.В.', '3', 'expert', ('1.1', '3.1')),
    ('expert.morozov', 'Морозов Д.С.', '4', 'expert', ('18.1',)),
    ('expert.kovalev', 'Ковалёв Р.М.', '4', 'expert', ('13.1',)),
    ('expert.lebedeva', 'Лебедева А.В.', '4', 'expert', ('19.1',)),
    ('expert.romanov', 'Романов И.С.', '4', 'expert', ('18.1', '19.1')),
    ('trainee', 'Мельникова Е.А.', '4', 'trainee', ('19.1',)),
    ('clerk', 'Павлова Л.Н.', 'aup', 'clerk', ()),
    ('director', 'Андреев С.В.', 'aup', 'director', ()),
)
TOPICS = (
    ('1.1', '3', 'Подпись в договоре поставки оборудования', 'Кем выполнена подпись от имени покупателя?'),
    ('3.1', '3', 'Реквизиты товарной накладной', 'Имеются ли изменения первоначального содержания документа?'),
    ('16.1', '3', 'Несущие конструкции складского здания', 'Соответствует ли фактическое состояние конструкций проектной документации?'),
    ('16.2', '3', 'Границы участков в квартале Берёзовый', 'Каково фактическое расположение границ земельных участков?'),
    ('13.1', '4', 'Обстоятельства столкновения двух автомобилей', 'Имел ли водитель техническую возможность предотвратить столкновение?'),
    ('18.1', '4', 'Стоимость автомобиля Лада Веста 2021 года', 'Какова рыночная стоимость автомобиля на дату оценки?'),
    ('19.1', '4', 'Стоимость комплекта деревообрабатывающего оборудования', 'Какова рыночная стоимость представленного оборудования?'),
)
AUTHORITIES = {
    '1': ('sk', 'Следственные органы', 'sk', 'Следственный отдел по Зареченскому району'),
    '2': ('courts_general', 'Суды общей юрисдикции', 'court', 'Зареченский районный суд'),
    '3': ('arbitration_courts', 'Арбитражные суды', 'court', 'Арбитражный суд Северного округа'),
    '4': ('mvd', 'Органы внутренних дел', 'mvd', 'Отдел полиции Центрального района'),
    '5': ('mvd', 'Органы внутренних дел', 'mvd', 'Управление МВД города Зареченска'),
    '6': ('legal', 'Юридические лица', 'legal', 'АО «Северный контур»'),
}


def attached_pdf(document, work, actor, description):
    from ._stand_documents import make_pdf
    data = make_pdf(document.title, work.registration_number, description,
                    pages=6 if document.kind in ('expert_conclusion', 'research_act') else 2)
    version = FileVersion(document=document, number=1,
        original_name=document.title.replace('/', '_')[:245] + '.pdf',
        content_type='application/pdf', size=len(data), sha256=hashlib.sha256(data).hexdigest(), created_by=actor)
    version.file.save(version.original_name, ContentFile(data), save=False)
    version.save()
    document.source_kind = 'uploaded_copy'
    document.version = 2
    document.save(update_fields=['source_kind', 'version'])
    return version


class Command(BaseCommand):
    help = 'Наполнить отдельный пустой стенд вымышленными сотрудниками и делами без чтения Google/Excel.'

    def add_arguments(self, parser):
        parser.add_argument('--count', type=int, default=1200)
        parser.add_argument('--as-of', default=None)
        parser.add_argument('--credentials-file', required=True)

    @transaction.atomic
    def handle(self, *args, **options):
        if not getattr(settings, 'AIS_STAND_MODE', False):
            raise CommandError('Требуется явно включённый AIS_STAND_MODE=1.')
        if getattr(settings, 'JOURNAL_GOOGLE_ID', '') or JournalSourceSettings.objects.exists():
            raise CommandError('На стенде не должно быть настроенного Google-источника.')
        if AuditEvent.objects.filter(action='stand.populate').exists():
            self.stdout.write('Данные стенда уже заполнены; записи и пароли сохранены.')
            return
        if User.objects.exists() or Employee.objects.exists() or Expertise.objects.exists() or ImportBatch.objects.exists():
            raise CommandError('Нельзя наполнять базу с существующими пользователями или рабочими данными.')
        count = options['count']
        if not 12 <= count <= 5000:
            raise CommandError('Количество должно быть от 12 до 5000.')
        try:
            as_of = date.fromisoformat(options['as_of']) if options['as_of'] else timezone.localdate()
        except ValueError as error:
            raise CommandError('Дата должна иметь формат ГГГГ-ММ-ДД.') from error
        if as_of.month < 2:
            raise CommandError('Для распределения примеров нужна дата не ранее февраля.')
        access_path = Path(options['credentials_file'])
        if access_path.exists():
            raise CommandError('Файл доступа уже существует; автоматическая перезапись не выполняется.')
        access_path.parent.mkdir(parents=True, exist_ok=True)
        passwords = {login: secrets.token_urlsafe(18) for login in ('admin', *(p[0] for p in PROFILES))}
        old_password = os.environ.get('AIS_BOOTSTRAP_PASSWORD')
        os.environ['AIS_BOOTSTRAP_PASSWORD'] = passwords['admin']
        try:
            call_command('bootstrap_access', username='admin', full_name='Администратор стенда', no_input=True, stdout=self.stdout)
        finally:
            if old_password is None:
                os.environ.pop('AIS_BOOTSTRAP_PASSWORD', None)
            else:
                os.environ['AIS_BOOTSTRAP_PASSWORD'] = old_password
        seed_result_catalogs()
        seed_correspondence_catalogs()
        call_command('seed_issue_catalogs', stdout=self.stdout)
        admin_user = User.objects.get(username='admin')
        admin_user.is_staff = admin_user.is_superuser = True
        admin_user.save(update_fields=['is_staff', 'is_superuser'])
        admin_employee = Employee.objects.get(user=admin_user)
        full = Role.objects.create(name='Администратор стенда', description='Полный доступ к отдельному стенду')
        RolePermission.objects.bulk_create([RolePermission(role=full, permission_code=code,
            scope='institution' if 'institution' in value.scopes else value.scopes[-1]) for code, value in PERMISSIONS.items()])
        EmployeeRole.objects.create(employee=admin_employee, role=full, reason='Первоначальная настройка стенда')
        departments = {item.code: item for item in Department.objects.all()}
        specialties = {item.code: item for item in Specialty.objects.all()}
        people = {}
        qualified = {code: [] for code in specialties}
        for login, name, department, position, codes in PROFILES:
            user = User.objects.create_user(username=login, password=passwords[login])
            person = Employee.objects.create(user=user, full_name=name)
            people[login] = person
            job, _ = Position.objects.get_or_create(code=position, defaults={'name': 'Стажёр'})
            EmployeeOrgAssignment.objects.create(employee=person, department=departments[department], position=job,
                valid_from=date(as_of.year - 2, 1, 1), reason='Приказ о назначении на должность')
            template = {'head': 'Руководитель отдела', 'expert': 'Эксперт', 'trainee': 'Эксперт',
                        'clerk': 'Делопроизводитель', 'director': 'Руководитель учреждения'}[position]
            grant = EmployeeRole.objects.create(employee=person, role=Role.objects.get(name=template), reason='Назначение по должности')
            if position == 'head':
                grant.departments.add(departments[department])
                EmployeeRole.objects.create(employee=person, role=Role.objects.get(name='Эксперт'), reason='Работа по полученным специальностям')
            for code in codes:
                EmployeeSpecialty.objects.create(employee=person, specialty=specialties[code],
                    status='training' if position == 'trainee' else 'qualified',
                    qualified_at=None if position == 'trainee' else date(as_of.year - 2, 6, 10),
                    training_started_at=date(as_of.year, 9, 1) if position == 'trainee' else None,
                    basis='Индивидуальный план обучения' if position == 'trainee' else 'Свидетельство о квалификации')
                if position != 'trainee':
                    qualified[code].append(person)
        clerk = people['clerk']
        delay, _ = DelayReason.objects.get_or_create(code='research_complexity', defaults={'name': 'Сложность проведённых исследований', 'report_group': 'research_complexity'})
        sndz = SndzReason.objects.get(code='science_cannot_answer')
        unresolved_reason = UnresolvedQuestionReason.objects.get(code='materials_insufficient')
        return_reason = ReturnReason.objects.get(code='appointing_party_request')
        journals = {direction: LetterJournal.objects.create(code=direction, name='Входящий журнал' if direction == 'incoming' else 'Исходящий журнал', direction=direction) for direction in ('incoming', 'outgoing')}
        previous_count = count // 3
        current_count = count - previous_count
        works = []
        for i in range(count):
            previous = i < previous_count
            year = as_of.year - 1 if previous else as_of.year
            sequence = i + 1 if previous else i - previous_count + 1
            span = 350 if previous else (as_of - date(year, 1, 1)).days
            population = previous_count if previous else current_count
            received = date(year, 1, 1) + timedelta(days=(sequence - 1) * span // max(1, population))
            code, department_code, topic, question = TOPICS[i % len(TOPICS)]
            category = str((i // len(TOPICS)) % 6 + 1)
            preceding = works[-1][0] if works else None
            shared = bool(not previous and sequence % 12 == 1 and preceding and preceding.year == year
                          and preceding.sequence == sequence - 1 and preceding.complex_group_id)
            if shared:
                category = preceding.category_code
                received = preceding.receipt.received_at
            authority_code, authority_label, authority_group, authority_name = AUTHORITIES[category]
            authority, _ = AuthorityType.objects.get_or_create(code=authority_code,
                defaults={'name': authority_label, 'report_group': authority_group})
            active = not previous and sequence > current_count - max(8, current_count // 8)
            state = ('suspended' if sequence % 4 == 1 else 'in_progress') if active else ('without_execution' if sequence % 19 == 0 else 'completed')
            number = f'{sequence}/{department_code}-{category}-{str(year)[-2:]}'
            basis_kind = 'case_material' if category == '6' else 'decision' if category in ('2', '3') else 'resolution'
            basis_title = ('Заявление о проведении исследования' if category == '6' else 'Определение о назначении экспертизы' if basis_kind == 'decision' else 'Постановление о назначении экспертизы') + f' № {number}'
            if shared:
                material, receipt = preceding.material, preceding.receipt
                basis = receipt.basis_document or preceding.document_links.filter(document__kind='case_material').first().document
                basis_title = basis.title
            else:
                material = Material.objects.create(title=topic, created_by=clerk)
                basis = Document.objects.create(kind=basis_kind, title=basis_title, source_kind='paper_original', department=departments[department_code], created_by=clerk)
                receipt = Receipt.objects.create(material=material, received_at=received, sender_name=authority_name,
                    basis_document=basis if category != '6' else None, department=departments[department_code], created_by=clerk, status='accepted')
            complex_group = preceding.complex_group if shared else ComplexGroup.objects.create(material=material,
                title=f'Комплексное исследование материалов дела № {1000 + sequence}') if not previous and sequence % 12 == 0 and sequence < current_count else None
            nature = 'repeated' if sequence % 31 == 0 else 'additional' if sequence % 37 == 0 else 'primary'
            work = Expertise.objects.create(material=material, receipt=receipt, registration_number=number,
                sequence=sequence, year=year, category_code=category, department=departments[department_code],
                specialty=specialties[code], origin_kind='native', appointment_nature=nature,
                is_commission=sequence % 11 == 0, complex_group=complex_group, state=state, registered_by=clerk.user)
            WorkDocumentLink.objects.create(expertise=work, document=basis, actor=clerk.user, note='Основание поступления')
            attach = not previous and (sequence <= 12 or sequence > current_count - 6)
            if attach:
                attached_pdf(basis, work, clerk, topic + '. ' + question)
            experts = qualified[code]
            executor = experts[sequence % len(experts)]
            if not (active and sequence % 4 == 0):
                participants = [executor]
                if work.is_commission:
                    participants.append(next(p for p in experts if p.pk != executor.pk))
                for participant in participants:
                    ExpertAssignment.objects.create(expertise=work, employee=participant, actor=people['head' + department_code].user,
                        started_at=timezone.make_aware(datetime.combine(received, time(10))),
                        reason='Поручение производства экспертизы', qualification_snapshot={'status': 'qualified', 'specialty_code': code})
            duration = 5 + sequence % 40
            ended = min(as_of, received + timedelta(days=duration))
            DeadlineEvent.objects.create(expertise=work, kind='initial', recorded_on=received, due_on=received + timedelta(days=30), actor=clerk.user, reason='Срок производства при регистрации')
            if state == 'suspended':
                Suspension.objects.create(expertise=work, suspended_on=min(as_of, received + timedelta(days=4)),
                    reason='Ожидание дополнительных материалов', actor=executor.user)
            construction = code in ('16.1', '16.2') and sequence % 10 == 0
            WorkCaseDetails.objects.create(expertise=work, authority_type=authority, authority_name=authority_name,
                official='Смирнов А.В., уполномоченное должностное лицо', case_number=f'{category}-{year}-{1000 + sequence}',
                case_description=topic, basis_text=basis_title, inventory='Материалы дела — 1 том; объекты исследования по описи.',
                questions_text=question, decree3214=construction, decree_basis='Исследование самовольного строения' if construction else '', created_by=clerk.user)
            classification = WorkClassification.objects.create(expertise=work, previous_complete=True, created_by=clerk.user)
            if nature != 'primary':
                PreviousConclusion.objects.create(classification=classification, ordinal=1,
                    reference=f'Заключение № {max(1, sequence - 2)}/{department_code}-{category}-{str(year - 1)[-2:]}',
                    organization_name='Экспертный центр Северного округа', organization_group='other',
                    same_input_data=sequence % 2 == 0, confirms_previous=sequence % 3 != 0)
            timing = WorkTimingFacts.objects.create(expertise=work, reasons_complete=True,
                primary_reason=delay if duration > 30 else None, notification_sent=duration > 30,
                notification_on=min(as_of, received + timedelta(days=25)) if duration > 30 else None,
                extension_requested=duration > 30, request_on=min(as_of, received + timedelta(days=23)) if duration > 30 else None,
                deadline_breached=False, created_by=executor.user)
            if duration > 30:
                TimingReason.objects.create(timing=timing, reason=delay, comment='Исследование нескольких объектов и сравнительных образцов')
            if state in ('completed', 'without_execution'):
                kind = 'return_decision' if state == 'without_execution' else 'research_act' if category == '6' else 'sndz' if sequence % 23 == 0 else 'expert_conclusion'
                title = {'return_decision': 'Возврат материалов без исполнения', 'research_act': 'Акт экспертного исследования', 'sndz': 'Сообщение о невозможности дать заключение', 'expert_conclusion': 'Заключение эксперта'}[kind] + f' № {number}'
                document = Document.objects.create(kind=kind, title=title, source_kind='paper_original', department=departments[department_code], created_by=executor)
                WorkDocumentLink.objects.create(expertise=work, document=document, actor=executor.user, note='Итоговый документ')
                accepted_version = attached_pdf(document, work, executor, topic + '. ' + question) if attach else None
                result = None
                if state == 'completed':
                    questions = 3 + sequence % 6
                    unresolved = questions if kind == 'sndz' else 1 if sequence % 17 == 0 else 0
                    probable = 1 if unresolved < questions and sequence % 5 == 0 else 0
                    result = ResultRevision.objects.create(expertise=work, number=1, kind=kind, completed_on=ended,
                        document=document, complexity_level=1 + sequence % 3, questions=questions,
                        categorical=questions - unresolved - probable, probable=probable, unresolved=unresolved,
                        statistics_complete=True, sndz_reason=sndz if kind == 'sndz' else None,
                        allocations_complete=True, note='Объекты исследованы. Ответы приведены по поставленным вопросам.',
                        actor=executor.user, reason='Окончание производства')
                    if unresolved:
                        UnresolvedAllocation.objects.create(result=result, reason=unresolved_reason, count=unresolved,
                            comment='Представленных объектов недостаточно для разрешения части вопросов')
                WorkClosure.objects.create(expertise=work, number=1, kind=state, ended_on=ended,
                    result=result, document=document, accepted_version=accepted_version,
                    return_reason=return_reason if state == 'without_execution' else None,
                    actor=executor.user, reason='Результат производства зарегистрирован')
            works.append((work, received, authority_name, executor))
        for index, (work, received, authority_name, executor) in enumerate(works[::max(1, count // 60)], 1):
            direction = 'incoming' if index % 2 else 'outgoing'
            actual = min(as_of, received + timedelta(days=7))
            letter = Letter.objects.create(direction=direction, department=work.department, responsible=executor, created_by=clerk)
            revision = LetterRevision.objects.create(letter=letter, number=1, kind=LetterKind.objects.get(code='request' if direction == 'incoming' else 'reply'),
                subject=f'Материалы и сведения по экспертизе № {work.registration_number}',
                body='Просим приобщить дополнительные материалы и уточнить перечень поставленных вопросов.' if direction == 'incoming' else 'Сообщаем о получении материалов и ходе производства экспертизы.',
                sender_name=authority_name if direction == 'incoming' else 'Экспертное учреждение',
                document_on=actual, received_on=actual if direction == 'incoming' else None,
                material=work.material, actor=clerk, reason='Регистрация переписки')
            revision.expertises.add(work)
            letter.current_revision = revision
            letter.save(update_fields=['current_revision'])
            LetterRecipient.objects.create(revision=revision, name='Экспертное учреждение' if direction == 'incoming' else authority_name)
            LetterRegistration.objects.create(letter=letter, revision=revision, journal=journals[direction],
                registration_number=f'{index}/{str(actual.year)[-2:]}', registered_on=actual, year=actual.year,
                actor=clerk, reason='Запись в журнал переписки')
            if direction == 'incoming' and work.state in ('in_progress', 'suspended'):
                control = ControlTask.objects.create(letter=letter, opened_on=actual, due_on=as_of + timedelta(days=7), due_basis='Срок ответа на запрос')
                ControlEvent.objects.create(control=control, kind='opened', actual_on=actual,
                    due_on=control.due_on, due_basis=control.due_basis, actor=clerk, reason='Постановка запроса на контроль')
        for work, received, authority_name, executor in works[:8]:
            package = IssuePackage.objects.create(material=work.material, created_by=clerk.user)
            revision = PackageRevision.objects.create(package=package, number=1,
                materials_description='Материалы дела — 1 том; объекты исследования по описи.',
                note='Комплект подготовлен к проверке перед передачей получателю.', actor=clerk.user, reason='Подготовка выдачи')
            package.current_revision = revision
            package.save(update_fields=['current_revision'])
            paid = work.category_code in ('2', '3', '6')
            PackageWorkBilling.objects.create(revision=revision, expertise=work, is_paid=paid)
            kinds = ['expert_subscription', 'cover_letter'] + (['notification'] if work.category_code in ('1', '5') else []) + (['invoice'] if paid else [])
            names = {'expert_subscription': 'Подписка эксперта', 'cover_letter': 'Сопроводительное письмо', 'notification': 'Уведомление', 'invoice': 'Счёт на оплату'}
            for kind in kinds:
                document = Document.objects.create(kind=kind, title=f'{names[kind]} по экспертизе № {work.registration_number}',
                    source_kind='paper_original', department=work.department, created_by=clerk)
                WorkDocumentLink.objects.create(expertise=work, document=document, actor=clerk.user)
                PackageItem.objects.create(revision=revision, kind=kind, expertise=work, document=document)
        for year in (as_of.year - 1, as_of.year):
            counts = (60, 60, 60, 60, 70, 70, 70) if year < as_of.year else (80, 80, 80, 80, 90, 90, 100)
            plan, _ = StateAssignmentPlan.objects.update_or_create(year=year, defaults={'total': sum(counts), 'basis_text': f'Годовой план работы на {year} год', 'version': 1, 'created_by': admin_user})
            for topic, value in zip(TOPICS, counts):
                StateAssignmentPlanLine.objects.update_or_create(plan=plan, specialty=specialties[topic[0]], defaults={'count': value})
        audit(admin_user, 'stand.populate', admin_employee, {'count': count, 'as_of': as_of.isoformat(), 'source': 'invented_cases'})
        payload = {'format': 'ais-stand-v1', 'accounts': [{'username': login, 'password': password} for login, password in passwords.items()]}
        access_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        if os.name != 'nt':
            access_path.chmod(0o600)
        self.stdout.write(f'Стенд заполнен: {count} экспертиз, {Employee.objects.count()} сотрудников, {Letter.objects.count()} писем, {FileVersion.objects.count()} файлов. Доступы сохранены в отдельном файле.')
