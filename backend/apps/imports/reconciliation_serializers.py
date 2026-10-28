from rest_framework import serializers
from apps.accounts.serializers import StrictSerializer
from apps.references.models import Department,Specialty
from .serializers import BatchFilters


class ReconciliationFilters(BatchFilters):
    search=serializers.CharField(required=False,allow_blank=True)
    classification=serializers.ChoiceField(choices=["new","unchanged","changed","invalid"],required=False)


class SelectionInput(StrictSerializer):
    expected_version=serializers.IntegerField(min_value=0)
    reason=serializers.CharField()
    department_id=serializers.PrimaryKeyRelatedField(source="department",queryset=Department.objects.all())
    specialty_id=serializers.PrimaryKeyRelatedField(source="specialty",queryset=Specialty.objects.all(),allow_null=True)
    employee_ids=serializers.ListField(child=serializers.UUIDField(),max_length=100,allow_empty=True)
    appointment_nature=serializers.ChoiceField(choices=["primary","repeated","additional"],allow_null=True)
    is_commission=serializers.BooleanField(allow_null=True)
    complex_known=serializers.BooleanField()
    complex_group_key=serializers.CharField(max_length=100,allow_null=True)
    statistics_confirmed=serializers.BooleanField()

    def validate(self,data):
        if len(set(data["employee_ids"]))!=len(data["employee_ids"]):raise serializers.ValidationError({"employee_ids":"Сотрудник выбран повторно."})
        if data["complex_group_key"] and not data["complex_known"]:raise serializers.ValidationError({"complex_group_key":"Подтвердите признак комплекса."})
        if data["is_commission"] is True and len(data["employee_ids"])<2:raise serializers.ValidationError({"employee_ids":"Подтверждённая комиссия требует не менее двух участников."})
        if data["is_commission"] is False and len(data["employee_ids"])>1:raise serializers.ValidationError({"employee_ids":"Единоличная работа не может иметь несколько текущих исторических участников."})
        return data


class SelectedRow(StrictSerializer):
    row_id=serializers.UUIDField()
    expected_selection_version=serializers.IntegerField(min_value=1)


class ApplyInput(StrictSerializer):
    reason=serializers.CharField()
    selections=SelectedRow(many=True,allow_empty=False,max_length=1000)

    def validate_selections(self,values):
        ids=[item["row_id"] for item in values]
        if len(set(ids))!=len(ids):raise serializers.ValidationError("Строка выбрана несколько раз.")
        return values
