from django.http import HttpResponse
from django.utils import timezone
from rest_framework.generics import GenericAPIView

from apps.accounts.policies import permission_scopes
from apps.issuance.policies import material_queryset
from .journal_export import MIME, build_journal
from .policies import expertise_scope_queryset
from .query import filter_registry


class ExpertiseExportView(GenericAPIView):
    def get(self, request):
        scopes = permission_scopes(request.user)
        visible = expertise_scope_queryset(request.user, 'expertise.view', scopes)
        exportable = expertise_scope_queryset(request.user, 'expertise.export', scopes)
        queryset = filter_registry(visible.filter(pk__in=exportable.values('pk')), request.query_params)
        # Apply the shared package ACL once: every sibling work must be readable
        # and allowed for issue.view even when that sibling is outside the filter.
        issue_material_ids = material_queryset(request.user, 'issue.view', scopes).filter(
            pk__in=queryset.values('material_id')
        ).values_list('pk', flat=True)
        from django.db.models import Case,When,IntegerField
        from .ordering import ordered_registry
        ordered=ordered_registry(queryset,request.query_params)
        if isinstance(ordered,list) and ordered:
            queryset=queryset.order_by(Case(*[When(pk=item.pk,then=index) for index,item in enumerate(ordered)],output_field=IntegerField()))
        content = build_journal(queryset, issue_material_ids=issue_material_ids)
        response = HttpResponse(content, content_type=MIME)
        response['Content-Disposition'] = f'attachment; filename="expertises-{timezone.localdate():%Y-%m-%d}.xlsx"'
        response['Cache-Control'] = 'no-store'
        return response
