from datetime import date
import uuid
import pytest
from django.test import Client
from apps.intake.models import Receipt
from apps.accounts.models import CommandReceipt
from apps.audit.models import AuditEvent
from apps.references.models import Department
from test_expert_assignments import assignment_setup,qualified,assign
from test_registration import register

pytestmark=pytest.mark.django_db


def production_setup(employee_factory,grant):
    clerk,head,work,department,specialty=assignment_setup(employee_factory,grant)
    actor=qualified(employee_factory,specialty,department=department)
    for action in ("expertise.view","expertise.suspend","expertise.resume"):grant(actor,action,"own")
    response=assign(clerk,work,[actor]);assert response.status_code==200
    work=response.json()
    Receipt.objects.filter(pk=work["receipt"]["id"]).update(received_at=date(2026,10,1))
    client=Client();client.force_login(actor.user)
    return client,actor,work,clerk,head,department,specialty


def transition(client,work,kind,on,*,version=None,key=None,reason="Причина изменения производства"):
    field="suspended_on" if kind=="suspend" else "resumed_on"
    return client.post(f"/api/v1/expertises/{work['id']}/{kind}/",{"expected_version":version if version is not None else work["version"],field:on,"reason":reason},content_type="application/json",HTTP_IDEMPOTENCY_KEY=key or str(uuid.uuid4()))


def test_pause_resume_keeps_history_audit_and_event_identity_on_replay(employee_factory,grant):
    client,_,work,_,_,_,_=production_setup(employee_factory,grant)
    key=str(uuid.uuid4())
    paused=transition(client,work,"suspend","2026-10-03",key=key)
    assert paused.status_code==200
    paused=paused.json(); assert paused["expertise"]["state"]=="suspended"
    assert paused["expertise"]["version"]==3
    assert "expertise.resume" in paused["expertise"]["allowed_actions"]
    assert "expertise.suspend" not in paused["expertise"]["allowed_actions"]
    resumed=transition(client,paused["expertise"],"resume","2026-10-06")
    assert resumed.status_code==200 and resumed.json()["expertise"]["state"]=="in_progress"
    assert resumed.json()["event"]["id"]==paused["event"]["id"]
    history=resumed.json()["expertise"]["suspensions"]
    assert len(history)==1 and history[0]["suspended_on"]=="2026-10-03" and history[0]["resumed_on"]=="2026-10-06"
    replay=transition(client,work,"suspend","2026-10-03",key=key)
    assert replay.status_code==200 and replay.json()["event"]["id"]==paused["event"]["id"]
    assert replay.json()["expertise"]["state"]=="in_progress" and replay.json()["expertise"]["version"]==4
    assert AuditEvent.objects.filter(action="expertise.suspend").count()==1
    assert AuditEvent.objects.filter(action="expertise.resume").count()==1


@pytest.mark.parametrize("on",["2026-09-30","2099-01-01"])
def test_invalid_pause_date_rolls_back_command_and_allows_corrected_retry(employee_factory,grant,on):
    client,_,work,_,_,_,_=production_setup(employee_factory,grant)
    key=str(uuid.uuid4())
    response=transition(client,work,"suspend",on,key=key)
    assert response.status_code==400
    assert not CommandReceipt.objects.filter(key=key).exists()
    assert transition(client,work,"suspend","2026-10-03",key=key).status_code==200


def test_pause_chronology_state_and_work_version_are_enforced(employee_factory,grant):
    client,_,work,_,_,_,_=production_setup(employee_factory,grant)
    assert transition(client,work,"resume","2026-10-03").status_code==400
    paused=transition(client,work,"suspend","2026-10-05")
    assert paused.status_code==200
    assert transition(client,work,"resume","2026-10-06").status_code==409
    paused=paused.json()["expertise"]
    assert transition(client,paused,"suspend","2026-10-05").status_code==400
    assert transition(client,paused,"resume","2026-10-04").status_code==400
    resumed=transition(client,paused,"resume","2026-10-06").json()["expertise"]
    assert transition(client,resumed,"suspend","2026-10-05").status_code==400
    again=transition(client,resumed,"suspend","2026-10-06")
    assert again.status_code==200 and len(again.json()["expertise"]["suspensions"])==2


def test_granular_scope_and_revocation_still_apply_to_replays(employee_factory,grant):
    client,actor,work,_,_,_,_=production_setup(employee_factory,grant)
    key=str(uuid.uuid4()); assert transition(client,work,"suspend","2026-10-03",key=key).status_code==200
    actor.role_assignments.filter(role__permissions__permission_code="expertise.suspend").update(is_active=False)
    assert transition(client,work,"suspend","2026-10-03",key=key).status_code==403


def test_mutation_and_view_are_both_required_for_command_response(employee_factory,grant):
    client,actor,work,_,_,_,_=production_setup(employee_factory,grant)
    actor.role_assignments.filter(role__permissions__permission_code="expertise.view").update(is_active=False)
    assert transition(client,work,"suspend","2026-10-03").status_code==403


