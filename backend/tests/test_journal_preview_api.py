import hashlib
import pytest
from django.test import Client
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.audit.models import AuditEvent
from apps.accounts.models import CommandReceipt
from apps.intake.models import Material
from apps.expertises.models import Expertise,WorkClosure
from apps.issuance.models import MaterialIssue
from apps.documents.models import Document
from apps.personnel.models import Employee
from journal_samples import csv_source,row

pytestmark=pytest.mark.django_db


def preview_setup(employee_factory,grant):
    actor=employee_factory()
    for action in ("imports.preview","imports.results.view"):grant(actor,action)
    client=Client();client.force_login(actor.user)
    return client,actor


def send_preview(client,content=None,key="preview-one",reason="ДЕМО · проверка первого листа",name="DEMO.csv",**extra):
    return client.post("/api/v1/imports/preview/",{"file":SimpleUploadedFile(name,csv_source() if content is None else content),"reason":reason,**extra},**({"HTTP_IDEMPOTENCY_KEY":key} if key is not None else {}))


def business_counts():
    return [model.objects.count() for model in (Material,Expertise,WorkClosure,MaterialIssue,Document,Employee)]


def test_preview_stores_original_rows_and_metadata_but_never_business_facts(employee_factory,grant,settings,tmp_path):
    settings.MEDIA_ROOT=tmp_path;client,_=preview_setup(employee_factory,grant);before=business_counts()
    content=csv_source([row(),row(B="ошибка",P="")]);response=send_preview(client,content)
    assert response.status_code==201
    batch=response.json()["batch"]
    assert batch["apply_available"] is False and batch["row_count"]==2 and batch["summary"]["error_rows"]==1
    assert batch["source_sha256"]==hashlib.sha256(content).hexdigest()
    assert batch["source_name"]=="DEMO.csv" and batch["actor"] is not None
    assert batch["date_system"]=="1900"
    source=client.get(batch["source_url"]);assert source.status_code==200 and b"".join(source.streaming_content)==content
    assert source["Content-Disposition"].startswith("attachment;")
    rows=client.get(f"/api/v1/imports/{batch['id']}/rows/").json()
    assert rows["count"]==2 and rows["results"][0]["raw"]["B"]=="151/4-1-26"
    assert rows["results"][0]["facts"]["completed_on"]=="2026-03-06"
    assert business_counts()==before
    assert client.post(f"/api/v1/imports/{batch['id']}/apply/",{}).status_code==404
    assert "journal_import_preview" in client.get("/api/v1/me/").json()["supported_modules"]


def test_preview_replay_is_one_batch_file_event_and_minimal_receipt(employee_factory,grant,settings,tmp_path):
    settings.MEDIA_ROOT=tmp_path;client,_=preview_setup(employee_factory,grant)
    first=send_preview(client);assert first.status_code==201
    second=send_preview(client);assert second.status_code==201 and second.json()==first.json()
    from apps.imports.models import ImportBatch,ImportRow
    assert ImportBatch.objects.count()==1 and ImportRow.objects.count()==1
    assert len([path for path in tmp_path.rglob("*") if path.is_file()])==1
    assert AuditEvent.objects.filter(action="imports.preview").count()==1
    receipt=CommandReceipt.objects.get(action="imports.preview")
    assert set(receipt.result)=={"id","batch_id"}
    assert send_preview(client,reason="Иное основание").status_code==409
    assert send_preview(client,csv_source([row(B="152/4-1-26")])).status_code==409


@pytest.mark.parametrize("key,reason,extra",[(None,"Причина",{}),("","Причина",{}),("a"*101,"Причина",{}),("k","",{}),("k","Причина",{"apply":True})])
def test_preview_requires_explicit_command_contract(employee_factory,grant,settings,tmp_path,key,reason,extra):
    settings.MEDIA_ROOT=tmp_path;client,_=preview_setup(employee_factory,grant)
    assert send_preview(client,key=key,reason=reason,**extra).status_code==400
    assert not CommandReceipt.objects.filter(action="imports.preview").exists()
    assert not any(path.is_file() for path in tmp_path.rglob("*"))


@pytest.mark.parametrize("permission",["imports.preview","imports.results.view"])
def test_replay_checks_current_import_permissions(employee_factory,grant,settings,tmp_path,permission):
    settings.MEDIA_ROOT=tmp_path;client,actor=preview_setup(employee_factory,grant)
    first=send_preview(client);assert first.status_code==201
    actor.role_assignments.filter(role__permissions__permission_code=permission).update(is_active=False)
    assert send_preview(client).status_code==403
    if permission=="imports.results.view":
        batch=first.json()["batch"]
        for path in ("/api/v1/imports/",f"/api/v1/imports/{batch['id']}/",f"/api/v1/imports/{batch['id']}/rows/",batch["source_url"]):assert client.get(path).status_code==403


