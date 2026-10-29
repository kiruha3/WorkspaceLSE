import uuid
import pytest
from django.core.management import call_command
from django.test import Client
from apps.accounts.models import CommandReceipt
from apps.audit.models import AuditEvent
from apps.expertises.models import Expertise
from apps.references.models import Department
from test_production import production_setup
from test_basis_documents import upload,PNG
from test_expert_assignments import assign,qualified
from test_registration import register

pytestmark=pytest.mark.django_db


def result_setup(employee_factory,grant,category="1"):
    client,actor,work,clerk,head,department,specialty=production_setup(employee_factory,grant)
    for action in ("expertise.result.draft","documents.view","documents.upload"):grant(actor,action,"own")
    if category!="1":Expertise.objects.filter(pk=work["id"]).update(category_code=category,registration_number=f"151/3-{category}-26")
    return client,actor,work,clerk,head,department,specialty


def draft(client,work,*,key=None,**values):
    body={"expected_version":work["version"],"reason":"Внесение результата по документам","kind":"expert_conclusion","completed_on":None,"document_id":None,"complexity_level":None,"questions":None,"categorical":None,"probable":None,"unresolved":None,"statistics_complete":False,"sndz_reason_id":None,"sndz_comment":"","unresolved_allocations":[],"allocations_complete":False,"note":"",**values}
    return client.post(f"/api/v1/expertises/{work['id']}/result/",body,content_type="application/json",HTTP_IDEMPOTENCY_KEY=key or str(uuid.uuid4()))


def reasons(client,work):
    path=f"/api/v1/expertises/{work['id']}/result-options/"
    assert client.get(path).status_code==200
    call_command("seed_result_catalogs",verbosity=0)
    return client.get(path).json()


def result_document(client,kind="expert_conclusion",source="uploaded_copy"):
    response=client.post("/api/v1/documents/",{"kind":kind,"source_kind":source,"title":"ДЕМО · итоговый документ"},content_type="application/json")
    assert response.status_code==201
    return response.json()


def test_result_revisions_preserve_nulls_history_and_do_not_complete_work(employee_factory,grant):
    client,_,work,_,_,_,_=result_setup(employee_factory,grant)
    first=draft(client,work,questions=4,categorical=2,probable=1,unresolved=1,statistics_complete=True,complexity_level=5)
    assert first.status_code==200
    work=first.json()["expertise"]
    assert work["state"]=="in_progress" and work["closure"] is None and work["version"]==3
    result=work["result"]
    assert result["questions"]==4 and result["probable"]==1 and result["complexity_level"]==5
    assert result["number"]==1 and work["result_history"][0]["id"]==result["id"]
    second=draft(client,work,questions=4,categorical=2,probable=None,unresolved=1)
    assert second.status_code==200
    work=second.json()["expertise"]
    assert work["result"]["probable"] is None and work["result"]["statistics_complete"] is False
    assert work["result"]["number"]==2 and len(work["result_history"])==2
    assert work["result_history"][0]["probable"]==1
    assert AuditEvent.objects.filter(action="expertise.result.draft").count()==2
    assert work["result_readiness"]["completion_blockers"]
    assert any(g["field"]=="statistics_complete" for g in work["result_readiness"]["report_gaps"])


@pytest.mark.parametrize("values",[
    {"questions":4,"categorical":2,"probable":1,"unresolved":0},
    {"questions":1,"categorical":2},
    {"unresolved":-1},{"questions":1.5},{"statistics_complete":True},
    {"complexity_level":0},{"completed_on":"2099-01-01"},
])
def test_inconsistent_or_invalid_result_counts_are_not_saved(employee_factory,grant,values):
    client,_,work,_,_,_,_=result_setup(employee_factory,grant)
    key=str(uuid.uuid4());response=draft(client,work,key=key,**values)
    assert response.status_code==400
    assert not CommandReceipt.objects.filter(key=key).exists()
    assert not AuditEvent.objects.filter(action="expertise.result.draft").exists()


def test_zero_is_explicit_and_unknown_is_not_inferred(employee_factory,grant):
    client,_,work,_,_,_,_=result_setup(employee_factory,grant)
    first=draft(client,work,questions=2,categorical=1,unresolved=1)
    assert first.status_code==200 and first.json()["expertise"]["result"]["probable"] is None
    work=first.json()["expertise"]
    second=draft(client,work,questions=2,categorical=1,probable=0,unresolved=1,statistics_complete=True)
    assert second.status_code==200
    assert second.json()["expertise"]["result"]["probable"]==0


