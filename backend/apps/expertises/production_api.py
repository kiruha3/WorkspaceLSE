from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from apps.accounts.policies import permission_scopes
from .api import loaded
from .serializers import ExpertiseOutput
from .production_serializers import SuspendInput,ResumeInput
from .production import suspend_work,resume_work


class TransitionView(GenericAPIView):
    kind="suspend"
    def post(self,request,pk):
        form=(SuspendInput if self.kind=="suspend" else ResumeInput)(data=request.data)
        form.is_valid(raise_exception=True)
        command=suspend_work if self.kind=="suspend" else resume_work
        result=command(actor=request.user,expertise_id=pk,data=form.validated_data,key=request.headers.get("Idempotency-Key"),payload=request.data)
        work=loaded().get(pk=result["expertise_id"])
        return Response({"event":{"id":result["id"]},"expertise":ExpertiseOutput(work,context={"user":request.user,"scopes":permission_scopes(request.user)}).data})
