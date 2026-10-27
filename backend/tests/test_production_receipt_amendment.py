from concurrent.futures import ThreadPoolExecutor,TimeoutError
from threading import Event
import pytest
from django.db import close_old_connections,connection
from django.test import Client
from apps.intake.models import Receipt
from apps.personnel.models import Employee
from apps.audit.models import AuditEvent
from test_production import production_setup,transition
from test_deadline_events import record

pytestmark=pytest.mark.django_db


def amend(client,work,on):
    return client.post(f"/api/v1/receipts/{work['receipt']['id']}/amend/",{"expected_version":2,"received_at":on,"reason":"Уточнение по входящему документу"},content_type="application/json")


@pytest.mark.parametrize("fact,new_received",[("pause","2026-10-04"),("recorded","2026-10-11"),("due","2026-10-04")])
def test_receipt_date_cannot_move_past_existing_production_facts(employee_factory,grant,fact,new_received):
    client,actor,work,clerk,_,_,_=production_setup(employee_factory,grant)
    grant(Employee.objects.get(user_id=clerk.session["_auth_user_id"]),"receipts.amend")
    if fact=="pause":
        assert transition(client,work,"suspend","2026-10-03").status_code==200
    else:
        grant(actor,"expertise.deadline.record","own")
        assert record(client,work,on="2026-10-10" if fact=="recorded" else "2026-10-05",due="2026-11-01" if fact=="recorded" else "2026-10-03").status_code==200
    response=amend(clerk,work,new_received)
    assert response.status_code==400
    assert "received_at" in response.json()["field_errors"]
    receipt=Receipt.objects.get(pk=work["receipt"]["id"])
    assert receipt.received_at.isoformat()=="2026-10-01" and receipt.version==2
    assert not AuditEvent.objects.filter(action="receipt.amend").exists()


def test_compatible_receipt_date_correction_keeps_history_and_recomputes_days(employee_factory,grant):
    client,_,work,clerk,_,_,_=production_setup(employee_factory,grant)
    grant(Employee.objects.get(user_id=clerk.session["_auth_user_id"]),"receipts.amend")
    assert transition(client,work,"suspend","2026-10-03").status_code==200
    assert amend(clerk,work,"2026-10-02").status_code==200
    detail=client.get(f"/api/v1/expertises/{work['id']}/").json()
    assert detail["receipt"]["received_at"]=="2026-10-02"
    assert detail["suspensions"][0]["suspended_on"]=="2026-10-03"


@pytest.mark.django_db(transaction=True)
def test_concurrent_receipt_correction_cannot_overtake_validated_deadline(employee_factory,grant,monkeypatch):
    client,actor,work,clerk,_,_,_=production_setup(employee_factory,grant)
    clerk_employee=Employee.objects.get(user_id=clerk.session["_auth_user_id"])
    grant(clerk_employee,"receipts.amend");grant(actor,"expertise.deadline.record","own")
    from apps.expertises import production
    validated,release=Event(),Event()
    original=production.validate_event_date
    def hold_after_validation(*args):
        original(*args);validated.set()
        assert release.wait(timeout=10)
    monkeypatch.setattr(production,"validate_event_date",hold_after_validation)
    def run(employee,operation):
        close_old_connections()
        try:
            session=Client();session.force_login(employee.user)
            return operation(session).status_code
        finally:connection.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        deadline=pool.submit(run,actor,lambda session:record(session,work,on="2026-10-03"))
        try:
            assert validated.wait(timeout=10)
            correction=pool.submit(run,clerk_employee,lambda session:amend(session,work,"2026-10-04"))
            try:correction.result(timeout=.5)
            except TimeoutError:pass  # shared receipt lock correctly blocks until the fact commits
        finally:release.set()
        assert deadline.result(timeout=10)==200
        assert correction.result(timeout=10)==400
    assert Receipt.objects.get(pk=work["receipt"]["id"]).received_at.isoformat()=="2026-10-01"
