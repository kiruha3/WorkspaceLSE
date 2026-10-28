from dataclasses import dataclass
from datetime import date
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from apps.accounts.commands import execute_once,CommandConflict
from apps.accounts.policies import require
from apps.accounts.services import audit,check_version
from apps.expertises.models import Expertise
from apps.personnel.models import Employee
from apps.references.models import Department,Specialty
from .models import ImportRow,ImportSelection,ImportApplicationItem
from .policies import require_preview_read


def require_reconcile(actor):
    require_preview_read(actor)
    require(actor,"imports.reconcile")


def identity_blockers(row):
    blockers=[item for item in row.diagnostics if item["code"] in ("registration_invalid","duplicate_number","received_missing","state_unknown") or item["code"]=="date_invalid" and "C" in item["columns"]]
    if row.facts.get("received_on") and date.fromisoformat(row.facts["received_on"])>timezone.localdate():
        blockers.append({"code":"received_future","columns":["C"],"severity":"error","message":"Поступление не может быть в будущем."})
    return blockers


@dataclass
class ReconciliationContext:
    departments:dict
    specialties:dict
    works:dict

    @classmethod
    def for_rows(cls,rows):
        numbers=[row.facts.get("registration_number") for row in rows if row.facts.get("registration_number")]
        return cls({ref.code:ref for ref in Department.objects.all()},{ref.code:ref for ref in Specialty.objects.all()},
            {work.registration_number:work for work in Expertise.objects.filter(registration_number__in=numbers).select_related("historical__source_row")})


def reference_data(ref):
    return {"id":str(ref.pk),"code":ref.code,"name":ref.name,"is_active":ref.is_active} if ref else None


def classify_row(row,context=None):
    context=context or ReconciliationContext.for_rows([row])
    blockers=identity_blockers(row)
    department=context.departments.get(row.facts.get("department_code"))
    if row.facts.get("department_code") and department is None:
        blockers.append({"code":"department_unmapped","severity":"error","columns":["B"],"message":"Отдел текущего номера отсутствует в справочнике; другой код не подставляется."})
    work=context.works.get(row.facts.get("registration_number"))
    history=getattr(work,"historical",None) if work else None
    classification="invalid" if blockers else "new" if work is None else "unchanged" if history and history.source_row.facts==row.facts else "changed"
    return {"classification":classification,"existing_work":{"id":str(work.pk),"registration_number":work.registration_number,"version":work.version} if work else None,
        "blockers":blockers,"suggested_department":reference_data(department),"suggested_specialty":reference_data(context.specialties.get(row.facts.get("specialty_code")))}


def selection_data(selection):
    if selection is None:return None
    return {"id":str(selection.pk),"row_id":str(selection.row_id),"version":selection.version,
        "department_id":str(selection.department_id),"specialty_id":str(selection.specialty_id) if selection.specialty_id else None,
        "employee_ids":sorted(str(employee.pk) for employee in selection.employees.all()),
        "appointment_nature":selection.appointment_nature,"is_commission":selection.is_commission,"complex_known":selection.complex_known,
        "complex_group_key":selection.complex_group_key,"statistics_confirmed":selection.statistics_confirmed,"reason":selection.reason}


def validate_mapping(row,department,specialty,statistics_confirmed):
    code=row.facts.get("department_code")
    if code and department.code!=code:raise ValidationError({"department_id":"Код отдела должен совпадать с текущим номером источника."})
    code=row.facts.get("specialty_code")
    if code and (specialty is None or specialty.code!=code):raise ValidationError({"specialty_id":"Признанный код M связывается только с той же специальностью."})
    if statistics_confirmed:
        counts=[row.facts.get(field) for field in ("questions","categorical","probable","unresolved")]
        if any(value is None for value in counts) or counts[0]!=sum(counts[1:]):raise ValidationError({"statistics_confirmed":"Подтверждение требует известных и сходящихся Q/R/S/T."})


@transaction.atomic
def save_selection(*,actor,row_id,data,key,payload):
    require_reconcile(actor)
    row=get_object_or_404(ImportRow.objects.select_for_update(),pk=row_id)
    def operation():
        require_reconcile(actor)
        if ImportApplicationItem.objects.filter(row=row).exists():raise CommandConflict("Строка уже применена; сохранённое сопоставление неизменно.")
        selection=ImportSelection.objects.filter(row=row).first()
        if selection:check_version(selection,data["expected_version"])
        elif data["expected_version"]!=0:raise CommandConflict("Сопоставление ещё не создано. Ожидалась версия0.")
        department=Department.objects.select_for_update().get(pk=data["department"].pk)
        specialty=Specialty.objects.select_for_update().get(pk=data["specialty"].pk) if data["specialty"] else None
        employees=list(Employee.objects.select_for_update().filter(pk__in=data["employee_ids"]).order_by("pk"))
        if len(employees)!=len(data["employee_ids"]):raise ValidationError({"employee_ids":"Сотрудник не найден; имя из источника не создаёт сотрудника автоматически."})
        validate_mapping(row,department,specialty,data["statistics_confirmed"])
        values={field:data[field] for field in ("appointment_nature","is_commission","complex_known","complex_group_key","statistics_confirmed","reason")}
        if selection:
            selection.version+=1
            for field,value in values.items():setattr(selection,field,value)
            selection.actor=actor;selection.department=department;selection.specialty=specialty;selection.save()
        else:selection=ImportSelection.objects.create(row=row,actor=actor,department=department,specialty=specialty,**values)
        selection.employees.set(employees)
        event=audit(actor,"imports.reconcile",selection,selection_data(selection),data["reason"])
        return {"id":str(event.pk),"selection_id":str(selection.pk)}
    return execute_once(actor=actor,action="imports.reconcile",key=key,payload={"row_id":str(row.pk),"data":payload},operation=operation)
