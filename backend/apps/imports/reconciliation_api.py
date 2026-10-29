from collections import Counter
from django.shortcuts import get_object_or_404
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from apps.personnel.models import Employee
from apps.references.models import Department,Specialty
from .api import read_batch
from .models import ImportSelection,ImportApplication
from .serializers import row_data
from .reconciliation import classify_row,ReconciliationContext,selection_data,save_selection,require_reconcile,reference_data
from .reconciliation_serializers import SelectionInput,ApplyInput,ReconciliationFilters
from .application import apply_selection,application_data,require_apply
from .policies import require_preview_read
from .updates import update_preview


class ReconciliationOptionsView(GenericAPIView):
    def get(self,request):
        require_reconcile(request.user)
        return Response({"departments":[reference_data(ref) for ref in Department.objects.all()],"specialties":[reference_data(ref) for ref in Specialty.objects.all()],
            "employees":[{"id":str(person.pk),"full_name":person.full_name,"is_active":person.is_active} for person in Employee.objects.all().order_by("full_name","pk")]})


class ReconciliationView(GenericAPIView):
    def get(self,request,pk):
        batch=read_batch(request.user,pk)
        form=ReconciliationFilters(data=request.query_params);form.is_valid(raise_exception=True);filters=form.validated_data
        rows=list(batch.rows.select_related("selection").prefetch_related("selection__employees"))
        context=ReconciliationContext.for_rows(rows)
        by_id={str(row.pk):row for row in rows}
        classified=[{"row":row_data(row),**classify_row(row,context),"selection":selection_data(getattr(row,"selection",None))} for row in rows]
        for item in classified:
            if item['classification']=='changed':
                source=by_id[item['row']['id']]
                item['update_preview']=update_preview(source,context.works[source.facts['registration_number']])
        counts=Counter(item["classification"] for item in classified)
        if filters.get("classification"):classified=[item for item in classified if item["classification"]==filters["classification"]]
        if filters.get("search"):
            term=filters["search"].casefold()
            classified=[item for item in classified if term in " ".join(str(item["row"]["facts"].get(field) or "") for field in ("registration_number","executor_raw","case_description","authority_name")).casefold()]
        from apps.common.ordering import ordered_rows,ordering_key
        fields={
            'number':lambda r:r['row']['facts'].get('registration_number') or r['row']['raw'].get('B'),
            'classification':lambda r:{'new':'Новая','unchanged':'Совпадает','changed':'Изменена','invalid':'Нужна проверка'}[r['classification']],
            'department':lambda r:(r['row']['facts'].get('department_code'),(r.get('suggested_specialty') or {}).get('code')),
            'executor':lambda r:r['row']['facts'].get('executor_raw'),
            'selection':lambda r:(bool(r.get('selection')),(r.get('selection') or {}).get('version')),
        }
        classified=ordered_rows(classified,ordering_key(request.query_params,fields),fields)
        response=self.get_paginated_response(self.paginate_queryset(classified))
        response.data.update(batch_id=str(batch.pk),summary={key:counts[key] for key in ("new","unchanged","changed","invalid")})
        return response


class SelectionView(GenericAPIView):
    def put(self,request,pk,row_pk):
        require_reconcile(request.user)
        batch=read_batch(request.user,pk);get_object_or_404(batch.rows,pk=row_pk)
        form=SelectionInput(data=request.data);form.is_valid(raise_exception=True)
        result=save_selection(actor=request.user,row_id=row_pk,data=form.validated_data,key=request.headers.get("Idempotency-Key"),payload=request.data)
        require_reconcile(request.user)
        selection=get_object_or_404(ImportSelection.objects.prefetch_related("employees"),pk=result["selection_id"])
        return Response({"event":{"id":result["id"]},"selection":selection_data(selection)})


class ApplicationView(GenericAPIView):
    def post(self,request,pk):
        require_apply(request.user)
        form=ApplyInput(data=request.data);form.is_valid(raise_exception=True)
        result=apply_selection(actor=request.user,batch_id=pk,**form.validated_data,key=request.headers.get("Idempotency-Key"),payload=request.data)
        require_apply(request.user)
        application=get_object_or_404(ImportApplication,pk=result["application_id"])
        return Response({"event":{"id":result["id"]},"application":application_data(application)},status=201)


class ApplicationDetailView(GenericAPIView):
    def get(self,request,pk):
        require_preview_read(request.user)
        return Response(application_data(get_object_or_404(ImportApplication,pk=pk)))
