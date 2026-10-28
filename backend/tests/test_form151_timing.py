from datetime import date
from io import BytesIO
from zipfile import ZipFile
from xml.etree import ElementTree as ET
import pytest
from django.test import Client
from apps.documents.models import Document
from apps.reports.registry import calculate_registry
from test_form151_reasons import accepted_work,cell
from test_timing_facts import body,entry,refs,send
pytestmark=pytest.mark.django_db

def configure(work,grant,**changes):
 work.refresh_from_db();actor=work.registered_by.employee
 for action in ('expertise.view','expertise.closed.correct','documents.view'):grant(actor,action)
 client=Client();client.force_login(actor.user);reasons=refs(client,work)
 result=send(client,work,body(work,**changes));assert result.status_code==200,result.content
 return client,reasons

@pytest.mark.parametrize('policy,want',[('all',[1,0,1,0,0,0]),('primary',[1,0,0,0,0,0]),(None,[1,0,None,0,0,0])])
def test_multiple_reasons_and_literal_xlsx_do_not_multiply_one_work(accepted_work,grant,monkeypatch,django_assert_num_queries,policy,want):
 from apps.reports import timing_columns
 monkeypatch.setattr(timing_columns,'DELAY_REASON_POLICY',policy)
 work,_,_=accepted_work();work.receipt.received_at=date(2026,8,1);work.receipt.save(update_fields=['received_at'])
 actor=work.registered_by.employee;grant(actor,'expertise.view');grant(actor,'expertise.closed.correct');client=Client();client.force_login(actor.user);reasons=refs(client,work)
 data=body(work,reasons_complete=True,primary_reason_id=reasons['research_complexity']['id'],reasons=[entry(reasons['research_complexity']),entry(reasons['expert_workload'])])
 assert send(client,work,data).status_code==200
 with django_assert_num_queries(1):report=calculate_registry(year=2026,month=10)
 assert len(report['cells'])==996 and len(report['column_rules'])==83
 assert [cell(report,3,f'{c}107')['value'] for c in 'GHIJKL']==want
 assert cell(report,3,'G58')['value']==1
 grant(actor,'reports.form151.run');grant(actor,'reports.form151.download')
 response=client.get('/api/v1/reports/form151/',{'source':'registry','year':2026,'month':10}).json();archive=client.get(response['download_url']);assert archive.status_code==200
 with ZipFile(BytesIO(archive.content)) as z:
  root=ET.fromstring(z.read('xl/worksheets/sheet4.xml'));ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
  assert root.find('.//s:c[@r="G107"]/s:v',ns).text=='1'

@pytest.mark.parametrize('notice,notice_on,requested,request_on,want',[
 (True,'2026-10-03',True,'2026-10-04',1),(True,None,True,'2026-10-04',None),
 (False,None,None,None,0),(None,None,False,None,0),(None,None,True,'2026-10-04',None),
 (True,'2026-10-11',True,'2026-10-04',0),
])
def test_notification_and_petition_need_actual_facts_and_dates_not_just_a_request_event(accepted_work,grant,notice,notice_on,requested,request_on,want):
 work,_,_=accepted_work();doc=Document.objects.create(kind='letter',source_kind='paper_original',created_by=work.registered_by.employee)
 configure(work,grant,notification_sent=notice,notification_on=notice_on,notification_document_id=str(doc.pk) if notice else None,extension_requested=requested,request_on=request_on,request_document_id=str(doc.pk) if requested else None)
 report=calculate_registry(year=2026,month=10)
 assert cell(report,3,'M107')['value']==want
 # Only10calendar days: M/N must not inherit the >30 reason gate.
 assert cell(report,3,'D107')['value']==1 and all(cell(report,3,f'{c}107')['value']==0 for c in 'GHIJKL')

