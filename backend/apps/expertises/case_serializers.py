from rest_framework import serializers
from apps.accounts.serializers import StrictSerializer
from apps.documents.models import Document
from apps.references.models import AuthorityType

TEXT_FIELDS = ('authority_name','official','contact','case_number','case_description','basis_text','inventory','questions_text','decree_basis')
HISTORY_TEXT_FIELDS = ('authority_name','official','contact','case_description','basis_text','inventory')


class CaseDetailsInput(StrictSerializer):
    expected_version=serializers.IntegerField(min_value=1)
    reason=serializers.CharField()
    authority_type_id=serializers.PrimaryKeyRelatedField(source='authority_type',queryset=AuthorityType.objects.all(),allow_null=True)
    authority_name=serializers.CharField(allow_blank=True,max_length=100000)
    official=serializers.CharField(allow_blank=True,max_length=100000)
    contact=serializers.CharField(allow_blank=True,max_length=100000)
    case_number=serializers.CharField(allow_blank=True,max_length=500)
    case_description=serializers.CharField(allow_blank=True,max_length=100000)
    basis_text=serializers.CharField(allow_blank=True,max_length=100000)
    inventory=serializers.CharField(allow_blank=True,max_length=100000)
    questions_text=serializers.CharField(allow_blank=True,max_length=100000)
    decree3214=serializers.BooleanField(allow_null=True)
    decree_document_id=serializers.PrimaryKeyRelatedField(source='decree_document',queryset=Document.objects.all(),allow_null=True)
    decree_basis=serializers.CharField(allow_blank=True,max_length=100000)

    def validate(self,data):
        if data['decree3214'] is not True and (data['decree_document'] is not None or data['decree_basis']):
            raise serializers.ValidationError({'decree_basis':'Основание3214-р относится только к явному признаку «Да».'})
        return data
