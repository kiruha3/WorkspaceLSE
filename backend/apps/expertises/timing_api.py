from django.shortcuts import get_object_or_404
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from apps.accounts.policies import permission_scopes
from .api import loaded
from .policies import require_work
from .serializers import ExpertiseOutput
from .timing import timing_options,save_timing
from .timing_serializers import TimingInput

class TimingView(GenericAPIView):
    def get(self,request,pk):
        work=get_object_or_404(loaded(),pk=pk);require_work(request.user,'expertise.view',work)
        return Response(timing_options(work))
    def post(self,request,pk):
        form=TimingInput(data=request.data);form.is_valid(raise_exception=True)
        result=save_timing(actor=request.user,expertise_id=pk,data=form.validated_data,key=request.headers.get('Idempotency-Key'),payload=request.data)
        work=get_object_or_404(loaded(),pk=pk);scopes=permission_scopes(request.user);require_work(request.user,'expertise.view',work,scopes)
        return Response({'event':{'id':result['id']},'expertise':ExpertiseOutput(work,context={'user':request.user,'scopes':scopes}).data})
