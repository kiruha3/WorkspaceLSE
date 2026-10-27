from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from apps.accounts.policies import effective_scope,require
from apps.accounts.serializers import VersionedSerializer
from .models import Receipt
from .serializers import ReceiptCreate,ReceiptAmend,ReceiptOutput
from .services import create_receipt,accept_receipt,amend_receipt,receipt_context


class ReceiptListView(GenericAPIView):
    def get(self,request):
        scope=effective_scope(request.user,"receipts.view")
        if not scope.rules:raise PermissionDenied("Нет права просматривать поступления.")
        queryset=Receipt.objects.filter(scope.query(employee_field="created_by_id",department_field="department_id")).select_related("material","basis_document")
        if search:=request.query_params.get("search","").strip():queryset=queryset.filter(Q(sender_name__icontains=search)|Q(material__title__icontains=search))
        page=self.paginate_queryset(queryset)
        return self.get_paginated_response(ReceiptOutput(page,many=True,context={"user":request.user}).data)

    def post(self,request):
        serializer=ReceiptCreate(data=request.data);serializer.is_valid(raise_exception=True)
        receipt=create_receipt(actor=request.user,data=serializer.validated_data)
        return Response(ReceiptOutput(receipt,context={"user":request.user}).data,status=201)


class ReceiptDetailView(GenericAPIView):
    def get(self,request,pk):
        receipt=get_object_or_404(Receipt.objects.select_related("material","basis_document"),pk=pk)
        require(request.user,"receipts.view",**receipt_context(receipt))
        return Response(ReceiptOutput(receipt,context={"user":request.user}).data)


class ReceiptAcceptView(GenericAPIView):
    def post(self,request,pk):
        serializer=VersionedSerializer(data=request.data);serializer.is_valid(raise_exception=True)
        receipt=accept_receipt(actor=request.user,receipt_id=pk,expected_version=serializer.validated_data["expected_version"])
        return Response(ReceiptOutput(receipt,context={"user":request.user}).data)


class ReceiptAmendView(GenericAPIView):
    def post(self,request,pk):
        serializer=ReceiptAmend(data=request.data);serializer.is_valid(raise_exception=True)
        return Response(ReceiptOutput(amend_receipt(actor=request.user,receipt_id=pk,data=serializer.validated_data),context={"user":request.user}).data)
