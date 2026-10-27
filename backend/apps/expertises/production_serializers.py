from rest_framework import serializers
from apps.accounts.serializers import VersionedSerializer
from .models import Suspension


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
