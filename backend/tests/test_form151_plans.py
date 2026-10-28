from io import BytesIO
from zipfile import ZipFile
from xml.etree import ElementTree as ET
import pytest
from apps.reports.registry import calculate_registry
from apps.reports.calculation import calculate
from apps.reports.models import StateAssignmentPlan
from apps.references.models import Specialty
from test_report_plans import setup,send,body,line
from test_form151_reasons import accepted_work,cell
from test_journal_preview_api import send_preview
from test_form151 import report as journal_report
from journal_samples import row,csv_source
pytestmark=pytest.mark.django_db

def counts(report,*addresses):return [cell(report,6,address)['value'] for address in addresses]

def plan_fixture(client,*,year=2027,first=2,second=5,unknown=None):
 refs={code:Specialty.objects.get_or_create(code=code,defaults={'name':'ДЕМО · '+code})[0] for code in ('1.1','16.1','16.2')}
 entries=[line(refs['1.1'],first),line(refs['16.1'],3)]
 if second is not None:entries.append(line(refs['16.2'],second))
 if unknown is not None:
  spec=Specialty.objects.create(code='99.9',name='Несопоставленная');entries.append(line(spec,unknown[0]))
 response=send(client,body(total=10,lines=entries),year=year);assert response.status_code==200,response.content
 return refs,response.json()

def test_one_select_empty_registry_keeps_selected_year_plan_and_parent_sum(employee_factory,grant,django_assert_num_queries):
 client,_=setup(employee_factory,grant);plan_fixture(client)
 with django_assert_num_queries(1):report=calculate_registry(year=2027,month=10)
 assert counts(report,'D10','D57','D58','D59','D107')==[2,8,3,5,10]
 assert len(report['cells'])==996 and len(report['column_rules'])==83
 assert report['plan_summary']['year']==2027 and report['plan_summary']['version']==1
 assert report['plan_summary']['known_sum']==10 and report['plan_summary']['unallocated']==0
 assert not report['records'] and all(c['rows']==[] for c in report['cells'])

@pytest.mark.parametrize('second,unknown,want',[(None,None,[2,None,3,None,10]),(0,None,[2,3,3,0,10]),(None,(0,),[2,None,3,None,10]),(None,(2,),[2,None,3,None,10]),(None,(None,),[2,None,3,None,10])])
def test_partial_zero_and_unmapped_lines_do_not_invent_subtotals(employee_factory,grant,second,unknown,want):
 client,_=setup(employee_factory,grant);plan_fixture(client,second=second,unknown=unknown)
 report=calculate_registry(year=2027,month=10)
 assert counts(report,'D10','D57','D58','D59','D107')==want
 gaps=[g for g in report['gaps'] if g['code'].startswith('plan')]
 assert gaps and all(g['rows']==[] and g['plan_year']==2027 for g in gaps)

@pytest.mark.parametrize('first,unknown,want',[(2,(None,),[2,None,3,5,10]),(0,(2,),[0,None,3,5,10])])
def test_unmapped_lines_preserve_explicit_leaf_amounts_and_zero_but_not_dependent_parents(employee_factory,grant,first,unknown,want):
 client,_=setup(employee_factory,grant);plan_fixture(client,first=first,unknown=unknown)
 report=calculate_registry(year=2027,month=10)
 assert counts(report,'D10','D57','D58','D59','D107')==want
 assert any(g['code']=='planMapping' and g['rows']==[] for g in report['gaps'])

def test_pure_calculation_never_reads_or_falls_back_to_2026_constant(django_assert_num_queries):
 from types import SimpleNamespace
 rows=[SimpleNamespace(source_row=4,raw={},facts={'registration_number':'1/4-1-26','received_on':'2026-01-01','state':'in_progress','category_code':'1','specialty_code':'18.1'})]
 with django_assert_num_queries(0):report=calculate(rows,2026,10)
 assert counts(report,'D107')==[None] and report['plan_summary']['version']==0
 with django_assert_num_queries(0):injected=calculate(rows,2026,10,plan_snapshot={'id':'demo','year':2026,'total':294,'version':1,'basis_text':'Подтверждено','document_id':None,'lines':[]})
 assert counts(injected,'D107')==[294] and len(injected['cells'])==660
 assert [c for c in report['cells'] if c['sheet']!='Раздел 6' or not c['address'].startswith('D')]==[c for c in injected['cells'] if c['sheet']!='Раздел 6' or not c['address'].startswith('D')]

@pytest.mark.parametrize('source',['registry','journal'])
def test_both_http_sources_keep_literal_plan_and_invalidate_stale_download(employee_factory,grant,settings,tmp_path,source):
 settings.MEDIA_ROOT=tmp_path;client,actor=setup(employee_factory,grant)
 for code in ('imports.preview','imports.results.view','reports.form151.download'):grant(actor,code)
 refs,_=plan_fixture(client,year=2027)
 params={'source':source,'year':2027,'month':10}
 if source=='journal':
  batch=send_preview(client,csv_source([row(B='151/4-1-27',C='12.02.2027',P='06.03.2027')])).json()['batch']
  params['batch_id']=batch['id']
 response=client.get('/api/v1/reports/form151/',params);assert response.status_code==200,response.content
 report=response.json();assert report['source']['type']==source and report['data_revision']==report['source']['data_revision']
 assert counts(report,'D10','D57','D58','D59','D107')==[2,8,3,5,10]
 archive=client.get(report['download_url']);assert archive.status_code==200
 with ZipFile(BytesIO(archive.content)) as z:
  xml=ET.fromstring(z.read('xl/worksheets/sheet7.xml'));ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
  assert [xml.find(f'.//s:c[@r="{a}"]/s:v',ns).text for a in ('D10','D57','D58','D59','D107')]==['2','8','3','5','10']
 rule=next(r for r in report['column_rules'] if r['section']==6 and r['column']=='D')
 assert '294' not in rule['meaning'] and '2026' not in str(rule)
 assert send(client,body(expected_version=1,total=11,lines=[line(refs['1.1'],2),line(refs['16.1'],3),line(refs['16.2'],6)])).status_code==200
 assert client.get(report['download_url']).status_code==409
 next_report=client.get('/api/v1/reports/form151/',params).json();assert counts(next_report,'D107')==[11] and next_report['data_revision']!=report['data_revision']
 Specialty.objects.filter(pk=refs['16.1'].pk).update(code='99.8')
 assert client.get(next_report['download_url']).status_code==409

def test_accepted_result_and_old_provenance_survive_json_transport(accepted_work,employee_factory,grant,django_assert_num_queries):
 work,_,_=accepted_work(questions=2,categorical=2,probable=0,unresolved=0,complexity_level=1)
 with django_assert_num_queries(1):before=calculate_registry(year=2026,month=10)
 assert cell(before,1,'J108')['value']==1 and cell(before,2,'D107')['value']==2
 assert cell(before,1,'J108')['rows']==[str(work.pk)]
 assert before['records'][str(work.pk)]['registration_number']==work.registration_number
 # A plan edit cannot rewrite any non-plan report value or contributing work.
 client,_=setup(employee_factory,grant)
 old=StateAssignmentPlan.objects.get(year=2026)
 assert send(client,body(expected_version=old.version,total=300),year=2026).status_code==200
 with django_assert_num_queries(1):after=calculate_registry(year=2026,month=10)
 actual=lambda report:[c for c in report['cells'] if c['sheet']!='Раздел 6' or not c['address'].startswith('D')]
 assert actual(before)==actual(after) and before['records']==after['records']
