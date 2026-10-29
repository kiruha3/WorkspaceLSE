from django.shortcuts import get_object_or_404
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from apps.accounts.policies import permission_scopes
from apps.references.api import reference_data
from apps.references.models import SndzReason, UnresolvedQuestionReason, ReturnReason
from .models import ResultRevision
from .api import loaded
from .policies import require_work
from .serializers import ExpertiseOutput
from .result_serializers import ResultInput,CompleteInput,ReturnInput,CorrectInput
from .results import save_result,complete_work,return_work,correct_closed_work


def command_response(request,result):
    work=loaded().get(pk=result["expertise_id"])
    return Response({"event":{"id":result["id"]},"expertise":ExpertiseOutput(work,context={"user":request.user,"scopes":permission_scopes(request.user)}).data})


class ResultOptionsView(GenericAPIView):
    def get(self,request,pk):
        work=get_object_or_404(loaded(),pk=pk);require_work(request.user,"expertise.view",work)
        return Response({
            "result_kinds":[{"code":code,"name":name} for code,name in ResultRevision._meta.get_field("kind").choices],
            "complexity_groups":[{"code":str(n),"name":str(n)} for n in (1,2,3)]+[{"code":"above_3","name":"Выше 3"}],
            "sndz_reasons":[reference_data(r) for r in SndzReason.objects.all()],
            "unresolved_reasons":[reference_data(r) for r in UnresolvedQuestionReason.objects.all()],
            "return_reasons":[reference_data(r) for r in ReturnReason.objects.all()],
        })


class ResultView(GenericAPIView):
    def post(self,request,pk):
        form=ResultInput(data=request.data);form.is_valid(raise_exception=True)
        return command_response(request,save_result(actor=request.user,expertise_id=pk,data=form.validated_data,key=request.headers.get("Idempotency-Key"),payload=request.data))


class ClosureView(GenericAPIView):
    kind="complete"
    def post(self,request,pk):
        serializer,command={"complete":(CompleteInput,complete_work),"return":(ReturnInput,return_work),"correct":(CorrectInput,correct_closed_work)}[self.kind]
        form=serializer(data=request.data);form.is_valid(raise_exception=True)
        return command_response(request,command(actor=request.user,expertise_id=pk,data=form.validated_data,key=request.headers.get("Idempotency-Key"),payload=request.data))


class ReopenView(GenericAPIView):
    def post(self,request,pk):
        from .result_serializers import ReopenInput
        from .reopen import reopen_work
        form=ReopenInput(data=request.data);form.is_valid(raise_exception=True)
        return command_response(request,reopen_work(actor=request.user,expertise_id=pk,data=form.validated_data,key=request.headers.get('Idempotency-Key'),payload=request.data))
