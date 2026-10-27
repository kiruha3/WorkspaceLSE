from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from apps.accounts.policies import permission_scopes, require
from apps.accounts.services import require_any_scope, audit
from apps.intake.models import Receipt
from apps.intake.services import receipt_context
from apps.references.models import Department
from .models import Expertise, ComplexGroup
from .policies import expertise_scope_queryset, require_work
from .serializers import RegistrationInput, GroupInput, ExpertiseOutput, WorkFilters, AssignmentInput
from .services import register_expertise, assign_experts, reassign_experts


def loaded(queryset=None):
    return (queryset if queryset is not None else Expertise.objects.all()).select_related("receipt__basis_document","material","department","specialty","complex_group").prefetch_related("assignments__employee","receipt__basis_document__versions","suspensions__actor__employee","suspensions__resumed_by__employee","deadline_events__actor__employee","deadline_events__document__versions","result_revisions__actor__employee","result_revisions__document__versions","result_revisions__sndz_reason","result_revisions__unresolved_allocations__reason","result_revisions__unresolved_allocations__document__versions","result_revisions__closures","closures__actor__employee","closures__document__versions","closures__return_reason")


class ExpertiseRegisterView(GenericAPIView):
    def post(self,request,pk):
        form=RegistrationInput(data=request.data);form.is_valid(raise_exception=True)
        result=register_expertise(actor=request.user,receipt_id=pk,data=form.validated_data,idempotency_key=request.headers.get("Idempotency-Key"),payload=request.data)
        return Response(result,status=201)


class ExpertiseListView(GenericAPIView):
    def get(self,request):
        scopes=permission_scopes(request.user)
        queryset=expertise_scope_queryset(request.user,"expertise.view",scopes)
        form=WorkFilters(data=request.query_params);form.is_valid(raise_exception=True);filters=form.validated_data
        for field in ("department_id","specialty_id"):
            if field in filters:queryset=queryset.filter(**{field:filters[field]})
        if filters.get("employee_id"):queryset=queryset.filter(assignments__employee_id=filters["employee_id"],assignments__ended_at__isnull=True)
        if filters.get("received_from"):queryset=queryset.filter(receipt__received_at__gte=filters["received_from"])
        if filters.get("received_to"):queryset=queryset.filter(receipt__received_at__lte=filters["received_to"])
        if "state" in filters:queryset=queryset.filter(state=filters["state"])
        from .calendar_query import filter_calendar_days
        queryset=filter_calendar_days(queryset,filters)
        if search:=filters.get("search"):queryset=queryset.filter(Q(registration_number__icontains=search)|Q(material__title__icontains=search))
        page=self.paginate_queryset(loaded(queryset.distinct()))
        return self.get_paginated_response(ExpertiseOutput(page,many=True,context={"user":request.user,"scopes":scopes}).data)


class ExpertiseDetailView(GenericAPIView):
    def get(self,request,pk):
        work=get_object_or_404(loaded(),pk=pk);scopes=permission_scopes(request.user)
        require_work(request.user,"expertise.view",work,scopes)
        return Response(ExpertiseOutput(work,context={"user":request.user,"scopes":scopes}).data)


class AssignmentCandidatesView(GenericAPIView):
    def get(self,request,pk):
        from django.utils import timezone
        from apps.personnel.models import Employee, EmployeeSpecialty
        from apps.personnel.services import qualification_eligibility
        work=get_object_or_404(loaded(),pk=pk)
        action="expertise.reassign" if any(a.ended_at is None for a in work.assignments.all()) else "expertise.assign"
        require_work(request.user,action,work)
        qualifications={q.employee_id:q for q in EmployeeSpecialty.objects.filter(specialty_id=work.specialty_id)}
        return Response([{"id":str(e.id),"full_name":e.full_name,**qualification_eligibility(e,work.specialty,timezone.localdate(),qualification=qualifications.get(e.id))} for e in Employee.objects.all()])


class AssignView(GenericAPIView):
    reassign=False

    def post(self,request,pk):
        form=AssignmentInput(data=request.data);form.is_valid(raise_exception=True)
        command=reassign_experts if self.reassign else assign_experts
        work=command(actor=request.user,expertise_id=pk,**form.validated_data)
        work=loaded().get(pk=work.id)
        return Response(ExpertiseOutput(work,context={"user":request.user,"scopes":permission_scopes(request.user)}).data)


class NumberHintView(GenericAPIView):
    def get(self,request):
        class Input(serializers.Serializer):
            department_id=serializers.UUIDField()
            year=serializers.IntegerField(min_value=2000,max_value=2099)
        form=Input(data=request.query_params);form.is_valid(raise_exception=True);data=form.validated_data
        require(request.user,"expertise.register",department_ids=[data["department_id"]])
        get_object_or_404(Department,pk=data["department_id"],is_active=True)
        last=Expertise.objects.filter(department_id=data["department_id"],year=data["year"]).order_by("-sequence","id").first()
        return Response({"last_number":last.registration_number if last else None})


class FilterOptionsView(GenericAPIView):
    def get(self,request):
        from apps.personnel.models import Employee
        works=expertise_scope_queryset(request.user,"expertise.view")
        employees=Employee.objects.filter(expert_assignments__expertise__in=works,expert_assignments__ended_at__isnull=True).distinct()
        return Response({"employees":[{"id":str(e.id),"full_name":e.full_name} for e in employees]})


class ComplexGroupView(GenericAPIView):
    def get(self,request):
        try:receipt_id=serializers.UUIDField().run_validation(request.query_params.get("receipt_id"))
        except serializers.ValidationError:raise ValidationError({"receipt_id":"Укажите поступление."})
        receipt=get_object_or_404(Receipt,pk=receipt_id)
        require(request.user,"receipts.view",**receipt_context(receipt))
        page=self.paginate_queryset(ComplexGroup.objects.filter(material=receipt.material).order_by("created_at","id"))
        return self.get_paginated_response([{"id":str(g.id),"material_id":str(g.material_id),"title":g.title} for g in page])

    @transaction.atomic
    def post(self,request):
        form=GroupInput(data=request.data);form.is_valid(raise_exception=True);data=form.validated_data
        receipt=data["receipt"]
        require(request.user,"receipts.view",**receipt_context(receipt))
        require_any_scope(request.user,"expertise.register")
        if receipt.status!="accepted":raise ValidationError("Сначала примите поступление.")
        group=ComplexGroup.objects.create(material=receipt.material,title=data["title"])
        audit(request.user,"complex_group.create",group,{"receipt_id":str(receipt.id)})
        return Response({"id":str(group.id),"material_id":str(group.material_id),"title":group.title},status=201)
