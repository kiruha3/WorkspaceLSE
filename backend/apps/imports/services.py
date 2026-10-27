import hashlib
import os
from pathlib import Path
from django.core.files.base import ContentFile
from django.db import transaction
from rest_framework.exceptions import ValidationError
from apps.accounts.commands import execute_once
from apps.accounts.services import audit
from .models import ImportBatch,ImportRow
from .policies import require_preview_create
from .source import parse_journal,JournalSourceError,MAX_FILE_BYTES


def save_source_file(field,content):
    """Own the local file from its exclusive creation, including failed writes.

    The application uses local FileSystemStorage. An existing path is never
    overwritten or removed. This boundary must be replaced explicitly if a
    remote storage backend is introduced.
    """
    name=field.field.generate_filename(field.instance,field.instance.source_name)
    target=Path(field.storage.path(name))
    target.parent.mkdir(parents=True,exist_ok=True)
    owned=False
    try:
        with target.open("xb") as output:
            owned=True
            for chunk in content.chunks():output.write(chunk)
        mode=field.storage.file_permissions_mode
        if mode is not None:os.chmod(target,mode)
    except Exception:
        if owned:target.unlink(missing_ok=True)
        raise
    field.name=name
    field._committed=True


def create_preview(*,actor,upload,reason,key):
    saved_file=None
    try:
        with transaction.atomic():
            require_preview_create(actor)
            if upload.size>MAX_FILE_BYTES:raise ValidationError({"file":"Размер источника превышает 20 MiB."})
            upload.seek(0);content=upload.read(MAX_FILE_BYTES+1)
            if len(content)>MAX_FILE_BYTES:raise ValidationError({"file":"Размер источника превышает 20 MiB."})
            payload={"source_name":upload.name,"source_sha256":hashlib.sha256(content).hexdigest(),"reason":reason}

            def operation():
                nonlocal saved_file
                try:parsed=parse_journal(content,upload.name)
                except JournalSourceError as error:raise ValidationError({"file":str(error)}) from error
                batch=ImportBatch(source_name=parsed.source_name,source_kind=parsed.source_kind,source_sha256=parsed.source_sha256,sheet_name=parsed.sheet_name,
                    date_system=parsed.date_system,parser_version=parsed.parser_version,uploaded_by=actor,row_count=len(parsed.rows),summary=parsed.summary)
                save_source_file(batch.source_file,ContentFile(content))
                saved_file=batch.source_file
                batch.save()
                ImportRow.objects.bulk_create([ImportRow(batch=batch,source_row=row.source_row,raw=row.raw,formulas=row.formulas,extra=row.extra,facts=row.facts,
                    diagnostics=[{"code":item.code,"severity":item.severity,"columns":item.columns,"message":item.message} for item in row.diagnostics]) for row in parsed.rows],batch_size=250)
                event=audit(actor,"imports.preview",batch,{"source_name":batch.source_name,"source_sha256":batch.source_sha256,"row_count":batch.row_count,"parser_version":batch.parser_version},reason)
                return {"id":str(event.pk),"batch_id":str(batch.pk)}

            return execute_once(actor=actor,action="imports.preview",key=key,payload=payload,operation=operation)
    except Exception:
        if saved_file is not None:saved_file.storage.delete(saved_file.name)
        raise
