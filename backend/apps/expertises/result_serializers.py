from rest_framework import serializers
from apps.accounts.serializers import StrictSerializer
from apps.documents.models import Document
from apps.documents.policies import can_document
from apps.documents.serializers import DocumentOutput
from apps.references.api import reference_data
from apps.references.models import SndzReason, UnresolvedQuestionReason, ReturnReason
from .models import ResultRevision, UnresolvedAllocation, WorkClosure
from .production_serializers import actor_data


class AllocationInput(StrictSerializer):
    reason_id=serializers.PrimaryKeyRelatedField(source="reason",queryset=UnresolvedQuestionReason.objects.all())
    count=serializers.IntegerField(min_value=1,max_value=2147483647)
    comment=serializers.CharField(allow_blank=True,required=False,default="")
    document_id=serializers.PrimaryKeyRelatedField(source="document",queryset=Document.objects.all(),allow_null=True,required=False,default=None)


class ResultData(StrictSerializer):
    kind=serializers.ChoiceField(choices=ResultRevision._meta.get_field("kind").choices,allow_null=True,required=False,default=None)
    completed_on=serializers.DateField(allow_null=True,required=False,default=None)
    document_id=serializers.PrimaryKeyRelatedField(source="document",queryset=Document.objects.all(),allow_null=True,required=False,default=None)
    complexity_level=serializers.IntegerField(min_value=1,max_value=2147483647,allow_null=True,required=False,default=None)
    questions=serializers.IntegerField(min_value=0,max_value=2147483647,allow_null=True,required=False,default=None)
    categorical=serializers.IntegerField(min_value=0,max_value=2147483647,allow_null=True,required=False,default=None)
    probable=serializers.IntegerField(min_value=0,max_value=2147483647,allow_null=True,required=False,default=None)
    unresolved=serializers.IntegerField(min_value=0,max_value=2147483647,allow_null=True,required=False,default=None)
    statistics_complete=serializers.BooleanField(required=False,default=False)
    sndz_reason_id=serializers.PrimaryKeyRelatedField(source="sndz_reason",queryset=SndzReason.objects.all(),allow_null=True,required=False,default=None)
    sndz_comment=serializers.CharField(allow_blank=True,required=False,default="")
    unresolved_allocations=AllocationInput(many=True,required=False,default=list)
    allocations_complete=serializers.BooleanField(required=False,default=False)
    note=serializers.CharField(allow_blank=True,required=False,default="")

    def validate(self,data):
        q=data["questions"];parts=[data[k] for k in ("categorical","probable","unresolved")]
        total=sum(p for p in parts if p is not None)
        all_known=q is not None and all(p is not None for p in parts)
        if q is not None and (total>q or (all_known and total!=q)):
            raise serializers.ValidationError({"questions":"Число вопросов должно соответствовать сумме результатов."})
        if data["statistics_complete"] and not all_known:
            raise serializers.ValidationError({"statistics_complete":"Для подтверждения заполните Q, R, S и T, в том числе явные нули."})
        if data["kind"]!="sndz" and (data["sndz_reason"] or data["sndz_comment"]):
            raise serializers.ValidationError({"sndz_reason_id":"Причина полного СНДЗ относится только к результату СНДЗ."})
        allocations=data["unresolved_allocations"];seen=set()
        for allocation in allocations:
            reason=allocation["reason"]
            if reason.pk in seen:raise serializers.ValidationError({"unresolved_allocations":"Одна причина указана несколько раз."})
            seen.add(reason.pk)
            if reason.code=="other" and not allocation["comment"]:
                raise serializers.ValidationError({"unresolved_allocations":"Для иной причины нужно пояснение."})
        allocated=sum(a["count"] for a in allocations);unresolved=data["unresolved"]
        if unresolved is not None and allocated>unresolved:
            raise serializers.ValidationError({"unresolved_allocations":"Распределение превышает число нерешённых вопросов T."})
        if data["allocations_complete"] and (unresolved is None or allocated!=unresolved):
            raise serializers.ValidationError({"allocations_complete":"Подтверждённое распределение должно равняться известному T."})
        return data


class ResultInput(ResultData):
    expected_version=serializers.IntegerField(min_value=1)
    reason=serializers.CharField()


