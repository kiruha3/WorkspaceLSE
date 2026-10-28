from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError
from .models import Material, Receipt


def locked_material(material_id):
    return get_object_or_404(Material.objects.select_for_update(), pk=material_id)


def locked_receipt(receipt_id):
    anchor = get_object_or_404(Receipt.objects.only("material_id"), pk=receipt_id)
    locked_material(anchor.material_id)
    return Receipt.objects.select_for_update().get(pk=receipt_id)


def material_has_issue(material_id):
    from apps.issuance.models import MaterialIssue
    from apps.expertises.models import HistoricalWork
    return MaterialIssue.objects.filter(package__material_id=material_id).exists() or HistoricalWork.objects.filter(expertise__material_id=material_id,issued_on__isnull=False).exists()


def require_not_issued(material_id):
    if material_has_issue(material_id):
        raise ValidationError("Материалы уже выданы. Изменение выданного комплекта требует отдельной процедуры.")
