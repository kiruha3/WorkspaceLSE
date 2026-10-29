"""Complete registry projection. Full workflow data belongs to the detail API."""
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from apps.accounts.policies import permission_scopes
from .policies import expertise_scope_queryset
from .query import filter_registry
from .ordering import ordered_registry,registry_queryset

def registry_data(work):
    history=getattr(work,'historical',None) if work.origin_kind=='historical' else None
    return {
        'id':str(work.pk),'origin_kind':work.origin_kind,'registration_number':work.registration_number,
        'historical_number':work.historical_number,
        'receipt':{'received_at':work.receipt.received_at.isoformat()},
        'material':{'title':work.material.title,'is_demo':work.material.is_demo},
        'department':{'code':work.department.code,'name':work.department.name},
        'specialty':{'code':work.specialty.code,'name':work.specialty.name} if work.specialty_id else None,
        'current_assignments':[{'id':str(item.pk),'employee':{'id':str(item.employee_id),'full_name':item.employee.full_name}} for item in work.assignments.all() if item.ended_at is None],
        'historical':{'current_participants':[{'id':str(item.employee_id),'full_name':item.employee.full_name} for item in history.participants.all()]} if history else None,
        'appointment_nature':work.appointment_nature,'is_commission':work.is_commission,
        'complex_group':{'id':str(work.complex_group_id),'title':work.complex_group.title} if work.complex_group_id else None,
        'state':work.state,
    }

class ExpertiseRegistryView(GenericAPIView):
    def get(self,request):
        queryset=expertise_scope_queryset(request.user,'expertise.view',permission_scopes(request.user))
        queryset=registry_queryset(filter_registry(queryset,request.query_params))
        rows=[registry_data(work) for work in ordered_registry(queryset,request.query_params)]
        return Response({'count':len(rows),'results':rows})
