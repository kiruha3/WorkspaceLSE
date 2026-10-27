from rest_framework import serializers
from apps.accounts.serializers import StrictSerializer


class PreviewInput(StrictSerializer):
    file=serializers.FileField()
    reason=serializers.CharField()


class GooglePreviewInput(StrictSerializer):
    reason=serializers.CharField()
    spreadsheet_id=serializers.CharField(max_length=200)
    gid=serializers.CharField(max_length=10)


class BatchFilters(StrictSerializer):
    page=serializers.IntegerField(min_value=1,required=False)


class RowFilters(BatchFilters):
    search=serializers.CharField(allow_blank=True,required=False)
    severity=serializers.ChoiceField(choices=["error","warning","info"],required=False)
    state=serializers.ChoiceField(choices=["completed","without_execution","in_progress","suspended","unknown"],required=False)


def batch_data(batch,user):
    employee=getattr(batch.uploaded_by,"employee",None)
    return {"id":str(batch.pk),"source_name":batch.source_name,"source_kind":batch.source_kind,"source_origin":batch.source_origin,"origin_url":batch.origin_url,"source_observed_at":batch.source_observed_at,"date_system":batch.date_system,"source_sha256":batch.source_sha256,"sheet_name":batch.sheet_name,
        "parser_version":batch.parser_version,"created_at":batch.created_at,"actor":{"id":str(employee.pk),"full_name":employee.full_name} if employee else None,
        "row_count":batch.row_count,"summary":batch.summary,"version":batch.version,"apply_available":False,"source_url":f"/api/v1/imports/{batch.pk}/source/"}


def row_data(row):
    return {"id":str(row.pk),"source_row":row.source_row,"raw":row.raw,"formulas":row.formulas,"extra":row.extra,"facts":row.facts,"diagnostics":row.diagnostics,
        "normalization_complete":not any(item["severity"]=="error" for item in row.diagnostics)}
