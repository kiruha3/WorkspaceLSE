import hashlib
import os
from dataclasses import dataclass,replace
from pathlib import Path
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models.fields.files import FieldFile
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from apps.accounts.commands import execute_once,CommandConflict
from apps.accounts.services import audit
from .models import ImportBatch,ImportRow
from .policies import require_preview_create
from .source import parse_journal,JournalSourceError,MAX_FILE_BYTES
from .types import ParsedJournal


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


@dataclass
class PersistedPreview:
    receipt:dict[str,str]
    source_file:FieldFile


def persist_preview(*,actor,parsed:ParsedJournal,content:bytes,reason:str,source_origin="upload",origin_url="",source_observed_at=None)->PersistedPreview:
    batch=ImportBatch(source_name=parsed.source_name,source_kind=parsed.source_kind,source_sha256=parsed.source_sha256,sheet_name=parsed.sheet_name,
        date_system=parsed.date_system,parser_version=parsed.parser_version,uploaded_by=actor,row_count=len(parsed.rows),summary=parsed.summary,
        source_origin=source_origin,origin_url=origin_url,source_observed_at=source_observed_at)
    saved_file=None
    try:
        save_source_file(batch.source_file,ContentFile(content));saved_file=batch.source_file
        batch.save()
        ImportRow.objects.bulk_create([ImportRow(batch=batch,source_row=row.source_row,raw=row.raw,formulas=row.formulas,extra=row.extra,facts=row.facts,
            diagnostics=[{"code":item.code,"severity":item.severity,"columns":item.columns,"message":item.message} for item in row.diagnostics]) for row in parsed.rows],batch_size=250)
        event=audit(actor,"imports.preview",batch,{"source_name":batch.source_name,"source_sha256":batch.source_sha256,"row_count":batch.row_count,"parser_version":batch.parser_version,"source_origin":source_origin,"origin_url":origin_url},reason)
        return PersistedPreview({"id":str(event.pk),"batch_id":str(batch.pk)},batch.source_file)
    except Exception:
        if saved_file is not None:saved_file.storage.delete(saved_file.name)
        raise


def _execute_preview(*,actor,action,key,payload,produce):
    saved=None
    try:
        with transaction.atomic():
            require_preview_create(actor)
            def operation():
                nonlocal saved
                saved=produce()
                return saved.receipt
            return execute_once(actor=actor,action=action,key=key,payload=payload,operation=operation)
    except Exception:
        if saved is not None:saved.source_file.storage.delete(saved.source_file.name)
        raise


def create_preview(*,actor,upload,reason,key):
    require_preview_create(actor)
    if upload.size>MAX_FILE_BYTES:raise ValidationError({"file":"Размер источника превышает 20 MiB."})
    upload.seek(0);content=upload.read(MAX_FILE_BYTES+1)
    if len(content)>MAX_FILE_BYTES:raise ValidationError({"file":"Размер источника превышает 20 MiB."})
    def produce():
        try:parsed=parse_journal(content,upload.name)
        except JournalSourceError as error:raise ValidationError({"file":str(error)}) from error
        return persist_preview(actor=actor,parsed=parsed,content=content,reason=reason)
    return _execute_preview(actor=actor,action="imports.preview",key=key,payload={"source_name":upload.name,"source_sha256":hashlib.sha256(content).hexdigest(),"reason":reason},produce=produce)


def create_google_preview(*,actor,reason,spreadsheet_id,gid,key):
    from . import google_source
    require_preview_create(actor)
    try:source=google_source.configured_google_source()
    except JournalSourceError as error:raise ValidationError({"source":str(error)}) from error
    if source is None:raise ValidationError({"source":"Google-источник не настроен."})
    if (spreadsheet_id,gid)!=(source.spreadsheet_id,source.gid):raise CommandConflict("Настроенный источник изменился. Обновите сведения и начните новую проверку.")
    def produce():
        try:
            content=google_source.fetch_google_csv(source)
            observed_at=timezone.now()
            parsed=replace(parse_journal(content,"Google-journal.csv"),sheet_name=source.sheet_name)
        except JournalSourceError as error:raise ValidationError({"source":str(error)}) from error
        require_preview_create(actor)
        return persist_preview(actor=actor,parsed=parsed,content=content,reason=reason,source_origin="google_csv",origin_url=source.url,source_observed_at=observed_at)
    return _execute_preview(actor=actor,action="imports.google_preview",key=key,payload={"spreadsheet_id":spreadsheet_id,"gid":gid,"reason":reason},produce=produce)
