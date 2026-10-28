from datetime import date
import uuid
import pytest
from django.db import IntegrityError,transaction
from django.test import Client
from apps.expertises.models import Expertise,ExpertAssignment,WorkClosure,ResultRevision,Suspension,DeadlineEvent
from apps.documents.models import Document,FileVersion
from apps.personnel.models import EmployeeSpecialty
from apps.accounts.models import CommandReceipt
from historical_samples import historical_setup

pytestmark=pytest.mark.django_db


def test_historical_work_exposes_unknowns_without_fake_workflow_facts(employee_factory,grant,settings,tmp_path):
    client,_,work,history,_,_=historical_setup(employee_factory,grant,settings,tmp_path,specialty_known=False)
    response=client.get(f"/api/v1/expertises/{work.pk}/");assert response.status_code==200
    data=response.json()
    assert data["origin_kind"]=="historical" and data["appointment_nature"] is None and data["is_commission"] is None and data["specialty"] is None
    assert data["receipt"]["status"]=="historical" and data["basis_document"] is None
    assert data["historical"]["completed_on"]=="2026-10-06" and data["historical"]["issued_on"] is None
    assert data["historical"]["operational"] is False and data["historical"]["composition_known"] is False
    assert data["historical"]["questions"]==2 and data["historical"]["source"]["row_id"]==str(history.source_row_id)
    assert data["historical"]["source"]["origin_url"]=="https://docs.google.com/spreadsheets/d/DEMO_sheet_123/edit#gid=0"
    assert data["allowed_actions"]==[]
    assert not any(model.objects.exists() for model in (Document,FileVersion,ExpertAssignment,ResultRevision,WorkClosure,Suspension,DeadlineEvent,EmployeeSpecialty))


@pytest.mark.parametrize("field",["appointment_nature","is_commission","specialty"])
def test_native_work_cannot_use_historical_unknowns(employee_factory,grant,settings,tmp_path,field):
    _,_,work,_,_,specialty=historical_setup(employee_factory,grant,settings,tmp_path)
    values={"origin_kind":"native","appointment_nature":"primary","is_commission":False,"specialty":specialty,field:None}
    with pytest.raises(IntegrityError),transaction.atomic():Expertise.objects.filter(pk=work.pk).update(**values)


@pytest.mark.parametrize("state,ended,expected",[("completed",date(2026,10,6),6),("completed",None,None),("without_execution",None,None)])
def test_historical_calendar_and_sql_filter_share_the_real_known_end(employee_factory,grant,settings,tmp_path,state,ended,expected):
    client,_,work,_,_,_=historical_setup(employee_factory,grant,settings,tmp_path,state=state,ended=ended)
    data=client.get(f"/api/v1/expertises/{work.pk}/").json()
    assert data["production"]["calendar_days"]==expected
    assert data["production"]["paused_days"] is None and data["production"]["active_calendar_days"] is None
    filtered=client.get("/api/v1/expertises/",{"calendar_days_min":1,"calendar_days_max":10000}).json()
    assert filtered["count"]==(1 if expected is not None else 0)
    if expected is not None:
        assert client.get("/api/v1/expertises/",{"calendar_days_min":6,"calendar_days_max":6}).json()["count"]==1


def test_historical_open_work_calendar_does_not_claim_zero_unknown_pause_days(employee_factory,grant,settings,tmp_path):
    _,_,work,history,_,_=historical_setup(employee_factory,grant,settings,tmp_path,state="in_progress",ended=None)
    from apps.expertises.production import production_summary
    result=production_summary(work,as_of=date(2026,10,10))
    assert result["calendar_days"]==10 and result["paused_days"] is None and result["active_calendar_days"] is None
    history.suspension_history_complete=True;history.save()
    # Use a fresh instance: projections must follow current persisted facts.
    result=production_summary(Expertise.objects.get(pk=work.pk),as_of=date(2026,10,10))
    assert result["calendar_days"]==10 and result["paused_days"]==0 and result["active_calendar_days"]==10


