from rest_framework import serializers
from apps.accounts.serializers import StrictSerializer
from apps.documents.models import Document
from .models import PreviousConclusion

class PreviousConclusionInput(StrictSerializer):
    reference=serializers.CharField(max_length=500)
    organization_name=serializers.CharField(max_length=500,allow_blank=True)
    organization_group=serializers.ChoiceField(choices=PreviousConclusion.GROUPS,allow_null=True)
    same_input_data=serializers.BooleanField(allow_null=True)
    confirms_previous=serializers.BooleanField(allow_null=True)
    document_id=serializers.PrimaryKeyRelatedField(source='document',queryset=Document.objects.all(),allow_null=True)

class ClassificationInput(StrictSerializer):
    expected_version=serializers.IntegerField(min_value=1)
    reason=serializers.CharField()
    appointment_nature=serializers.ChoiceField(choices=['primary','repeated','additional'],allow_null=True)
    previous_complete=serializers.BooleanField()
    previous_conclusions=PreviousConclusionInput(many=True,max_length=100)
    def validate(self,data):
        if data['appointment_nature'] in ('repeated','additional') and data['previous_complete'] and not data['previous_conclusions']:
            raise serializers.ValidationError({'previous_complete':'Полный список предыдущих заключений для повторной/дополнительной работы не может быть пустым.'})
        return data
