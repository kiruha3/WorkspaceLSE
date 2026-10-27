from dataclasses import asdict
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from .catalog import PERMISSIONS
from .models import Role, RolePermission
from .policies import can, require
from .serializers import RoleOutput, RoleCreate, RoleUpdate, RolePermissionsUpdate
from .services import audit, check_version, require_any


class PermissionsView(GenericAPIView):
    def get(self,request):
        require_any(request.user,"access.roles.view","access.roles.manage","access.roles.assign")
        return Response([asdict(item) for item in PERMISSIONS.values()])


class RoleListView(GenericAPIView):
    def get(self,request):
        require_any(request.user,"access.roles.view","access.roles.manage","access.roles.assign")
        queryset = Role.objects.prefetch_related("permissions")
        if not can(request.user,"access.roles.view") and not can(request.user,"access.roles.manage"):
            queryset = queryset.filter(is_active=True)
        if search := request.query_params.get("search","").strip():
            queryset = queryset.filter(Q(name__icontains=search)|Q(description__icontains=search))
        page = self.paginate_queryset(queryset)
        return self.get_paginated_response(RoleOutput(page,many=True).data)

    @transaction.atomic
    def post(self,request):
        require(request.user,"access.roles.manage")
        serializer = RoleCreate(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data.copy()
        permissions = data.pop("permissions")
        role = Role.objects.create(**data)
        RolePermission.objects.bulk_create([RolePermission(role=role,**item) for item in permissions])
        audit(request.user,"role.create",role,RoleOutput(role).data)
        return Response(RoleOutput(role).data,status=201)


class RoleDetailView(GenericAPIView):
    def get(self,request,pk):
        require_any(request.user,"access.roles.view","access.roles.manage")
        return Response(RoleOutput(get_object_or_404(Role,pk=pk)).data)

    @transaction.atomic
    def patch(self,request,pk):
        require(request.user,"access.roles.manage")
        serializer = RoleUpdate(data=request.data)
        serializer.is_valid(raise_exception=True)
        role = get_object_or_404(Role.objects.select_for_update(),pk=pk)
        data = serializer.validated_data.copy()
        check_version(role,data.pop("expected_version"))
        if "name" in data and Role.objects.exclude(pk=role.pk).filter(name=data["name"]).exists():
            raise ValidationError({"name":"Роль с таким названием уже существует."})
        before = RoleOutput(role).data
        for key,value in data.items():
            setattr(role,key,value)
        role.version += 1
        role.save()
        audit(request.user,"role.update",role,{"before":before,"after":RoleOutput(role).data})
        return Response(RoleOutput(role).data)


class RolePermissionsView(GenericAPIView):
    @transaction.atomic
    def put(self,request,pk):
        require(request.user,"access.roles.manage")
        serializer = RolePermissionsUpdate(data=request.data)
        serializer.is_valid(raise_exception=True)
        role = get_object_or_404(Role.objects.select_for_update(),pk=pk)
        check_version(role,serializer.validated_data["expected_version"])
        before = RoleOutput(role).data
        role.permissions.all().delete()
        RolePermission.objects.bulk_create([RolePermission(role=role,**item) for item in serializer.validated_data["permissions"]])
        role.version += 1
        role.save()
        audit(request.user,"role.permissions.replace",role,{"before":before,"after":RoleOutput(role).data})
        return Response(RoleOutput(role).data)
