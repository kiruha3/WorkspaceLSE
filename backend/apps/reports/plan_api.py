from rest_framework import serializers
from django.db import transaction
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from apps.accounts.policies import require
from .models import StateAssignmentPlan
from .plan_serializers import PlanInput
from .plans import MANAGE,require_plan_read,plan_output,save_plan

def validated_year(value):
    if not 1900<=value<=2200:raise serializers.ValidationError({'year':'Укажите год1900–2200.'})
    return value

class ReportPlanView(GenericAPIView):
    @transaction.atomic
    def get(self,request,year):
        require_plan_read(request.user);validated_year(year)
        # Keep the version, lines and revision history together through DTO
        # assembly; READ COMMITTED atomic alone would permit a torn response.
        response=Response(plan_output(StateAssignmentPlan.objects.select_for_update().filter(year=year).first(),request.user,year))
        response['Cache-Control']='private, no-store'
        return response

    @transaction.atomic
    def post(self,request,year):
        require(request.user,MANAGE);validated_year(year)
        form=PlanInput(data=request.data);form.is_valid(raise_exception=True)
        save_plan(actor=request.user,year=year,data=form.validated_data,key=request.headers.get('Idempotency-Key'),payload=request.data)
        # save_plan's row lock lives until the outer transaction commits,
        # after this response's complete values have been assembled.
        response=Response(plan_output(StateAssignmentPlan.objects.get(year=year),request.user,year))
        response['Cache-Control']='private, no-store'
        return response
