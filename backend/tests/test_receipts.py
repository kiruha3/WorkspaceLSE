import pytest
from django.test import Client

pytestmark = pytest.mark.django_db


def clerk_client(employee_factory,grant):
    employee=employee_factory()
    for action in ["receipts.view","receipts.create","receipts.accept","documents.view","documents.upload"]:
        grant(employee,action)
    client=Client();client.force_login(employee.user)
    return client,employee


def create_basis(client,source="paper_original"):
    response=client.post("/api/v1/documents/",{"kind":"decision","title":"Определение суда","source_kind":source},content_type="application/json")
    assert response.status_code==201
    return response.json()


def test_paper_basis_accepts_without_fake_file(employee_factory,grant):
    client,_=clerk_client(employee_factory,grant)
    basis=create_basis(client)
    response=client.post("/api/v1/receipts/",{"received_at":"2026-10-28","sender_name":"Суд","material_title":"Материалы дела","basis_document_id":basis["id"]},content_type="application/json")
    assert response.status_code==201
    receipt=response.json()
    assert receipt["status"]=="draft" and receipt["basis_document"]["versions"]==[]
    accepted=client.post(f"/api/v1/receipts/{receipt['id']}/register/",{"expected_version":1},content_type="application/json")
    assert accepted.status_code==200
    assert accepted.json()["status"]=="accepted"
    assert accepted.json()["basis_document"]["source_kind"]=="paper_original"
    assert client.get(f"/api/v1/receipts/{receipt['id']}/").json()["material"]["id"]==receipt["material"]["id"]


def test_missing_basis_does_not_accept(employee_factory,grant):
    client,_=clerk_client(employee_factory,grant)
    response=client.post("/api/v1/receipts/",{"received_at":"2026-10-28","sender_name":"Суд"},content_type="application/json")
    assert response.status_code==201
    receipt=response.json()
    response=client.post(f"/api/v1/receipts/{receipt['id']}/register/",{"expected_version":1},content_type="application/json")
    assert response.status_code==400
    assert "basis_document_id" in response.json()["field_errors"]
    assert client.get(f"/api/v1/receipts/{receipt['id']}/").json()["status"]=="draft"


def test_missing_basis_can_be_added_by_an_explicit_amendment(employee_factory,grant):
    client,employee=clerk_client(employee_factory,grant);grant(employee,"receipts.amend")
    receipt=client.post("/api/v1/receipts/",{"received_at":"2026-10-28"},content_type="application/json").json()
    basis=create_basis(client)
    response=client.post(f"/api/v1/receipts/{receipt['id']}/amend/",{"expected_version":1,"basis_document_id":basis["id"],"reason":"Дослано определение"},content_type="application/json")
    assert response.status_code==200 and response.json()["version"]==2
    assert client.post(f"/api/v1/receipts/{receipt['id']}/register/",{"expected_version":2},content_type="application/json").status_code==200
    assert client.post(f"/api/v1/receipts/{receipt['id']}/amend/",{"expected_version":3,"basis_document_id":None,"reason":"Ошибка"},content_type="application/json").status_code==400


def test_pending_uploaded_copy_cannot_be_accepted(employee_factory,grant):
    client,_=clerk_client(employee_factory,grant)
    basis=create_basis(client,"uploaded_copy")
    receipt=client.post("/api/v1/receipts/",{"received_at":"2026-10-28","basis_document_id":basis["id"]},content_type="application/json").json()
    response=client.post(f"/api/v1/receipts/{receipt['id']}/register/",{"expected_version":1},content_type="application/json")
    assert response.status_code==400
    assert "basis_document_id" in response.json()["field_errors"]


def test_shared_document_not_copied_for_receipts(employee_factory,grant):
    client,_=clerk_client(employee_factory,grant)
    basis=create_basis(client)
    for _ in range(2):
        assert client.post("/api/v1/receipts/",{"received_at":"2026-10-28","basis_document_id":basis["id"]},content_type="application/json").status_code==201
    from apps.documents.models import Document
    assert Document.objects.count()==1


def test_receipts_list_and_detail_require_their_own_scope(employee_factory,grant):
    client,_=clerk_client(employee_factory,grant)
    receipt=client.post("/api/v1/receipts/",{"received_at":"2026-10-28"},content_type="application/json").json()
    outsider=employee_factory();grant(outsider,"receipts.view","own")
    other=Client();other.force_login(outsider.user)
    assert other.get("/api/v1/receipts/").json()["count"]==0
    assert other.get(f"/api/v1/receipts/{receipt['id']}/").status_code==403


def test_amend_only_user_can_load_department_choices_and_amend(employee_factory,grant):
    from apps.references.models import Department
    department=Department.objects.create(code="3",name="Отдел 3")
    client,_=clerk_client(employee_factory,grant)
    receipt=client.post("/api/v1/receipts/",{"received_at":"2026-10-28","department_id":str(department.id)},content_type="application/json").json()
    employee=employee_factory()
    for action in ("receipts.view","receipts.amend"):grant(employee,action,"departments",departments=[department])
    other=Client();other.force_login(employee.user)
    choices=other.get("/api/v1/references/departments/")
    assert choices.status_code==200 and choices.json()["results"][0]["id"]==str(department.id)
    response=other.post(f"/api/v1/receipts/{receipt['id']}/amend/",{"expected_version":1,"sender_name":"Уточнённый отправитель","reason":"Письмо отправителя"},content_type="application/json")
    assert response.status_code==200 and response.json()["sender_name"]=="Уточнённый отправитель"
