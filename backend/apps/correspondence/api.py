from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from apps.accounts.policies import AccessScope, active_employee, permission_scopes
from apps.accounts.services import require_any_scope
from apps.expertises.policies import require_work
from apps.expertises.models import Expertise
from apps.references.api import reference_data
from apps.references.models import Department, LetterKind, LetterJournal, DispatchChannel, ControlClosureReason
from .models import Letter, LetterRevision, LetterAttachment, LetterRegistration, LetterDispatch, LetterDelivery, LetterReceipt, ControlEvent
from .policies import letter_scope_queryset, require_letter, visible_works, material_queryset
from .serializers import LetterCreate, DraftInput, AttachmentInput, letter_data, letter_summary, person_data
from .drafts import create_letter, save_draft, attach_document


def loaded(queryset=None):
    queryset = Letter.objects.all() if queryset is None else queryset
    revisions = LetterRevision.objects.select_related("kind", "material", "actor", "parent__current_revision", "parent__registration").prefetch_related("expertises", "recipients")
    attachments = LetterAttachment.objects.select_related("document", "actor").prefetch_related("document__versions")
    dispatches = LetterDispatch.objects.select_related("actor", "channel", "evidence_document").prefetch_related("recipients", "evidence_document__versions", "files__file_version__document__versions")
    deliveries = LetterDelivery.objects.select_related("actor", "evidence_document").prefetch_related("evidence_document__versions")
    events = ControlEvent.objects.select_related("actor", "closure_reason", "reply__current_revision")
    return queryset.select_related("department", "responsible", "current_revision", "registration__journal", "registration__actor", "control", "receipt_fact__actor", "receipt_fact__evidence_document").prefetch_related(
        Prefetch("revisions", queryset=revisions), Prefetch("attachments", queryset=attachments), Prefetch("dispatches", queryset=dispatches),
        Prefetch("dispatches__deliveries", queryset=deliveries), "registration__files__file_version__document__versions", "receipt_fact__evidence_document__versions",
        "assignment_history__actor", "assignment_history__previous", "assignment_history__responsible", "current_revision__recipients", Prefetch("control__events", queryset=events))


def command_response(request, result, *, status=200):
    letter = loaded().get(pk=result["letter_id"])
    require_letter(request.user, "letters.view", letter)
    return Response({"event": {"id": result["id"]}, "letter": letter_data(letter, request.user)}, status=status)


class LetterListView(GenericAPIView):
    def get(self, request):
        scopes = permission_scopes(request.user)
        queryset = letter_scope_queryset(request.user, "letters.view", scopes)
        for param, field in [("direction", "direction"), ("kind_id", "current_revision__kind_id"), ("responsible_id", "responsible_id"), ("department_id", "department_id")]:
            value = request.query_params.get(param)
            if value:
                if param.endswith("_id"):
                    from rest_framework.fields import UUIDField
                    value = UUIDField().run_validation(value)
                elif value not in ("incoming", "outgoing"):
                    raise ValidationError({param: "Неизвестное направление."})
                queryset = queryset.filter(**{field: value})
        if work_id := request.query_params.get("expertise_id"):
            from rest_framework.fields import UUIDField
            work_id = UUIDField().run_validation(work_id)
            if not visible_works(request.user, scopes).filter(pk=work_id).exists(): queryset = queryset.none()
            else: queryset = queryset.filter(current_revision__expertises=work_id)
        if state := request.query_params.get("state"):
            if state not in ("draft", "registered", "partially_sent", "sent"): raise ValidationError({"state": "Неизвестное состояние."})
            from .queries import with_letter_state
            queryset = with_letter_state(queryset).filter(computed_state=state)
        from .queries import filter_dates, filter_control
        queryset = filter_dates(queryset, request.query_params)
        if request.query_params.get("control_status"): queryset = filter_control(queryset, request.user, request.query_params["control_status"], scopes)
        if search := request.query_params.get("search", "").strip():
            queryset = queryset.filter(Q(current_revision__subject__icontains=search) | Q(current_revision__sender_name__icontains=search) | Q(current_revision__external_number__icontains=search) | Q(registration__registration_number__icontains=search))
        from apps.common.ordering import paginated_data
        return paginated_data(self,request,loaded(queryset),lambda rows:[letter_data(item,request.user,scopes) for item in rows],{
            'number':lambda r:((r.get('registration') or {}).get('registration_number'),r['content'].get('subject')),
            'direction':lambda r:('Входящее' if r['direction']=='incoming' else 'Исходящее',(r['content'].get('kind') or {}).get('name')),
            'registered_on':lambda r:((r.get('registration') or {}).get('registered_on'),r.get('received_on')),
            'responsible':lambda r:(r.get('responsible') or {}).get('full_name'),
            'state':lambda r:{'draft':'Черновик','registered':'Зарегистрировано','partially_sent':'Отправлено части адресатов','sent':'Отправлено всем адресатам'}.get(r['state']),
            'control':lambda r:('Открыт' if (r.get('control') or {}).get('status')=='open' else 'Закрыт',(r.get('control') or {}).get('due_on')) if r.get('control') else None,
        })

    def post(self, request):
        form = LetterCreate(data=request.data); form.is_valid(raise_exception=True)
        result = create_letter(actor=request.user, data=form.validated_data, key=request.headers.get("Idempotency-Key"), payload=request.data)
        return command_response(request, result, status=201)


