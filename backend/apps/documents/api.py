from django.http import FileResponse
from django.shortcuts import get_object_or_404
from rest_framework.generics import GenericAPIView
from rest_framework.parsers import MultiPartParser,FormParser
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError,NotFound
from .models import Document,FileVersion
from .policies import require_document
from .serializers import DocumentCreate,DocumentOutput,FileUpload,FileVersionOutput
from .services import create_document,add_file_version


class DocumentListView(GenericAPIView):
    def get(self,request):
        from .search import document_options
        page=self.paginate_queryset(document_options(request.user,request.query_params))
        return self.get_paginated_response(DocumentOutput(page,many=True).data)

    def post(self,request):
        serializer=DocumentCreate(data=request.data);serializer.is_valid(raise_exception=True)
        return Response(DocumentOutput(create_document(actor=request.user,data=serializer.validated_data,idempotency_key=request.headers.get("Idempotency-Key"))).data,status=201)


class DocumentDetailView(GenericAPIView):
    def get(self,request,pk):
        document=get_object_or_404(Document.objects.prefetch_related("versions"),pk=pk)
        require_document(request.user,"documents.view",document)
        return Response(DocumentOutput(document).data)


class DocumentVersionsView(GenericAPIView):
    parser_classes=[MultiPartParser,FormParser]

    def post(self,request,pk):
        serializer=FileUpload(data=request.data);serializer.is_valid(raise_exception=True)
        version=add_file_version(actor=request.user,document_id=pk,expected_version=serializer.validated_data["expected_version"],upload=serializer.validated_data["file"],relative_path=serializer.validated_data.get('relative_path',''),idempotency_key=request.headers.get("Idempotency-Key"))
        return Response(FileVersionOutput(version).data,status=201)


class FileVersionView(GenericAPIView):
    def get(self,request,pk,mode):
        version=get_object_or_404(FileVersion.objects.select_related("document"),pk=pk)
        require_document(request.user,"documents.view",version.document)
        if mode=="preview" and version.content_type not in ("application/pdf","image/png","image/jpeg"):
            raise ValidationError("Для этого формата доступно скачивание оригинала.")
        try:
            file=version.file.open("rb")
        except FileNotFoundError:
            raise NotFound("Исходный файл недоступен в хранилище.")
        response=FileResponse(file,content_type=version.content_type,as_attachment=mode=="download",filename=version.original_name)
        response["X-Content-Type-Options"]="nosniff"
        response["Content-Security-Policy"]="sandbox; default-src 'none'"
        return response