def test_missing_key_and_reused_key_with_other_payload_do_not_mutate_twice(employee_factory,grant):
    client,_,work,_,_,_,_=production_setup(employee_factory,grant)
    assert client.post(f"/api/v1/expertises/{work['id']}/suspend/",{"expected_version":work["version"],"suspended_on":"2026-10-03","reason":"Приостановка"},content_type="application/json").status_code==400
    key=str(uuid.uuid4())
    assert transition(client,work,"suspend","2026-10-03",key=key).status_code==200
    assert transition(client,work,"suspend","2026-10-04",key=key).status_code==409


def test_institution_view_never_expands_scoped_action(employee_factory,grant):
    _,_,work,_,head,_,_=production_setup(employee_factory,grant)
    other=Department.objects.create(code="4",name="Отдел 4")
    grant(head,"expertise.suspend","departments",departments=[other])
    head_client=Client();head_client.force_login(head.user)
    assert head_client.get(f"/api/v1/expertises/{work['id']}/").status_code==200
    assert transition(head_client,work,"suspend","2026-10-03").status_code==403


def test_current_assignee_not_sibling_or_former_expert_controls_work(employee_factory,grant):
    client,actor,work,clerk,_,department,specialty=production_setup(employee_factory,grant)
    receipt=Receipt.objects.get(pk=work["receipt"]["id"])
    sibling=register(clerk,{"id":str(receipt.id)},{"expected_version":receipt.version,"registration_number":"152/3-1-26","department_id":str(department.id),"specialty_id":str(specialty.id),"appointment_nature":"primary","is_commission":False})
    assert sibling.status_code==201
    assert transition(client,sibling.json(),"suspend","2026-10-03").status_code==403
    next_expert=qualified(employee_factory,specialty)
    assigned=assign(clerk,work,[next_expert],reassign=True)
    assert assigned.status_code==200
    assert transition(client,assigned.json(),"suspend","2026-10-03").status_code==403
    from apps.expertises.models import Expertise
    assert Expertise.objects.get(pk=sibling.json()["id"]).state=="in_progress"


def test_head_with_own_expert_assignment_can_suspend_but_title_alone_cannot(employee_factory,grant):
    client,actor,work,clerk,head,department,specialty=production_setup(employee_factory,grant)
    grant(head,"expertise.suspend","own")
    head_client=Client();head_client.force_login(head.user)
    assert transition(head_client,work,"suspend","2026-10-03").status_code==403
    from apps.personnel.models import EmployeeSpecialty
    EmployeeSpecialty.objects.create(employee=head,specialty=specialty,status="qualified",basis="Подтверждено для проверки совмещения")
    reassigned=assign(clerk,work,[head],reassign=True)
    assert reassigned.status_code==200
    assert transition(head_client,reassigned.json(),"suspend","2026-10-03").status_code==200


@pytest.mark.parametrize("intervals,expected",[
    ([],{"calendar_days":10,"paused_days":0,"active_calendar_days":10}),
    ([(date(2026,10,3),date(2026,10,6)),(date(2026,10,8),None)],{"calendar_days":10,"paused_days":6,"active_calendar_days":4}),
    ([(date(2026,10,3),date(2026,10,3))],{"calendar_days":10,"paused_days":0,"active_calendar_days":10}),
])
def test_calendar_counter_has_explicit_boundary_semantics(intervals,expected):
    from apps.expertises.production import calculate_days
    assert calculate_days(date(2026,10,1),intervals,date(2026,10,10))==expected


def test_closed_work_without_ending_is_unknown_not_accumulated_to_today(employee_factory,grant):
    client,_,work,_,_,_,_=production_setup(employee_factory,grant)
    from apps.expertises.models import Expertise
    Expertise.objects.filter(pk=work["id"]).update(state="completed")
    detail=client.get(f"/api/v1/expertises/{work['id']}/").json()
    assert detail["production"]["calendar_days"] is None
    assert detail["production"]["active_calendar_days"] is None
    assert transition(client,work,"suspend","2026-10-03").status_code==400


def test_state_and_calendar_filters_before_pagination_and_invalid_ranges(employee_factory,grant):
    client,_,work,_,_,_,_=production_setup(employee_factory,grant)
    assert transition(client,work,"suspend","2026-10-03").status_code==200
    response=client.get("/api/v1/expertises/?state=suspended&calendar_days_min=1&calendar_days_max=365000")
    assert response.status_code==200 and response.json()["count"]==1
    assert client.get("/api/v1/expertises/?state=in_progress").json()["count"]==0
    assert client.get("/api/v1/expertises/?calendar_days_min=365000").json()["count"]==0
    for query in ("state=invalid","calendar_days_min=-1","calendar_days_min=5&calendar_days_max=1"):
        assert client.get("/api/v1/expertises/?"+query).status_code==400
