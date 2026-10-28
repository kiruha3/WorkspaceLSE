from django.shortcuts import get_object_or_404
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from apps.accounts.policies import permission_scopes
from .api import loaded
from .models import PreviousConclusion
from .policies import require_work
from .serializers import ExpertiseOutput
from .classification import save_classification
from .classification_serializers import ClassificationInput

class ClassificationView(GenericAPIView):
    def get(self,request,pk):
        work=get_object_or_404(loaded(),pk=pk);require_work(request.user,'expertise.view',work)
        return Response({'organization_groups':[{'code':code,'name':name} for code,name in PreviousConclusion.GROUPS]})
    def post(self,request,pk):
        form=ClassificationInput(data=request.data);form.is_valid(raise_exception=True)
        result=save_classification(actor=request.user,expertise_id=pk,data=form.validated_data,key=request.headers.get('Idempotency-Key'),payload=request.data)
        work=get_object_or_404(loaded(),pk=pk);scopes=permission_scopes(request.user);require_work(request.user,'expertise.view',work,scopes)
        return Response({'event':{'id':result['id']},'expertise':ExpertiseOutput(work,context={'user':request.user,'scopes':scopes}).data})