def test_other_broad_permissions_and_department_grant_do_not_read_global_source(employee_factory,grant,settings,tmp_path):
    settings.MEDIA_ROOT=tmp_path;client,_=preview_setup(employee_factory,grant);first=send_preview(client);assert first.status_code==201
    other=employee_factory();grant(other,"expertise.view");grant(other,"documents.view");grant(other,"imports.results.view","departments")
    outsider=Client();outsider.force_login(other.user)
    for path in ("/api/v1/imports/",first.json()["batch"]["source_url"]):assert outsider.get(path).status_code==403
    assert send_preview(outsider).status_code==403


def test_rows_are_filtered_before_pagination_and_summary_stays_global(employee_factory,grant,settings,tmp_path):
    settings.MEDIA_ROOT=tmp_path;client,_=preview_setup(employee_factory,grant)
    content=csv_source([row(B=f"{index}/4-1-26",L="ДЕМО · искомый" if index<=30 else "ДЕМО · иной",D="неизвестно" if index==36 else "Завершена",P="" if index==35 else "06.03.2026") for index in range(1,37)])
    response=send_preview(client,content);assert response.status_code==201
    batch=response.json()["batch"];base=f"/api/v1/imports/{batch['id']}/rows/"
    filtered=client.get(base,{"search":"искомый"}).json()
    assert filtered["count"]==30 and len(filtered["results"])==25 and filtered["next"]
    assert len(client.get(base,{"search":"искомый","page":2}).json()["results"])==5
    warning=client.get(base,{"severity":"warning"}).json();assert warning["count"]==1 and warning["results"][0]["source_row"]==38
    unknown=client.get(base,{"state":"unknown"}).json();assert unknown["count"]==1 and unknown["results"][0]["source_row"]==39
    assert client.get(f"/api/v1/imports/{batch['id']}/").json()["summary"]["row_count"]==36
    assert client.get(base,{"severity":"bad"}).status_code==400
    assert client.get(base,{"unrecognised":"x"}).status_code==400


def test_bad_source_rolls_back_without_file_or_command_receipt(employee_factory,grant,settings,tmp_path):
    settings.MEDIA_ROOT=tmp_path;client,_=preview_setup(employee_factory,grant)
    response=send_preview(client,b"bad source")
    assert response.status_code==400 and not AuditEvent.objects.filter(action="imports.preview").exists()
    assert not CommandReceipt.objects.filter(action="imports.preview").exists()
    assert not any(path.is_file() for path in tmp_path.rglob("*"))


def test_audit_failure_rolls_back_rows_and_removes_only_its_new_file(employee_factory,grant,settings,tmp_path,monkeypatch):
    settings.MEDIA_ROOT=tmp_path;client,_=preview_setup(employee_factory,grant)
    first=send_preview(client);assert first.status_code==201
    before=set(path for path in tmp_path.rglob("*") if path.is_file())
    from apps.imports import services
    def fail(*args,**kwargs):raise RuntimeError("DEMO audit unavailable")
    monkeypatch.setattr(services,"audit",fail)
    with pytest.raises(RuntimeError):send_preview(client,key="second-preview")
    from apps.imports.models import ImportBatch
    assert ImportBatch.objects.count()==1 and set(path for path in tmp_path.rglob("*") if path.is_file())==before
    assert CommandReceipt.objects.filter(action="imports.preview").count()==1


def test_partial_file_write_failure_removes_owned_bytes_not_previous_source(employee_factory,grant,settings,tmp_path,monkeypatch):
    settings.MEDIA_ROOT=tmp_path;client,_=preview_setup(employee_factory,grant)
    first=send_preview(client);assert first.status_code==201
    before={path:path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    from django.core.files.base import ContentFile
    def broken_chunks(self,*args,**kwargs):
        yield self.read(8)
        raise OSError("DEMO disk write failed")
    monkeypatch.setattr(ContentFile,"chunks",broken_chunks)
    with pytest.raises(OSError):send_preview(client,key="failed-write")
    from apps.imports.models import ImportBatch,ImportRow
    assert {path:path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}==before
    assert ImportBatch.objects.count()==1 and ImportRow.objects.count()==1
    assert AuditEvent.objects.filter(action="imports.preview").count()==1
    assert CommandReceipt.objects.filter(action="imports.preview").count()==1
