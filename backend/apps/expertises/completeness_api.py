from rest_framework.generics import GenericAPIView
from .policies import expertise_scope_queryset
from .completeness import completeness_queryset, missing_for


class IncompleteExpertisesView(GenericAPIView):
    def get(self, request):
        queryset = expertise_scope_queryset(request.user, 'expertise.view').order_by('-year', 'sequence', 'id')
        records = []
        for work in completeness_queryset(queryset):
            missing = missing_for(work)
            if missing:
                records.append({'id': str(work.pk), 'registration_number': work.registration_number,
                                'state': work.state, 'missing': missing})
        page = self.paginate_queryset(records)
        response = self.get_paginated_response(page)
        response['Cache-Control'] = 'no-store'
        return response