class LetterDetailView(GenericAPIView):
    def get(self, request, pk):
        letter = get_object_or_404(loaded(), pk=pk)
        require_letter(request.user, "letters.view", letter)
        return Response(letter_data(letter, request.user))


class DraftView(GenericAPIView):
    def post(self, request, pk):
        form = DraftInput(data=request.data); form.is_valid(raise_exception=True)
        return command_response(request, save_draft(actor=request.user, letter_id=pk, data=form.validated_data, key=request.headers.get("Idempotency-Key"), payload=request.data))


class AttachmentView(GenericAPIView):
    def post(self, request, pk):
        form = AttachmentInput(data=request.data); form.is_valid(raise_exception=True)
        return command_response(request, attach_document(actor=request.user, letter_id=pk, data=form.validated_data, key=request.headers.get("Idempotency-Key"), payload=request.data))


class LetterOptionsView(GenericAPIView):
    def get(self, request):
        require_any_scope(request.user, "letters.view", "letters.draft", "letters.register")
        scopes = permission_scopes(request.user); employee = active_employee(request.user)
        from django.utils import timezone
        draft = scopes.get("letters.draft", AccessScope())
        today = timezone.localdate()
        org_ids = set(employee.org_assignments.filter(Q(valid_from__isnull=True) | Q(valid_from__lte=today), Q(valid_to__isnull=True) | Q(valid_to__gte=today)).values_list("department_id", flat=True)) if employee else set()
        linked_ids = set(visible_works(request.user, scopes).values_list("department_id", flat=True))
        departments = [d for d in Department.objects.all() if draft.allows(employee_id=None, department_ids=[d.pk]) or (d.pk in org_ids | linked_ids and draft.allows(employee_id=str(employee.pk) if employee else None, department_ids=[d.pk]))]
        from apps.personnel.models import Employee
        from .commands import can_assign_employee
        employees = [p for p in Employee.objects.filter(is_active=True).select_related("user").prefetch_related("org_assignments") if can_assign_employee(request.user, p, scopes)]
        return Response({
            "kinds": [reference_data(r) for r in LetterKind.objects.all()],
            "journals": [reference_data(r) for r in LetterJournal.objects.all()],
            "channels": [reference_data(r) for r in DispatchChannel.objects.all()],
            "closure_reasons": [reference_data(r) for r in ControlClosureReason.objects.all()],
            "departments": [reference_data(r) for r in departments],
            "employees": [person_data(p) for p in employees],
        })


class WorkOptionsView(GenericAPIView):
    def get(self, request):
        require_any_scope(request.user, "letters.draft")
        from apps.expertises.policies import expertise_scope_queryset
        scopes = permission_scopes(request.user)
        queryset = visible_works(request.user, scopes).filter(pk__in=expertise_scope_queryset(request.user, "letters.draft", scopes)).select_related("material")
        if search := request.query_params.get("search", "").strip(): queryset = queryset.filter(Q(registration_number__icontains=search) | Q(material__title__icontains=search))
        page = self.paginate_queryset(queryset)
        return self.get_paginated_response([{"id": str(w.pk), "registration_number": w.registration_number, "material": {"id": str(w.material_id), "title": w.material.title}} for w in page])


class MaterialOptionsView(GenericAPIView):
    def get(self, request):
        require_any_scope(request.user, "letters.draft")
        queryset = material_queryset(request.user).order_by("title", "id")
        if search := request.query_params.get("search", "").strip(): queryset = queryset.filter(title__icontains=search)
        page = self.paginate_queryset(queryset)
        return self.get_paginated_response([{"id": str(m.pk), "title": m.title} for m in page])


class ExpertiseLettersView(GenericAPIView):
    def get(self, request, pk):
        work = get_object_or_404(Expertise.objects.prefetch_related("assignments"), pk=pk)
        scopes = permission_scopes(request.user); require_work(request.user, "expertise.view", work, scopes)
        queryset = letter_scope_queryset(request.user, "letters.view", scopes).filter(current_revision__expertises=pk).select_related("current_revision")
        page = self.paginate_queryset(queryset)
        return self.get_paginated_response([letter_summary(letter) for letter in page])
