from django.shortcuts import get_object_or_404
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from apps.accounts.policies import permission_scopes
from .api import loaded
from .policies import require_work
from .serializers import ExpertiseOutput
from .case_details import case_options,save_case_details
from .case_serializers import CaseDetailsInput


class CaseDetailsView(GenericAPIView):
    def get(self,request,pk):
        work=get_object_or_404(loaded(),pk=pk)
        require_work(request.user,'expertise.view',work)
        return Response(case_options(work))

    def post(self,request,pk):
        form=CaseDetailsInput(data=request.data);form.is_valid(raise_exception=True)
        result=save_case_details(actor=request.user,expertise_id=pk,data=form.validated_data,
                                 key=request.headers.get('Idempotency-Key'),payload=request.data)
        work=get_object_or_404(loaded(),pk=pk);scopes=permission_scopes(request.user)
        require_work(request.user,'expertise.view',work,scopes)
        return Response({'event':{'id':result['id']},'expertise':ExpertiseOutput(work,context={'user':request.user,'scopes':scopes}).data})
