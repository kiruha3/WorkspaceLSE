"""The maintenance console is separate from the application's scoped roles."""
from django.contrib.admin import AdminSite
from django.contrib.admin.apps import AdminConfig


APP_NAMES = {
    'accounts': 'Учётные записи и роли', 'personnel': 'Сотрудники',
    'references': 'Справочники', 'audit': 'Журнал действий',
    'intake': 'Поступления', 'expertises': 'Экспертизы', 'documents': 'Документы',
    'correspondence': 'Переписка', 'issuance': 'Выдача материалов',
    'imports': 'Импорт журнала', 'reports': 'Годовые планы', 'admin': 'Журнал Django',
}
MODEL_NAMES = {
    'User': 'Учётные записи', 'Role': 'Роли АИС', 'RolePermission': 'Права ролей АИС',
    'CommandReceipt': 'Выполненные команды', 'Employee': 'Сотрудники',
    'EmployeeOrgAssignment': 'Отделы и должности сотрудников',
    'EmployeeSpecialty': 'Специальности сотрудников', 'EmployeeRole': 'Назначения ролей',
    'Department': 'Отделы', 'Position': 'Должности', 'Specialty': 'Специальности',
    'SndzReason': 'Причины СНДЗ', 'UnresolvedQuestionReason': 'Причины нерешённых вопросов',
    'ReturnReason': 'Причины возврата', 'IssueMethod': 'Способы выдачи',
    'LetterKind': 'Виды писем', 'LetterJournal': 'Журналы переписки',
    'DispatchChannel': 'Каналы отправки', 'ControlClosureReason': 'Причины снятия с контроля',
    'AuthorityType': 'Типы назначающих органов', 'DelayReason': 'Причины длительности',
    'AuditEvent': 'Действия пользователей', 'Document': 'Документы',
    'FileVersion': 'Версии файлов', 'WorkDocumentLink': 'Связи документов с экспертизами',
    'StorageRoot': 'Папки документов', 'Material': 'Материалы', 'Receipt': 'Поступления',
    'ComplexGroup': 'Комплексные работы', 'Expertise': 'Экспертизы',
    'ExpertAssignment': 'Назначения экспертов', 'Suspension': 'Приостановки',
    'DeadlineEvent': 'События сроков', 'ResultRevision': 'Редакции результатов',
    'UnresolvedAllocation': 'Нерешённые вопросы', 'WorkClosure': 'Завершения работ',
    'HistoricalWork': 'Сведения перенесённого журнала', 'WorkReopening': 'Возвраты в работу',
    'HistoricalUnresolvedAllocation': 'Нерешённые вопросы старого журнала',
    'HistoricalCorrection': 'Уточнения старого журнала', 'HistoricalParticipant': 'Исполнители старого журнала',
    'WorkCaseDetails': 'Сведения о делах', 'CaseDetailsRevision': 'Изменения сведений о делах',
    'WorkClassification': 'Классификация работ', 'PreviousConclusion': 'Предыдущие заключения',
    'ClassificationRevision': 'Изменения классификации', 'WorkTimingFacts': 'Сведения о сроках',
    'TimingReason': 'Указанные причины сроков', 'TimingRevision': 'Изменения сведений о сроках',
    'Letter': 'Письма', 'LetterRevision': 'Редакции писем', 'LetterRecipient': 'Адресаты',
    'LetterAttachment': 'Вложения писем', 'LetterRegistration': 'Регистрации писем',
    'LetterRegistrationFile': 'Файлы при регистрации писем', 'LetterDispatch': 'Отправки писем',
    'LetterDispatchFile': 'Файлы отправленных писем', 'LetterDelivery': 'Доставка писем',
    'LetterReceipt': 'Получение писем', 'LetterAssignment': 'Ответственные за переписку',
    'ControlTask': 'Контроль переписки', 'ControlEvent': 'События контроля',
    'IssuePackage': 'Комплекты выдачи', 'PackageRevision': 'Редакции комплектов',
    'PackageItem': 'Документы комплектов', 'PackageWorkBilling': 'Оплата работ в комплектах',
    'PackageCheck': 'Проверки комплектов', 'CheckWork': 'Работы при проверке комплекта',
    'CheckFile': 'Файлы при проверке комплекта', 'MaterialIssue': 'Выдачи материалов',
    'JournalSourceSettings': 'Настройки Google-источника', 'ImportBatch': 'Снимки журнала',
    'ImportRow': 'Строки снимков', 'ImportSelection': 'Сопоставления строк',
    'ImportApplication': 'Применения импорта', 'ImportApplicationItem': 'Перенесённые записи',
    'StateAssignmentPlan': 'Годовые планы', 'StateAssignmentPlanLine': 'Планы по специальностям',
    'StateAssignmentPlanRevision': 'Изменения планов', 'LogEntry': 'События Django-админки',
}


class LaboratoryAdminSite(AdminSite):
    site_header = 'ФГБУ Абаканская ЛСЭ — администрирование'
    site_title = 'Администрирование АИС'
    index_title = 'Служебное управление'
    site_url = '/workspace'

    def has_permission(self, request):
        return super().has_permission(request) and request.user.is_superuser

    def get_app_list(self, request, app_label=None):
        result = super().get_app_list(request, app_label)
        for app in result:
            app['name'] = APP_NAMES.get(app['app_label'], app['name'])
            for model in app['models']:
                model['name'] = MODEL_NAMES.get(model['object_name'], model['name'])
            app['models'].sort(key=lambda model: model['name'])
        return sorted(result, key=lambda app: app['name'])


class LaboratoryAdminConfig(AdminConfig):
    default_site = 'config.admin.LaboratoryAdminSite'

    def ready(self):
        super().ready()
        from django.apps import apps
        from django.contrib import admin
        from django.contrib.admin.models import LogEntry
        from django.contrib.auth.models import Group
        from apps.common.admin import ReadOnlyAdmin
        # Django auth groups are not the application's Role/EmployeeRole system.
        if admin.site.is_registered(Group):
            admin.site.unregister(Group)
        for app in apps.get_app_configs():
            if app.name.startswith('apps.'):
                for model in app.get_models():
                    if not admin.site.is_registered(model):
                        admin.site.register(model, ReadOnlyAdmin)
        admin.site.register(LogEntry, ReadOnlyAdmin)
