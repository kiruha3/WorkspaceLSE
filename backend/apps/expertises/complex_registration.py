"""One receipt, one transaction, one work per specialty; no empty UI groups."""
import hashlib
from django.db import transaction
from rest_framework.exceptions import ValidationError
from apps.accounts.commands import execute_once
from apps.accounts.policies import require
from apps.accounts.services import audit,check_version
from apps.intake.locking import locked_receipt,require_not_issued
from apps.intake.services import validate_basis
from apps.references.models import Department,Specialty
from .models import ComplexGroup
from .services import register_expertise,project_registration_result


def register_complex(*,actor,receipt_id,data,key,payload):
    for row in data['works']:
        require(actor,'expertise.register',department_ids=[row['department'].id])

    def operation():
        receipt=locked_receipt(receipt_id)
        check_version(receipt,data['expected_version'])
        require_not_issued(receipt.material_id)
        if receipt.status!='accepted':raise ValidationError('Сначала примите поступление с основанием.')
        validate_basis(receipt)
        # Deterministic reference lock order across multi-department packages.
        list(Department.objects.select_for_update().filter(pk__in=[row['department'].pk for row in data['works']]).order_by('pk'))
        list(Specialty.objects.select_for_update().filter(pk__in=[row['specialty'].pk for row in data['works']]).order_by('pk'))
        # Shared metadata must not reveal another department's hidden numbers.
        group=ComplexGroup.objects.create(material=receipt.material,title='Комплексная экспертиза')
        audit(actor,'complex_group.create',group,{'receipt_id':str(receipt.id),'registration_numbers':[row['registration_number'] for row in data['works']]})
        results=[]
        for index,row in enumerate(data['works']):
            child_key=hashlib.sha256(f'complex:{key}:{index}'.encode()).hexdigest()
            child_payload={**payload['works'][index],'expected_version':data['expected_version'],'complex_group_id':str(group.id)}
            results.append(register_expertise(actor=actor,receipt_id=receipt.id,
                data={**row,'expected_version':data['expected_version'],'complex_group':group},
                idempotency_key=child_key,payload=child_payload))
        return {'expertises':results}

    # Every child command, group and audit event rolls back with the outer one.
    with transaction.atomic():
        result=execute_once(actor=actor,action='expertise.register_complex',key=key,payload={'receipt_id':str(receipt_id),'data':payload},operation=operation)
        return {'expertises':[project_registration_result(actor,item) for item in result['expertises']]}
