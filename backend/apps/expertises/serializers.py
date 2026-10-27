from rest_framework import serializers
from apps.accounts.serializers import StrictSerializer, VersionedSerializer
from apps.accounts.policies import AccessScope
from apps.references.models import Department, Specialty
from apps.intake.models import Receipt
from apps.documents.policies import can_document
from apps.documents.serializers import DocumentOutput
from .models import ComplexGroup, Expertise, ExpertAssignment
from .policies import work_context


class RegistrationInput(VersionedSerializer):
    registration_number = serializers.CharField(max_length=100)
    historical_number = serializers.CharField(max_length=300, allow_blank=True, required=False, default="")
    # Active status is checked under the command lock for NEW registrations.
    # A replay must still resolve a reference that was deactivated afterwards.
    department_id = serializers.PrimaryKeyRelatedField(source="department",queryset=Department.objects.all())
    specialty_id = serializers.PrimaryKeyRelatedField(source="specialty",queryset=Specialty.objects.all())
    appointment_nature = serializers.ChoiceField(choices=["primary","repeated","additional"])
    is_commission = serializers.BooleanField()
    complex_group_id = serializers.PrimaryKeyRelatedField(source="complex_group",queryset=ComplexGroup.objects.all(),required=False,allow_null=True,default=None)


class GroupInput(StrictSerializer):
    receipt_id = serializers.PrimaryKeyRelatedField(source="receipt",queryset=Receipt.objects.all())
    title = serializers.CharField(max_length=300,allow_blank=True,required=False,default="")


class AssignmentInput(VersionedSerializer):
    employee_ids = serializers.ListField(child=serializers.UUIDField(),allow_empty=False)
    reason = serializers.CharField()

    def validate_employee_ids(self,values):
        if len(set(values))!=len(values):raise serializers.ValidationError("Сотрудник указан несколько раз.")
        return values


class WorkFilters(serializers.Serializer):
    search = serializers.CharField(required=False,allow_blank=True)
    department_id = serializers.UUIDField(required=False)
    specialty_id = serializers.UUIDField(required=False)
    employee_id = serializers.UUIDField(required=False)
    received_from = serializers.DateField(required=False)
    received_to = serializers.DateField(required=False)
    state = serializers.ChoiceField(choices=["in_progress","suspended","completed","without_execution"],required=False)
    calendar_days_min=serializers.IntegerField(min_value=0,max_value=365000,required=False)
    calendar_days_max=serializers.IntegerField(min_value=0,max_value=365000,required=False)

    def validate(self, data):
        if data.get("received_from") and data.get("received_to") and data["received_from"]>data["received_to"]:
            raise serializers.ValidationError({"received_to":"Конец периода раньше начала."})
        if "calendar_days_min" in data and "calendar_days_max" in data and data["calendar_days_min"]>data["calendar_days_max"]:
            raise serializers.ValidationError({"calendar_days_max":"Верхняя граница меньше нижней."})
        return data


class AssignmentOutput(serializers.ModelSerializer):
    employee = serializers.SerializerMethodField()
    class Meta:
        model = ExpertAssignment
        fields = ["id","employee","started_at","ended_at","reason"]
    def get_employee(self,obj): return {"id":str(obj.employee_id),"full_name":obj.employee.full_name}


class ExpertiseOutput(serializers.ModelSerializer):
    department = serializers.SerializerMethodField()
    specialty = serializers.SerializerMethodField()
    receipt = serializers.SerializerMethodField()
    material = serializers.SerializerMethodField()
    complex_group = serializers.SerializerMethodField()
    current_assignments = serializers.SerializerMethodField()
    assignment_history = serializers.SerializerMethodField()
    allowed_actions = serializers.SerializerMethodField()
    basis_document = serializers.SerializerMethodField()
    production=serializers.SerializerMethodField()
    suspensions=serializers.SerializerMethodField()
    deadline_events=serializers.SerializerMethodField()

    class Meta:
        model = Expertise
        fields = ["id","registration_number","historical_number","sequence","year","category_code","department","specialty","receipt","material","appointment_nature","is_commission","complex_group","state","version","current_assignments","assignment_history","allowed_actions","basis_document","production","suspensions","deadline_events"]

    def get_department(self,obj): return {"id":str(obj.department_id),"code":obj.department.code,"name":obj.department.name}
    def get_specialty(self,obj): return {"id":str(obj.specialty_id),"code":obj.specialty.code,"name":obj.specialty.name}
    def get_receipt(self,obj): return {"id":str(obj.receipt_id),"received_at":obj.receipt.received_at.isoformat(),"status":obj.receipt.status}
    def get_material(self,obj): return {"id":str(obj.material_id),"title":obj.material.title}
    def get_complex_group(self,obj): return {"id":str(obj.complex_group_id),"title":obj.complex_group.title} if obj.complex_group_id else None
    def get_current_assignments(self,obj): return AssignmentOutput([a for a in obj.assignments.all() if a.ended_at is None],many=True).data
    def get_assignment_history(self,obj): return AssignmentOutput(list(obj.assignments.all()),many=True).data
    def get_allowed_actions(self,obj):
        # Only implemented commands are advertised; execution always rechecks.
        scopes=self.context["scopes"];context=work_context(obj,self.context["user"],scopes)
        if obj.state not in ("in_progress","suspended"): return []
        action = "expertise.reassign" if any(a.ended_at is None for a in obj.assignments.all()) else "expertise.assign"
        result=[action] if scopes.get(action,AccessScope()).allows(**context) else []
        production_action="expertise.suspend" if obj.state=="in_progress" else "expertise.resume"
        if scopes.get(production_action,AccessScope()).allows(**context):result.append(production_action)
        return result
    def get_production(self,obj):
        from .production import production_summary
        return production_summary(obj)
    def get_suspensions(self,obj):
        from .production_serializers import SuspensionOutput
        return SuspensionOutput(obj.suspensions.all(),many=True).data
    def get_deadline_events(self,obj):return []
    def get_basis_document(self,obj):
        document=obj.receipt.basis_document
        if document is None: return None
        return DocumentOutput(document).data if can_document(self.context["user"],"documents.view",document) else {"id":str(document.id),"restricted":True}
