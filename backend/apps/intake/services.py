from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError
from apps.accounts.policies import active_employee,require
from apps.accounts.services import audit,check_version
from apps.documents.policies import require_document
from .models import Receipt,Material
from .locking import locked_receipt, require_not_issued


def receipt_context(receipt):
    return {"employee_id":receipt.created_by_id,"department_ids":[receipt.department_id] if receipt.department_id else []}


def validate_basis(receipt):
    document=receipt.basis_document
    if document is None or document.kind not in ("resolution","decision"):
        raise ValidationError({"basis_document_id":"Нужно постановление или определение."})
    if document.source_kind=="uploaded_copy" and not document.versions.exists():
        raise ValidationError({"basis_document_id":"Сначала сохраните файл копии основания."})


@transaction.atomic
def create_receipt(*,actor,data):
    data=data.copy();title=data.pop("material_title","")
    employee=active_employee(actor);department=data.get("department")
    require(actor,"receipts.create",employee_id=employee.pk if employee else None,department_ids=[department.id] if department else [])
    if data.get("basis_document"):
        require_document(actor,"documents.view",data["basis_document"])
    material=Material.objects.create(title=title,created_by=employee)
    receipt=Receipt.objects.create(material=material,created_by=employee,**data)
    audit(actor,"receipt.create",receipt,{"material_id":str(material.id),"received_at":receipt.received_at,"basis_document_id":str(receipt.basis_document_id) if receipt.basis_document_id else None})
    return receipt


@transaction.atomic
def accept_receipt(*,actor,receipt_id,expected_version):
    receipt=get_object_or_404(Receipt.objects.select_for_update(),pk=receipt_id)
    require(actor,"receipts.accept",**receipt_context(receipt));check_version(receipt,expected_version)
    if receipt.status!="draft":raise ValidationError("Поступление уже принято.")
    validate_basis(receipt)
    receipt.status="accepted";receipt.version+=1;receipt.save()
    audit(actor,"receipt.accept",receipt,{"status":"accepted","version":receipt.version})
    return receipt


@transaction.atomic
def amend_receipt(*,actor,receipt_id,data):
    receipt=locked_receipt(receipt_id)
    require(actor,"receipts.amend",**receipt_context(receipt))
    data=data.copy();check_version(receipt,data.pop("expected_version"));reason=data.pop("reason")
    require_not_issued(receipt.material_id)
    if data.get("basis_document"):require_document(actor,"documents.view",data["basis_document"])
    before={key:str(getattr(receipt,key+"_id")) if key in ("department","basis_document") else str(getattr(receipt,key)) for key in data}
    for key,value in data.items():setattr(receipt,key,value)
    require(actor,"receipts.amend",**receipt_context(receipt))
    if "received_at" in data and receipt.expertises.filter(Q(suspensions__suspended_on__lt=receipt.received_at)|Q(deadline_events__recorded_on__lt=receipt.received_at)|Q(deadline_events__due_on__lt=receipt.received_at)).exists():
        raise ValidationError({"received_at":"Дата поступления позже уже внесённого события производства или срока. Уточните исходные документы; история автоматически не переписывается."})
    if "received_at" in data:
        from apps.expertises.results import latest_closure
        for work in receipt.expertises.prefetch_related("closures"):
            closure=latest_closure(work)
            if closure and closure.ended_on<receipt.received_at:
                raise ValidationError({"received_at":"Дата поступления позже подтверждённого окончания работы."})
    if receipt.status=="accepted":validate_basis(receipt)
    receipt.version+=1;receipt.save()
    audit(actor,"receipt.amend",receipt,{"before":before,"fields":list(data),"version":receipt.version},reason)
    return receipt
