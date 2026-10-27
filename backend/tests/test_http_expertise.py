import json
import uuid
from http.cookiejar import CookieJar
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener
import pytest
from apps.personnel.models import EmployeeSpecialty
from apps.references.models import Department, Specialty


@pytest.mark.django_db(transaction=True)
def test_real_http_clerk_head_expert_registration_and_training_denial(live_server,employee_factory,grant):
    department=Department.objects.create(code="3",name="Отдел 3")
    specialty=Specialty.objects.create(code="1.1",name="Почерк")
    clerk=employee_factory();head=employee_factory(department=department)
    expert=employee_factory(department=department);trainee=employee_factory(department=department)
    for action in ("receipts.create","receipts.view","receipts.accept","documents.upload","documents.view","expertise.register","expertise.view"):grant(clerk,action)
    for action in ("expertise.view","expertise.assign","documents.view"):grant(head,action,"departments",departments=[department])
    for action in ("expertise.view","documents.view"):grant(expert,action,"own")
    EmployeeSpecialty.objects.create(employee=expert,specialty=specialty,status="qualified",basis="Подтверждено, дата неизвестна")
    EmployeeSpecialty.objects.create(employee=trainee,specialty=specialty,status="training")

    def login(employee):
        browser=build_opener(HTTPCookieProcessor(CookieJar()));token=None
        def call(path,method="GET",body=None,headers=None):
            actual={"Content-Type":"application/json",**(headers or {})}
            if method!="GET":actual["X-CSRFToken"]=token
            request=Request(live_server.url+"/api/v1"+path,data=json.dumps(body).encode() if body is not None else None,headers=actual,method=method)
            try:
                with browser.open(request,timeout=5) as response:return response.status,json.load(response)
            except HTTPError as response:return response.code,json.load(response)
        token=call("/auth/csrf/")[1]["csrf_token"]
        token=call("/auth/login/","POST",{"username":employee.user.username,"password":"Test-only-LongPassword9"})[1]["csrf_token"]
        return call

    clerk_http=login(clerk);head_http=login(head);expert_http=login(expert)
    status,basis=clerk_http("/documents/","POST",{"kind":"resolution","title":"ДЕМО постановление","source_kind":"paper_original","department_id":str(department.id)})
    assert status==201
    status,receipt=clerk_http("/receipts/","POST",{"received_at":"2026-10-28","material_title":"Контрольный материал","department_id":str(department.id),"basis_document_id":basis["id"]})
    assert status==201
    status,receipt=clerk_http(f"/receipts/{receipt['id']}/register/","POST",{"expected_version":1})
    assert status==200
    status,work=clerk_http(f"/receipts/{receipt['id']}/expertises/","POST",{"expected_version":2,"registration_number":"1/3-1-26","department_id":str(department.id),"specialty_id":str(specialty.id),"appointment_nature":"primary","is_commission":False},headers={"Idempotency-Key":str(uuid.uuid4())})
    assert status==201 and work["current_assignments"]==[]
    assert head_http(f"/expertises/{work['id']}/")[1]["allowed_actions"]==["expertise.assign"]
    payload={"expected_version":1,"employee_ids":[str(trainee.id)],"reason":"Проверка допуска"}
    assert head_http(f"/expertises/{work['id']}/assignments/","POST",payload)[0]==400
    payload["employee_ids"]=[str(expert.id)]
    status,assigned=head_http(f"/expertises/{work['id']}/assignments/","POST",payload)
    assert status==200 and assigned["version"]==2
    assert expert_http("/expertises/")[1]["count"]==1
    reloaded=expert_http(f"/expertises/{work['id']}/")[1]
    assert reloaded["current_assignments"][0]["employee"]["id"]==str(expert.id)
    assert reloaded["basis_document"]["id"]==basis["id"]
    assert reloaded["allowed_actions"]==[]
    assert expert_http(f"/expertises/{work['id']}/assignments/","POST",payload)[0]==403
