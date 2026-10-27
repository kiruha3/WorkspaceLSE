import uuid
from django.conf import settings
from django.db import models


def source_path(instance,filename):
    return f"imports/{instance.pk}/{filename}"


class ImportBatch(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    source_name=models.CharField(max_length=255)
    source_kind=models.CharField(max_length=10,choices=[("csv","CSV"),("xlsx","XLSX")])
    source_origin=models.CharField(max_length=20,default="upload",choices=[("upload","Загруженный файл"),("google_csv","Значения Google CSV")])
    origin_url=models.URLField(max_length=500,blank=True,default="")
    source_observed_at=models.DateTimeField(null=True,blank=True)
    date_system=models.CharField(max_length=4,choices=[("1900","Excel 1900"),("1904","Excel 1904")])
    source_sha256=models.CharField(max_length=64)
    sheet_name=models.CharField(max_length=255)
    parser_version=models.CharField(max_length=80)
    uploaded_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name="journal_previews")
    created_at=models.DateTimeField(auto_now_add=True)
    source_file=models.FileField(upload_to=source_path,max_length=500)
    row_count=models.PositiveIntegerField()
    summary=models.JSONField()
    version=models.PositiveIntegerField(default=1)

    class Meta:
        ordering=["-created_at","id"]


class ImportRow(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    batch=models.ForeignKey(ImportBatch,related_name="rows",on_delete=models.PROTECT)
    source_row=models.PositiveIntegerField()
    raw=models.JSONField()
    formulas=models.JSONField()
    extra=models.JSONField()
    facts=models.JSONField()
    diagnostics=models.JSONField()

    class Meta:
        ordering=["source_row","id"]
        constraints=[models.UniqueConstraint(fields=["batch","source_row"],name="unique_preview_source_row")]
