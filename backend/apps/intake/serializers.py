from rest_framework import serializers
from apps.accounts.serializers import StrictSerializer,VersionedSerializer
from apps.documents.models import Document
from apps.documents.serializers import DocumentOutput
from apps.documents.policies import can_document
from apps.references.models import Department
from .models import Receipt


class ReceiptCreate(StrictSerializer):
    received_at=serializers.DateField()
    is_demo=serializers.BooleanField(required=False,default=False)
    sender_name=serializers.CharField(max_length=500,allow_blank=True,required=False,default="")
    material_title=serializers.CharField(max_length=500,allow_blank=True,required=False,default="")
    basis_document_id=serializers.PrimaryKeyRelatedField(queryset=Document.objects.all(),source="basis_document",allow_null=True,required=False)
    department_id=serializers.PrimaryKeyRelatedField(queryset=Department.objects.filter(is_active=True),source="department",allow_null=True,required=False)


class ReceiptAmend(VersionedSerializer):
    received_at=serializers.DateField(required=False)
    sender_name=serializers.CharField(max_length=500,allow_blank=True,required=False)
    basis_document_id=serializers.PrimaryKeyRelatedField(queryset=Document.objects.all(),source="basis_document",allow_null=True,required=False)
    department_id=serializers.PrimaryKeyRelatedField(queryset=Department.objects.filter(is_active=True),source="department",allow_null=True,required=False)
    reason=serializers.CharField()


class ReceiptOutput(serializers.ModelSerializer):
    basis_document=serializers.SerializerMethodField()
    material=serializers.SerializerMethodField()
    department_id=serializers.UUIDField(allow_null=True)

    class Meta:
        model=Receipt
        fields=["id","received_at","sender_name","material","basis_document","department_id","status","version"]

    def get_basis_document(self,obj):
        document=obj.basis_document
        if document is None:return None
        if not can_document(self.context["user"],"documents.view",document):
            return {"id":str(document.id),"restricted":True}
        return DocumentOutput(document).data

    def get_material(self,obj):
        return {"id":str(obj.material_id),"title":obj.material.title,"is_demo":obj.material.is_demo}
