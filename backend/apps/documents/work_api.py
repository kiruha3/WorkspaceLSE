from django.shortcuts import get_object_or_404
from django.db import transaction
from rest_framework import serializers
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from apps.accounts.serializers import VersionedSerializer
from apps.expertises.models import Expertise
from .work_commands import link_document,detach_document
from .work_library import library_data,options_data


class WorkDocumentInput(VersionedSerializer):
    document_id=serializers.UUIDField()
    note=serializers.CharField(allow_blank=True,required=False,default='')
    reason=serializers.CharField()


class WorkDocumentDetachInput(VersionedSerializer):
    reason=serializers.CharField()


def loaded_work(pk):
    return get_object_or_404(Expertise.objects.select_related('receipt__basis_document','material','department').prefetch_related('assignments','historical__participants'),pk=pk)


class WorkDocumentsView(GenericAPIView):
    def get(self,request,pk):
        return Response(library_data(loaded_work(pk),request.user,request))

    @transaction.atomic
    def post(self,request,pk):
        form=WorkDocumentInput(data=request.data);form.is_valid(raise_exception=True)
        result=link_document(actor=request.user,work_id=pk,data=form.validated_data,key=request.headers.get('Idempotency-Key'),payload=request.data)
        return Response({'event':{'id':result['id']},'library':library_data(loaded_work(pk),request.user,request)})


class WorkDocumentDetachView(GenericAPIView):
    @transaction.atomic
    def post(self,request,pk,link_id):
        form=WorkDocumentDetachInput(data=request.data);form.is_valid(raise_exception=True)
        result=detach_document(actor=request.user,work_id=pk,link_id=link_id,data=form.validated_data,key=request.headers.get('Idempotency-Key'),payload=request.data)
        return Response({'event':{'id':result['id']},'library':library_data(loaded_work(pk),request.user,request)})


class WorkDocumentOptionsView(GenericAPIView):
    def get(self,request,pk):
        return Response(options_data(loaded_work(pk),request.user,request))
