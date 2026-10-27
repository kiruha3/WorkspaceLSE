from rest_framework import serializers
from apps.accounts.serializers import StrictSerializer
from apps.documents.models import Document
from apps.references.models import LetterJournal, DispatchChannel, ControlClosureReason


class CommandInput(StrictSerializer):
    expected_version = serializers.IntegerField(min_value=1)
    reason = serializers.CharField()


class RegisterInput(CommandInput):
    journal_id = serializers.PrimaryKeyRelatedField(source="journal", queryset=LetterJournal.objects.all())
    registration_number = serializers.CharField(max_length=200)
    registered_on = serializers.DateField()


class EvidenceInput(CommandInput):
    evidence_document_id = serializers.PrimaryKeyRelatedField(source="evidence_document", queryset=Document.objects.all(), required=False, allow_null=True, default=None)


class SendInput(EvidenceInput):
    sent_on = serializers.DateField()
    channel_id = serializers.PrimaryKeyRelatedField(source="channel", queryset=DispatchChannel.objects.all())
    recipient_ids = serializers.ListField(child=serializers.UUIDField(), allow_empty=False)
    tracking = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")
    comment = serializers.CharField(required=False, allow_blank=True, default="")


class ReceiveInput(EvidenceInput):
    received_on = serializers.DateField()


class DeliverInput(EvidenceInput):
    dispatch_id = serializers.UUIDField()
    recipient_id = serializers.UUIDField()
    delivered_on = serializers.DateField()


class AssignInput(CommandInput):
    responsible_id = serializers.UUIDField()


class DeadlineInput(CommandInput):
    due_on = serializers.DateField(required=False, allow_null=True, default=None)
    due_basis = serializers.CharField(required=False, allow_blank=True, default="")


class ControlInput(DeadlineInput):
    opened_on = serializers.DateField()


class CloseInput(CommandInput):
    closed_on = serializers.DateField()
    closure_reason_id = serializers.PrimaryKeyRelatedField(source="closure_reason", queryset=ControlClosureReason.objects.all())
    reply_id = serializers.UUIDField(required=False, allow_null=True, default=None)
    comment = serializers.CharField(required=False, allow_blank=True, default="")


class ReopenInput(CommandInput):
    reopened_on = serializers.DateField()
    comment = serializers.CharField(required=False, allow_blank=True, default="")