@pytest.mark.parametrize('value,want',[(True,1),(False,0),(None,None)])
def test_breach_is_an_evidence_backed_assessment_not_a_missing_agreement_guess(accepted_work,grant,value,want):
 work,_,_=accepted_work();doc=Document.objects.create(kind='decision',source_kind='paper_original',created_by=work.registered_by.employee)
 configure(work,grant,deadline_breached=value,breach_basis='Подтверждённая оценка срока' if value is not None else '',breach_document_id=str(doc.pk) if value is not None else None)
 assert cell(calculate_registry(year=2026,month=10),3,'N107')['value']==want

@pytest.mark.parametrize('kind,returned',[('sndz',None),('research_act',None),('expert_conclusion','other')])
def test_nonconclusion_outcomes_do_not_enter_timing_columns(accepted_work,grant,kind,returned):
 work,_,_=accepted_work(kind=kind,returned=returned);work.receipt.received_at=date(2026,8,1);work.receipt.save(update_fields=['received_at'])
 configure(work,grant)
 assert [cell(calculate_registry(year=2026,month=10),3,f'{c}107')['value'] for c in 'GHIJKLMN']==[0]*8

def test_draft_future_and_unaccepted_deadline_request_are_not_report_facts(accepted_work):
 from apps.expertises.models import DeadlineEvent
 work,_,_=accepted_work();work.state='in_progress';work.save(update_fields=['state'])
 DeadlineEvent.objects.create(expertise=work,kind='request',recorded_on='2026-10-03',due_on='2026-12-01',reason='Запрос не равен отправке',actor=work.registered_by)
 report=calculate_registry(year=2026,month=10);assert [cell(report,3,f'{c}107')['value'] for c in 'GHIJKLMN']==[0]*8
 work.state='completed';work.save(update_fields=['state']);report=calculate_registry(year=2026,month=10)
 assert cell(report,3,'M107')['value'] is None and cell(report,3,'N107')['value'] is None

def test_policy_and_reference_mapping_changes_invalidate_export_fingerprint(accepted_work,grant,monkeypatch):
 from apps.reports import timing_columns
 from django.apps import apps
 work,_,_=accepted_work();client,reasons=configure(work,grant)
 monkeypatch.setattr(timing_columns,'DELAY_REASON_POLICY',None);first=calculate_registry(year=2026,month=10)
 monkeypatch.setattr(timing_columns,'DELAY_REASON_POLICY','all');second=calculate_registry(year=2026,month=10)
 assert second['data_revision']!=first['data_revision']
 work.refresh_from_db();assert send(client,work,body(work,reasons=[entry(reasons['other'])])).status_code==200
 third=calculate_registry(year=2026,month=10)
 apps.get_model('references','DelayReason').objects.filter(pk=reasons['other']['id']).update(report_group=None)
 assert calculate_registry(year=2026,month=10)['data_revision']!=third['data_revision']


def test_future_accepted_completion_does_not_enter_any_timing_column(accepted_work,grant):
 work,_,_=accepted_work(ended=date(2026,11,1));doc=Document.objects.create(kind='letter',source_kind='paper_original',created_by=work.registered_by.employee)
 configure(work,grant,notification_sent=True,notification_on='2026-10-03',notification_document_id=str(doc.pk),extension_requested=True,request_on='2026-10-04',request_document_id=str(doc.pk),deadline_breached=True,breach_basis='Учебная подтверждённая оценка',breach_document_id=str(doc.pk))
 assert [cell(calculate_registry(year=2026,month=10),3,f'{c}107')['value'] for c in 'GHIJKLMN']==[0]*8


