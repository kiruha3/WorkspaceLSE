from django.db.models import Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from rest_framework.generics import GenericAPIView
from rest_framework.parsers import MultiPartParser,FormParser
from rest_framework.response import Response
from rest_framework.exceptions import NotFound,ValidationError
from .models import ImportBatch
from .policies import require_preview_read,require_preview_create
from .serializers import PreviewInput,GooglePreviewInput,BatchFilters,RowFilters,batch_data,row_data
from .services import create_preview,create_google_preview


def read_batch(user,pk):
    require_preview_read(user)
    return get_object_or_404(ImportBatch.objects.select_related("uploaded_by__employee"),pk=pk)


class ImportPreviewView(GenericAPIView):
    parser_classes=[MultiPartParser,FormParser]

    def post(self,request):
        require_preview_create(request.user)
        form=PreviewInput(data=request.data);form.is_valid(raise_exception=True)
        result=create_preview(actor=request.user,upload=form.validated_data["file"],reason=form.validated_data["reason"],key=request.headers.get("Idempotency-Key"))
        return Response({"event":{"id":result["id"]},"batch":batch_data(read_batch(request.user,result["batch_id"]),request.user)},status=201)


class ImportListView(GenericAPIView):
    def get(self,request):
        require_preview_read(request.user)
        form=BatchFilters(data=request.query_params);form.is_valid(raise_exception=True)
        page=self.paginate_queryset(ImportBatch.objects.select_related("uploaded_by__employee"))
        return self.get_paginated_response([batch_data(batch,request.user) for batch in page])


class GoogleSourceView(GenericAPIView):
    def get(self,request):
        from .google_source import configured_google_source
        from .source import JournalSourceError
        require_preview_read(request.user)
        try:source=configured_google_source()
        except JournalSourceError as error:raise ValidationError({"source":str(error)}) from error
        return Response({"configured":True,"spreadsheet_id":source.spreadsheet_id,"gid":source.gid,"sheet_name":source.sheet_name,"label":source.label,"url":source.url} if source else {"configured":False})


class GooglePreviewView(GenericAPIView):
    def post(self,request):
        require_preview_create(request.user)
        form=GooglePreviewInput(data=request.data);form.is_valid(raise_exception=True)
        result=create_google_preview(actor=request.user,**form.validated_data,key=request.headers.get("Idempotency-Key"))
        return Response({"event":{"id":result["id"]},"batch":batch_data(read_batch(request.user,result["batch_id"]),request.user)},status=201)


class ImportDetailView(GenericAPIView):
    def get(self,request,pk):return Response(batch_data(read_batch(request.user,pk),request.user))


class ImportRowsView(GenericAPIView):
    def get(self,request,pk):
        batch=read_batch(request.user,pk)
        form=RowFilters(data=request.query_params);form.is_valid(raise_exception=True);data=form.validated_data
        rows=batch.rows.all()
        if data.get("search"):
            search=data["search"]
            rows=rows.filter(Q(raw__B__icontains=search)|Q(facts__registration_number__icontains=search)|Q(facts__executor_raw__icontains=search)|Q(facts__case_description__icontains=search)|Q(facts__authority_name__icontains=search))
        if data.get("severity"):rows=rows.filter(diagnostics__contains=[{"severity":data["severity"]}])
        if data.get("state"):rows=rows.filter(facts__state=None if data["state"]=="unknown" else data["state"])
        return self.get_paginated_response([row_data(row) for row in self.paginate_queryset(rows)])


class ImportSourceView(GenericAPIView):
    def get(self,request,pk):
        batch=read_batch(request.user,pk)
        try:file=batch.source_file.open("rb")
        except FileNotFoundError:raise NotFound("Исходный файл недоступен в хранилище.")
        response=FileResponse(file,as_attachment=True,filename=batch.source_name,content_type="text/csv; charset=utf-8" if batch.source_kind=="csv" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response["X-Content-Type-Options"]="nosniff";response["Content-Security-Policy"]="sandbox; default-src 'none'"
        return response
