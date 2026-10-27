import uuid
from datetime import date
import pytest
from django.test import Client
from apps.accounts.models import CommandReceipt
from apps.audit.models import AuditEvent
from test_production import production_setup
from test_basis_documents import upload,PNG

pytestmark=pytest.mark.django_db


def deadline_setup(employee_factory,grant):
    client,actor,work,clerk,head,department,specialty=production_setup(employee_factory,grant)
    for action in ("expertise.deadline.record","documents.view","documents.upload"):grant(actor,action,"own")
    grant(head,"expertise.deadline.record")
    return client,actor,work,clerk,head,department


def record(client,work,kind="initial",due="2026-11-10",on="2026-10-10",document=None,key=None,reason="Явное основание срока"):
    return client.post(f"/api/v1/expertises/{work['id']}/deadline-events/",{"expected_version":work["version"],"kind":kind,"recorded_on":on,"due_on":due,"reason":reason,"document_id":document},content_type="application/json",HTTP_IDEMPOTENCY_KEY=key or str(uuid.uuid4()))


def document(client,kind="deadline_agreement",source="paper_original"):
    response=client.post("/api/v1/documents/",{"kind":kind,"source_kind":source,"title":"ДЕМО · документ срока"},content_type="application/json")
    assert response.status_code==201,response.content
    return response.json()


def test_initial_request_and_agreement_are_independent_audited_facts(employee_factory,grant):
    client,_,work,_,_,_=deadline_setup(employee_factory,grant)
    initial=record(client,work,due="2026-10-12")
    assert initial.status_code==200
    work=initial.json()["expertise"]
    assert work["version"]==3 and work["production"]["initial_due_on"]=="2026-10-12"
    requested=record(client,work,"request",due="2026-11-20")
    assert requested.status_code==200
    work=requested.json()["expertise"]
    assert work["production"]["current_due_on"]=="2026-10-12"
    assert work["production"]["last_requested_due_on"]=="2026-11-20"
    assert work["production"]["agreed_due_on"] is None
    evidence=document(client)
    agreed=record(client,work,"agreement",due="2026-11-15",on="2026-10-11",document=evidence["id"])
    assert agreed.status_code==200
    work=agreed.json()["expertise"]
    assert work["production"]["current_due_on"]=="2026-11-15"
    assert work["production"]["initial_due_on"]=="2026-10-12"
    assert work["production"]["last_requested_due_on"]=="2026-11-20"
    assert len(work["deadline_events"])==3
    assert work["deadline_events"][-1]["document"]["versions"]==[]
    assert AuditEvent.objects.filter(action="expertise.deadline.record").count()==3
    assert "expertise.deadline.record" in work["allowed_actions"]


def test_agreed_deadline_does_not_invent_unknown_initial_date(employee_factory,grant):
    client,_,work,_,_,_=deadline_setup(employee_factory,grant)
    evidence=document(client)
    response=record(client,work,"agreement",document=evidence["id"])
    assert response.status_code==200
    summary=response.json()["expertise"]["production"]
    assert summary["initial_due_on"] is None and summary["agreed_due_on"]=="2026-11-10"


def test_latest_factual_date_not_entry_order_selects_effective_deadline(employee_factory,grant):
    client,_,work,_,_,_=deadline_setup(employee_factory,grant)
    evidence=document(client)
    work=record(client,work,"agreement",due="2026-11-20",on="2026-10-20",document=evidence["id"]).json()["expertise"]
    response=record(client,work,"agreement",due="2026-11-01",on="2026-10-10",document=evidence["id"])
    assert response.status_code==200
    work=response.json()["expertise"]
    assert work["production"]["current_due_on"]=="2026-11-20"
    assert len(work["deadline_events"])==2
    # Same factual date: explicit later correction wins, old fact remains.
    work=record(client,work,"agreement",due="2026-11-22",on="2026-10-20",document=evidence["id"]).json()["expertise"]
    assert work["production"]["current_due_on"]=="2026-11-22"
    assert len(work["deadline_events"])==3


def test_overdue_days_are_calendar_only_and_unknown_when_closed(employee_factory,grant):
    client,_,work,_,_,_=deadline_setup(employee_factory,grant)
    assert record(client,work,due="2026-10-08").status_code==200
    from apps.expertises.models import Expertise
    from apps.expertises.production import production_summary
    work=Expertise.objects.get(pk=work["id"])
    assert production_summary(work,as_of=date(2026,10,10))["overdue_calendar_days"]==2
    work.state="completed";work.save()
    assert production_summary(work,as_of=date(2026,10,10))["overdue_calendar_days"] is None


@pytest.mark.parametrize("on,due",[("2026-09-30","2026-11-01"),("2099-01-01","2099-02-01"),("2026-10-10","2026-09-30")])
def test_invalid_deadline_dates_leave_no_command_or_event(employee_factory,grant,on,due):
    client,_,work,_,_,_=deadline_setup(employee_factory,grant)
    key=str(uuid.uuid4())
    assert record(client,work,on=on,due=due,key=key).status_code==400
    assert not CommandReceipt.objects.filter(key=key).exists()
    assert record(client,work,key=key).status_code==200


