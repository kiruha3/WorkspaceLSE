import uuid
import json
import pytest
from django.test import Client
from apps.expertises.models import Expertise, ComplexGroup
from apps.references.models import Department, Specialty
from apps.audit.models import AuditEvent
from test_registration import registration_setup, register

pytestmark=pytest.mark.django_db


def complex_setup(employee_factory,grant):
    client,employee,receipt,department,specialty,data=registration_setup(employee_factory,grant)
    other_department=Department.objects.create(code="4",name="Отдел 4")
    other_specialty=Specialty.objects.create(code="18.1",name="Оценка транспортных средств")
    first={k:v for k,v in data.items() if k!="expected_version"}
    second={**first,"registration_number":"152/4-1-26","department_id":str(other_department.id),"specialty_id":str(other_specialty.id)}
    return client,employee,receipt,department,other_department,{"expected_version":2,"works":[first,second]}


def post_complex(client,receipt,body,key=None):
    return client.post(f"/api/v1/receipts/{receipt['id']}/complex-expertises/",body,content_type="application/json",HTTP_IDEMPOTENCY_KEY=key or str(uuid.uuid4()))


def test_registers_two_numbers_as_one_atomic_complex(employee_factory,grant):
    client,_,receipt,_,_,body=complex_setup(employee_factory,grant)
    response=post_complex(client,receipt,body)
    assert response.status_code==201,response.content
    works=response.json()["expertises"]
    assert [work["registration_number"] for work in works]==["151/3-1-26","152/4-1-26"]
    assert len({work["complex_group"]["id"] for work in works})==1
    assert all(work["material"]["id"]==receipt["material"]["id"] for work in works)
    assert all(work["basis_document"]["id"]==receipt["basis_document"]["id"] for work in works)
    assert all(len(work["complex_group"]["expertises"])==2 for work in works)
    assert Expertise.objects.count()==2 and ComplexGroup.objects.count()==1
    assert client.get("/api/v1/expertises/").json()["count"]==2


def test_complex_retry_restores_same_numbers_and_conflicting_payload_is_rejected(employee_factory,grant):
    client,_,receipt,_,_,body=complex_setup(employee_factory,grant)
    key=str(uuid.uuid4())
    first=post_complex(client,receipt,body,key)
    assert first.status_code==201,first.content
    repeated=post_complex(client,receipt,body,key)
    assert repeated.status_code==201
    assert [w["id"] for w in repeated.json()["expertises"]]==[w["id"] for w in first.json()["expertises"]]
    changed={**body,"works":[{**body["works"][0],"registration_number":"153/3-1-26"},body["works"][1]]}
    assert post_complex(client,receipt,changed,key).status_code==409
    assert Expertise.objects.count()==2 and ComplexGroup.objects.count()==1
    assert AuditEvent.objects.filter(action="expertise.register").count()==2


def test_second_number_conflict_rolls_back_first_number_and_group(employee_factory,grant):
    client,_,receipt,_,_,body=complex_setup(employee_factory,grant)
    assert register(client,receipt,{**body["works"][1],"expected_version":2}).status_code==201
    response=post_complex(client,receipt,body)
    assert response.status_code==409,response.content
    assert list(Expertise.objects.values_list("registration_number",flat=True))==["152/4-1-26"]
    assert ComplexGroup.objects.count()==0
    assert AuditEvent.objects.filter(action="expertise.register").count()==1


@pytest.mark.parametrize("change",["same_specialty","same_sequence","other_category","other_year","one_row"])
def test_complex_requires_distinct_specialties_and_sequences_in_one_case_year(employee_factory,grant,change):
    client,_,receipt,_,_,body=complex_setup(employee_factory,grant)
    if change=="same_specialty":body["works"][1]["specialty_id"]=body["works"][0]["specialty_id"]
    if change=="same_sequence":body["works"][1]["registration_number"]="151/4-1-26"
    if change=="other_category":body["works"][1]["registration_number"]="152/4-2-26"
    if change=="other_year":body["works"][1]["registration_number"]="152/4-1-27"
    if change=="one_row":body["works"]=body["works"][:1]
    assert post_complex(client,receipt,body).status_code==400
    assert Expertise.objects.count()==0 and ComplexGroup.objects.count()==0


def test_complex_checks_registration_authority_for_every_department(employee_factory,grant):
    client,employee,receipt,department,_,body=complex_setup(employee_factory,grant)
    employee.role_assignments.filter(role__permissions__permission_code="expertise.register").update(is_active=False)
    grant(employee,"expertise.register","departments",departments=[department])
    assert post_complex(client,receipt,body).status_code==403
    assert Expertise.objects.count()==0 and ComplexGroup.objects.count()==0


def test_complex_links_hide_numbers_outside_read_scope(employee_factory,grant):
    client,_,receipt,department,_,body=complex_setup(employee_factory,grant)
    response=post_complex(client,receipt,body)
    assert response.status_code==201,response.content
    works=response.json()["expertises"]
    employee=employee_factory();grant(employee,"expertise.view","departments",departments=[department])
    reader=Client();reader.force_login(employee.user)
    detail=reader.get(f"/api/v1/expertises/{works[0]['id']}/")
    assert detail.status_code==200
    related=detail.json()["complex_group"]["expertises"]
    assert [work["id"] for work in related]==[works[0]["id"]]
    assert works[1]['registration_number'] not in json.dumps(detail.json(),ensure_ascii=False)
    assert works[1]['registration_number'] not in json.dumps(reader.get('/api/v1/expertises/').json(),ensure_ascii=False)
    assert reader.get(f"/api/v1/expertises/{works[1]['id']}/").status_code==403
