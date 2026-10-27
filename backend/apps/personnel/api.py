from django.db import transaction
from django.db.models import Q, FilteredRelation
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.http import JsonResponse
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, PermissionDenied
from apps.accounts.policies import effective_scope, require, access_snapshot, can
from apps.accounts.services import audit, check_version, require_any
from .models import Employee, EmployeeOrgAssignment, EmployeeSpecialty, EmployeeRole
from .serializers import EmployeeOutput, EmployeeCreate, EmployeeUpdate, SpecialtyOutput, SpecialtyCreate, SpecialtyQualify, RoleAssignmentOutput, RoleAssignmentCreate, OrgAssignmentCreate, OrgAssignmentEnd, OrgAssignmentOutput, RoleAssignmentRevoke, AccountCreate, AccountUpdate


def current_assignments():
    today = timezone.localdate()
    return EmployeeOrgAssignment.objects.filter(Q(valid_from__isnull=True)|Q(valid_from__lte=today),Q(valid_to__isnull=True)|Q(valid_to__gte=today))


def require_employee(user,action,employee):
    require(user,action,employee_id=employee.pk,department_ids=current_assignments().filter(employee=employee).values_list("department_id",flat=True))


def employee_queryset():
    return Employee.objects.prefetch_related("org_assignments__department","org_assignments__position","specialties__specialty")


class EmployeeListView(GenericAPIView):
    def get(self,request):
        scope = effective_scope(request.user,"employees.view")
        if not scope.rules:
            raise PermissionDenied("Нет права просматривать сотрудников.")
        today = timezone.localdate()
        current = (Q(org_assignments__valid_from__isnull=True)|Q(org_assignments__valid_from__lte=today)) & (Q(org_assignments__valid_to__isnull=True)|Q(org_assignments__valid_to__gte=today))
        queryset = employee_queryset().annotate(current_org=FilteredRelation("org_assignments",condition=current)).filter(scope.query(department_field="current_org__department_id")).distinct()
        if search := request.query_params.get("search","").strip():
            queryset = queryset.filter(full_name__icontains=search)
        page = self.paginate_queryset(queryset)
        return self.get_paginated_response(EmployeeOutput(page,many=True).data)

    @transaction.atomic
    def post(self,request):
        require(request.user,"employees.create")
        serializer = EmployeeCreate(data=request.data)
        serializer.is_valid(raise_exception=True)
        employee = Employee.objects.create(**serializer.validated_data)
        audit(request.user,"employee.create",employee,EmployeeOutput(employee).data)
        return Response(EmployeeOutput(employee).data,status=201)


class EmployeeDetailView(GenericAPIView):
    def get(self,request,pk):
        employee = get_object_or_404(employee_queryset(),pk=pk)
        require_employee(request.user,"employees.view",employee)
        return Response(EmployeeOutput(employee).data)

    @transaction.atomic
    def patch(self,request,pk):
        serializer = EmployeeUpdate(data=request.data)
        serializer.is_valid(raise_exception=True)
        employee = get_object_or_404(Employee.objects.select_for_update(),pk=pk)
        data = serializer.validated_data.copy()
        if "full_name" in data:
            require_employee(request.user,"employees.update",employee)
        if "is_active" in data:
            require_employee(request.user,"employees.deactivate",employee)
        if not (set(data)-{"expected_version"}):
            raise ValidationError("Укажите изменения.")
        check_version(employee,data.pop("expected_version"))
        before = EmployeeOutput(employee).data
        for key,value in data.items():
            setattr(employee,key,value)
        employee.version += 1
        employee.save()
        audit(request.user,"employee.update",employee,{"before":before,"after":EmployeeOutput(employee).data})
        return Response(EmployeeOutput(employee).data)