def test_unresolved_distribution_is_separate_from_whole_sndz(employee_factory,grant):
    client,_,work,_,_,_,_=result_setup(employee_factory,grant)
    options=reasons(client,work)
    reason=next(r for r in options["unresolved_reasons"] if r["code"]=="materials_insufficient")
    allocation={"reason_id":reason["id"],"count":2,"comment":"Недостаточно исходных сведений","document_id":None}
    response=draft(client,work,questions=4,categorical=2,probable=0,unresolved=2,statistics_complete=True,unresolved_allocations=[allocation],allocations_complete=True)
    assert response.status_code==200
    result=response.json()["expertise"]["result"]
    assert result["kind"]=="expert_conclusion" and result["sndz_reason"] is None
    assert result["unresolved_allocations"][0]["reason"]["code"]=="materials_insufficient"


@pytest.mark.parametrize("variant",["excess","duplicate","other_blank","confirmed_without_total"])
def test_unresolved_distribution_rejects_conflicting_facts(employee_factory,grant,variant):
    client,_,work,_,_,_,_=result_setup(employee_factory,grant)
    options=reasons(client,work)
    reason=next(r for r in options["unresolved_reasons"] if r["code"]==("other" if variant=="other_blank" else "materials_insufficient"))
    allocation={"reason_id":reason["id"],"count":3 if variant=="excess" else 1,"comment":"","document_id":None}
    response=draft(client,work,unresolved=None if variant=="confirmed_without_total" else 2,unresolved_allocations=[allocation,allocation] if variant=="duplicate" else [allocation],allocations_complete=variant=="confirmed_without_total")
    assert response.status_code==400


def test_replay_keeps_event_identity_but_returns_fresh_result_and_authority(employee_factory,grant):
    client,actor,work,_,_,_,_=result_setup(employee_factory,grant)
    key=str(uuid.uuid4());first=draft(client,work,key=key,note="Первая редакция")
    assert first.status_code==200
    second=draft(client,first.json()["expertise"],note="Уточнённая редакция")
    assert second.status_code==200
    replay=draft(client,work,key=key,note="Первая редакция")
    assert replay.status_code==200 and replay.json()["event"]==first.json()["event"]
    assert replay.json()["expertise"]["result"]["note"]=="Уточнённая редакция"
    assert replay.json()["expertise"]["version"]==4
    assert draft(client,work,key=key,note="Другое содержание").status_code==409
    actor.role_assignments.filter(role__permissions__permission_code="expertise.result.draft").update(is_active=False)
    assert draft(client,work,key=key,note="Первая редакция").status_code==403


def test_catalog_seed_preserves_edited_deactivated_values_and_new_inactive_choice_is_denied(employee_factory,grant):
    client,actor,work,_,_,_,_=result_setup(employee_factory,grant)
    options=reasons(client,work)
    selected=next(r for r in options["sndz_reasons"] if r["code"]=="outside_expert_knowledge")
    grant(actor,"references.manage")
    count=Expertise.objects.count()
    patched=client.patch(f"/api/v1/references/sndz-reasons/{selected['id']}/",{"expected_version":1,"name":"Уточнённое имя","is_active":False},content_type="application/json")
    assert patched.status_code==200
    call_command("seed_result_catalogs",verbosity=0)
    current=reasons(client,work)["sndz_reasons"]
    value=next(r for r in current if r["id"]==selected["id"])
    assert value["name"]=="Уточнённое имя" and not value["is_active"] and value["version"]==2
    assert len(current)==3 and Expertise.objects.count()==count
    assert draft(client,work,kind="sndz",sndz_reason_id=selected["id"]).status_code==400


def test_inactive_existing_choice_is_retained_without_new_adoption(employee_factory,grant):
    client,_,work,_,_,_,_=result_setup(employee_factory,grant)
    options=reasons(client,work);selected=options["sndz_reasons"][0]
    first=draft(client,work,kind="sndz",sndz_reason_id=selected["id"])
    assert first.status_code==200
    from apps.references.models import SndzReason
    SndzReason.objects.filter(pk=selected["id"]).update(is_active=False)
    assert draft(client,first.json()["expertise"],kind="sndz",sndz_reason_id=selected["id"]).status_code==200


@pytest.mark.parametrize("category,kind,status",[("1","research_act",400),("1","sndz",200),("6","expert_conclusion",400),("6","sndz",400),("6","research_act",200)])
def test_result_kind_matches_work_category_not_question_count(employee_factory,grant,category,kind,status):
    client,_,work,_,_,_,_=result_setup(employee_factory,grant,category)
    assert draft(client,work,kind=kind).status_code==status


