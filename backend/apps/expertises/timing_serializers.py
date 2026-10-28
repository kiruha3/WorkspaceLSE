from rest_framework import serializers
from apps.accounts.serializers import StrictSerializer
from apps.documents.models import Document
from apps.references.models import DelayReason

class TimingReasonInput(StrictSerializer):
    reason_id=serializers.PrimaryKeyRelatedField(source='reason',queryset=DelayReason.objects.all())
    comment=serializers.CharField(allow_blank=True,max_length=100000)
    document_id=serializers.PrimaryKeyRelatedField(source='document',queryset=Document.objects.all(),allow_null=True)

class TimingInput(StrictSerializer):
    expected_version=serializers.IntegerField(min_value=1)
    reason=serializers.CharField()
    reasons_complete=serializers.BooleanField()
    primary_reason_id=serializers.PrimaryKeyRelatedField(source='primary_reason',queryset=DelayReason.objects.all(),allow_null=True)
    reasons=TimingReasonInput(many=True,max_length=100)
    notification_sent=serializers.BooleanField(allow_null=True)
    notification_on=serializers.DateField(allow_null=True)
    notification_document_id=serializers.PrimaryKeyRelatedField(source='notification_document',queryset=Document.objects.all(),allow_null=True)
    extension_requested=serializers.BooleanField(allow_null=True)
    request_on=serializers.DateField(allow_null=True)
    request_document_id=serializers.PrimaryKeyRelatedField(source='request_document',queryset=Document.objects.all(),allow_null=True)
    deadline_breached=serializers.BooleanField(allow_null=True)
    breach_basis=serializers.CharField(allow_blank=True,max_length=100000)
    breach_document_id=serializers.PrimaryKeyRelatedField(source='breach_document',queryset=Document.objects.all(),allow_null=True)
    def validate(self,data):
        ids=[item['reason'].pk for item in data['reasons']]
        if len(ids)!=len(set(ids)):raise serializers.ValidationError({'reasons':'Причина указана несколько раз.'})
        if data['primary_reason'] and data['primary_reason'].pk not in ids:
            raise serializers.ValidationError({'primary_reason_id':'Основная причина должна входить в указанный список.'})
        for flag,on,document in [('notification_sent','notification_on','notification_document'),('extension_requested','request_on','request_document')]:
            if data[flag] is True and data[document] is None:raise serializers.ValidationError({document+'_id':'Подтверждённый факт требует документа.'})
            if data[flag] is False and (data[on] is not None or data[document] is not None):
                raise serializers.ValidationError({flag:'Для «нет» дата и документ фактической отправки не задаются.'})
        if data['deadline_breached'] is not None and (not data['breach_basis'].strip() or data['breach_document'] is None):
            raise serializers.ValidationError({'deadline_breached':'Известная оценка срока требует основания и документа.'})
        return data
