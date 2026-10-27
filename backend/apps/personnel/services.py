from .models import EmployeeSpecialty

_UNSET = object()


def qualification_eligibility(employee, specialty, at, *, qualification=_UNSET):
    def denied(code, message):
        return {"eligible":False,"code":code,"message":message}
    if not employee.is_active or not specialty.is_active:
        return denied("inactive","Сотрудник или специальность неактивны.")
    item = EmployeeSpecialty.objects.filter(employee=employee,specialty=specialty).first() if qualification is _UNSET else qualification
    if item is None:
        return denied("specialty_missing","Специальность у сотрудника не указана.")
    if item.status == "training":
        return denied("specialty_training","По этой специальности сотрудник обучается: назначение на экспертизу недоступно.")
    if item.status != "qualified":
        return denied("qualification_unconfirmed","Получение специальности пока не подтверждено.")
    if item.qualified_at is None and not item.basis.strip():
        return denied("qualification_unconfirmed","При неизвестной дате получения требуется явное подтверждение и основание.")
    if item.qualified_at is not None and item.qualified_at > at:
        return denied("qualification_not_yet_valid","Дата получения специальности позже даты назначения.")
    if item.valid_until is not None and item.valid_until < at:
        return denied("qualification_expired","Указанный срок действия специальности закончился.")
    return {"eligible":True,"code":"qualified","message":"Полученная специальность соответствует назначению."}
