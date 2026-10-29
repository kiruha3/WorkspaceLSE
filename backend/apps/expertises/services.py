from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import APIException, ValidationError
from apps.accounts.commands import execute_once
from apps.accounts.policies import require, permission_scopes
from apps.accounts.services import audit, check_version
from apps.intake.models import Receipt
from apps.intake.services import validate_basis
from apps.intake.locking import locked_receipt, require_not_issued
from apps.references.models import Department, Specialty
from .models import Expertise, ComplexGroup, ExpertAssignment, WorkCaseDetails, CaseDetailsRevision
from .numbering import parse_current_number
from .policies import require_work


class RegistrationConflict(APIException):
    status_code=409
    default_code="registration_conflict"
    default_detail="Этот номер или специальность комплекса уже зарегистрированы. Обновите журнал."


def register_expertise(*,actor,receipt_id,data,idempotency_key,payload):
    # Also checked on a replay: a cached command never restores a revoked right.
    require(actor,"expertise.register",department_ids=[data["department"].id])

    def operation():
        receipt=locked_receipt(receipt_id)
        values=data.copy();check_version(receipt,values.pop("expected_version"))
        require_not_issued(receipt.material_id)
        if receipt.status!="accepted":raise ValidationError("Сначала примите поступление с основанием.")
        validate_basis(receipt)
        # Resolve active references under lock, not the serializer's old copies.
        department=get_object_or_404(Department.objects.select_for_update(),pk=values["department"].id)
        specialty=get_object_or_404(Specialty.objects.select_for_update(),pk=values["specialty"].id)
        if not department.is_active:raise ValidationError({"department_id":"Отдел неактивен."})
        if not specialty.is_active:raise ValidationError({"specialty_id":"Специальность неактивна."})
        construction=values.pop('decree3214',None)
        if construction is True and specialty.code not in ('16.1','16.2'):
            raise ValidationError({'decree3214':'Самовольное строение отмечается только для специальностей16.1 и16.2.'})
        parsed=parse_current_number(values["registration_number"])
        if parsed.department_code!=department.code:
            raise ValidationError({"department_id":"Отдел не совпадает с текущим регистрационным номером."})
        group=values.get("complex_group")
        if group is not None:
            group=ComplexGroup.objects.select_for_update().get(pk=group.pk)
            if group.material_id!=receipt.material_id:raise ValidationError({"complex_group_id":"Комплекс относится к другому материалу."})
        values.update(registration_number=parsed.normalized,sequence=parsed.sequence,year=parsed.year,category_code=parsed.category_code,department=department,specialty=specialty,complex_group=group)
        try:
            with transaction.atomic():
                work=Expertise.objects.create(receipt=receipt,material=receipt.material,registered_by=actor,**values)
        except IntegrityError as exc:
            if getattr(exc.__cause__,"sqlstate",None)=="23505": raise RegistrationConflict() from exc
            raise
        if construction is not None:
            from .case_details import case_snapshot
            before=case_snapshot(work)
            details=WorkCaseDetails.objects.create(expertise=work,created_by=actor,decree3214=construction)
            work.case_details=details
            CaseDetailsRevision.objects.create(details=details,number=1,actor=actor,
                reason='Отметка при регистрации экспертизы',before=before,after=case_snapshot(work))
        audit(actor,"expertise.register",work,{"registration_number":work.registration_number,"receipt_id":str(receipt.id),"specialty_id":str(specialty.id)})
        from .serializers import ExpertiseOutput
        return ExpertiseOutput(work,context={"user":actor,"scopes":permission_scopes(actor)}).data

    result=execute_once(actor=actor,action="expertise.register",key=idempotency_key,payload={"receipt_id":str(receipt_id),"data":payload},operation=operation)
    # Replay preserves business facts, never yesterday's authority. Do not
    # overwrite the stored result when projecting today's permission fields.
    from apps.documents.models import Document
    from apps.documents.policies import can_document
    from .serializers import ExpertiseOutput
    work=Expertise.objects.prefetch_related("assignments").get(pk=result["id"])
    output=dict(result)
    output["allowed_actions"]=ExpertiseOutput(context={"user":actor,"scopes":permission_scopes(actor)}).get_allowed_actions(work)
    if basis:=result.get("basis_document"):
        document=Document.objects.filter(pk=basis["id"]).first()
        if document is None or not can_document(actor,"documents.view",document):
            output["basis_document"]={"id":basis["id"],"restricted":True}
    return output


@transaction.atomic
def _set_experts(*,actor,expertise_id,employee_ids,expected_version,reason,reassign):
    from apps.personnel.models import Employee, EmployeeSpecialty
    from apps.personnel.services import qualification_eligibility
    work=get_object_or_404(Expertise.objects.select_for_update(),pk=expertise_id)
    action="expertise.reassign" if reassign else "expertise.assign"
    require_work(actor,action,work);check_version(work,expected_version)
    from .history import require_operational
    require_operational(work)
    if work.state not in ("in_progress","suspended"):raise ValidationError("Состав завершённой работы изменяется отдельной процедурой.")
    current=list(work.assignments.select_for_update().all())
    active={a.employee_id:a for a in current if a.ended_at is None}
    if bool(active)!=reassign:raise ValidationError("Используйте назначение для новой работы или перепоручение для уже назначенной.")
    selected=set(employee_ids)
    if len(selected)!=len(employee_ids):raise ValidationError({"employee_ids":"Сотрудник указан несколько раз."})
    if (work.is_commission and len(selected)<2) or (not work.is_commission and len(selected)!=1):
        raise ValidationError({"employee_ids":"Для комиссии нужны минимум два эксперта; для обычной работы — один."})
    if reassign and selected==set(active):raise ValidationError({"employee_ids":"Состав исполнителей не изменён."})
    specialty=Specialty.objects.select_for_update().get(pk=work.specialty_id)
    employees=list(Employee.objects.select_for_update().filter(pk__in=selected).order_by("id"))
    if len(employees)!=len(selected):raise ValidationError({"employee_ids":"Один из сотрудников не найден."})
    qualifications={q.employee_id:q for q in EmployeeSpecialty.objects.select_for_update().filter(employee_id__in=selected,specialty=specialty).order_by("employee_id")}
    at=timezone.now();today=timezone.localdate(at)
    for employee in employees:
        eligibility=qualification_eligibility(employee,specialty,today,qualification=qualifications.get(employee.id))
        if not eligibility["eligible"]:raise ValidationError({"employee_ids":f"{employee.full_name}: {eligibility['message']}"})
    for employee_id,assignment in active.items():
        if employee_id not in selected:
            assignment.ended_at=at;assignment.save(update_fields=["ended_at"])
    for employee in employees:
        if employee.id in active:continue
        q=qualifications[employee.id]
        snapshot={"qualification_id":str(q.id),"specialty_id":str(specialty.id),"status":q.status,"qualified_at":q.qualified_at.isoformat() if q.qualified_at else None,"valid_until":q.valid_until.isoformat() if q.valid_until else None,"basis":q.basis,"version":q.version}
        ExpertAssignment.objects.create(expertise=work,employee=employee,started_at=at,actor=actor,reason=reason,qualification_snapshot=snapshot)
    work.version+=1;work.save(update_fields=["version"])
    audit(actor,action,work,{"before_employee_ids":sorted(map(str,active)),"employee_ids":sorted(map(str,selected)),"version":work.version},reason)
    return work


def assign_experts(**kwargs):return _set_experts(**kwargs,reassign=False)


def reassign_experts(**kwargs):return _set_experts(**kwargs,reassign=True)
