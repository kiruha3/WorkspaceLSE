from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework.exceptions import NotFound, ValidationError
from apps.accounts.policies import require
from apps.accounts.services import audit, check_version, require_any_scope
from apps.accounts.serializers import StrictSerializer, VersionedSerializer
from .models import Department, Position, Specialty, SndzReason, UnresolvedQuestionReason, ReturnReason, LetterKind, LetterJournal, DispatchChannel, ControlClosureReason, IssueMethod, AuthorityType

CATALOGS = {"departments":Department,"positions":Position,"specialties":Specialty,
    "sndz-reasons":SndzReason,"unresolved-question-reasons":UnresolvedQuestionReason,"return-reasons":ReturnReason,
    "letter-kinds":LetterKind,"letter-journals":LetterJournal,"dispatch-channels":DispatchChannel,"control-closure-reasons":ControlClosureReason,"issue-methods":IssueMethod,"authority-types":AuthorityType}


class ReferenceCreate(StrictSerializer):
    code = serializers.CharField(max_length=80)
    name = serializers.CharField(max_length=300)


class ReferenceUpdate(VersionedSerializer):
    name = serializers.CharField(max_length=300,required=False)
    is_active = serializers.BooleanField(required=False)


class LetterJournalCreate(ReferenceCreate):
    direction = serializers.ChoiceField(choices=["incoming", "outgoing"])
    department_id = serializers.PrimaryKeyRelatedField(source="department", queryset=Department.objects.all(), allow_null=True, required=False, default=None)


class ClosureReasonCreate(ReferenceCreate):
    rule = serializers.ChoiceField(choices=ControlClosureReason._meta.get_field("rule").choices, required=False, default="other")


class AuthorityTypeCreate(ReferenceCreate):
    report_group = serializers.ChoiceField(choices=AuthorityType.REPORT_GROUPS, allow_null=True)


class AuthorityTypeUpdate(ReferenceUpdate):
    report_group = serializers.ChoiceField(choices=AuthorityType.REPORT_GROUPS, allow_null=True, required=False)


def reference_data(obj):
    data = {"id":str(obj.id),"code":obj.code,"name":obj.name,"is_active":obj.is_active,"version":obj.version}
    if isinstance(obj,LetterJournal):data.update(direction=obj.direction,department_id=str(obj.department_id) if obj.department_id else None)
    if isinstance(obj,ControlClosureReason):data["rule"]=obj.rule
    if isinstance(obj,AuthorityType):data['report_group']=obj.report_group
    return data


def catalog_model(catalog):
    if catalog not in CATALOGS:
        raise NotFound("Справочник не найден.")
    return CATALOGS[catalog]


class ReferenceListView(GenericAPIView):
    def get(self,request,catalog):
        model = catalog_model(catalog)
        options = ["references.view","references.manage"]
        if catalog == "departments":
            options += ["access.roles.assign","employees.org_assignments.manage","receipts.create","receipts.amend","expertise.view","expertise.register","expertise.assign","expertise.reassign"]
        elif catalog == "positions":
            options += ["employees.org_assignments.manage"]
        elif catalog == "specialties":
            options += ["specialties.training.manage","specialties.qualify","expertise.view","expertise.register","expertise.assign","expertise.reassign"]
        elif catalog in ("sndz-reasons","unresolved-question-reasons","return-reasons"):
            options += ["expertise.view","expertise.result.draft","expertise.complete","expertise.closed.correct","expertise.return_without_execution"]
        elif catalog in ("letter-kinds","letter-journals","dispatch-channels","control-closure-reasons"):
            options += ["letters.view","letters.draft","letters.register","control.view","control.assign"]
        elif catalog == "issue-methods":
            options += ["issue.view","issue.prepare","issue.check","issue.confirm"]
        elif catalog == 'authority-types':
            options += ['expertise.view','expertise.work.update','expertise.closed.correct']
        require_any_scope(request.user,*options)
        queryset = model.objects.all()
        if search := request.query_params.get("search","").strip():
            queryset = queryset.filter(Q(name__icontains=search)|Q(code__icontains=search))
        if "is_active" in request.query_params:
            value = request.query_params["is_active"]
            if value not in ("true","false"):
                raise ValidationError({"is_active":"Ожидается true или false."})
            queryset = queryset.filter(is_active=value=="true")
        page = self.paginate_queryset(queryset)
        return self.get_paginated_response([reference_data(obj) for obj in page])

    @transaction.atomic
    def post(self,request,catalog):
        require(request.user,"references.manage")
        model = catalog_model(catalog)
        create_type = LetterJournalCreate if model is LetterJournal else ClosureReasonCreate if model is ControlClosureReason else AuthorityTypeCreate if model is AuthorityType else ReferenceCreate
        serializer = create_type(data=request.data)
        serializer.is_valid(raise_exception=True)
        from .commands import create_reference
        item = create_reference(actor=request.user,catalog=catalog,model=model,values=serializer.validated_data,key=request.headers.get('Idempotency-Key'),payload=request.data)
        return Response(reference_data(item),status=201)


class ReferenceDetailView(GenericAPIView):
    @transaction.atomic
    def patch(self,request,catalog,pk):
        require(request.user,"references.manage")
        item = get_object_or_404(catalog_model(catalog).objects.select_for_update(),pk=pk)
        serializer = (AuthorityTypeUpdate if isinstance(item,AuthorityType) else ReferenceUpdate)(data=request.data)
        serializer.is_valid(raise_exception=True)
        from .commands import update_reference
        item = update_reference(actor=request.user,catalog=catalog,item=item,values=serializer.validated_data,key=request.headers.get('Idempotency-Key'),payload=request.data)
        return Response(reference_data(item))
