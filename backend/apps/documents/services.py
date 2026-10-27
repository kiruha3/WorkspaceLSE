import hashlib
from pathlib import PureWindowsPath
from django.conf import settings
from django.db import transaction
from django.db.models import Max
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError
from apps.accounts.policies import active_employee,require
from apps.accounts.services import audit,check_version
from apps.accounts.commands import execute_once
from .models import Document,FileVersion
from .policies import require_document
from .serializers import DocumentOutput,FileVersionOutput


@transaction.atomic
def create_document(*,actor,data,idempotency_key=None):
    employee=active_employee(actor)
    department=data.get("department")
    require(actor,"documents.upload",employee_id=employee.id if employee else None,department_ids=[department.id] if department else [])
    def operation():
        document=Document.objects.create(created_by=employee,**data)
        audit(actor,"document.create",document,DocumentOutput(document).data)
        return {"id":str(document.pk)}

    # Keep unkeyed legacy callers compatible; the shared UI always supplies a
    # stable key before its first metadata POST, not only before file upload.
    payload={"kind":data["kind"],"title":data["title"],"source_kind":data["source_kind"],"department_id":str(department.pk) if department else None}
    result=operation() if idempotency_key is None else execute_once(actor=actor,action="document.create",key=idempotency_key,payload=payload,operation=operation)
    document=Document.objects.get(pk=result["id"])
    if idempotency_key is not None:require_document(actor,"documents.view",document)
    return document


def add_file_version(*,actor,document_id,expected_version,upload,idempotency_key=None):
    saved_file=None
    try:
        with transaction.atomic():
            document=get_object_or_404(Document.objects.select_for_update(),pk=document_id)
            require_document(actor,"documents.upload",document)
            if upload.size>settings.MAX_UPLOAD_SIZE:
                raise ValidationError({"file":"Файл превышает настроенный предел загрузки."})
            header=upload.read(12);upload.seek(0)
            content_type="image/png" if header.startswith(b"\x89PNG\r\n\x1a\n") else "image/jpeg" if header.startswith(b"\xff\xd8\xff") else "application/pdf" if header.startswith(b"%PDF-") else "application/octet-stream"
            digest=hashlib.sha256()
            for chunk in upload.chunks():
                digest.update(chunk)
            upload.seek(0)
            original_name=PureWindowsPath(upload.name).name[:255]

            def operation():
                nonlocal saved_file
                check_version(document,expected_version)
                number=(document.versions.aggregate(n=Max("number"))["n"] or 0)+1
                version=FileVersion(document=document,number=number,original_name=original_name,content_type=content_type,size=upload.size,sha256=digest.hexdigest(),created_by=active_employee(actor))
                version.file.save(version.original_name,upload,save=False)
                saved_file=version.file
                version.save()
                document.version+=1;document.save(update_fields=["version"])
                audit(actor,"document.version.add",version,FileVersionOutput(version).data)
                return {"id":str(version.id)}

            result=operation() if idempotency_key is None else execute_once(actor=actor,action="document.version.add",key=idempotency_key,payload={"document_id":str(document_id),"expected_version":expected_version,"original_name":original_name,"size":upload.size,"sha256":digest.hexdigest()},operation=operation)
            return FileVersion.objects.get(pk=result["id"])
    except Exception:
        if saved_file is not None:
            saved_file.storage.delete(saved_file.name)
        raise
