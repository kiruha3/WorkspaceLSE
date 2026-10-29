from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import uuid
import pytest
from django.db import close_old_connections, connection
from django.test import Client
from test_registration import registration_setup

pytestmark = pytest.mark.django_db(transaction=True)


def test_complex_package_concurrent_retry_creates_exactly_two_works(employee_factory,grant):
    from test_complex_registration import complex_setup,post_complex
    from apps.expertises.models import Expertise,ComplexGroup
    _,employee,receipt,_,_,body=complex_setup(employee_factory,grant)
    barrier=Barrier(2);key=str(uuid.uuid4())
    def run(_):
        close_old_connections()
        try:
            client=Client();client.force_login(employee.user);barrier.wait(timeout=10)
            response=post_complex(client,receipt,body,key)
            return response.status_code,response.json()
        finally:connection.close()
    with ThreadPoolExecutor(max_workers=2) as pool:responses=list(pool.map(run,range(2)))
    assert [status for status,_ in responses]==[201,201]
    assert [w['id'] for w in responses[0][1]['expertises']]==[w['id'] for w in responses[1][1]['expertises']]
    assert Expertise.objects.count()==2 and ComplexGroup.objects.count()==1


@pytest.mark.parametrize("same_key", [False, True])
def test_same_number_concurrent_one_success_one_conflict(employee_factory, grant, same_key):
    _, employee, receipt, _, _, data = registration_setup(employee_factory, grant)
    barrier = Barrier(2)
    keys = [str(uuid.uuid4()), str(uuid.uuid4())]
    if same_key: keys[1] = keys[0]

    def run(key):
        close_old_connections()
        try:
            client = Client(); client.force_login(employee.user)
            barrier.wait(timeout=10)
            response = client.post(f"/api/v1/receipts/{receipt['id']}/expertises/", data, content_type="application/json", HTTP_IDEMPOTENCY_KEY=key)
            return response.status_code, response.json()
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(run, keys))
    assert sorted(status for status, _ in responses) == ([201,201] if same_key else [201,409])
    from apps.expertises.models import Expertise
    from apps.audit.models import AuditEvent
    assert Expertise.objects.count() == 1
    assert AuditEvent.objects.filter(action="expertise.register").count() == 1
    if same_key: assert responses[0][1] == responses[1][1]


def test_concurrent_creation_of_same_named_complex_group_creates_one_record(employee_factory, grant):
    from apps.expertises.models import ComplexGroup
    from apps.audit.models import AuditEvent
    _, employee, receipt, _, _, _ = registration_setup(employee_factory, grant)
    barrier=Barrier(2)

    def run(_):
        close_old_connections()
        try:
            client=Client();client.force_login(employee.user)
            barrier.wait(timeout=10)
            response=client.post("/api/v1/complex-groups/",{"receipt_id":receipt["id"],"title":"Комплексное исследование"},content_type="application/json",HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
            return response.status_code,response.json()
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses=list(pool.map(run,range(2)))
    assert all(status in (200,201) for status,_ in responses)
    assert responses[0][1]["id"] == responses[1][1]["id"]
    assert ComplexGroup.objects.count() == 1
    assert AuditEvent.objects.filter(action="complex_group.create").count() == 1