def test_explicit_historical_employee_link_grants_own_read_not_live_work(employee_factory,grant,settings,tmp_path):
    _,_,work,history,_,_=historical_setup(employee_factory,grant,settings,tmp_path,state="in_progress",ended=None)
    from apps.expertises.models import HistoricalParticipant
    expert=employee_factory()
    grant(expert,"expertise.view","own");grant(expert,"expertise.suspend","own")
    HistoricalParticipant.objects.create(history=history,employee=expert)
    client=Client();client.force_login(expert.user)
    data=client.get(f"/api/v1/expertises/{work.pk}/");assert data.status_code==200
    assert data.json()["historical"]["source"]["origin_url"] is None and data.json()["allowed_actions"]==[]
    assert client.get("/api/v1/expertises/",{"employee_id":expert.pk}).json()["count"]==1
    assert any(item["id"]==str(expert.pk) for item in client.get("/api/v1/expertises/filter-options/").json()["employees"])
    assert client.post(f"/api/v1/expertises/{work.pk}/suspend/",{"expected_version":1,"suspended_on":"2026-10-05","reason":"ДЕМО"},content_type="application/json",HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4())).status_code==403
    assert not Suspension.objects.exists()


def test_real_current_assignment_supersedes_old_historical_employee_filter(employee_factory,grant,settings,tmp_path):
    _,actor,work,history,_,_=historical_setup(employee_factory,grant,settings,tmp_path,state="in_progress",ended=None)
    from apps.expertises.models import HistoricalParticipant
    from django.utils import timezone
    old=employee_factory();new=employee_factory()
    for person in (old,new):grant(person,"expertise.view","own")
    HistoricalParticipant.objects.create(history=history,employee=old)
    ExpertAssignment.objects.create(expertise=work,employee=new,actor=actor.user,started_at=timezone.now(),reason="ДЕМО · настоящее новое назначение",qualification_snapshot={"status":"qualified"})
    client=Client();client.force_login(old.user)
    assert client.get("/api/v1/expertises/",{"employee_id":old.pk}).json()["count"]==0
    assert client.get(f"/api/v1/expertises/{work.pk}/").status_code==403
    client.force_login(new.user)
    assert client.get("/api/v1/expertises/",{"employee_id":new.pk}).json()["count"]==1


def test_institution_permission_cannot_skip_historical_operational_confirmation(employee_factory,grant,settings,tmp_path):
    client,actor,work,_,_,_=historical_setup(employee_factory,grant,settings,tmp_path,state="in_progress",ended=None,specialty_known=False)
    grant(actor,"expertise.suspend");grant(actor,"expertise.assign")
    before=CommandReceipt.objects.count()
    response=client.post(f"/api/v1/expertises/{work.pk}/suspend/",{"expected_version":1,"suspended_on":"2026-10-05","reason":"ДЕМО"},content_type="application/json",HTTP_IDEMPOTENCY_KEY="history-not-ready")
    assert response.status_code==400 and "историческ" in response.json()["message"].lower()
    assert client.get(f"/api/v1/expertises/{work.pk}/assignment-candidates/").status_code==400
    assert not Suspension.objects.exists() and CommandReceipt.objects.count()==before


def test_known_historical_issue_blocks_shared_material_changes_and_preparation(employee_factory,grant,settings,tmp_path):
    client,actor,work,_,_,_=historical_setup(employee_factory,grant,settings,tmp_path,issued=date(2026,10,7))
    for action in ("issue.view","issue.prepare","receipts.amend"):grant(actor,action)
    from apps.intake.locking import require_not_issued
    from rest_framework.exceptions import ValidationError
    with pytest.raises(ValidationError):require_not_issued(work.material_id)
    response=client.get(f"/api/v1/materials/{work.material_id}/issue-packages/")
    assert response.status_code==200 and response.json()["can_prepare"] is False
    response=client.post(f"/api/v1/materials/{work.material_id}/issue-packages/",{"materials_description":"ДЕМО","items":[],"reason":"ДЕМО"},content_type="application/json",HTTP_IDEMPOTENCY_KEY="do-not-reissue-history")
    assert response.status_code==400


def test_historical_receipt_cannot_be_amended_as_if_it_were_a_native_draft(employee_factory,grant,settings,tmp_path):
    client,actor,work,_,_,_=historical_setup(employee_factory,grant,settings,tmp_path)
    grant(actor,"receipts.amend")
    response=client.post(f"/api/v1/receipts/{work.receipt_id}/amend/",{"expected_version":1,"reason":"ДЕМО","sender_name":"Новое имя"},content_type="application/json")
    assert response.status_code==400
    work.receipt.refresh_from_db();assert work.receipt.sender_name=="" and work.receipt.version==1


