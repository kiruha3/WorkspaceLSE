from urllib.parse import urlencode
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.generics import GenericAPIView
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from apps.accounts.policies import require
from apps.imports.policies import require_preview_read
from apps.imports.models import ImportBatch
from .calculation import calculate
from .xlsx import export_xlsx


class Parameters(serializers.Serializer):
    batch_id=serializers.UUIDField()
    year=serializers.IntegerField(min_value=1900,max_value=2200)
    month=serializers.IntegerField(min_value=1,max_value=12)
    opening_balances_complete=serializers.BooleanField(default=False)

    def to_internal_value(self,data):
        unknown=set(data)-set(self.fields)
        if unknown:raise ValidationError({key:"Неизвестный параметр." for key in sorted(unknown)})
        if hasattr(data,"getlist") and any(len(data.getlist(k))!=1 for k in data):
            raise ValidationError({"non_field_errors":["Параметры должны быть однозначными, без повторений."]})
        return super().to_internal_value(data)


class Form151View(GenericAPIView):
    download=False

    def get(self,request):
        require_preview_read(request.user)
        require(request.user,"reports.form151.run")
        if self.download:require(request.user,"reports.form151.download")
        form=Parameters(data=request.query_params);form.is_valid(raise_exception=True)
        args=form.validated_data.copy();batch=get_object_or_404(ImportBatch,pk=args.pop("batch_id"))
        try:report=calculate(batch.rows.all(),**args)
        except ValueError as error:raise ValidationError({"report":str(error)}) from error
        report["source"]={"id":str(batch.id),"name":batch.source_name,"sheet_name":batch.sheet_name,"row_count":batch.row_count,
            "sha256":batch.source_sha256,"observed_at":batch.source_observed_at,"created_at":batch.created_at,"origin_url":batch.origin_url,"parser_version":batch.parser_version}
        params={"batch_id":str(batch.id),"year":report["year"],"month":report["month"],"opening_balances_complete":str(report["opening_balances_complete"]).lower()}
        report["download_url"]="/api/v1/reports/form151/xlsx/?"+urlencode(params)
        if self.download:
            response=HttpResponse(export_xlsx(report),content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            response["Content-Disposition"]=f'attachment; filename="15-1-preview-{report["year"]}-{report["month"]:02d}.xlsx"'
        else:response=Response(report)
        response["Cache-Control"]="private, no-store"
        response["X-Content-Type-Options"]="nosniff"
        return response
