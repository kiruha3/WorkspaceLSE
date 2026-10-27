from rest_framework.generics import GenericAPIView
from .api import command_response
from . import commands
from .command_serializers import (RegisterInput, SendInput, ReceiveInput, DeliverInput, AssignInput,
    ControlInput, DeadlineInput, CloseInput, ReopenInput)


class LetterCommandView(GenericAPIView):
    kind = "register"

    def post(self, request, pk):
        serializer, command = {
            "register": (RegisterInput, commands.register_letter),
            "send": (SendInput, commands.send_letter),
            "receive": (ReceiveInput, commands.receive_letter),
            "deliver": (DeliverInput, commands.deliver_letter),
            "assign": (AssignInput, commands.assign_letter),
            "control": (ControlInput, commands.open_control),
            "deadline": (DeadlineInput, commands.change_control_deadline),
            "close": (CloseInput, commands.close_control),
            "reopen": (ReopenInput, commands.reopen_control),
        }[self.kind]
        form = serializer(data=request.data); form.is_valid(raise_exception=True)
        return command_response(request, command(actor=request.user, letter_id=pk, data=form.validated_data, key=request.headers.get("Idempotency-Key"), payload=request.data))