def test_report_facts_preserve_typed_source_unknowns_and_ignore_unaccepted_draft(employee_factory,grant,settings,tmp_path):
    from decimal import Decimal
    from apps.expertises.history import historical_facts
    _,actor,work,history,_,_=historical_setup(employee_factory,grant,settings,tmp_path,specialty_known=False)
    history.amount=Decimal("123.45");history.save()
    ResultRevision.objects.create(expertise=work,number=1,kind="sndz",completed_on=date(2026,10,9),questions=99,actor=actor.user,reason="ДЕМО · ещё не принятый черновик")
    facts=historical_facts(work)
    assert facts["expertise_id"]==str(work.pk) and facts["source_row_id"]==str(history.source_row_id)
    assert facts["received_on"]==date(2026,10,1) and facts["completed_on"]==date(2026,10,6)
    assert facts["result_kind"]=="expert_conclusion" and facts["questions"]==2
    assert facts["specialty_code"] is None and facts["appointment_nature"] is None and facts["is_commission"] is None
    assert facts["amount"]==Decimal("123.45") and facts["statistics_confirmed"] is False
    assert facts["issued_on"] is None


@pytest.mark.parametrize("origin",["historical","native"])
def test_accepted_closure_wins_over_historical_facts_and_newer_draft_in_report_and_calendar(employee_factory,grant,settings,tmp_path,origin):
    from apps.expertises.history import historical_facts
    client,actor,work,history,_,_=historical_setup(employee_factory,grant,settings,tmp_path)
    if origin=="native":
        work.origin_kind="native";work.appointment_nature="primary";work.is_commission=False;work.save()
    document=Document.objects.create(kind="sndz",title="ДЕМО · принятый документ",source_kind="paper_original",created_by=actor)
    accepted=ResultRevision.objects.create(expertise=work,number=1,kind="sndz",completed_on=date(2026,10,8),document=document,questions=3,categorical=0,probable=0,unresolved=3,statistics_complete=True,actor=actor.user,reason="ДЕМО")
    WorkClosure.objects.create(expertise=work,number=1,kind="completed",ended_on=date(2026,10,8),result=accepted,document=document,actor=actor.user,reason="ДЕМО")
    ResultRevision.objects.create(expertise=work,number=2,kind="expert_conclusion",questions=100,actor=actor.user,reason="ДЕМО · новый черновик")
    facts=historical_facts(work)
    assert facts["result_kind"]=="sndz" and facts["completed_on"]==date(2026,10,8) and facts["questions"]==3
    assert facts["categorical"]==0 and facts["unresolved"]==3 and facts["statistics_confirmed"] is True
    assert facts["return_decided_on"] is None
    assert facts["source_row_id"]==(str(history.source_row_id) if origin=="historical" else None)
    data=client.get(f"/api/v1/expertises/{work.pk}/").json()
    assert data["production"]["calendar_days"]==8
    assert client.get("/api/v1/expertises/",{"calendar_days_min":8,"calendar_days_max":8}).json()["count"]==1
    assert client.get("/api/v1/expertises/",{"calendar_days_min":6,"calendar_days_max":6}).json()["count"]==0


def test_real_material_issue_is_used_in_report_without_changing_source_issue_fact(employee_factory,grant,settings,tmp_path):
    from apps.expertises.history import historical_facts
    from apps.issuance.models import IssuePackage,PackageRevision,PackageCheck,MaterialIssue
    from apps.references.models import IssueMethod
    _,actor,work,history,_,_=historical_setup(employee_factory,grant,settings,tmp_path)
    package=IssuePackage.objects.create(material=work.material,created_by=actor.user)
    revision=PackageRevision.objects.create(package=package,number=1,actor=actor.user,reason="ДЕМО")
    check=PackageCheck.objects.create(package=package,revision=revision,actor=actor.user,reason="ДЕМО")
    method=IssueMethod.objects.create(code="demo",name="ДЕМО · лично")
    MaterialIssue.objects.create(package=package,package_check=check,issued_on=date(2026,10,10),method=method,recipient_name="ДЕМО",recipient_basis="ДЕМО",actor=actor.user,reason="ДЕМО")
    assert historical_facts(work)["issued_on"]==date(2026,10,10)
    history.refresh_from_db();assert history.issued_on is None
