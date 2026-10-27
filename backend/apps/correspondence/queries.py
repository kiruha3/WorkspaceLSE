from django.db.models import Case, When, Value, CharField, IntegerField, Count, F, Q, OuterRef, Subquery
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.fields import DateField
from .models import LetterRecipient, ControlEvent
from .policies import letter_scope_queryset


def with_letter_state(queryset):
    recipients = LetterRecipient.objects.filter(revision_id=OuterRef("current_revision_id"))
    sent = recipients.filter(dispatches__letter_id=OuterRef("pk"))
    total_count = recipients.order_by().values("revision_id").annotate(n=Count("id", distinct=True)).values("n")[:1]
    sent_count = sent.order_by().values("revision_id").annotate(n=Count("id", distinct=True)).values("n")[:1]
    return queryset.annotate(
        _total=Coalesce(Subquery(total_count, output_field=IntegerField()), 0),
        _sent=Coalesce(Subquery(sent_count, output_field=IntegerField()), 0),
    ).annotate(computed_state=Case(
        When(registration__isnull=True, then=Value("draft")),
        When(Q(direction="outgoing", _sent__gt=0) & Q(_sent__gte=F("_total")), then=Value("sent")),
        When(direction="outgoing", _sent__gt=0, then=Value("partially_sent")),
        default=Value("registered"), output_field=CharField(),
    ))


def filter_dates(queryset, params):
    for prefix, field in (("registered", "registration__registered_on"), ("received", "receipt_fact__received_on")):
        lower = DateField().run_validation(params[prefix + "_from"]) if params.get(prefix + "_from") else None
        upper = DateField().run_validation(params[prefix + "_to"]) if params.get(prefix + "_to") else None
        if lower and upper and lower > upper: raise ValidationError({prefix + "_to": "Конец периода раньше начала."})
        if lower: queryset = queryset.filter(**{field + "__gte": lower})
        if upper: queryset = queryset.filter(**{field + "__lte": upper})
    return queryset


def filter_control(queryset, user, status, scopes):
    if status not in ("open", "closed", "overdue"): raise ValidationError({"control_status": "Неизвестное состояние контроля."})
    allowed = letter_scope_queryset(user, "control.view", scopes)
    latest = ControlEvent.objects.filter(control_id=OuterRef("control__pk")).exclude(kind="deadline_changed").order_by("-created_at", "-id").values("kind")[:1]
    queryset = queryset.filter(pk__in=allowed, control__isnull=False).annotate(_control_state=Subquery(latest))
    if status == "closed": return queryset.filter(_control_state="closed")
    queryset = queryset.exclude(_control_state="closed")
    return queryset.filter(control__due_on__lt=timezone.localdate()) if status == "overdue" else queryset
