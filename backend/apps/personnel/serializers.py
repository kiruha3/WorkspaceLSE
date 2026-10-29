from rest_framework import serializers
from apps.accounts.catalog import SCOPES
from apps.accounts.models import Role
from apps.accounts.serializers import StrictSerializer, VersionedSerializer
from apps.references.models import Department, Position, Specialty
from .models import Employee, EmployeeSpecialty, EmployeeOrgAssignment, EmployeeRole


class ReferenceOutput(serializers.Serializer):
    id = serializers.UUIDField()
    code = serializers.CharField()
    name = serializers.CharField()


class OrgAssignmentOutput(serializers.ModelSerializer):
    department = ReferenceOutput()
    position = ReferenceOutput()

    class Meta:
        model = EmployeeOrgAssignment
        fields = ["id","department","position","valid_from","valid_to","version","reason"]


class SpecialtyOutput(serializers.ModelSerializer):
    specialty = ReferenceOutput()
    mentor_id = serializers.UUIDField(allow_null=True)

    class Meta:
        model = EmployeeSpecialty
        fields = ["id","specialty","status","training_started_at","qualified_at","valid_until","basis","mentor_id","version"]


class EmployeeOutput(serializers.ModelSerializer):
    org_assignments = OrgAssignmentOutput(many=True)
    specialties = SpecialtyOutput(many=True)

    class Meta:
        model = Employee
        fields = ["id","full_name","is_active","version","org_assignments","specialties"]


class EmployeeCreate(StrictSerializer):
    full_name = serializers.CharField(max_length=220)


class EmployeeUpdate(VersionedSerializer):
    full_name = serializers.CharField(max_length=220,required=False)
    is_active = serializers.BooleanField(required=False)


class SpecialtyCreate(StrictSerializer):
    specialty_id = serializers.PrimaryKeyRelatedField(queryset=Specialty.objects.filter(is_active=True),source="specialty")
    status = serializers.ChoiceField(choices=["training","unknown_legacy","qualified"])
    training_started_at = serializers.DateField(allow_null=True,required=False)
    qualified_at = serializers.DateField(allow_null=True,required=False)
    valid_until = serializers.DateField(allow_null=True,required=False)
    basis = serializers.CharField(allow_blank=True,required=False,default="")
    mentor_id = serializers.PrimaryKeyRelatedField(queryset=Employee.objects.filter(is_active=True),source="mentor",allow_null=True,required=False)

    def validate(self, attrs):
        if attrs.get("qualified_at") and attrs.get("valid_until") and attrs["valid_until"] < attrs["qualified_at"]:
            raise serializers.ValidationError({"valid_until":"Окончание срока раньше даты получения. Уточните справочные даты или оставьте неизвестные пустыми."})
        return attrs


class SpecialtyQualify(VersionedSerializer):
    qualified_at = serializers.DateField(allow_null=True,required=False)
    valid_until = serializers.DateField(allow_null=True,required=False)
    basis = serializers.CharField(allow_blank=True,required=False)

    def validate(self, attrs):
        if attrs.get("valid_until") and attrs.get("qualified_at") and attrs["valid_until"] < attrs["qualified_at"]:
            raise serializers.ValidationError({"valid_until":"Окончание срока раньше даты получения."})
        return attrs


class SpecialtyMetadataUpdate(VersionedSerializer):
    training_started_at = serializers.DateField(allow_null=True,required=False)
    qualified_at = serializers.DateField(allow_null=True,required=False)
    valid_until = serializers.DateField(allow_null=True,required=False)
    basis = serializers.CharField(allow_blank=True,required=False)


class OrderedDates(StrictSerializer):
    valid_from = serializers.DateField(allow_null=True,required=False)
    valid_to = serializers.DateField(allow_null=True,required=False)

    def validate(self,attrs):
        if attrs.get("valid_from") and attrs.get("valid_to") and attrs["valid_to"] < attrs["valid_from"]:
            raise serializers.ValidationError({"valid_to":"Окончание периода раньше начала."})
        return attrs


class RoleAssignmentCreate(OrderedDates):
    role_id = serializers.PrimaryKeyRelatedField(queryset=Role.objects.filter(is_active=True),source="role")
    scope_limit = serializers.ChoiceField(choices=SCOPES)
    department_ids = serializers.PrimaryKeyRelatedField(queryset=Department.objects.filter(is_active=True),many=True,source="departments")
    reason = serializers.CharField()

    def validate(self,attrs):
        attrs = super().validate(attrs)
        needs_departments = attrs["scope_limit"] == "departments" or attrs["role"].permissions.filter(scope="departments").exists()
        if needs_departments and not attrs["departments"]:
            raise serializers.ValidationError({"department_ids":"Выберите отделы назначения роли."})
        if len(attrs["departments"]) != len({d.pk for d in attrs["departments"]}):
            raise serializers.ValidationError({"department_ids":"Отдел не должен повторяться."})
        return attrs


class RoleAssignmentOutput(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()
    department_ids = serializers.PrimaryKeyRelatedField(source="departments",many=True,read_only=True)

    class Meta:
        model = EmployeeRole
        fields = ["id","role","scope_limit","department_ids","valid_from","valid_to","is_active","reason","version"]

    def get_role(self,obj):
        return {"id":str(obj.role_id),"name":obj.role.name}


class OrgAssignmentCreate(OrderedDates):
    department_id = serializers.PrimaryKeyRelatedField(queryset=Department.objects.filter(is_active=True),source="department")
    position_id = serializers.PrimaryKeyRelatedField(queryset=Position.objects.filter(is_active=True),source="position")
    reason = serializers.CharField()


class OrgAssignmentEnd(VersionedSerializer):
    valid_to = serializers.DateField()
    reason = serializers.CharField()


class RoleAssignmentRevoke(VersionedSerializer):
    is_active = serializers.BooleanField()
    reason = serializers.CharField()

    def validate_is_active(self,value):
        if value:
            raise serializers.ValidationError("Создайте новое назначение вместо восстановления прекращённого.")
        return value


class AccountCreate(StrictSerializer):
    from django.contrib.auth.validators import UnicodeUsernameValidator
    username = serializers.CharField(max_length=150,validators=[UnicodeUsernameValidator()])
    password = serializers.CharField(write_only=True,trim_whitespace=False)


class AccountUpdate(StrictSerializer):
    is_active = serializers.BooleanField()
    reason = serializers.CharField()


class AccountPasswordReset(StrictSerializer):
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    reason = serializers.CharField(required=False, allow_blank=True, default="")
