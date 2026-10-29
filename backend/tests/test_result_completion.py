from datetime import date
import uuid
import pytest
from apps.expertises.models import Expertise
from apps.intake.models import Receipt
from apps.audit.models import AuditEvent
from test_result_drafts import result_setup,draft,result_document,reasons
from test_basis_documents import upload
from test_production import transition
from test_production_receipt_amendment import amend
from test_deadline_events import record
from test_expert_assignments import assign,qualified
from test_registration import register

pytestmark=pytest.mark.django_db


def completion_setup(employee_factory,grant):
    client,actor,work,clerk,head,department,specialty=result_setup(employee_factory,grant)
    grant(actor,"expertise.complete","own");grant(actor,"expertise.return_without_execution","own")
    return client,actor,work,clerk,head,department,specialty


def send(client,work,command,*,key=None,**fields):
    return client.post(f"/api/v1/expertises/{work['id']}/{command}/",{"expected_version":work["version"],"reason":"Подтверждено по итоговому документу",**fields},content_type="application/json",HTTP_IDEMPOTENCY_KEY=key or str(uuid.uuid4()))


def ready_result(client,work,*,on="2026-10-10",kind="expert_conclusion",**fields):
    doc=result_document(client,kind);assert upload(client,doc["id"]).status_code==201
    response=draft(client,work,kind=kind,completed_on=on,document_id=doc["id"],**fields)
    assert response.status_code==200
    return response.json()["expertise"]


def result_body(work,**fields):
    r=work["result"]
    return {"kind":r["kind"],"completed_on":r["completed_on"],"document_id":r["document"]["id"],"complexity_level":r["complexity_level"],"questions":r["questions"],"categorical":r["categorical"],"probable":r["probable"],"unresolved":r["unresolved"],"statistics_complete":r["statistics_complete"],"sndz_reason_id":r["sndz_reason"]["id"] if r["sndz_reason"] else None,"sndz_comment":r["sndz_comment"],"unresolved_allocations":[],"allocations_complete":False,"note":r["note"],**fields}


def test_completion_without_file_does_not_invent_optional_report_statistics(employee_factory,grant,settings,tmp_path):
    settings.MEDIA_ROOT=tmp_path
    client,_,work,_,_,_,_=completion_setup(employee_factory,grant)
    document=result_document(client)
    work=draft(client,work,completed_on="2026-10-10",document_id=document["id"]).json()["expertise"]
    completed=send(client,work,"complete",result_id=work["result"]["id"])
    assert completed.status_code==200
    done=completed.json()["expertise"]
    assert done["state"]=="completed" and done["version"]==4 and len(done["current_assignments"])==1
    assert done["closure"]["ended_on"]=="2026-10-10" and done["closure"]["result_id"]==work["result"]["id"]
    assert done["result"]["questions"] is None and done["result_readiness"]["report_gaps"]
    assert not done["result_readiness"]["completion_blockers"]
    assert not done["allowed_actions"] and "issued_on" not in done
    assert draft(client,done).status_code==400
    assert send(client,done,"complete",result_id=work["result"]["id"]).status_code==400
    assert AuditEvent.objects.filter(action="expertise.complete").count()==1


@pytest.mark.parametrize("kind",["expert_conclusion","sndz","research_act"])
def test_completed_result_kind_is_not_inferred_from_unresolved_questions(employee_factory,grant,settings,tmp_path,kind):
    settings.MEDIA_ROOT=tmp_path
    client,actor,work,_,_,_,_=completion_setup(employee_factory,grant)
    if kind=="research_act":Expertise.objects.filter(pk=work["id"]).update(category_code="6")
    work=ready_result(client,work,kind=kind,questions=2,categorical=0,probable=0,unresolved=2,statistics_complete=True)
    done=send(client,work,"complete",result_id=work["result"]["id"])
    assert done.status_code==200 and done.json()["expertise"]["result"]["kind"]==kind


def test_only_latest_revision_can_be_confirmed(employee_factory,grant,settings,tmp_path):
    settings.MEDIA_ROOT=tmp_path
    client,_,work,_,_,_,_=completion_setup(employee_factory,grant)
    first=ready_result(client,work)
    second=ready_result(client,first,on="2026-10-11")
    assert send(client,second,"complete",result_id=first["result"]["id"]).status_code==400
    assert send(client,second,"complete",result_id=second["result"]["id"]).status_code==200


