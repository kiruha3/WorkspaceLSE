from rest_framework import serializers
from apps.accounts.serializers import StrictSerializer
from apps.documents.models import Document
from apps.references.models import Specialty


class PlanLineInput(StrictSerializer):
    specialty_id=serializers.PrimaryKeyRelatedField(source='specialty',queryset=Specialty.objects.all())
    count=serializers.IntegerField(min_value=0,max_value=2147483647,allow_null=True)


class PlanInput(StrictSerializer):
    expected_version=serializers.IntegerField(min_value=0)
    reason=serializers.CharField(max_length=100000)
    total=serializers.IntegerField(min_value=0,max_value=2147483647,allow_null=True)
    basis_text=serializers.CharField(allow_blank=True,max_length=100000)
    document_id=serializers.PrimaryKeyRelatedField(source='document',queryset=Document.objects.all(),allow_null=True)
    lines=PlanLineInput(many=True,max_length=1000)

    def validate(self,data):
        ids=[item['specialty'].pk for item in data['lines']]
        if len(ids)!=len(set(ids)):raise serializers.ValidationError({'lines':'Специальность указана несколько раз.'})
        known=[item['count'] for item in data['lines'] if item['count'] is not None]
        if data['total'] is not None and sum(known)>data['total']:
            raise serializers.ValidationError({'lines':'Сумма известных планов специальностей превышает общий план.'})
        if (data['total'] is not None or known) and not(data['basis_text'] or data['document']):
            raise serializers.ValidationError({'basis_text':'Для известных плановых значений укажите основание или документ.'})
        return data
