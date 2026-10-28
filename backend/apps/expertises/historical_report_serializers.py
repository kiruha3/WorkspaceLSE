import json
from django.core.serializers.json import DjangoJSONEncoder
from rest_framework import serializers
from apps.accounts.serializers import StrictSerializer
from apps.references.models import Specialty,ReturnReason
from apps.references.api import reference_data
from .result_serializers import ResultData,AllocationOutput
from .production_serializers import actor_data


class HistoricalResultData(ResultData):
    # An archival correction does not assert a newly signed result document.
    document_id=None


class HistoricalReturnData(StrictSerializer):
    decided_on=serializers.DateField(allow_null=True)
    return_reason_id=serializers.PrimaryKeyRelatedField(source='return_reason',queryset=ReturnReason.objects.all(),allow_null=True)
    comment=serializers.CharField(allow_blank=True)

    def validate(self,data):
        if data['return_reason'] and data['return_reason'].code=='other' and not data['comment']:
            raise serializers.ValidationError({'comment':'Для иной причины нужно пояснение.'})
        return data


class HistoricalReportInput(StrictSerializer):
    expected_version=serializers.IntegerField(min_value=1)
    reason=serializers.CharField()
    specialty_id=serializers.PrimaryKeyRelatedField(source='specialty',queryset=Specialty.objects.all(),allow_null=True)
    correction_kind=serializers.ChoiceField(choices=['result','return'])
    result=HistoricalResultData(required=False)
    return_data=HistoricalReturnData(required=False)

    def validate(self,data):
        field='result' if data['correction_kind']=='result' else 'return_data'
        other='return_data' if field=='result' else 'result'
        if field not in data or other in data:raise serializers.ValidationError('Укажите только выбранный вид уточнения.')
        return data


def ref_snapshot(value):
    return {'id':str(value.pk),'code':value.code,'name':value.name} if value else None


def historical_snapshot(work,history):
    fields=('result_kind','completed_on','return_decided_on','complexity_level','questions','categorical','probable','unresolved','statistics_confirmed','sndz_comment','allocations_complete','report_note','return_comment')
    data={**{field:getattr(history,field) for field in fields},'registration_number':work.registration_number,'state':work.state,'department_code':work.registration_department_code,'source_row_id':str(history.source_row_id),
        'specialty':ref_snapshot(work.specialty),'sndz_reason':ref_snapshot(history.sndz_reason),'return_reason':ref_snapshot(history.return_reason),
        'unresolved_allocations':[{'reason':ref_snapshot(item.reason),'count':item.count,'comment':item.comment,'document_id':str(item.document_id) if item.document_id else None} for item in history.unresolved_allocations.all()]}
    return json.loads(json.dumps(data,cls=DjangoJSONEncoder))


def historical_report_output(history,user):
    return {'sndz_reason':reference_data(history.sndz_reason) if history.sndz_reason_id else None,'sndz_comment':history.sndz_comment,
        'allocations_complete':history.allocations_complete,'note':history.report_note,
        'unresolved_allocations':AllocationOutput(history.unresolved_allocations.all(),many=True,context={'user':user}).data,
        'return_reason':reference_data(history.return_reason) if history.return_reason_id else None,'return_comment':history.return_comment}


def historical_corrections_output(history):
    return [{'id':str(c.pk),'number':c.number,'actor':actor_data(c.actor),'created_at':c.created_at,'reason':c.reason,'before':c.before,'after':c.after} for c in history.corrections.all()]