def test_agreement_needs_actual_evidence_and_request_cannot_confirm_it(employee_factory,grant):
    client,_,work,_,_,_=deadline_setup(employee_factory,grant)
    assert record(client,work,"agreement").status_code==400
    request=document(client,kind="deadline_request")
    assert record(client,work,"agreement",document=request["id"]).status_code==400
    pending=document(client,source="uploaded_copy")
    assert record(client,work,"agreement",document=pending["id"]).status_code==400
    assert record(client,work,"request",document=pending["id"]).status_code==400
    assert record(client,work,"request").status_code==200


@pytest.mark.parametrize("kind",["resolution","decision"])
def test_original_basis_document_can_confirm_deadline(employee_factory,grant,kind):
    client,_,work,_,_,_=deadline_setup(employee_factory,grant)
    evidence=document(client,kind=kind)
    assert record(client,work,"agreement",document=evidence["id"]).status_code==200


def test_linked_agreement_file_is_visible_only_through_allowed_work(employee_factory,grant,settings,tmp_path):
    settings.MEDIA_ROOT=tmp_path
    client,actor,work,clerk,_,_=deadline_setup(employee_factory,grant)
    evidence=document(clerk,source="uploaded_copy")
    file=upload(clerk,evidence["id"]).json()
    assert client.get(file["download_url"]).status_code==403
    assert record(client,work,"agreement",document=evidence["id"]).status_code==403
    clerk_employee=clerk.session["_auth_user_id"]
    from apps.personnel.models import Employee
    grant(Employee.objects.get(user_id=clerk_employee),"expertise.deadline.record")
    linked=record(clerk,work,"agreement",document=evidence["id"])
    assert linked.status_code==200
    detail=client.get(f"/api/v1/expertises/{work['id']}/").json()
    assert detail["deadline_events"][0]["document"]["versions"][0]["id"]==file["id"]
    assert b"".join(client.get(file["preview_url"]).streaming_content)==PNG
    assert upload(client,evidence["id"]).status_code==403  # link grants read, not upload
    outsider=Client()
    other=employee_factory();grant(other,"documents.view","own");grant(other,"expertise.view","own");outsider.force_login(other.user)
    assert outsider.get(file["download_url"]).status_code==403
    actor.role_assignments.filter(role__permissions__permission_code="documents.view").update(is_active=False)
    redacted=client.get(f"/api/v1/expertises/{work['id']}/").json()["deadline_events"][0]["document"]
    assert redacted=={"id":evidence["id"],"restricted":True}
    assert client.get(file["preview_url"]).status_code==403


def test_deadline_replay_is_fresh_redacted_and_requires_current_rights(employee_factory,grant):
    client,actor,work,_,_,_=deadline_setup(employee_factory,grant)
    evidence=document(client);key=str(uuid.uuid4())
    first=record(client,work,"agreement",document=evidence["id"],key=key)
    assert first.status_code==200
    current=record(client,first.json()["expertise"],"request",due="2026-12-01")
    assert current.status_code==200
    actor.role_assignments.filter(role__permissions__permission_code="documents.view").update(is_active=False)
    replay=record(client,work,"agreement",document=evidence["id"],key=key)
    assert replay.status_code==200 and replay.json()["event"]==first.json()["event"]
    assert replay.json()["expertise"]["version"]==4
    assert replay.json()["expertise"]["deadline_events"][0]["document"]=={"id":evidence["id"],"restricted":True}
    actor.role_assignments.filter(role__permissions__permission_code="expertise.deadline.record").update(is_active=False)
    assert record(client,work,"agreement",document=evidence["id"],key=key).status_code==403


@pytest.mark.parametrize("kind",["deadline_agreement","deadline_request"])
def test_deadline_document_cannot_replace_minimum_receipt_basis(employee_factory,grant,kind):
    _,_,work,clerk,_,_=deadline_setup(employee_factory,grant)
    evidence=document(clerk,kind=kind)
    receipt=clerk.post("/api/v1/receipts/",{"received_at":"2026-10-28","basis_document_id":evidence["id"]},content_type="application/json").json()
    assert clerk.post(f"/api/v1/receipts/{receipt['id']}/register/",{"expected_version":1},content_type="application/json").status_code==400
    from apps.personnel.models import Employee
    grant(Employee.objects.get(user_id=clerk.session["_auth_user_id"]),"receipts.amend")
    assert clerk.post(f"/api/v1/receipts/{work['receipt']['id']}/amend/",{"expected_version":2,"basis_document_id":evidence["id"],"reason":"Неверное основание"},content_type="application/json").status_code==400


def test_deadline_command_key_version_and_closed_state(employee_factory,grant):
    client,_,work,_,_,_=deadline_setup(employee_factory,grant)
    path=f"/api/v1/expertises/{work['id']}/deadline-events/"
    assert client.post(path,{"expected_version":work["version"],"kind":"initial","recorded_on":"2026-10-10","due_on":"2026-11-01","reason":"Срок"},content_type="application/json").status_code==400
    key=str(uuid.uuid4());first=record(client,work,key=key)
    assert first.status_code==200
    assert record(client,work,key=key,due="2026-11-11").status_code==409
    assert record(client,work).status_code==409
    from apps.expertises.models import Expertise
    Expertise.objects.filter(pk=work["id"]).update(state="completed")
    assert record(client,first.json()["expertise"]).status_code==400


def test_deadline_action_does_not_bypass_work_view(employee_factory,grant):
    client,actor,work,_,_,_=deadline_setup(employee_factory,grant)
    actor.role_assignments.filter(role__permissions__permission_code="expertise.view").update(is_active=False)
    assert record(client,work).status_code==403