def test_closed_correction_appends_history_and_replay_does_not_roll_back(employee_factory,grant,settings,tmp_path):
    settings.MEDIA_ROOT=tmp_path
    client,actor,work,_,_,_,_=completion_setup(employee_factory,grant)
    work=ready_result(client,work);key=str(uuid.uuid4())
    done=send(client,work,"complete",key=key,result_id=work["result"]["id"]).json()["expertise"]
    payload=result_body(done,completed_on="2026-10-11",questions=1,categorical=1,probable=0,unresolved=0,statistics_complete=True,note="Уточнение по оригиналу")
    assert send(client,done,"correct",correction_kind="result",result=payload).status_code==403
    grant(actor,"expertise.closed.correct","own")
    assert send(client,done,"correct",correction_kind="result",result=payload,reason=" ").status_code==400
    corrected=send(client,done,"correct",correction_kind="result",result=payload)
    assert corrected.status_code==200
    current=corrected.json()["expertise"]
    assert current["state"]=="completed" and len(current["closure_history"])==2 and len(current["result_history"])==2
    assert current["closure_history"][0]["ended_on"]=="2026-10-10" and current["closure"]["ended_on"]=="2026-10-11"
    replay=send(client,work,"complete",key=key,result_id=work["result"]["id"])
    assert replay.status_code==200 and replay.json()["expertise"]["closure"]==current["closure"]
    assert replay.json()["event"]["id"]==done["closure"]["id"]
    assert send(client,current,"correct",correction_kind="return",decided_on="2026-10-11",document_id=payload["document_id"],return_reason_id=None,comment="").status_code==400
    actor.role_assignments.filter(role__permissions__permission_code="documents.view").update(is_active=False)
    replay=send(client,work,"complete",key=key,result_id=work["result"]["id"])
    assert replay.status_code==200 and replay.json()["expertise"]["closure"]["document"]["restricted"]
    actor.role_assignments.filter(role__permissions__permission_code="expertise.complete").update(is_active=False)
    assert send(client,work,"complete",key=key,result_id=work["result"]["id"]).status_code==403


def test_return_decision_has_separate_proof_unknown_reason_and_no_actual_issue(employee_factory,grant,settings,tmp_path):
    settings.MEDIA_ROOT=tmp_path
    client,actor,work,_,_,_,_=completion_setup(employee_factory,grant)
    options=reasons(client,work);doc=result_document(client,"return_decision")
    fields={"decided_on":"2026-10-10","document_id":doc["id"],"return_reason_id":None,"comment":"Материалы ещё не забрали"}
    done=send(client,work,"return-without-execution",**fields)
    assert done.status_code==200
    done=done.json()["expertise"]
    assert done["state"]=="without_execution" and done["result"] is None and done["closure"]["return_reason"] is None
    assert not done["result_readiness"]["completion_blockers"]
    assert any(g["field"]=="return_reason_id" for g in done["result_readiness"]["report_gaps"])
    grant(actor,"expertise.closed.correct","own")
    fields["return_reason_id"]=next(r["id"] for r in options["return_reasons"] if r["code"]=="appointing_party_request")
    corrected=send(client,done,"correct",correction_kind="return",**fields)
    assert corrected.status_code==200
    current=corrected.json()["expertise"]
    assert current["closure"]["return_reason"]["code"]=="appointing_party_request" and len(current["closure_history"])==2
    assert "issued_on" not in current and current["state"]=="without_execution"


@pytest.mark.parametrize("fact",["pause","resume","deadline"])
def test_ending_cannot_precede_recorded_production_facts(employee_factory,grant,settings,tmp_path,fact):
    settings.MEDIA_ROOT=tmp_path
    client,actor,work,_,_,_,_=completion_setup(employee_factory,grant)
    work=ready_result(client,work,on="2026-10-10")
    if fact in ("pause","resume"):
        work=transition(client,work,"suspend","2026-10-11" if fact=="pause" else "2026-10-09").json()["expertise"]
        if fact=="resume":work=transition(client,work,"resume","2026-10-11").json()["expertise"]
    else:
        grant(actor,"expertise.deadline.record","own")
        work=record(client,work,on="2026-10-11",due="2026-12-01").json()["expertise"]
    assert any(i["field"]=="completed_on" for i in work["result_readiness"]["completion_blockers"])
    assert send(client,work,"complete",result_id=work["result"]["id"]).status_code==400


