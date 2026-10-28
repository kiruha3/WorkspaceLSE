from django.shortcuts import get_object_or_404
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from apps.references.models import Specialty,SndzReason,ReturnReason,UnresolvedQuestionReason
from apps.references.api import reference_data
from .api import loaded
from .policies import require_work
from .result_api import command_response
from .historical_report_serializers import HistoricalReportInput
from .historical_reports import correct_historical_report


class HistoricalReportView(GenericAPIView):
    def get(self,request,pk):
        work=get_object_or_404(loaded(),pk=pk);require_work(request.user,'expertise.view',work)
        return Response({'specialties':[reference_data(s) for s in Specialty.objects.all()],
            'sndz_reasons':[reference_data(r) for r in SndzReason.objects.all()],
            'return_reasons':[reference_data(r) for r in ReturnReason.objects.all()],
            'unresolved_reasons':[reference_data(r) for r in UnresolvedQuestionReason.objects.all()]})

    def post(self,request,pk):
        form=HistoricalReportInput(data=request.data);form.is_valid(raise_exception=True)
        return command_response(request,correct_historical_report(actor=request.user,expertise_id=pk,data=form.validated_data,key=request.headers.get('Idempotency-Key'),payload=request.data))
