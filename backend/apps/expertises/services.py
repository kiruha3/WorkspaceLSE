from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import APIException, ValidationError
from apps.accounts.commands import execute_once
from apps.accounts.policies import require, permission_scopes
from apps.accounts.services import audit, check_version
from apps.intake.models import Receipt
from apps.intake.services import validate_basis
from apps.references.models import Department, Specialty
from .models import Expertise, ComplexGroup
from .numbering import parse_current_number


class RegistrationConflict(APIException):
    status_code=409
    default_code="registration_conflict"
    default_detail="Этот номер или специальность комплекса уже зарегистрированы. Обновите журнал."


def register_expertise(*,actor,receipt_id,data,idempotency_key,payload):
    # Also checked on a replay: a cached command never restores a revoked right.
    require(actor,"expertise.register",department_ids=[data["department"].id])

    def operation():
        receipt=get_object_or_404(Receipt.objects.select_for_update(),pk=receipt_id)
        values=data.copy();check_version(receipt,values.pop("expected_version"))
        if receipt.status!="accepted":raise ValidationError("Сначала примите поступление с основанием.")
        validate_basis(receipt)
        # Resolve active references under lock, not the serializer's old copies.
        department=get_object_or_404(Department.objects.select_for_update(),pk=values["department"].id,is_active=True)
        specialty=get_object_or_404(Specialty.objects.select_for_update(),pk=values["specialty"].id,is_active=True)
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
        audit(actor,"expertise.register",work,{"registration_number":work.registration_number,"receipt_id":str(receipt.id),"specialty_id":str(specialty.id)})
        from .serializers import ExpertiseOutput
        return ExpertiseOutput(work,context={"user":actor,"scopes":permission_scopes(actor)}).data

    return execute_once(actor=actor,action="expertise.register",key=idempotency_key,payload={"receipt_id":str(receipt_id),"data":payload},operation=operation)