def test_future_due_does_not_block_completion_and_open_pause_is_clipped_not_resumed(employee_factory,grant,settings,tmp_path):
    settings.MEDIA_ROOT=tmp_path
    client,actor,work,_,_,_,_=completion_setup(employee_factory,grant)
    grant(actor,"expertise.deadline.record","own")
    work=record(client,work,on="2026-10-01",due="2026-12-01").json()["expertise"]
    work=transition(client,work,"suspend","2026-10-08").json()["expertise"]
    work=ready_result(client,work)
    response=send(client,work,"complete",result_id=work["result"]["id"])
    assert response.status_code==200
    done=response.json()["expertise"]
    from apps.expertises.production import production_summary
    counters=production_summary(Expertise.objects.get(pk=work["id"]),as_of=date(2026,10,20))
    assert counters["as_of"]=="2026-10-20" and counters["counted_through"]=="2026-10-10"
    assert counters["calendar_days"]==10 and counters["paused_days"]==3 and counters["active_calendar_days"]==7
    assert done["suspensions"][0]["resumed_on"] is None and done["production"]["current_due_on"]=="2026-12-01"


def test_closed_calendar_filters_use_confirmed_end_before_pagination(employee_factory,grant,settings,tmp_path):
    settings.MEDIA_ROOT=tmp_path
    client,_,work,clerk,_,department,specialty=completion_setup(employee_factory,grant)
    work=ready_result(client,work);done=send(client,work,"complete",result_id=work["result"]["id"]).json()["expertise"]
    receipt=Receipt.objects.get(pk=work["receipt"]["id"])
    legacy=register(clerk,{"id":str(receipt.id)},{"expected_version":receipt.version,"registration_number":"152/3-1-26","department_id":str(department.id),"specialty_id":str(specialty.id),"appointment_nature":"primary","is_commission":False}).json()
    Expertise.objects.filter(pk=legacy["id"]).update(state="completed")
    assert clerk.get("/api/v1/expertises/?state=completed").json()["count"]==2
    matched=clerk.get("/api/v1/expertises/?state=completed&calendar_days_min=10&calendar_days_max=10").json()
    assert matched["count"]==1 and matched["results"][0]["id"]==done["id"]
    assert clerk.get("/api/v1/expertises/?state=completed&calendar_days_min=11").json()["count"]==0
    assert clerk.get("/api/v1/expertises/?state=completed&calendar_days_max=9").json()["count"]==0


def test_receipt_amendment_guards_current_confirmed_end_not_old_revisions(employee_factory,grant,settings,tmp_path):
    settings.MEDIA_ROOT=tmp_path
    client,actor,work,clerk,head,_,_=completion_setup(employee_factory,grant);grant(head,"receipts.amend")
    work=ready_result(client,work);done=send(client,work,"complete",result_id=work["result"]["id"]).json()["expertise"]
    assert amend(clerk,work,"2026-10-11").status_code==400
    grant(actor,"expertise.closed.correct","own")
    done=send(client,done,"correct",correction_kind="result",result=result_body(done,completed_on="2026-10-12")).json()["expertise"]
    assert amend(clerk,work,"2026-10-11").status_code==200
    assert client.get(f"/api/v1/expertises/{work['id']}/").json()["production"]["calendar_days"]==2


def test_unconfirmed_draft_is_not_receipt_proof_and_readiness_revalidates(employee_factory,grant,settings,tmp_path):
    settings.MEDIA_ROOT=tmp_path
    client,_,work,clerk,head,_,_=completion_setup(employee_factory,grant);grant(head,"receipts.amend")
    work=ready_result(client,work)
    assert amend(clerk,work,"2026-10-11").status_code==200
    detail=client.get(f"/api/v1/expertises/{work['id']}/").json()
    assert any(i["field"]=="completed_on" for i in detail["result_readiness"]["completion_blockers"])
    assert send(client,work,"complete",result_id=work["result"]["id"]).status_code==400


def test_completion_scope_does_not_follow_title_or_previous_assignment(employee_factory,grant,settings,tmp_path):
    settings.MEDIA_ROOT=tmp_path
    client,_,work,clerk,head,_,specialty=completion_setup(employee_factory,grant)
    work=ready_result(client,work);grant(head,"expertise.complete","own")
    assert send(clerk,work,"complete",result_id=work["result"]["id"]).status_code==403
    work=assign(clerk,work,[qualified(employee_factory,specialty)],reassign=True).json()
    assert send(client,work,"complete",result_id=work["result"]["id"]).status_code==403


