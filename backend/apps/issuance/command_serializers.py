from rest_framework import serializers
from apps.accounts.serializers import StrictSerializer
from apps.documents.models import Document
from apps.references.models import IssueMethod


class CheckInput(StrictSerializer):
    expected_version = serializers.IntegerField(min_value=1)
    reason = serializers.CharField()


class IssueInput(CheckInput):
    issued_on = serializers.DateField()
    method_id = serializers.PrimaryKeyRelatedField(source="method", queryset=IssueMethod.objects.all())
    recipient_name = serializers.CharField(max_length=500)
    recipient_basis = serializers.CharField()
    tracking = serializers.CharField(max_length=300, allow_blank=True, required=False, default="")
    comment = serializers.CharField(allow_blank=True, required=False, default="")
    evidence_document_id = serializers.PrimaryKeyRelatedField(source="evidence_document", queryset=Document.objects.all(), allow_null=True, required=False, default=None)