def test_empty_complete_reasons_do_not_become_false_zeros_after_end_date_correction(employee_factory,grant,settings,tmp_path):
 from test_timing_facts import setup
 from test_historical_report_correction import body as correction_body,send as correct
 client,_,work,history,_,_=setup(employee_factory,grant,settings,tmp_path,ended=date(2026,8,6))
 work.receipt.received_at=date(2026,8,1);work.receipt.save(update_fields=['received_at'])
 assert send(client,work,body(work,reasons_complete=True)).status_code==200
 assert all(cell(calculate_registry(year=2026,month=10),3,f'{c}107')['value']==0 for c in 'GHIJKL')
 work.refresh_from_db();response=correct(client,work,correction_body(work));assert response.status_code==200,response.content
 report=calculate_registry(year=2026,month=10)
 assert cell(report,3,'F107')['value']==1
 assert all(cell(report,3,f'{c}107')['value'] is None for c in 'GHIJKL')
 assert str(work.pk) in next(g for g in report['gaps'] if g['code']=='delayReasons')['rows']


def test_empty_complete_reasons_do_not_become_false_zeros_at_later_completion(employee_factory,grant,settings,tmp_path):
 from apps.expertises.models import Expertise
 from test_result_completion import completion_setup,ready_result,send as complete
 settings.MEDIA_ROOT=tmp_path
 client,actor,current,_,_,_,_=completion_setup(employee_factory,grant);grant(actor,'expertise.work.update','own')
 work=Expertise.objects.get(pk=current['id']);work.receipt.received_at=date(2026,8,1);work.receipt.save(update_fields=['received_at'])
 response=send(client,work,body(work,reasons_complete=True));assert response.status_code==200,response.content
 current=ready_result(client,response.json()['expertise'],on='2026-10-08')
 response=complete(client,current,'complete',result_id=current['result']['id']);assert response.status_code==200,response.content
 report=calculate_registry(year=2026,month=10)
 assert cell(report,3,'F107')['value']==1
 assert all(cell(report,3,f'{c}107')['value'] is None for c in 'GHIJKL')
 assert str(work.pk) in next(g for g in report['gaps'] if g['code']=='delayReasons')['rows']


def test_owner_policy_counts_each_selected_group_without_requiring_primary(accepted_work,grant):
 work,_,_=accepted_work();work.receipt.received_at=date(2026,8,1);work.receipt.save(update_fields=['received_at'])
 actor=work.registered_by.employee;grant(actor,'expertise.view');grant(actor,'expertise.closed.correct');client=Client();client.force_login(actor.user);reasons=refs(client,work)
 assert send(client,work,body(work,reasons_complete=True,reasons=[entry(reasons['research_complexity']),entry(reasons['expert_workload'])])).status_code==200
 report=calculate_registry(year=2026,month=10)
 assert [cell(report,3,f'{c}107')['value'] for c in 'GHIJKL']==[1,0,1,0,0,0]
 assert not any(g['code']=='delayReasons' for g in report['gaps'])
 assert client.get(f'/api/v1/expertises/{work.pk}/timing/').json()['delay_reason_policy']=='all'

@pytest.mark.parametrize('policy,complete,entries,primary,want',[
 ('all',True,[('a','expert_workload'),('b','expert_workload')],None,[0,0,1,0,0,0]),
 ('all',False,[('a','expert_workload')],None,[None,None,1,None,None,None]),
 ('all',True,[('a',None)],None,[None]*6),
 ('primary',False,[('a','research_complexity'),('b',None)],'a',[1,0,0,0,0,0]),
 (None,True,[('a','expert_workload')],None,[0,0,1,0,0,0]),
 (None,True,[('a','expert_workload'),('b','expert_workload')],None,[0,0,1,0,0,0]),
 (None,True,[('a','research_complexity'),('b','expert_workload')],None,[None,0,None,0,0,0]),
 (None,True,[('a',None)],None,[None]*6),
])
def test_reason_grouping_partial_and_unknown_policy_are_tristate(policy,complete,entries,primary,want):
 from apps.reports.timing_columns import delay_counts
 facts={'delay_reasons':[{'reason_id':pk,'report_group':group} for pk,group in entries],'delay_reasons_complete':complete,'primary_delay_reason_id':primary}
 counts=delay_counts(facts,policy)
 assert [counts[c] for c in ('research_complexity','large_material_volume','expert_workload','long_research_methods','appointing_party_deadline','other')]==want