def test_later_file_upload_does_not_replace_file_accepted_by_old_closure(employee_factory,grant,settings,tmp_path):
    from django.core.files.uploadedfile import SimpleUploadedFile
    from test_basis_documents import PNG
    settings.MEDIA_ROOT=tmp_path
    client,actor,work,_,_,_,_=completion_setup(employee_factory,grant)
    work=ready_result(client,work)
    first=work["result"]["document"]["versions"][0]
    done=send(client,work,"complete",result_id=work["result"]["id"]);assert done.status_code==200
    done=done.json()["expertise"];doc=done["result"]["document"]
    newer=client.post(f"/api/v1/documents/{doc['id']}/versions/",{"expected_version":doc["version"],"file":SimpleUploadedFile("other.png",PNG+b"new-version")})
    assert newer.status_code==201
    current=client.get(f"/api/v1/expertises/{work['id']}/").json()
    assert current["closure"]["document"].get("accepted_version_id")==first["id"]
    assert current["result"]["document"].get("accepted_version_id")==first["id"]
    assert current["closure_history"][0]["document"].get("accepted_version_id")==first["id"]
    assert len(current["closure"]["document"]["versions"])==2
    assert current["version"]==done["version"] and "expertise.closed.correct" not in current["allowed_actions"]
    grant(actor,"expertise.closed.correct","own")
    corrected=send(client,current,"correct",correction_kind="result",result=result_body(current,note="Новая версия явно перепроверена"))
    assert corrected.status_code==200
    history=corrected.json()["expertise"]["closure_history"]
    assert history[0]["document"]["accepted_version_id"]==first["id"]
    assert history[1]["document"]["accepted_version_id"]==newer.json()["id"]


def test_inactive_historical_return_reason_can_be_restored(employee_factory,grant,settings,tmp_path):
    from apps.references.models import ReturnReason
    settings.MEDIA_ROOT=tmp_path
    client,actor,work,_,_,_,_=completion_setup(employee_factory,grant);options=reasons(client,work)
    a,b=options["return_reasons"][:2];doc=result_document(client,"return_decision");assert upload(client,doc["id"]).status_code==201
    fields={"decided_on":"2026-10-10","document_id":doc["id"],"return_reason_id":a["id"],"comment":"По документу"}
    done=send(client,work,"return-without-execution",**fields);assert done.status_code==200
    grant(actor,"expertise.closed.correct","own")
    fields["return_reason_id"]=b["id"]
    changed=send(client,done.json()["expertise"],"correct",correction_kind="return",**fields);assert changed.status_code==200
    ReturnReason.objects.filter(pk=a["id"]).update(is_active=False)
    fields["return_reason_id"]=a["id"]
    assert send(client,changed.json()["expertise"],"correct",correction_kind="return",**fields).status_code==200


@pytest.mark.parametrize("file_existed",[True,False])
def test_existing_closure_migration_does_not_accept_a_later_file(employee_factory,grant,settings,tmp_path,file_existed):
    import importlib
    from datetime import timedelta
    from django.apps import apps
    from django.utils import timezone
    from apps.expertises.models import WorkClosure
    settings.MEDIA_ROOT=tmp_path
    client,_,work,_,_,_,_=completion_setup(employee_factory,grant);work=ready_result(client,work)
    first=work["result"]["document"]["versions"][0]
    response=send(client,work,"complete",result_id=work["result"]["id"]);assert response.status_code==200
    closure=WorkClosure.objects.get(pk=response.json()["event"]["id"])
    values={"accepted_version_id":None}
    if not file_existed:values["created_at"]=timezone.now()-timedelta(days=1)
    WorkClosure.objects.filter(pk=closure.pk).update(**values)
    doc=work["result"]["document"]
    assert upload(client,doc["id"],version=doc["version"]).status_code==201
    migration=importlib.import_module("apps.expertises.migrations.0006_workclosure_accepted_version")
    migration.pin_existing_files(apps,None)
    closure.refresh_from_db()
    assert str(closure.accepted_version_id) == (first["id"] if file_existed else "None")
