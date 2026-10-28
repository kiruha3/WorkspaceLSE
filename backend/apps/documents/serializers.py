from rest_framework import serializers
from apps.accounts.serializers import StrictSerializer,VersionedSerializer
from apps.references.models import Department
from .models import Document,FileVersion
from .sources import validate_source_url,normalize_relative_path


class DocumentCreate(StrictSerializer):
    kind=serializers.ChoiceField(choices=Document._meta.get_field("kind").choices)
    title=serializers.CharField(max_length=400)
    source_kind=serializers.ChoiceField(choices=Document._meta.get_field("source_kind").choices)
    source_url=serializers.CharField(max_length=2048,allow_blank=True,required=False,trim_whitespace=False)
    department_id=serializers.PrimaryKeyRelatedField(queryset=Department.objects.filter(is_active=True),source="department",allow_null=True,required=False)

    def validate(self,attrs):
        url=attrs.get('source_url','')
        if attrs['source_kind']=='external_link':
            try:validate_source_url(url)
            except serializers.ValidationError as error:raise serializers.ValidationError({'source_url':error.detail})
        elif url:raise serializers.ValidationError({'source_url':'Ссылка допустима только для внешнего источника.'})
        return attrs


class FileUpload(VersionedSerializer):
    file=serializers.FileField()
    relative_path=serializers.CharField(max_length=1000,allow_blank=True,required=False,trim_whitespace=False)

    def validate(self,attrs):
        from pathlib import PureWindowsPath
        attrs['relative_path']=normalize_relative_path(attrs.get('relative_path',''),PureWindowsPath(attrs['file'].name).name[:255])
        return attrs


class FileVersionOutput(serializers.ModelSerializer):
    download_url=serializers.SerializerMethodField()
    preview_url=serializers.SerializerMethodField()

    class Meta:
        model=FileVersion
        fields=["id","number","original_name","relative_path","content_type","size","sha256","created_at","download_url","preview_url"]

    def get_download_url(self,obj):
        return f"/api/v1/file-versions/{obj.id}/download/"

    def get_preview_url(self,obj):
        return f"/api/v1/file-versions/{obj.id}/preview/" if obj.content_type in ("application/pdf","image/png","image/jpeg") else None


class DocumentOutput(serializers.ModelSerializer):
    versions=FileVersionOutput(many=True)

    class Meta:
        model=Document
        fields=["id","kind","title","source_kind","source_url","department_id","version","versions"]
