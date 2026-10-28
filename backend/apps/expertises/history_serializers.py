from rest_framework import serializers
from apps.accounts.serializers import StrictSerializer
from apps.documents.models import Document
from apps.references.models import Specialty
from .models import ComplexGroup
from .result_serializers import ResultData,ReturnData


class PastSuspensionInput(StrictSerializer):
    suspended_on=serializers.DateField()
    resumed_on=serializers.DateField()
    reason=serializers.CharField()


class HistoryActivationInput(StrictSerializer):
    expected_version=serializers.IntegerField(min_value=1)
    reason=serializers.CharField()
    basis_document_id=serializers.PrimaryKeyRelatedField(source='basis_document',queryset=Document.objects.all())
    specialty_id=serializers.PrimaryKeyRelatedField(source='specialty',queryset=Specialty.objects.all(),required=False,allow_null=True,default=None)
    appointment_nature=serializers.ChoiceField(choices=['primary','repeated','additional'])
    is_commission=serializers.BooleanField()
    complex_known=serializers.BooleanField()
    complex_group_id=serializers.PrimaryKeyRelatedField(source='complex_group',queryset=ComplexGroup.objects.all(),allow_null=True)
    suspension_history_complete=serializers.BooleanField()
    past_suspensions=PastSuspensionInput(many=True,max_length=500)
    suspended_on=serializers.DateField(allow_null=True,required=False,default=None)
    result=ResultData(required=False)
    return_data=ReturnData(required=False)

    def validate_complex_known(self,value):
        if not value:raise serializers.ValidationError('Подтвердите признак комплекса, неизвестность не заменяется отсутствием.')
        return value
