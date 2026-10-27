from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import uuid
import pytest
from django.db import close_old_connections,connection
from django.test import Client
from test_production import production_setup,transition

pytestmark=pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("same_key",[False,True])
def test_concurrent_pause_commands_create_one_interval(employee_factory,grant,same_key):
    _,actor,work,_,_,_,_=production_setup(employee_factory,grant)
    barrier=Barrier(2);keys=[str(uuid.uuid4()),str(uuid.uuid4())]
    if same_key:keys[1]=keys[0]
    def run(key):
        close_old_connections()
        try:
            client=Client();client.force_login(actor.user)
            barrier.wait(timeout=10)
            response=transition(client,work,"suspend","2026-10-03",key=key)
            return response.status_code,response.json() if response.headers.get("Content-Type","").startswith("application/json") else None
        finally:connection.close()
    with ThreadPoolExecutor(max_workers=2) as pool:responses=list(pool.map(run,keys))
    assert sorted(r[0] for r in responses)==([200,200] if same_key else [200,409])
    from apps.expertises.models import Suspension,Expertise
    from apps.audit.models import AuditEvent
    assert Suspension.objects.count()==1 and Expertise.objects.get(pk=work["id"]).version==3
    assert AuditEvent.objects.filter(action="expertise.suspend").count()==1
    if same_key:assert responses[0][1]["event"]==responses[1][1]["event"]
