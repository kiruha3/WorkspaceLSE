"""15.1 facts from one database SELECT, without reading source raw/facts.

The correlated last-closure JSON joins its accepted result in the same SQL
statement as the work/history. A concurrent correction cannot mix old work
state and a newly accepted result between separate prefetch queries.
"""
from dataclasses import dataclass
from datetime import date
import hashlib
import json
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import OuterRef,Subquery,F
from django.db.models.functions import JSONObject
from django.utils import timezone
from apps.expertises.models import Expertise,WorkClosure
from .calculation import calculate

VERSION='form151-registry-v1'
RESULT_FIELDS=('result_kind','completed_on','return_decided_on','complexity_level','questions','categorical','probable','unresolved','authority_type')
COUNT_FIELDS=('complexity_level','questions','categorical','probable','unresolved')


@dataclass
class ReportRecord:
    source_row:str
    facts:dict
    raw:dict


def calculate_registry(*,year,month,opening_balances_complete=False):
    accepted=WorkClosure.objects.filter(expertise_id=OuterRef('pk')).order_by('-number').annotate(
        payload=JSONObject(id=F('pk'),number=F('number'),kind=F('kind'),ended_on=F('ended_on'),
            result_kind=F('result__kind'),sndz_reason=F('result__sndz_reason__code'),return_reason=F('return_reason__code'),
            **{field:F('result__'+field) for field in COUNT_FIELDS})
    ).values('payload')[:1]
    fields=('id','registration_number','category_code','state','origin_kind','receipt__received_at','department__code',
            'specialty__code','material__is_demo','appointment_nature','is_commission','historical__statistics_confirmed',
            'historical__source_row_id','historical__source_row__batch_id','historical__source_row__source_row',
            *('historical__'+field for field in RESULT_FIELDS))
    stored=list(Expertise.objects.annotate(accepted=Subquery(accepted)).order_by('id').values(*fields,'accepted'))
    rows=[];records={};extra=[];excluded=0;fingerprint=[]
    for item in stored:
        if item['material__is_demo']:
            excluded+=1;continue
        key=str(item['id']);closure=item['accepted']
        facts={field:item['historical__'+field] for field in RESULT_FIELDS}
        facts.update(registration_number=item['registration_number'],received_on=item['receipt__received_at'],
            category_code=item['category_code'],state=item['state'],department_code=item['department__code'],specialty_code=item['specialty__code'])
        if closure:
            facts.update({field:closure[field] for field in COUNT_FIELDS})
            facts['result_kind']=closure['result_kind']
            facts['completed_on']=closure['ended_on'] if closure['kind']=='completed' else None
            facts['return_decided_on']=closure['ended_on'] if closure['kind']=='without_execution' else None
        facts['source_end_on']=facts['completed_on'] if item['state']=='completed' else facts['return_decided_on'] if item['state']=='without_execution' else None
        facts={k:v.isoformat() if isinstance(v,date) else v for k,v in facts.items()}
        rows.append(ReportRecord(key,facts,{}))
        records[key]={'id':key,'registration_number':item['registration_number'],'origin_kind':item['origin_kind'],
            'source_batch_id':str(item['historical__source_row__batch_id']) if item['historical__source_row__batch_id'] else None,
            'source_row_id':str(item['historical__source_row_id']) if item['historical__source_row_id'] else None,
            'source_row_number':item['historical__source_row__source_row']}
        fingerprint.append(item)
        if item['state'] in ('in_progress','suspended') and (facts['completed_on'] or facts['return_decided_on']):
            extra.append(key)
    report=calculate(rows,year,month,opening_balances_complete,mode='registry')
    for gap in report['gaps']:
        if gap['code']=='reasons':gap['message']='Графы причин ещё не рассчитываются: структурированные причины из рабочих результатов и текстовые отметки истории нужно сопоставить бланку.'
        if gap['code']=='deadlines':gap['message']='Причины превышения 30 дней и учёт согласований в форме 15.1 ещё не сопоставлены.'
        if gap['code']=='repeated':gap['message']='Графы повторности и проверки прежних выводов ещё не рассчитываются; сохранённые признаки регистрации не потеряны.'
        if gap['code']=='returnDate':gap.update(message='Не указана дата решения без исполнения. Дата выдачи не заменяет её.',fields='return_decided_on / WorkClosure.ended_on')
        if gap['code']=='dates':gap.update(message='Нет достоверной даты поступления или подтверждённого окончания.',fields='received_at / completed_on / return_decided_on')
        if gap['code']=='questions':gap['fields']='questions, categorical, probable, unresolved'
        if gap['code']=='specialty':gap['fields']='specialty_id'
    if extra:report['gaps'].append({'code':'unaccepted_end','sections':list(range(1,7)),'message':'У открытой работы сохранена историческая дата окончания. Без закрытого состояния она не включена в законченные работы.','fields':'state / completed_on / return_decided_on','rows':extra})
    revision=hashlib.sha256(json.dumps({'records':fingerprint,'excluded_demo_count':excluded},sort_keys=True,cls=DjangoJSONEncoder).encode()).hexdigest()
    report.update(version=VERSION,records=records,data_revision=revision,
        source={'type':'registry','id':None,'name':'Рабочая база АИС','row_count':len(rows),'excluded_demo_count':excluded,'data_revision':revision,'calculated_at':timezone.now().isoformat()})
    return report
