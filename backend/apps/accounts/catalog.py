from dataclasses import dataclass

SCOPES = ("own", "departments", "institution")


@dataclass(frozen=True)
class Permission:
    code: str
    label: str
    module: str
    scopes: tuple[str, ...] = SCOPES


PERMISSIONS = {item.code: item for item in [
    Permission("employees.view", "Просматривать сотрудников", "Сотрудники"),
    Permission("employees.create", "Добавлять сотрудников", "Сотрудники", ("institution",)),
    Permission("employees.update", "Изменять сведения сотрудников", "Сотрудники", ("departments", "institution")),
    Permission("employees.deactivate", "Деактивировать сотрудников", "Сотрудники", ("departments", "institution")),
    Permission("employees.org_assignments.manage", "Вести должности и подразделения", "Сотрудники", ("institution",)),
    Permission("specialties.training.manage", "Вести обучение по специальностям", "Специальности", ("departments", "institution")),
    Permission("specialties.qualify", "Подтверждать получение специальности", "Специальности", ("departments", "institution")),
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
    Permission("expertise.closed.correct", "Корректировать завершённую работу", "Экспертизы"),
    Permission("expertise.export", "Выгружать выборку экспертиз", "Экспертизы"),
    Permission("documents.view", "Просматривать документы", "Документы"),
    Permission("documents.upload", "Подкреплять документы", "Документы"),
    Permission("letters.view", "Просматривать переписку", "Переписка"),
    Permission("letters.draft", "Готовить письма", "Переписка"),
    Permission("letters.register", "Регистрировать письма", "Переписка", ("departments", "institution")),
    Permission("letters.mark_sent", "Фиксировать отправку", "Переписка", ("departments", "institution")),
    Permission("control.close", "Снимать запрос с контроля", "Переписка"),
    Permission("issue.confirm", "Выдавать комплект материалов", "Выдача", ("departments", "institution")),
    Permission("reports.form151.run", "Рассчитывать отчёт 15.1", "Отчётность", ("departments", "institution")),
    Permission("reports.form151.download", "Выгружать отчёт 15.1", "Отчётность", ("departments", "institution")),
]}
