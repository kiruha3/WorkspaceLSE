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
from .serializers import RegistrationInput, GroupInput, ExpertiseOutput, AssignmentInput
from .services import register_expertise, assign_experts, reassign_experts, create_complex_group
from .query import filter_registry


def loaded(queryset=None):
    return (queryset if queryset is not None else Expertise.objects.all()).prefetch_related('reopenings__actor__employee').select_related(
        "receipt__basis_document","material","department","specialty","complex_group","historical__source_row__batch","historical__sndz_reason","historical__return_reason","case_details__authority_type","case_details__decree_document","classification","timing__primary_reason","timing__notification_document","timing__request_document","timing__breach_document"
    ).prefetch_related("timing__reasons__reason","timing__reasons__document__versions","timing__notification_document__versions","timing__request_document__versions","timing__breach_document__versions","timing__revisions__actor__employee","classification__previous_conclusions__document__versions","classification__revisions__actor__employee","case_details__decree_document__versions","case_details__revisions__actor__employee","historical__participants__employee","historical__unresolved_allocations__reason","historical__unresolved_allocations__document__versions","historical__corrections__actor__employee",
        "assignments__employee","receipt__basis_document__versions","suspensions__actor__employee","suspensions__resumed_by__employee","deadline_events__actor__employee","deadline_events__document__versions","result_revisions__actor__employee","result_revisions__document__versions","result_revisions__sndz_reason","result_revisions__unresolved_allocations__reason","result_revisions__unresolved_allocations__document__versions","result_revisions__closures","closures__actor__employee","closures__document__versions","closures__return_reason")


class ExpertiseRegisterView(GenericAPIView):
    def post(self,request,pk):
        form=RegistrationInput(data=request.data);form.is_valid(raise_exception=True)
        result=register_expertise(actor=request.user,receipt_id=pk,data=form.validated_data,idempotency_key=request.headers.get("Idempotency-Key"),payload=request.data)
        return Response(result,status=201)


class ExpertiseListView(GenericAPIView):
    def get(self,request):
        scopes=permission_scopes(request.user)
        queryset=expertise_scope_queryset(request.user,"expertise.view",scopes)
        page=self.paginate_queryset(loaded(filter_registry(queryset,request.query_params)))
        return self.get_paginated_response(ExpertiseOutput(page,many=True,context={"user":request.user,"scopes":scopes}).data)


class ExpertiseDetailView(GenericAPIView):
    def get(self,request,pk):
        work=get_object_or_404(loaded(),pk=pk);scopes=permission_scopes(request.user)
        require_work(request.user,"expertise.view",work,scopes)
        return Response(ExpertiseOutput(work,context={"user":request.user,"scopes":scopes}).data)


class HistoryActivationView(GenericAPIView):
    def post(self,request,pk):
        from .history_serializers import HistoryActivationInput
        from .history_activation import activate_history
        form=HistoryActivationInput(data=request.data);form.is_valid(raise_exception=True)
        result=activate_history(actor=request.user,expertise_id=pk,data=form.validated_data,key=request.headers.get('Idempotency-Key'),payload=request.data)
        work=get_object_or_404(loaded(),pk=result['expertise_id']);scopes=permission_scopes(request.user)
        require_work(request.user,'expertise.view',work,scopes)
        return Response({'event':{'id':result['id']},'expertise':ExpertiseOutput(work,context={'user':request.user,'scopes':scopes}).data})


class AssignmentCandidatesView(GenericAPIView):
    def get(self,request,pk):
        from django.utils import timezone
        from apps.personnel.models import Employee, EmployeeSpecialty
        from apps.personnel.services import qualification_eligibility
        work=get_object_or_404(loaded(),pk=pk)
        action="expertise.reassign" if any(a.ended_at is None for a in work.assignments.all()) else "expertise.assign"
        require_work(request.user,action,work)
        from .history import require_operational
        require_operational(work)
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
        # One yearly sequence for the institution; the selected department only
        # determines registration authority, not a separate numbering series.
        last=Expertise.objects.filter(year=data["year"],material__is_demo=False).order_by("-sequence","id").first()
        return Response({"last_number":last.registration_number if last else None,"next_sequence":last.sequence+1 if last else 1})


class FilterOptionsView(GenericAPIView):
    def get(self,request):
        from apps.personnel.models import Employee
        works=expertise_scope_queryset(request.user,"expertise.view")
        historical=works.filter(origin_kind="historical",assignments__isnull=True)
        employees=Employee.objects.filter(Q(expert_assignments__expertise__in=works,expert_assignments__ended_at__isnull=True)|Q(historical_participations__history__expertise__in=historical)).distinct()
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
        result=create_complex_group(actor=request.user,receipt_id=data["receipt"].id,title=data["title"],idempotency_key=request.headers.get("Idempotency-Key"),payload=request.data)
        return Response(result,status=201)