class EmployeeSpecialtiesView(GenericAPIView):
    def get(self,request,pk):
        employee = get_object_or_404(Employee,pk=pk)
        require_employee(request.user,"employees.view",employee)
        return Response(SpecialtyOutput(employee.specialties.select_related("specialty"),many=True).data)

    @transaction.atomic
    def post(self,request,pk):
        employee = get_object_or_404(Employee.objects.select_for_update(),pk=pk)
        require_employee(request.user,"specialties.training.manage",employee)
        if not employee.is_active:
            raise ValidationError("Сотрудник неактивен.")
        serializer = SpecialtyCreate(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if EmployeeSpecialty.objects.filter(employee=employee,specialty=data["specialty"]).exists():
            raise ValidationError({"specialty_id":"Эта специальность уже связана с сотрудником."})
        item = EmployeeSpecialty.objects.create(employee=employee,**data)
        audit(request.user,"employee.specialty.add",item,SpecialtyOutput(item).data)
        return Response(SpecialtyOutput(item).data,status=201)


class SpecialtyQualifyView(GenericAPIView):
    @transaction.atomic
    def post(self,request,pk):
        item = get_object_or_404(EmployeeSpecialty.objects.select_for_update(),pk=pk)
        require_employee(request.user,"specialties.qualify",item.employee)
        if not item.employee.is_active or not item.specialty.is_active:
            raise ValidationError("Сотрудник или специальность неактивны.")
        serializer = SpecialtyQualify(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data.copy()
        check_version(item,data.pop("expected_version"))
        if item.status == "qualified":
            raise ValidationError("Специальность уже подтверждена; нужна отдельная процедура корректировки.")
        before = SpecialtyOutput(item).data
        for key,value in data.items():
            setattr(item,key,value)
        item.status = "qualified"
        item.version += 1
        item.save()
        audit(request.user,"employee.specialty.qualify",item,{"before":before,"after":SpecialtyOutput(item).data})
        return Response(SpecialtyOutput(item).data)


class EmployeeRolesView(GenericAPIView):
    def get(self,request,pk):
        require_any(request.user,"access.roles.view","access.roles.assign","access.effective.view")
        employee = get_object_or_404(Employee,pk=pk)
        return Response(RoleAssignmentOutput(employee.role_assignments.select_related("role").prefetch_related("departments").order_by("role__name","id"),many=True).data)

    @transaction.atomic
    def post(self,request,pk):
        require(request.user,"access.roles.assign")
        employee = get_object_or_404(Employee.objects.select_for_update(),pk=pk)
        if not employee.is_active:
            raise ValidationError("Нельзя назначить роль неактивному сотруднику.")
        serializer = RoleAssignmentCreate(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data.copy()
        departments = data.pop("departments")
        assignment = EmployeeRole.objects.create(employee=employee,**data)
        assignment.departments.set(departments)
        audit(request.user,"employee.role.assign",assignment,RoleAssignmentOutput(assignment).data,assignment.reason)
        return Response(RoleAssignmentOutput(assignment).data,status=201)


class EmployeeEffectiveView(GenericAPIView):
    def get(self,request,pk):
        require(request.user,"access.effective.view")
        employee = get_object_or_404(Employee,pk=pk)
        return Response(access_snapshot(employee.user) if employee.user_id else {})


class EmployeeOrgAssignmentsView(GenericAPIView):
    @transaction.atomic
    def post(self,request,pk):
        require(request.user,"employees.org_assignments.manage")
        employee = get_object_or_404(Employee.objects.select_for_update(),pk=pk)
        if not employee.is_active:
            raise ValidationError("Сотрудник неактивен.")
        serializer = OrgAssignmentCreate(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if employee.org_assignments.filter(**data).exists():
            raise ValidationError("Такое кадровое назначение уже записано.")
        item = EmployeeOrgAssignment.objects.create(employee=employee,**data)
        audit(request.user,"employee.org_assignment.add",item,OrgAssignmentOutput(item).data,item.reason)
        return Response(OrgAssignmentOutput(item).data,status=201)


class OrgAssignmentDetailView(GenericAPIView):
    @transaction.atomic
    def patch(self,request,pk):
        require(request.user,"employees.org_assignments.manage")
        item = get_object_or_404(EmployeeOrgAssignment.objects.select_for_update(),pk=pk)
        serializer = OrgAssignmentEnd(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        check_version(item,data["expected_version"])
        if item.valid_from and data["valid_to"] < item.valid_from:
            raise ValidationError({"valid_to":"Окончание периода раньше начала."})
        before = OrgAssignmentOutput(item).data
        item.valid_to = data["valid_to"]
        item.version += 1
        item.save()
        audit(request.user,"employee.org_assignment.end",item,{"before":before,"after":OrgAssignmentOutput(item).data},data["reason"])
        return Response(OrgAssignmentOutput(item).data)


class EmployeeRoleDetailView(GenericAPIView):
    @transaction.atomic
    def patch(self,request,pk):
        require(request.user,"access.roles.assign")
        item = get_object_or_404(EmployeeRole.objects.select_for_update(),pk=pk)
        serializer = RoleAssignmentRevoke(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        check_version(item,data["expected_version"])
        before = RoleAssignmentOutput(item).data
        item.is_active = False
        item.version += 1
        item.save()
        audit(request.user,"employee.role.revoke",item,{"before":before,"after":RoleAssignmentOutput(item).data},data["reason"])
        return Response(RoleAssignmentOutput(item).data)


def account_data(user):
    return {"id":str(user.id),"username":user.username,"is_active":user.is_active} if user else None


class EmployeeAccountView(GenericAPIView):
    def get(self,request,pk):
        require_any(request.user,"users.view","users.create","users.deactivate")
        employee = get_object_or_404(Employee.objects.select_related("user"),pk=pk)
        # DRF treats Response(None) as an empty body, not JSON null.
        return JsonResponse(account_data(employee.user),safe=False)

    @transaction.atomic
    def post(self,request,pk):
        from django.contrib.auth import get_user_model
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError as DjangoValidationError

        require(request.user,"users.create")
        employee = get_object_or_404(Employee.objects.select_for_update(),pk=pk)
        if employee.user_id:
            raise ValidationError("У сотрудника уже есть учётная запись.")
        if not employee.is_active:
            raise ValidationError("Сотрудник неактивен.")
        serializer = AccountCreate(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        User = get_user_model()
        if User.objects.filter(username=data["username"]).exists():
            raise ValidationError({"username":"Такой логин уже используется."})
        try:
            validate_password(data["password"],User(username=data["username"]))
        except DjangoValidationError as exc:
            raise ValidationError({"password":exc.messages}) from exc
        user = User.objects.create_user(**data)
        employee.user = user
        employee.version += 1
        employee.save()
        audit(request.user,"employee.account.create",employee,account_data(user))
        return Response(account_data(user),status=201)

    @transaction.atomic
    def patch(self,request,pk):
        from django.contrib.auth import get_user_model

        require(request.user,"users.deactivate")
        employee = get_object_or_404(Employee.objects.select_for_update(),pk=pk)
        if not employee.user_id:
            raise ValidationError("У сотрудника нет учётной записи.")
        serializer = AccountUpdate(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = get_user_model().objects.select_for_update().get(pk=employee.user_id)
        before = account_data(user)
        user.is_active = serializer.validated_data["is_active"]
        user.save(update_fields=["is_active"])
        audit(request.user,"employee.account.status",employee,{"before":before,"after":account_data(user)},serializer.validated_data["reason"])
        return Response(account_data(user))
