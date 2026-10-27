from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework.exceptions import NotFound, ValidationError
from apps.accounts.policies import require
from apps.accounts.services import audit, check_version, require_any_scope
from apps.accounts.serializers import StrictSerializer, VersionedSerializer
from .models import Department, Position, Specialty

CATALOGS = {"departments":Department,"positions":Position,"specialties":Specialty}


class ReferenceCreate(StrictSerializer):
    code = serializers.CharField(max_length=80)
    name = serializers.CharField(max_length=300)


class ReferenceUpdate(VersionedSerializer):
    name = serializers.CharField(max_length=300,required=False)
    is_active = serializers.BooleanField(required=False)


def reference_data(obj):
    return {"id":str(obj.id),"code":obj.code,"name":obj.name,"is_active":obj.is_active,"version":obj.version}


def catalog_model(catalog):
    if catalog not in CATALOGS:
        raise NotFound("Справочник не найден.")
    return CATALOGS[catalog]


class ReferenceListView(GenericAPIView):
    def get(self,request,catalog):
        model = catalog_model(catalog)
        options = ["references.view","references.manage"]
        if catalog == "departments":
            options += ["access.roles.assign","employees.org_assignments.manage","receipts.create","receipts.amend","expertise.view","expertise.register","expertise.assign","expertise.reassign"]
        elif catalog == "positions":
            options += ["employees.org_assignments.manage"]
        elif catalog == "specialties":
            options += ["specialties.training.manage","specialties.qualify","expertise.view","expertise.register","expertise.assign","expertise.reassign"]
        require_any_scope(request.user,*options)
        queryset = model.objects.all()
        if search := request.query_params.get("search","").strip():
            queryset = queryset.filter(Q(name__icontains=search)|Q(code__icontains=search))
        if "is_active" in request.query_params:
            value = request.query_params["is_active"]
            if value not in ("true","false"):
                raise ValidationError({"is_active":"Ожидается true или false."})
            queryset = queryset.filter(is_active=value=="true")
        page = self.paginate_queryset(queryset)
        return self.get_paginated_response([reference_data(obj) for obj in page])

    @transaction.atomic
    def post(self,request,catalog):
        require(request.user,"references.manage")
        model = catalog_model(catalog)
        serializer = ReferenceCreate(data=request.data)
        serializer.is_valid(raise_exception=True)
        if model.objects.filter(code=serializer.validated_data["code"]).exists():
            raise ValidationError({"code":"Этот код уже существует."})
        item = model.objects.create(**serializer.validated_data)
        audit(request.user,"reference.create",item,reference_data(item))
        return Response(reference_data(item),status=201)


class ReferenceDetailView(GenericAPIView):
    @transaction.atomic
    def patch(self,request,catalog,pk):
        require(request.user,"references.manage")
        item = get_object_or_404(catalog_model(catalog).objects.select_for_update(),pk=pk)
        serializer = ReferenceUpdate(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data.copy()
        check_version(item,data.pop("expected_version"))
        before = reference_data(item)
        for key,value in data.items():
            setattr(item,key,value)
        item.version += 1
        item.save()
        audit(request.user,"reference.update",item,{"before":before,"after":reference_data(item)})
        return Response(reference_data(item))
