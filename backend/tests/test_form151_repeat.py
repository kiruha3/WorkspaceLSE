from datetime import date
from io import BytesIO
from zipfile import ZipFile
from xml.etree import ElementTree as ET
import pytest
from apps.reports.registry import calculate_registry
from test_form151_reasons import accepted_work,cell
from test_classification import body,previous,send
from django.test import Client
pytestmark=pytest.mark.django_db

def configure(work,grant,**changes):
 work.refresh_from_db()
 actor=work.registered_by.employee;grant(actor,'expertise.view');grant(actor,'expertise.closed.correct');client=Client();client.force_login(actor.user)
 result=send(client,work,body(work,**changes));assert result.status_code==200,result.content
 return client

def test_repeated_work_is_not_multiplied_by_previous_conclusions_and_xlsx_is_literal(accepted_work,grant,django_assert_num_queries):
 work,_,_=accepted_work();client=configure(work,grant,previous_conclusions=[previous(),previous(reference='Другое предыдущее',confirms_previous=True)])
 with django_assert_num_queries(1):report=calculate_registry(year=2026,month=10)
 assert len(report['cells'])==900
 assert [cell(report,4,f'{c}107')['value'] for c in 'HIJKLMN']==[1,1,1,0,0,0,0]
 assert cell(report,4,'J58')['value']==1
 grant(work.registered_by.employee,'reports.form151.run');grant(work.registered_by.employee,'reports.form151.download')
 fresh=client.get('/api/v1/reports/form151/',{'source':'registry','year':2026,'month':10}).json()
 archive=client.get(fresh['download_url']);assert archive.status_code==200
 with ZipFile(BytesIO(archive.content)) as z:
  root=ET.fromstring(z.read('xl/worksheets/sheet5.xml'));ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
  assert root.find('.//s:c[@r="H107"]/s:v',ns).text=='1'

@pytest.mark.parametrize('complete,entries,want',[
 (False,[previous()],[1,1,None,None,None,None]),
 (True,[previous(organization_group=None)],[None,None,None,None,None,None]),
 (True,[previous(same_input_data=None)],[1,None,0,0,0,0]),
 (True,[previous(same_input_data=False)],[1,0,0,0,0,0]),
 (True,[previous(organization_group='other_state'),previous(organization_group='other',same_input_data=False)],[0,0,1,1,1,0]),
])
def test_partial_previous_facts_do_not_turn_into_false_zeros(accepted_work,grant,complete,entries,want):
 work,_,_=accepted_work();configure(work,grant,previous_complete=complete,previous_conclusions=entries)
 report=calculate_registry(year=2026,month=10);assert [cell(report,4,f'{c}107')['value'] for c in 'IJKLMN']==want

@pytest.mark.parametrize('nature',['primary','additional'])
def test_known_nonrepeated_is_zero(accepted_work,grant,nature):
 work,_,_=accepted_work();configure(work,grant,appointment_nature=nature,previous_complete=False,previous_conclusions=[])
 report=calculate_registry(year=2026,month=10);assert [cell(report,4,f'{c}107')['value'] for c in 'HIJKLMN']==[0]*7

def test_repeated_sndz_is_unknown_until_owner_policy_is_confirmed(accepted_work,grant):
 work,_,_=accepted_work(kind='sndz');configure(work,grant)
 report=calculate_registry(year=2026,month=10);assert cell(report,4,'H107')['value'] is None
 assert any(g['code']=='repeatSndzPolicy' and str(work.pk) in g['rows'] for g in report['gaps'])

def test_unknown_nature_and_latest_accepted_closure_have_provenance(accepted_work,grant):
 work,result,closure=accepted_work();configure(work,grant)
 from apps.expertises.models import ResultRevision
 ResultRevision.objects.create(expertise=work,number=2,kind='sndz',completed_on=date(2026,10,15),actor=work.registered_by,reason='Непринятый черновик')
 report=calculate_registry(year=2026,month=10);assert cell(report,4,'H107')['value']==1 and cell(report,4,'H107')['rows']==[str(work.pk)]
 before=report['data_revision'];configure(work,grant,appointment_nature='primary',previous_complete=False,previous_conclusions=[])
 assert calculate_registry(year=2026,month=10)['data_revision']!=before
