from collections.abc import Mapping
from rest_framework import serializers
from .catalog import PERMISSIONS, SCOPES
from .models import Role


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, Mapping):
            raise serializers.ValidationError("Ожидается объект полей.")
        unknown = set(data) - set(self.fields)
        if unknown:
            raise serializers.ValidationError({key:"Неизвестное поле." for key in unknown})
        return super().to_internal_value(data)


class VersionedSerializer(StrictSerializer):
    expected_version = serializers.IntegerField(min_value=1)


class PermissionInput(StrictSerializer):
    permission_code = serializers.ChoiceField(choices=tuple(PERMISSIONS))
    scope = serializers.ChoiceField(choices=SCOPES)

    def validate(self, attrs):
        if attrs["scope"] not in PERMISSIONS[attrs["permission_code"]].scopes:
            raise serializers.ValidationError({"scope":"Эта область не поддерживается действием."})
        return attrs


class PermissionSet(StrictSerializer):
    permissions = PermissionInput(many=True)

    def validate_permissions(self, items):
        codes = [item["permission_code"] for item in items]
        if len(codes) != len(set(codes)):
            raise serializers.ValidationError("Действие не должно повторяться.")
        return items


class RoleCreate(PermissionSet):
    name = serializers.CharField(max_length=160)
    description = serializers.CharField(required=False,allow_blank=True,default="")
    permissions = PermissionInput(many=True,required=False,default=list)

    def validate_name(self, value):
        if Role.objects.filter(name=value).exists():
            raise serializers.ValidationError("Роль с таким названием уже существует.")
        return value


class RoleUpdate(VersionedSerializer):
    name = serializers.CharField(max_length=160,required=False)
    description = serializers.CharField(required=False,allow_blank=True)
    is_active = serializers.BooleanField(required=False)


class RolePermissionsUpdate(PermissionSet,VersionedSerializer):
    pass


class RoleOutput(serializers.ModelSerializer):
    permissions = PermissionInput(many=True,read_only=True)
    assignment_count = serializers.SerializerMethodField()

    class Meta:
        model = Role
        fields = ["id","name","description","is_active","version","permissions","assignment_count"]

    def get_assignment_count(self, role):
        return role.assignments.filter(is_active=True).count()
