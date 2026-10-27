from concurrent.futures import ThreadPoolExecutor,TimeoutError
from threading import Barrier,Event
import uuid
import pytest
from django.db import close_old_connections,connection
from django.test import Client
from test_result_completion import completion_setup,ready_result,send
from test_production_receipt_amendment import amend

pytestmark=pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("same_key",[False,True])
def test_concurrent_completion_confirms_only_once(employee_factory,grant,settings,tmp_path,same_key):
    settings.MEDIA_ROOT=tmp_path
    client,actor,work,_,_,_,_=completion_setup(employee_factory,grant);work=ready_result(client,work)
    barrier=Barrier(2);keys=[str(uuid.uuid4()),str(uuid.uuid4())]
    if same_key:keys[1]=keys[0]
    def run(key):
        close_old_connections()
        try:
            session=Client();session.force_login(actor.user);barrier.wait(timeout=10)
            response=send(session,work,"complete",key=key,result_id=work["result"]["id"])
            return response.status_code,response.json()
        finally:connection.close()
    with ThreadPoolExecutor(max_workers=2) as pool:responses=list(pool.map(run,keys))
    assert sorted(r[0] for r in responses)==([200,200] if same_key else [200,409])
    from apps.expertises.models import WorkClosure
    assert WorkClosure.objects.count()==1
    if same_key:assert responses[0][1]["event"]==responses[1][1]["event"]


def test_receipt_correction_cannot_overtake_completion_validation(employee_factory,grant,settings,tmp_path,monkeypatch):
    settings.MEDIA_ROOT=tmp_path
    client,actor,work,_,head,_,_=completion_setup(employee_factory,grant);work=ready_result(client,work)
    grant(head,"receipts.amend")
    from apps.expertises import results
    # If closure validation stops holding the shared receipt lock, amend wins and
    # completion would commit an ending before received_at.
    original=getattr(results,"validate_ending",lambda *args:None)
    validated,release=Event(),Event()
    def hold(*args):
        original(*args);validated.set();assert release.wait(timeout=10)
    monkeypatch.setattr(results,"validate_ending",hold,raising=False)
    def run(employee,operation):
        close_old_connections()
        try:
            session=Client();session.force_login(employee.user);return operation(session).status_code
        finally:connection.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        closing=pool.submit(run,actor,lambda s:send(s,work,"complete",result_id=work["result"]["id"]))
        try:
            assert validated.wait(timeout=5)
            amendment=pool.submit(run,head,lambda s:amend(s,work,"2026-10-11"))
            try:amendment.result(timeout=.3)
            except TimeoutError:pass
        finally:release.set()
        assert closing.result(timeout=10)==200 and amendment.result(timeout=10)==400
