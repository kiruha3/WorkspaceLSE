"""Registry filters shared by the paginated list and the complete export."""
from django.db.models import Q
from .calendar_query import filter_calendar_days
from .serializers import WorkFilters


def filter_registry(queryset, params):
    form = WorkFilters(data=params)
    form.is_valid(raise_exception=True)
    filters = form.validated_data
    for field in ('department_id', 'specialty_id'):
        if field in filters:
            queryset = queryset.filter(**{field: filters[field]})
    if filters.get('employee_id'):
        employee_id = filters['employee_id']
        queryset = queryset.filter(
            Q(assignments__employee_id=employee_id, assignments__ended_at__isnull=True) |
            Q(origin_kind='historical', assignments__isnull=True, historical__participants__employee_id=employee_id)
        )
    if filters.get('received_from'):
        queryset = queryset.filter(receipt__received_at__gte=filters['received_from'])
    if filters.get('received_to'):
        queryset = queryset.filter(receipt__received_at__lte=filters['received_to'])
    if 'state' in filters:
        queryset = queryset.filter(state=filters['state'])
    queryset = filter_calendar_days(queryset, filters)
    if search := filters.get('search'):
        queryset = queryset.filter(Q(registration_number__icontains=search) | Q(material__title__icontains=search))
    return queryset.distinct()
