"""Hand-checked official-template columns, never inferred from result prose."""
from datetime import date
from io import BytesIO
from itertools import count
from zipfile import ZipFile
from xml.etree import ElementTree as ET
import pytest
from django.test import Client
from apps.documents.models import Document
from apps.expertises.models import Expertise,ResultRevision,UnresolvedAllocation,WorkClosure
from apps.intake.models import Material,Receipt
from apps.references.models import Department,Specialty,SndzReason,ReturnReason,UnresolvedQuestionReason
from apps.reports.registry import calculate_registry,ReportRecord
from apps.reports.calculation import calculate
from historical_samples import historical_setup


def cell(report,section,address):
    found=[c for c in report['cells'] if c['sheet']==f'Раздел {section}' and c['address']==address]
    assert len(found)==1,f'Missing reason cell {section}:{address}'
    return found[0]


@pytest.fixture
def accepted_work(employee_factory):
    actor=employee_factory();numbers=count(1)
    dept=Department.objects.create(code='3',name='Отдел3')
    specialty=Specialty.objects.create(code='16.1',name='Строительная')
    def make(*,kind='expert_conclusion',sndz=None,returned=None,ended=date(2026,10,10),allocations=(),complete=False,**counts):
        n=next(numbers);material=Material.objects.create(created_by=actor)
        receipt=Receipt.objects.create(material=material,received_at=date(2026,10,1),created_by=actor,status='accepted')
        work=Expertise.objects.create(material=material,receipt=receipt,registration_number=f'{n}/3-{6 if kind=="research_act" else 1}-26',sequence=n,year=2026,category_code='6' if kind=='research_act' else '1',department=dept,specialty=specialty,appointment_nature='primary',is_commission=False,state='without_execution' if returned else 'completed',registered_by=actor.user)
        doc=Document.objects.create(kind='return_decision' if returned else kind,source_kind='paper_original',created_by=actor)
        result=None
        if not returned:
            reason=SndzReason.objects.get_or_create(code=sndz,defaults={'name':sndz})[0] if sndz else None
            result=ResultRevision.objects.create(expertise=work,number=1,kind=kind,completed_on=ended,document=doc,actor=actor.user,reason='Контрольный принятый результат',sndz_reason=reason,allocations_complete=complete,**counts)
            for code,quantity in allocations:
                ref=UnresolvedQuestionReason.objects.get_or_create(code=code,defaults={'name':code})[0]
                UnresolvedAllocation.objects.create(result=result,reason=ref,count=quantity)
        reason=ReturnReason.objects.get_or_create(code=returned,defaults={'name':returned})[0] if returned else None
        closure=WorkClosure.objects.create(expertise=work,number=1,kind='without_execution' if returned else 'completed',ended_on=ended,result=result,document=doc,return_reason=reason,actor=actor.user,reason='Подтверждённый контроль')
        return work,result,closure
    return make


def report():return calculate_registry(year=2026,month=10,opening_balances_complete=True)


@pytest.mark.django_db
def test_three_sndz_reasons_count_works_not_questions_and_do_not_double_parent(accepted_work):
    for code in ('outside_expert_knowledge','materials_insufficient_addition_refused','science_cannot_answer'):
        accepted_work(kind='sndz',sndz=code,questions=20,unresolved=20)
    result=report()
    assert [cell(result,1,f'{c}108')['value'] for c in 'FGHI']==[3,1,1,1]
    assert [cell(result,1,f'G{r}')['value'] for r in (58,59,108)]==[1,1,1]
    assert all(cell(result,2,f'{c}107')['value']==0 for c in 'HIJKL')
    assert not any(g['code'] in ('reasons','sndzReason','unresolvedReasons','returnReason') for g in result['gaps'])


@pytest.mark.django_db
def test_four_question_reasons_count_exact_allocations_of_accepted_result_in_one_select(accepted_work,django_assert_num_queries):
    work,_,_=accepted_work(questions=12,categorical=2,probable=0,unresolved=10,complete=True,allocations=[('methods_insufficient',1),('materials_insufficient',2),('objects_uninformative',3),('other',4)])
    with django_assert_num_queries(1):result=report()
    assert [cell(result,2,f'{c}107')['value'] for c in 'HIJKL']==[10,1,2,3,4]
    assert cell(result,2,'J107')['rows']==[str(work.pk)]
    assert cell(result,2,'J57')['value']==2 and cell(result,2,'J58')['value']==2


@pytest.mark.django_db
def test_five_return_reasons_count_decisions_in_period(accepted_work):
    for code in ('no_technical_facilities','no_required_specialist','no_special_conditions','appointing_party_request','other'):
        accepted_work(returned=code)
    result=report()
    assert [cell(result,4,f'{c}107')['value'] for c in 'OPQRST']==[5,1,1,1,1,1]
    assert cell(result,1,'F108')['value']==0 and cell(result,2,'H107')['value']==0


