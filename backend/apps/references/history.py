from django.shortcuts import get_object_or_404
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from apps.accounts.services import require_any_scope
from apps.audit.models import AuditEvent
from .api import catalog_model


class ReferenceHistoryView(GenericAPIView):
    def get(self, request, catalog, pk):
        require_any_scope(request.user, 'references.view', 'references.manage')
        item = get_object_or_404(catalog_model(catalog), pk=pk)
        events = AuditEvent.objects.filter(object_type=item._meta.label_lower, object_id=str(item.pk)).select_related('actor__employee')
        return Response([{
            'id': str(event.pk), 'action': event.action, 'reason': event.reason,
            'created_at': event.created_at, 'changes': event.changes,
            'actor': {'id': str(event.actor_id), 'full_name': getattr(getattr(event.actor,'employee',None),'full_name',event.actor.username)} if event.actor_id else None,
        } for event in events])
