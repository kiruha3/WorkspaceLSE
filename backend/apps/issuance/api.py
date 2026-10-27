from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from apps.accounts.policies import permission_scopes, AccessScope
from apps.accounts.services import require_any_scope
from apps.documents.models import Document
from apps.documents.policies import can_document, document_context
from apps.documents.serializers import DocumentOutput
from apps.intake.models import Material
from apps.references.models import IssueMethod
from apps.references.api import reference_data
from .models import IssuePackage, ITEM_KINDS
from .policies import package_queryset, require_material, material_queryset
from .serializers import ContentInput, DraftInput, PackageFilters, package_data
from .readiness import readiness, DOCUMENT_KINDS
from .drafts import create_package, save_package
from .command_serializers import CheckInput, IssueInput
from .commands import check_package, issue_material


def loaded(queryset=None):
    return (queryset if queryset is not None else IssuePackage.objects.all()).select_related("material", "current_revision", "issuance__method", "issuance__actor__employee", "issuance__evidence_document").prefetch_related(
        "revisions__actor__employee", "revisions__items__document__versions", "checks__actor__employee", "checks__works", "checks__files__document__versions", "issuance__evidence_document__versions")


def read_package(request, pk):
    package = get_object_or_404(loaded(), pk=pk)
    require_material(request.user, "issue.view", package.material)
    return package


def command_response(request, result, status=200):
    package = read_package(request, result["package_id"])
    return Response({"event": {"id": result["id"]}, "package": package_data(package, request.user)}, status=status)


class MaterialPackagesView(GenericAPIView):
    def get(self, request, pk):
        material = get_object_or_404(Material, pk=pk); scopes = permission_scopes(request.user)
        require_material(request.user, "issue.view", material, scopes)
        package = loaded().filter(material=material).first()
        return Response({"material": {"id": str(material.pk), "title": material.title}, "package": package_data(package, request.user, scopes) if package else None,
            "can_prepare": material_queryset(request.user, "issue.prepare", scopes).filter(pk=material.pk).exists() and not (package and getattr(package, "issuance", None))})

    def post(self, request, pk):
        form = ContentInput(data=request.data); form.is_valid(raise_exception=True)
        return command_response(request, create_package(actor=request.user, material_id=pk, data=form.validated_data, key=request.headers.get("Idempotency-Key"), payload=request.data), 201)


class PackageListView(GenericAPIView):
    def get(self, request):
        scopes = permission_scopes(request.user)
        require_any_scope(request.user, "issue.view")
        form = PackageFilters(data=request.query_params); form.is_valid(raise_exception=True); data = form.validated_data
        queryset = package_queryset(request.user, scopes=scopes)
        if data.get("search"): queryset = queryset.filter(Q(material__title__icontains=data["search"]) | Q(material__expertises__registration_number__icontains=data["search"])).distinct()
        if data.get("issued_from"): queryset = queryset.filter(issuance__issued_on__gte=data["issued_from"])
        if data.get("issued_to"): queryset = queryset.filter(issuance__issued_on__lte=data["issued_to"])
        if data.get("state") == "issued": queryset = queryset.filter(issuance__isnull=False)
        elif data.get("state"): queryset = queryset.filter(issuance__isnull=True)
        if data.get("state") and data["state"] != "issued":
            # These states depend on live file and closure facts, not a stale flag.
            rows = [package_data(package, request.user, scopes) for package in loaded(queryset)]
            rows = [row for row in rows if row["state"] == data["state"]]
            return self.get_paginated_response(self.paginate_queryset(rows))
        page = self.paginate_queryset(loaded(queryset))
        return self.get_paginated_response([package_data(package, request.user, scopes) for package in page])


class PackageDetailView(GenericAPIView):
    def get(self, request, pk): return Response(package_data(read_package(request, pk), request.user))


class PackageReadinessView(GenericAPIView):
    def get(self, request, pk): return Response(readiness(read_package(request, pk), request.user))


class PackageDraftView(GenericAPIView):
    def post(self, request, pk):
        form = DraftInput(data=request.data); form.is_valid(raise_exception=True)
        return command_response(request, save_package(actor=request.user, package_id=pk, data=form.validated_data, key=request.headers.get("Idempotency-Key"), payload=request.data))


class IssueOptionsView(GenericAPIView):
    def get(self, request):
        require_any_scope(request.user, "issue.view", "issue.prepare", "issue.check", "issue.confirm")
        return Response({"methods": [reference_data(method) for method in IssueMethod.objects.all()],
            "item_kinds": [{"code": code, "name": label, "document_kinds": DOCUMENT_KINDS[code]} for code, label in ITEM_KINDS]})


class DocumentOptionsView(GenericAPIView):
    def get(self, request, pk):
        read_package(request, pk)
        kind = request.query_params.get("kind")
        if kind not in DOCUMENT_KINDS: raise ValidationError({"kind": "Выберите назначение документа."})
        query = Document.objects.filter(kind__in=DOCUMENT_KINDS[kind]).prefetch_related("versions").order_by("-created_at", "pk")
        if search := request.query_params.get("search", "").strip(): query = query.filter(title__icontains=search)
        scope = permission_scopes(request.user).get("documents.view", AccessScope())
        allowed = [document for document in query if scope.allows(**document_context(document)) or can_document(request.user, "documents.view", document)]
        page = self.paginate_queryset(allowed)
        return self.get_paginated_response(DocumentOutput(page, many=True).data)


class PackageCommandView(GenericAPIView):
    command = "check"

    def post(self, request, pk):
        serializer, command = (CheckInput, check_package) if self.command == "check" else (IssueInput, issue_material)
        form = serializer(data=request.data); form.is_valid(raise_exception=True)
        return command_response(request, command(actor=request.user, package_id=pk, data=form.validated_data, key=request.headers.get("Idempotency-Key"), payload=request.data))


class WorkIssueStatusView(GenericAPIView):
    def get(self, request, pk):
        from apps.expertises.models import Expertise
        from apps.expertises.policies import require_work, work_context
        from .models import MaterialIssue
        work = get_object_or_404(Expertise.objects.select_related("material").prefetch_related("assignments"), pk=pk)
        scopes = permission_scopes(request.user)
        require_work(request.user, "expertise.view", work, scopes)
        if not scopes.get("issue.view", AccessScope()).allows(**work_context(work, request.user, scopes)):
            return Response({"status": "unavailable", "issued_on": None, "package": None})
        package = IssuePackage.objects.filter(material=work.material).first()
        issue = MaterialIssue.objects.filter(package=package).first() if package else None
        link = None
        if package:
            link = {"id": str(package.pk)}
            if not material_queryset(request.user, "issue.view", scopes).filter(pk=work.material_id).exists(): link["restricted"] = True
        return Response({"status": "issued" if issue else "not_issued", "issued_on": issue.issued_on if issue else None, "package": link})