@pytest.mark.parametrize('kind,code,section,address,gap_code',[
    ('sndz','new_sndz',1,'G108','sndzReason'),
    ('return','new_return',4,'P107','returnReason'),
    ('allocation','new_question_reason',2,'I107','unresolvedReasons')])
@pytest.mark.django_db
def test_new_unmapped_catalogue_codes_are_unknown_not_other(accepted_work,kind,code,section,address,gap_code):
    args={'kind':'sndz','sndz':code} if kind=='sndz' else {'returned':code} if kind=='return' else {'unresolved':1,'complete':True,'allocations':[(code,1)]}
    work,_,_=accepted_work(**args);result=report()
    assert cell(result,section,address)['value'] is None
    gap=next(g for g in result['gaps'] if g['code']==gap_code)
    assert gap['rows']==[str(work.pk)]


@pytest.mark.django_db
def test_saved_inactive_reason_is_still_counted_by_semantics(accepted_work):
    _,result,_=accepted_work(kind='sndz',sndz='science_cannot_answer')
    SndzReason.objects.filter(pk=result.sndz_reason_id).update(name='Другое название',is_active=False)
    assert cell(report(),1,'I108')['value']==1


@pytest.mark.django_db
def test_newer_draft_cannot_replace_accepted_reasons_but_correction_can(accepted_work):
    work,first,closure=accepted_work(kind='sndz',sndz='outside_expert_knowledge')
    ref=SndzReason.objects.create(code='science_cannot_answer',name='Наука')
    draft=ResultRevision.objects.create(expertise=work,number=2,kind='sndz',sndz_reason=ref,actor=first.actor,reason='Черновик')
    before=report();assert cell(before,1,'G108')['value']==1 and cell(before,1,'I108')['value']==0
    WorkClosure.objects.create(expertise=work,number=2,kind='completed',ended_on=closure.ended_on,result=draft,document=closure.document,actor=closure.actor,reason='Исправление принято')
    after=report();assert cell(after,1,'G108')['value']==0 and cell(after,1,'I108')['value']==1
    assert before['data_revision']!=after['data_revision']


@pytest.mark.django_db
def test_distribution_is_in_report_revision_and_not_borrowed_from_another_result(accepted_work):
    work,result,closure=accepted_work(unresolved=3,complete=True,allocations=[('materials_insufficient',3)])
    old=report();ref=UnresolvedQuestionReason.objects.create(code='other',name='Иные')
    draft=ResultRevision.objects.create(expertise=work,number=2,kind='expert_conclusion',unresolved=3,allocations_complete=True,actor=result.actor,reason='Черновик')
    UnresolvedAllocation.objects.create(result=draft,reason=ref,count=3)
    assert report()['data_revision']==old['data_revision']
    # Defensive reader: even correction of an existing accepted allocation
    # invalidates the exact downloaded revision, independently of work.version.
    UnresolvedAllocation.objects.filter(result=result).update(reason=ref)
    new=report();assert cell(new,2,'L107')['value']==3 and cell(new,2,'J107')['value']==0
    assert new['data_revision']!=old['data_revision']


@pytest.mark.parametrize('changes',[
    {'unresolved':None}, {'complete':False}, {'allocations':[]},
    {'allocations':[('materials_insufficient',1)]}, {'questions':1,'categorical':1},
])
@pytest.mark.django_db
def test_unknown_incomplete_or_inconsistent_question_distribution_never_looks_complete(accepted_work,changes):
    args={'unresolved':2,'complete':True,'allocations':[('materials_insufficient',2)],**changes}
    work,_,_=accepted_work(**args);result=report()
    assert all(cell(result,2,f'{c}107')['value'] is None for c in 'IJKL')
    assert str(work.pk) in next(g['rows'] for g in result['gaps'] if g['code']=='unresolvedReasons')


@pytest.mark.django_db
def test_known_zero_without_distribution_is_zero_even_if_not_confirmed(accepted_work):
    accepted_work(unresolved=0,complete=False)
    result=report();assert [cell(result,2,f'{c}107')['value'] for c in 'IJKL']==[0,0,0,0]
    assert not any(g['code']=='unresolvedReasons' for g in result['gaps'])


