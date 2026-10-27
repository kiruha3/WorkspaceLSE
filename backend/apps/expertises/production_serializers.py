from rest_framework import serializers
from apps.accounts.serializers import VersionedSerializer
from .models import Suspension,DeadlineEvent
from apps.documents.models import Document
from apps.documents.policies import can_document
from apps.documents.serializers import DocumentOutput


def actor_data(user):
    employee=getattr(user,"employee",None)
    return {"id":str(user.id),"full_name":employee.full_name if employee else user.username}


class SuspendInput(VersionedSerializer):
    suspended_on=serializers.DateField()
    reason=serializers.CharField()


class ResumeInput(VersionedSerializer):
    resumed_on=serializers.DateField()
    reason=serializers.CharField()


class SuspensionOutput(serializers.ModelSerializer):
    actor=serializers.SerializerMethodField()
    resumed_by=serializers.SerializerMethodField()
    class Meta:
        model=Suspension
        fields=["id","suspended_on","resumed_on","reason","resume_reason","created_at","resumed_recorded_at","actor","resumed_by"]
    def get_actor(self,obj):return actor_data(obj.actor)
    def get_resumed_by(self,obj):return actor_data(obj.resumed_by) if obj.resumed_by_id else None


class DeadlineInput(VersionedSerializer):
    kind=serializers.ChoiceField(choices=DeadlineEvent._meta.get_field("kind").choices)
    recorded_on=serializers.DateField()
    due_on=serializers.DateField()
    reason=serializers.CharField()
    document_id=serializers.PrimaryKeyRelatedField(source="document",queryset=Document.objects.all(),required=False,allow_null=True,default=None)


class DeadlineOutput(serializers.ModelSerializer):
    actor=serializers.SerializerMethodField()
    document=serializers.SerializerMethodField()
    class Meta:
        model=DeadlineEvent
        fields=["id","kind","recorded_on","due_on","reason","created_at","actor","document"]
    def get_actor(self,obj):return actor_data(obj.actor)
    def get_document(self,obj):
        if obj.document_id is None:return None
        return DocumentOutput(obj.document).data if can_document(self.context["user"],"documents.view",obj.document) else {"id":str(obj.document_id),"restricted":True}