class CompleteInput(StrictSerializer):
    expected_version=serializers.IntegerField(min_value=1)
    reason=serializers.CharField()
    result_id=serializers.UUIDField()


class ReturnData(StrictSerializer):
    decided_on=serializers.DateField()
    document_id=serializers.PrimaryKeyRelatedField(source="document",queryset=Document.objects.all())
    return_reason_id=serializers.PrimaryKeyRelatedField(source="return_reason",queryset=ReturnReason.objects.all(),allow_null=True,required=False,default=None)
    comment=serializers.CharField(allow_blank=True,required=False,default="")


class ReturnInput(ReturnData):
    expected_version=serializers.IntegerField(min_value=1)
    reason=serializers.CharField()


class CorrectInput(StrictSerializer):
    expected_version=serializers.IntegerField(min_value=1)
    reason=serializers.CharField()
    correction_kind=serializers.ChoiceField(choices=["result","return"])
    result=ResultData(required=False)
    decided_on=serializers.DateField(required=False)
    document_id=serializers.PrimaryKeyRelatedField(source="document",queryset=Document.objects.all(),required=False)
    return_reason_id=serializers.PrimaryKeyRelatedField(source="return_reason",queryset=ReturnReason.objects.all(),allow_null=True,required=False)
    comment=serializers.CharField(allow_blank=True,required=False)

    def validate(self,data):
        if data["correction_kind"]=="result":
            if "result" not in data:raise serializers.ValidationError({"result":"Нужна исправленная редакция."})
            if any(k in data for k in ("decided_on","document","return_reason","comment")):
                raise serializers.ValidationError("Не смешивайте исправление результата и решения без исполнения.")
        else:
            if "result" in data:raise serializers.ValidationError("Решение без исполнения не является результатом.")
            for field in ("decided_on","document"):
                if field not in data:raise serializers.ValidationError({field:"Обязательное поле."})
            data.setdefault("return_reason",None);data.setdefault("comment","")
        return data


_UNSET=object()


def document_link(document,user,accepted_version_id=_UNSET):
    if document is None:return None
    if not can_document(user,"documents.view",document):return {"id":str(document.pk),"restricted":True}
    data=DocumentOutput(document).data
    if accepted_version_id is not _UNSET:data["accepted_version_id"]=str(accepted_version_id) if accepted_version_id else None
    return data


class AllocationOutput(serializers.ModelSerializer):
    reason=serializers.SerializerMethodField()
    document=serializers.SerializerMethodField()
    class Meta:
        model=UnresolvedAllocation
        fields=["reason","count","comment","document"]
    def get_reason(self,obj):return reference_data(obj.reason)
    def get_document(self,obj):return document_link(obj.document,self.context["user"])


class ResultOutput(serializers.ModelSerializer):
    actor=serializers.SerializerMethodField()
    document=serializers.SerializerMethodField()
    sndz_reason=serializers.SerializerMethodField()
    unresolved_allocations=AllocationOutput(many=True)
    class Meta:
        model=ResultRevision
        fields=["id","number","kind","completed_on","document","complexity_level","questions","categorical","probable","unresolved","statistics_complete","sndz_reason","sndz_comment","unresolved_allocations","allocations_complete","note","actor","created_at","reason"]
    def get_actor(self,obj):return actor_data(obj.actor)
    def get_document(self,obj):
        closure=max(obj.closures.all(),key=lambda c:c.number,default=None)
        return document_link(obj.document,self.context["user"],closure.accepted_version_id) if closure else document_link(obj.document,self.context["user"])
    def get_sndz_reason(self,obj):return reference_data(obj.sndz_reason) if obj.sndz_reason_id else None


class ClosureOutput(serializers.ModelSerializer):
    actor=serializers.SerializerMethodField()
    document=serializers.SerializerMethodField()
    return_reason=serializers.SerializerMethodField()
    result_id=serializers.UUIDField(read_only=True,allow_null=True)
    class Meta:
        model=WorkClosure
        fields=["id","number","kind","ended_on","document","result_id","return_reason","comment","actor","created_at","reason"]
    def get_actor(self,obj):return actor_data(obj.actor)
    def get_document(self,obj):return document_link(obj.document,self.context["user"],obj.accepted_version_id)
    def get_return_reason(self,obj):return reference_data(obj.return_reason) if obj.return_reason_id else None
