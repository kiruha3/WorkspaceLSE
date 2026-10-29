from dataclasses import dataclass

SCOPES = ("own", "departments", "institution")


@dataclass(frozen=True)
class Permission:
    code: str
    label: str
    module: str
    scopes: tuple[str, ...] = SCOPES


PERMISSIONS = {item.code: item for item in [
    Permission("receipts.view", "Просматривать поступления", "Приёмка"),
    Permission("receipts.create", "Создавать поступления", "Приёмка", ("departments","institution")),
    Permission("receipts.accept", "Принимать поступления", "Приёмка", ("departments","institution")),
    Permission("receipts.amend", "Уточнять поступления", "Приёмка", ("departments","institution")),
    Permission("employees.view", "Просматривать сотрудников", "Сотрудники"),
    Permission("employees.create", "Добавлять сотрудников", "Сотрудники", ("institution",)),
    Permission("employees.update", "Изменять сведения сотрудников", "Сотрудники", ("departments", "institution")),
    Permission("employees.deactivate", "Деактивировать сотрудников", "Сотрудники", ("departments", "institution")),
    Permission("employees.org_assignments.manage", "Вести должности и подразделения", "Сотрудники", ("institution",)),
    Permission("specialties.training.manage", "Вести обучение по специальностям", "Специальности", ("departments", "institution")),
    Permission("specialties.qualify", "Вести полученные специальности", "Специальности", ("departments", "institution")),
    Permission("references.view", "Просматривать справочники", "Справочники", ("institution",)),
    Permission("references.manage", "Изменять справочники", "Справочники", ("institution",)),
    Permission("access.roles.view", "Просматривать роли", "Доступ", ("institution",)),
    Permission("access.roles.manage", "Настраивать роли и права", "Доступ", ("institution",)),
    Permission("access.roles.assign", "Назначать роли сотрудникам", "Доступ", ("institution",)),
    Permission("access.effective.view", "Проверять эффективные права", "Доступ", ("institution",)),
    Permission("users.view", "Просматривать учётные записи", "Доступ", ("institution",)),
    Permission("users.create", "Создавать учётные записи", "Доступ", ("institution",)),
    Permission("users.deactivate", "Блокировать вход пользователя", "Доступ", ("institution",)),
    Permission("expertise.view", "Просматривать экспертизы", "Экспертизы"),
    Permission("expertise.register", "Закреплять регистрационный номер", "Экспертизы", ("departments", "institution")),
    Permission("expertise.assign", "Назначать экспертов", "Экспертизы", ("departments", "institution")),
    Permission("expertise.reassign", "Перепоручать работу", "Экспертизы", ("departments", "institution")),
    Permission("expertise.work.update", "Вести рабочую карточку", "Экспертизы"),
    Permission("expertise.suspend", "Приостанавливать работу", "Экспертизы"),
    Permission("expertise.resume", "Возобновлять работу", "Экспертизы"),
    Permission("expertise.deadline.record", "Фиксировать согласованный срок", "Экспертизы"),
    Permission("expertise.complete", "Завершать экспертизу", "Экспертизы"),
    Permission("expertise.result.draft", "Сохранять результат экспертизы", "Экспертизы"),
    Permission("expertise.return_without_execution", "Оформлять решение без исполнения", "Экспертизы"),
    Permission("expertise.closed.correct", "Корректировать завершённую работу", "Экспертизы"),
    Permission("expertise.export", "Выгружать выборку экспертиз", "Экспертизы"),
    Permission("documents.view", "Просматривать документы", "Документы"),
    Permission("documents.upload", "Подкреплять документы", "Документы"),
    Permission("documents.link", "Связывать документы с экспертизой", "Документы"),
    Permission("documents.unlink", "Снимать дополнительные связи документов", "Документы"),
    Permission("letters.view", "Просматривать переписку", "Переписка"),
    Permission("letters.draft", "Готовить письма", "Переписка"),
    Permission("letters.reply", "Готовить связанные ответы", "Переписка"),
    Permission("letters.attach", "Прикреплять документы переписки", "Переписка"),
    Permission("letters.mark_received", "Фиксировать получение", "Переписка"),
    Permission("letters.mark_delivered", "Фиксировать доставку", "Переписка"),
    Permission("control.view", "Просматривать контроль ответов", "Переписка"),
    Permission("control.assign", "Назначать ответственного и срок контроля", "Переписка", ("departments", "institution")),
    Permission("control.reopen", "Возобновлять контроль ответа", "Переписка"),
    Permission("letters.register", "Регистрировать письма", "Переписка", ("departments", "institution")),
    Permission("letters.mark_sent", "Фиксировать отправку", "Переписка", ("departments", "institution")),
    Permission("control.close", "Снимать запрос с контроля", "Переписка"),
    Permission("issue.view", "Просматривать выдачу материалов", "Выдача"),
    Permission("issue.prepare", "Готовить комплект выдачи", "Выдача", ("departments", "institution")),
    Permission("issue.check", "Проверять комплект выдачи", "Выдача", ("departments", "institution")),
    Permission("issue.confirm", "Выдавать комплект материалов", "Выдача", ("departments", "institution")),
    Permission("reports.form151.run", "Рассчитывать отчёт 15.1", "Отчётность", ("departments", "institution")),
    Permission('reports.plans.manage','Вести годовые планы госзадания','Отчётность',('institution',)),
    Permission("imports.preview", "Проверять источник журнала", "Перенос журнала", ("institution",)),
    Permission("imports.results.view", "Просматривать снимки переноса", "Перенос журнала", ("institution",)),
    Permission("imports.source.manage", "Настраивать источник Google-таблицы", "Перенос журнала", ("institution",)),
    Permission("documents.storage.manage", "Настраивать папки документов", "Документы", ("institution",)),
    Permission("imports.reconcile", "Сопоставлять строки переноса", "Перенос журнала", ("institution",)),
    Permission("imports.apply", "Применять подтверждённый пакет переноса", "Перенос журнала", ("institution",)),
    Permission("imports.history.activate", "Подтверждать продолжение исторической работы", "Перенос журнала", ("institution",)),
    Permission("reports.form151.download", "Выгружать отчёт 15.1", "Отчётность", ("departments", "institution")),
]}
