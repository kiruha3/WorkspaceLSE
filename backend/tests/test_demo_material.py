import pytest
from apps.intake.models import Material
from apps.audit.models import AuditEvent
from test_receipts import clerk_client

pytestmark=pytest.mark.django_db


def test_explicit_training_intake_is_persisted_and_visible(employee_factory,grant):
    client,_=clerk_client(employee_factory,grant)
    response=client.post('/api/v1/receipts/',{'received_at':'2026-10-28','material_title':'Обучение','is_demo':True},content_type='application/json')
    assert response.status_code==201,response.content
    assert response.json()['material']['is_demo'] is True
    assert Material.objects.get().is_demo is True
    assert AuditEvent.objects.get(action='receipt.create').changes['is_demo'] is True


def test_demo_word_or_account_does_not_infer_training(employee_factory,grant):
    client,_=clerk_client(employee_factory,grant)
    response=client.post('/api/v1/receipts/',{'received_at':'2026-10-28','material_title':'ДЕМО не означает учебную запись'},content_type='application/json')
    assert response.status_code==201
    assert response.json()['material'].get('is_demo') is False


def test_receipt_amendment_cannot_silently_change_reporting_classification(employee_factory,grant):
    client,_=clerk_client(employee_factory,grant)
    created=client.post('/api/v1/receipts/',{'received_at':'2026-10-28'},content_type='application/json').json()
    response=client.post(f"/api/v1/receipts/{created['id']}/amend/",{'expected_version':1,'reason':'Скрыть из отчёта','is_demo':True},content_type='application/json')
    assert response.status_code==400
