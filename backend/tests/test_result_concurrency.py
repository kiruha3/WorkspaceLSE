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


def test_cross_work_shared_documents_are_locked_in_one_global_order(employee_factory,grant):
    from queue import Queue
    import time
    from django.db import transaction,OperationalError
    from apps.documents.models import Document
    from test_result_drafts import result_setup,result_document,reasons,draft
    from test_receipts import create_basis
    from test_registration import register
    _,_,first,clerk,head,department,specialty=result_setup(employee_factory,grant)
    grant(head,"expertise.result.draft")
    basis=create_basis(clerk)
    receipt=clerk.post("/api/v1/receipts/",{"received_at":"2026-10-01","basis_document_id":basis["id"]},content_type="application/json").json()
    assert clerk.post(f"/api/v1/receipts/{receipt['id']}/register/",{"expected_version":1},content_type="application/json").status_code==200
    second=register(clerk,receipt,{"expected_version":2,"registration_number":"152/3-1-26","department_id":str(department.pk),"specialty_id":str(specialty.pk),"appointment_nature":"primary","is_commission":False}).json()
    docs=sorted([result_document(clerk),result_document(clerk)],key=lambda d:d["id"])
    reason=reasons(clerk,first)["unresolved_reasons"][0]
    pids=Queue()
    sessions=[Client(),Client()]
    for session in sessions:session.force_login(head.user)
    def run(session,work,main,allocation):
        close_old_connections()
        try:
            with connection.cursor() as cursor:cursor.execute("SELECT pg_backend_pid()");pids.put(cursor.fetchone()[0])
            try:
                return draft(session,work,document_id=main["id"],unresolved=1,unresolved_allocations=[{"reason_id":reason["id"],"count":1,"comment":"Общий материал","document_id":allocation["id"]}]).status_code
            except OperationalError:return "database_deadlock"
        finally:connection.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        with transaction.atomic():
            Document.objects.select_for_update().get(pk=docs[0]["id"])
            with connection.cursor() as cursor:cursor.execute("SELECT pg_backend_pid()");holder=cursor.fetchone()[0]
            def wait_blocked(pid,expected):
                until=time.monotonic()+5
                while time.monotonic()<until:
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT pg_blocking_pids(%s)",[pid])
                        if expected.intersection(cursor.fetchone()[0]):return
                    time.sleep(.02)
                pytest.fail("Команда не достигла ожидаемой блокировки документа")
            a=pool.submit(run,sessions[0],first,docs[0],docs[1]);first_pid=pids.get(timeout=5);wait_blocked(first_pid,{holder})
            # PostgreSQL may queue the second waiter behind the first waiter's
            # tuple lock rather than directly behind the holder's transaction.
            b=pool.submit(run,sessions[1],second,docs[1],docs[0]);wait_blocked(pids.get(timeout=5),{holder,first_pid})
        assert [a.result(timeout=15),b.result(timeout=15)]==[200,200]