@pytest.mark.django_db
def test_history_prose_never_classifies_sndz_or_return_or_question_reasons(employee_factory,grant,settings,tmp_path):
    _,_,work,history,_,_=historical_setup(employee_factory,grant,settings,tmp_path)
    history.result_kind='sndz';history.notes='Современный уровень науки не позволяет';history.save()
    result=report();assert cell(result,1,'G108')['value'] is None
    assert str(work.pk) in next(g['rows'] for g in result['gaps'] if g['code']=='sndzReason')
    history.result_kind='expert_conclusion';history.questions=2;history.categorical=1;history.unresolved=1;history.save()
    assert cell(report(),2,'L107')['value'] is None
    work.state='without_execution';work.save();history.return_decided_on=None;history.issued_on=date(2026,10,20);history.save()
    result=report();assert cell(result,4,'P107')['value'] is None
    assert any(g['code']=='returnReason' and str(work.pk) in g['rows'] for g in result['gaps'])


@pytest.mark.django_db
def test_period_demo_and_unknown_specialty_preserve_reason_totals(accepted_work):
    accepted_work(kind='sndz',sndz='outside_expert_knowledge',ended=date(2026,11,1))
    demo,_,_=accepted_work(kind='sndz',sndz='science_cannot_answer');demo.material.is_demo=True;demo.material.save()
    work,_,_=accepted_work(kind='sndz',sndz='materials_insufficient_addition_refused')
    work.origin_kind='historical';work.specialty=None;work.save()
    result=report();assert [cell(result,1,f'{c}108')['value'] for c in 'GHI']==[0,1,0]
    assert cell(result,1,'H65')['value'] is None
    assert result['source']['excluded_demo_count']==1


@pytest.mark.django_db
def test_empty_registry_has_known_reason_zeroes_and_journal_shape_unchanged():
    result=report();assert len(result['cells'])==996
    assert cell(result,1,'P108')['value']==0
    assert cell(result,1,'G108')['value']==0 and cell(result,2,'I107')['value']==0 and cell(result,4,'T107')['value']==0
    sample=ReportRecord('row',{'registration_number':'1/3-1-26','received_on':'2026-01-01','source_end_on':'2026-02-01','state':'completed','category_code':'1','specialty_code':'1.1','result_kind':'sndz'}, {})
    old=calculate([sample],2026,10)
    assert len(old['cells'])==660 and any(g['code']=='reasons' for g in old['gaps'])
    assert not any(c['sheet']=='Раздел 1' and c['address']=='G108' for c in old['cells'])


@pytest.mark.parametrize('allocations',[
    [{'reason':'other','count':1},{'reason':'other','count':1}],
    [{'reason':'other','count':0}], [{'reason':'other','count':-1}],
    [{'reason':'other','count':True}], [{'reason':'other','count':2.0}],
    [{'reason':'other','count':3}], ['not-a-typed-allocation'],
])
def test_malformed_distribution_is_unknown_not_a_valid_reason_total(allocations):
    facts={'registration_number':'1/3-1-26','received_on':'2026-01-01','source_end_on':'2026-02-01','state':'completed','category_code':'1','specialty_code':'1.1','result_kind':'expert_conclusion','questions':2,'categorical':0,'probable':0,'unresolved':2,'allocations_complete':True,'unresolved_allocations':allocations}
    result=calculate([ReportRecord('work',facts,{})],2026,10,mode='registry')
    assert [cell(result,2,f'{c}107')['value'] for c in 'IJKL']==[None,None,None,None]
    assert next(g['rows'] for g in result['gaps'] if g['code']=='unresolvedReasons')==['work']


@pytest.mark.django_db
def test_result_command_through_own_expert_completion_to_report_and_export(employee_factory,grant,settings,tmp_path):
    from test_result_completion import completion_setup,ready_result,send
    from test_result_drafts import reasons
    settings.MEDIA_ROOT=tmp_path
    client,actor,work,_,_,_,_=completion_setup(employee_factory,grant)
    options=reasons(client,work);reason=next(r for r in options['sndz_reasons'] if r['code']=='science_cannot_answer')
    work=ready_result(client,work,kind='sndz',sndz_reason_id=reason['id'])
    completed=send(client,work,'complete',result_id=work['result']['id']);assert completed.status_code==200
    for action in ('expertise.view','reports.form151.run','reports.form151.download'):grant(actor,action)
    url='/api/v1/reports/form151/?source=registry&year=2026&month=10'
    data=client.get(url).json();assert cell(data,1,'I108')['value']==1
    archive=client.get(data['download_url']);assert archive.status_code==200
    with ZipFile(BytesIO(archive.content)) as z:
        xml=ET.fromstring(z.read('xl/worksheets/sheet2.xml'))
        assert xml.find(".//s:c[@r='I108']/s:v",{'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}).text=='1'
    ref=SndzReason.objects.create(code='outside_expert_knowledge',name='Вне знаний') if not SndzReason.objects.filter(code='outside_expert_knowledge').exists() else SndzReason.objects.get(code='outside_expert_knowledge')
    ResultRevision.objects.filter(pk=work['result']['id']).update(sndz_reason=ref)
    assert client.get(data['download_url']).status_code==409
