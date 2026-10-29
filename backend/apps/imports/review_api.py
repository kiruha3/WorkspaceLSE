from rest_framework import serializers
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from apps.accounts.serializers import StrictSerializer
from .api import read_batch
from .review import review_batch,apply_review


class ReviewChoice(StrictSerializer):
    row_id=serializers.UUIDField()
    action=serializers.ChoiceField(choices=['create','update'])
    expected_work_version=serializers.IntegerField(min_value=1,allow_null=True)
    expected_source_row_id=serializers.UUIDField(allow_null=True)
    expected_selection_version=serializers.IntegerField(min_value=0)
    proposal_hash=serializers.RegexField(r'^[0-9a-f]{64}$')
    accepted_fields=serializers.ListField(child=serializers.CharField(max_length=100),max_length=100)

    def validate_accepted_fields(self,values):
        if len(set(values))!=len(values):raise serializers.ValidationError('Поле выбрано повторно.')
        return values


class ReviewInput(StrictSerializer):
    selections=ReviewChoice(many=True,allow_empty=False,max_length=1000)

    def validate_selections(self,values):
        if len({item['row_id'] for item in values})!=len(values):raise serializers.ValidationError('Строка выбрана повторно.')
        return values


class ReviewView(GenericAPIView):
    def get(self,request,pk):
        return Response(review_batch(read_batch(request.user,pk)))

    def post(self,request,pk):
        form=ReviewInput(data=request.data);form.is_valid(raise_exception=True)
        result=apply_review(actor=request.user,batch_id=pk,**form.validated_data,key=request.headers.get('Idempotency-Key'),payload=request.data)
        return Response(result,status=201)