def test_pending_copy_draft_is_saved_with_a_nonblocking_document_gap(employee_factory,grant):
    client,_,work,_,_,_,_=result_setup(employee_factory,grant)
    document=result_document(client)
    response=draft(client,work,document_id=document["id"],completed_on="2026-10-10")
    assert response.status_code==200
    result=response.json()["expertise"]
    assert result["result"]["document"]["versions"]==[]
    assert not result["result_readiness"]["completion_blockers"]
    assert any(issue["field"]=="document_id" for issue in result["result_readiness"]["document_gaps"])
    wrong=result_document(client,kind="sndz")
    assert draft(client,result,document_id=wrong["id"]).status_code==400


def test_linked_result_file_read_does_not_grant_upload_and_replay_redacts(employee_factory,grant,settings,tmp_path):
    settings.MEDIA_ROOT=tmp_path
    client,actor,work,clerk,head,_,_=result_setup(employee_factory,grant)
    grant(head,"expertise.result.draft")
    document=result_document(clerk)
    version=upload(clerk,document["id"]).json()
    assert draft(client,work,document_id=document["id"]).status_code==403
    key=str(uuid.uuid4());saved=draft(clerk,work,key=key,document_id=document["id"],completed_on="2026-10-10")
    assert saved.status_code==200
    response=client.get(version["preview_url"])
    assert response.status_code==200 and b"".join(response.streaming_content)==PNG
    assert upload(client,document["id"]).status_code==403
    actor.role_assignments.filter(role__permissions__permission_code="documents.view").update(is_active=False)
    detail=client.get(f"/api/v1/expertises/{work['id']}/").json()
    assert detail["result"]["document"]=={"id":document["id"],"restricted":True}
    assert client.get(version["download_url"]).status_code==403
    head.role_assignments.filter(role__permissions__permission_code="documents.view").update(is_active=False)
    replay=draft(clerk,work,key=key,document_id=document["id"],completed_on="2026-10-10")
    assert replay.status_code==200 and replay.json()["expertise"]["result"]["document"]=={"id":document["id"],"restricted":True}


def test_result_scope_does_not_follow_institution_view_or_sibling_material(employee_factory,grant):
    client,actor,work,clerk,head,department,specialty=result_setup(employee_factory,grant)
    other_department=Department.objects.create(code="4",name="Отдел 4")
    grant(head,"expertise.result.draft","departments",departments=[other_department])
    assert draft(clerk,work).status_code==403
    from apps.intake.models import Receipt
    receipt=Receipt.objects.get(pk=work["receipt"]["id"])
    sibling=register(clerk,{"id":str(receipt.id)},{"expected_version":receipt.version,"registration_number":"152/3-1-26","department_id":str(department.id),"specialty_id":str(specialty.id),"appointment_nature":"primary","is_commission":False})
    assert sibling.status_code==201 and draft(client,sibling.json()).status_code==403
    assert assign(clerk,work,[qualified(employee_factory,specialty)],reassign=True).status_code==200
    assert draft(client,work).status_code==403


def test_result_requires_both_view_and_action_and_a_nonempty_command_key(employee_factory,grant):
    client,actor,work,_,_,_,_=result_setup(employee_factory,grant)
    assert draft(client,work,key=" ").status_code==400
    actor.role_assignments.filter(role__permissions__permission_code="expertise.view").update(is_active=False)
    assert draft(client,work).status_code==403


def test_inactive_historical_reasons_can_be_restored_in_the_same_work(employee_factory,grant):
    from apps.references.models import SndzReason,UnresolvedQuestionReason
    client,_,work,_,_,_,_=result_setup(employee_factory,grant);options=reasons(client,work)
    a,b=options["sndz_reasons"][:2];x,y=options["unresolved_reasons"][:2]
    def save(work,sndz,unresolved):
        return draft(client,work,kind="sndz",sndz_reason_id=sndz["id"],unresolved=1,unresolved_allocations=[{"reason_id":unresolved["id"],"count":1,"comment":"По документу","document_id":None}])
    first=save(work,a,x);assert first.status_code==200
    second=save(first.json()["expertise"],b,y);assert second.status_code==200
    SndzReason.objects.filter(pk=a["id"]).update(is_active=False)
    UnresolvedQuestionReason.objects.filter(pk=x["id"]).update(is_active=False)
    restored=save(second.json()["expertise"],a,x)
    assert restored.status_code==200
    assert restored.json()["expertise"]["result"]["sndz_reason"]["id"]==a["id"]
