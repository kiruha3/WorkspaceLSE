from .models import EmployeeSpecialty

_UNSET = object()


def qualification_eligibility(employee, specialty, at, *, qualification=_UNSET):
    """Eligibility follows the recorded status; specialty dates are reference data."""
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
        return denied("qualification_unconfirmed","Специальность ещё не отмечена как полученная.")
    return {"eligible":True,"code":"qualified","message":"Полученная специальность соответствует назначению."}
