from rest_framework import serializers
from apps.accounts.serializers import StrictSerializer,VersionedSerializer
from apps.references.models import Department
from .models import Document,FileVersion


class DocumentCreate(StrictSerializer):
    kind=serializers.ChoiceField(choices=Document._meta.get_field("kind").choices)
    title=serializers.CharField(max_length=400)
    source_kind=serializers.ChoiceField(choices=["paper_original","uploaded_copy"])
    department_id=serializers.PrimaryKeyRelatedField(queryset=Department.objects.filter(is_active=True),source="department",allow_null=True,required=False)


class FileUpload(VersionedSerializer):
    file=serializers.FileField()


class FileVersionOutput(serializers.ModelSerializer):
    download_url=serializers.SerializerMethodField()
    preview_url=serializers.SerializerMethodField()

    class Meta:
        model=FileVersion
        fields=["id","number","original_name","content_type","size","sha256","created_at","download_url","preview_url"]

    def get_download_url(self,obj):
        return f"/api/v1/file-versions/{obj.id}/download/"

    def get_preview_url(self,obj):
        return f"/api/v1/file-versions/{obj.id}/preview/" if obj.content_type in ("application/pdf","image/png","image/jpeg") else None


class DocumentOutput(serializers.ModelSerializer):
    versions=FileVersionOutput(many=True)

    class Meta:
        model=Document
        fields=["id","kind","title","source_kind","department_id","version","versions"]
