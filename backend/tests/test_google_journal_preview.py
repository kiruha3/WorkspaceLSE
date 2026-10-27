import pytest
from apps.accounts.models import CommandReceipt
from apps.audit.models import AuditEvent
from apps.imports.models import ImportBatch,ImportRow
from apps.imports.source import JournalSourceError
from test_journal_preview_api import preview_setup,business_counts,send_preview
from journal_samples import csv_source,row

pytestmark=pytest.mark.django_db


@pytest.fixture
def google_preview(employee_factory,grant,settings,tmp_path,monkeypatch):
    settings.MEDIA_ROOT=tmp_path;settings.JOURNAL_GOOGLE_ID="DEMO_sheet_123";settings.JOURNAL_GOOGLE_GID="0";settings.JOURNAL_GOOGLE_SHEET_NAME="Лист1"
    client,actor=preview_setup(employee_factory,grant)
    # Only the real remote byte boundary is replaced. DB/parse/file/audit remain real.
    from apps.imports import google_source
    reads=[]
    def read(source):
        reads.append(source)
        return csv_source([row(B="151/4-1-26" if len(reads)==1 else "152/4-1-26")])
    monkeypatch.setattr(google_source,"fetch_google_csv",read)
    return client,actor,reads


def post(client,**changes):
    data={"reason":"ДЕМО · чтение актуального Google-журнала","spreadsheet_id":"DEMO_sheet_123","gid":"0",**changes}
    return client.post("/api/v1/imports/google-preview/",data,content_type="application/json",HTTP_IDEMPOTENCY_KEY="google-preview-one")


def test_google_preview_replay_never_refetches_changed_source(google_preview):
    client,_,reads=google_preview;before=business_counts()
    source=client.get("/api/v1/imports/google-source/");assert source.status_code==200
    assert source.json()["configured"] is True and source.json()["gid"]=="0"
    first=post(client);assert first.status_code==201
    batch=first.json()["batch"]
    assert batch["source_origin"]=="google_csv" and batch["origin_url"]=="https://docs.google.com/spreadsheets/d/DEMO_sheet_123/edit#gid=0"
    assert batch["source_observed_at"] and batch["row_count"]==1
    second=post(client);assert second.status_code==201 and second.json()==first.json()
    assert len(reads)==1 and ImportBatch.objects.count()==1 and ImportRow.objects.count()==1
    assert ImportRow.objects.get().facts["registration_number"]=="151/4-1-26"
    receipt=CommandReceipt.objects.get(action="imports.google_preview")
    assert set(receipt.result)=={"id","batch_id"}
    assert AuditEvent.objects.filter(action="imports.preview").count()==1
    assert business_counts()==before
    assert "journal_google_preview" in client.get("/api/v1/me/").json()["supported_modules"]
    assert post(client,reason="Другое основание").status_code==409


def test_changed_configuration_does_not_reuse_previous_source_receipt(google_preview,settings):
    client,_,reads=google_preview;assert post(client).status_code==201
    settings.JOURNAL_GOOGLE_ID="DEMO_other_123"
    assert post(client).status_code==409 and len(reads)==1


@pytest.mark.parametrize("permission",["imports.preview","imports.results.view"])
def test_google_replay_uses_current_rights_before_network_or_cached_reply(google_preview,permission):
    client,actor,reads=google_preview;assert post(client).status_code==201
    actor.role_assignments.filter(role__permissions__permission_code=permission).update(is_active=False)
    assert post(client).status_code==403 and len(reads)==1


def test_google_failure_rolls_back_every_owned_artifact(google_preview,monkeypatch,settings,tmp_path):
    client,_,_=google_preview
    from apps.imports import google_source
    def fail(source):raise JournalSourceError("ДЕМО · источник недоступен")
    monkeypatch.setattr(google_source,"fetch_google_csv",fail)
    assert post(client).status_code==400
    assert not ImportBatch.objects.exists() and not ImportRow.objects.exists()
    assert not CommandReceipt.objects.filter(action="imports.google_preview").exists()
    assert not AuditEvent.objects.filter(action="imports.preview").exists()
    assert not any(path.is_file() for path in tmp_path.rglob("*"))


def test_unconfigured_google_does_not_hide_uploaded_source_workflow(google_preview,settings):
    client,_,reads=google_preview;settings.JOURNAL_GOOGLE_ID=""
    assert client.get("/api/v1/imports/google-source/").json()=={"configured":False}
    assert post(client).status_code==400 and not reads
    response=send_preview(client);assert response.status_code==201
    assert response.json()["batch"]["source_origin"]=="upload"
    assert response.json()["batch"]["origin_url"]=="" and response.json()["batch"]["source_observed_at"] is None


def test_google_wrong_or_extra_source_fields_are_rejected_without_reads(google_preview):
    client,_,reads=google_preview
    assert post(client,url="https://other.invalid/file").status_code==400
    assert post(client,gid="1").status_code==409
    assert not reads and not ImportBatch.objects.exists()
