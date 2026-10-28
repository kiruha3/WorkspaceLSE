from django.db.models import Case, When, Value, DateField, IntegerField, Subquery, OuterRef, Func, F
from django.db.models.functions import Coalesce
from django.utils import timezone
from .models import WorkClosure
from .production import OPEN_STATES


class CalendarDays(Func):
    # PostgreSQL date-date is integer days. Avoid Django's duration conversion.
    template="GREATEST((%(expressions)s) + 1, 0)"
    arg_joiner=" - "
    output_field=IntegerField()


def filter_calendar_days(queryset,filters):
    if not any(k in filters for k in ("calendar_days_min","calendar_days_max")):return queryset
    closure=WorkClosure.objects.filter(expertise_id=OuterRef("pk")).order_by("-number").values("ended_on")[:1]
    queryset=queryset.annotate(_calendar_end=Case(
        When(state__in=OPEN_STATES,then=Value(timezone.localdate(),output_field=DateField())),
        default=Coalesce(Subquery(closure,output_field=DateField()),Case(When(state="completed",then=F("historical__completed_on")),When(state="without_execution",then=F("historical__return_decided_on")),default=None,output_field=DateField())),output_field=DateField(),
    )).annotate(_calendar_days=Case(
        When(_calendar_end__isnull=False,then=CalendarDays(F("_calendar_end"),F("receipt__received_at"))),
        default=None,output_field=IntegerField(),
    )).filter(_calendar_days__isnull=False)
    for bound,lookup in (("min","gte"),("max","lte")):
        key="calendar_days_"+bound
        if key in filters:queryset=queryset.filter(**{"_calendar_days__"+lookup:filters[key]})
    return queryset
