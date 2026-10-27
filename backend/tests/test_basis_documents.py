import base64
import pytest
from django.test import Client
from django.core.files.uploadedfile import SimpleUploadedFile
from test_receipts import clerk_client,create_basis

pytestmark=pytest.mark.django_db
PNG=base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aZ1sAAAAASUVORK5CYII=")


def upload(client,document_id,version=1,key=None):
    return client.post(f"/api/v1/documents/{document_id}/versions/",{"expected_version":version,"file":SimpleUploadedFile("основание.png",PNG,content_type="image/png")},**({"HTTP_IDEMPOTENCY_KEY":key} if key else {}))


def test_uploaded_basis_survives_reload_and_original_bytes_are_served(employee_factory,grant,settings,tmp_path):
    settings.MEDIA_ROOT=tmp_path
    client,_=clerk_client(employee_factory,grant)
    document=create_basis(client,"uploaded_copy")
    response=upload(client,document["id"])
    assert response.status_code==201
    assert response.json()["number"]==1
    document=client.get(f"/api/v1/documents/{document['id']}/").json()
    assert document["version"]==2 and len(document["versions"])==1
    version=document["versions"][0]
    file_response=client.get(version["preview_url"])
    assert file_response.status_code==200
    assert b"".join(file_response.streaming_content)==PNG
    assert file_response["Content-Type"]=="image/png"
    receipt=client.post("/api/v1/receipts/",{"received_at":"2026-10-28","basis_document_id":document["id"]},content_type="application/json").json()
    assert client.post(f"/api/v1/receipts/{receipt['id']}/register/",{"expected_version":1},content_type="application/json").status_code==200


def test_denied_file_download_does_not_leak_original(employee_factory,grant,settings,tmp_path):
    settings.MEDIA_ROOT=tmp_path
    client,_=clerk_client(employee_factory,grant)
    document=create_basis(client)
    version=upload(client,document["id"]).json()
    outsider=employee_factory();grant(outsider,"documents.view","own")
    other=Client();other.force_login(outsider.user)
    assert other.get(version["download_url"]).status_code==403


def test_file_version_conflict_leaves_previous_bytes_intact(employee_factory,grant,settings,tmp_path):
    settings.MEDIA_ROOT=tmp_path
    client,_=clerk_client(employee_factory,grant)
    document=create_basis(client)
    first=upload(client,document["id"])
    assert first.status_code==201
    assert upload(client,document["id"],version=1).status_code==409
    assert upload(client,document["id"],version=2).json()["number"]==2
    assert len(list(tmp_path.rglob("*.png")))==2


def test_unpreviewable_content_is_download_only(employee_factory,grant,settings,tmp_path):
    settings.MEDIA_ROOT=tmp_path
    client,_=clerk_client(employee_factory,grant)
    document=create_basis(client)
    response=client.post(f"/api/v1/documents/{document['id']}/versions/",{"expected_version":1,"file":SimpleUploadedFile("not-image.png",b"<html>not an image</html>",content_type="image/png")})
    assert response.status_code==201
    version=response.json()
    assert version["preview_url"] is None
    file_response=client.get(version["download_url"])
    assert file_response.status_code==200
    assert file_response["Content-Disposition"].startswith("attachment;")


@pytest.mark.parametrize("key",[None,"failed-upload-command"])
def test_failed_version_command_removes_only_new_file(employee_factory,grant,settings,tmp_path,monkeypatch,key):
    from apps.documents import services
    settings.MEDIA_ROOT=tmp_path
    client,_=clerk_client(employee_factory,grant)
    document=create_basis(client)
    first=upload(client,document["id"]).json()
    def unavailable_audit(*args,**kwargs):raise RuntimeError("Audit persistence failed")
    monkeypatch.setattr(services,"audit",unavailable_audit)
    with pytest.raises(RuntimeError):upload(client,document["id"],version=2,key=key)
    assert len(list(tmp_path.rglob("*.png")))==1
    assert b"".join(client.get(first["download_url"]).streaming_content)==PNG
    assert len(client.get(f"/api/v1/documents/{document['id']}/").json()["versions"])==1
    from apps.accounts.models import CommandReceipt
    assert not CommandReceipt.objects.filter(action="document.version.add").exists()


def test_upload_replay_recovers_committed_file_without_duplicate(employee_factory,grant,settings,tmp_path):
    settings.MEDIA_ROOT=tmp_path
    client,employee=clerk_client(employee_factory,grant)
    document=create_basis(client,"uploaded_copy")
    def send(content=PNG):
        return client.post(f"/api/v1/documents/{document['id']}/versions/",{"expected_version":1,"file":SimpleUploadedFile("basis.png",content)},HTTP_IDEMPOTENCY_KEY="lost-upload-response")
    first=send();assert first.status_code==201
    second=send()
    assert second.status_code==201 and second.json()==first.json()
    assert len(list(tmp_path.rglob("*.png")))==1
    assert send(PNG+b"different").status_code==409
    employee.role_assignments.filter(role__permissions__permission_code="documents.upload").update(is_active=False)
    assert send().status_code==403


def test_metadata_replay_recovers_one_document_and_audit_then_uploads_same_id(employee_factory,grant,settings,tmp_path):
    from apps.documents.models import Document
    from apps.audit.models import AuditEvent
    settings.MEDIA_ROOT=tmp_path
    client,_=clerk_client(employee_factory,grant)
    data={"kind":"decision","title":"ДЕМО · потерян ответ метаданных","source_kind":"uploaded_copy"}
    def send(body=data,key="metadata-lost-response"):
        return client.post("/api/v1/documents/",body,content_type="application/json",HTTP_IDEMPOTENCY_KEY=key)
    first=send();assert first.status_code==201
    repeated=send();assert repeated.status_code==201
    assert repeated.json()["id"]==first.json()["id"]
    assert Document.objects.count()==1
    assert AuditEvent.objects.filter(action="document.create").count()==1
    version=upload(client,first.json()["id"],key="metadata-following-upload").json()
    fresh=send().json()
    assert fresh["version"]==2 and fresh["versions"][0]["id"]==version["id"]
    receipt=client.post("/api/v1/receipts/",{"received_at":"2026-10-28","basis_document_id":fresh["id"]},content_type="application/json")
    assert receipt.status_code==201 and receipt.json()["basis_document"]["id"]==first.json()["id"]
    assert send({**data,"title":"Другой документ"}).status_code==409
    assert Document.objects.count()==1


@pytest.mark.parametrize("permission",["documents.upload","documents.view"])
def test_metadata_replay_checks_current_rights_before_returning_document(employee_factory,grant,permission):
    client,employee=clerk_client(employee_factory,grant)
    data={"kind":"decision","title":"Скрытый документ","source_kind":"paper_original"}
    def send():return client.post("/api/v1/documents/",data,content_type="application/json",HTTP_IDEMPOTENCY_KEY="metadata-revoked")
    assert send().status_code==201
    employee.role_assignments.filter(role__permissions__permission_code=permission).update(is_active=False)
    response=send()
    assert response.status_code==403 and "id" not in response.json()


@pytest.mark.parametrize("key",["","x"*101])
def test_metadata_invalid_present_key_is_rejected_without_document(employee_factory,grant,key):
    from apps.documents.models import Document
    client,_=clerk_client(employee_factory,grant)
    response=client.post("/api/v1/documents/",{"kind":"decision","title":"Не создавать","source_kind":"paper_original"},content_type="application/json",HTTP_IDEMPOTENCY_KEY=key)
    assert response.status_code==400 and Document.objects.count()==0
