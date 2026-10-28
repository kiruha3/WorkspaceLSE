from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from apps.accounts.serializers import StrictSerializer
from .application import require_apply,application_data
from .models import ImportApplication
from .updates import apply_updates


class UpdatedRow(StrictSerializer):
    row_id=serializers.UUIDField()
    expected_selection_version=serializers.IntegerField(min_value=1)
    expected_work_version=serializers.IntegerField(min_value=1)
    expected_source_row_id=serializers.UUIDField()


class UpdateInput(StrictSerializer):
    reason=serializers.CharField()
    updates=UpdatedRow(many=True,allow_empty=False,max_length=1000)
    def validate_updates(self,values):
        if len({entry['row_id'] for entry in values})!=len(values):raise serializers.ValidationError('Строка выбрана несколько раз.')
        return values


class UpdatesView(GenericAPIView):
    def post(self,request,pk):
        require_apply(request.user)
        form=UpdateInput(data=request.data);form.is_valid(raise_exception=True)
        result=apply_updates(actor=request.user,batch_id=pk,**form.validated_data,key=request.headers.get('Idempotency-Key'),payload=request.data)
        require_apply(request.user)
        application=get_object_or_404(ImportApplication,pk=result['application_id'])
        return Response({'event':{'id':result['id']},'application':application_data(application)},status=201)
