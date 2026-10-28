"""A business journey, not several tests starting from prepared result/package ORM rows."""
from datetime import date
from io import BytesIO
from zipfile import ZipFile
from xml.etree import ElementTree as ET
import pytest
from full_workflow_support import create_people, WorkflowSession, register_work, run_journey, complete_simple_work

pytestmark=pytest.mark.django_db(transaction=True)
PASSWORD='Test-only-LongPassword9'


@pytest.fixture
def acceptance_url(live_server):
    # Same bound server, explicit IPv4 avoids Windows localhost IPv6 connection retries.
    return live_server.url.replace('http://localhost:','http://127.0.0.1:')


def test_continuous_roles_from_receipt_to_paid_issue_and_real_xlsx(acceptance_url,settings,tmp_path):
    settings.MEDIA_ROOT=tmp_path
    world=create_people(PASSWORD)
    result=run_journey(acceptance_url,world,PASSWORD)
    from apps.expertises.models import Expertise,WorkClosure,ResultRevision
    from apps.audit.models import AuditEvent
    work=Expertise.objects.get(pk=result['work_id'])
    assert Expertise.objects.count()==1 and work.origin_kind=='native'
    assert work.registration_number=='1/3-1-26' and work.state=='completed'
    assert WorkClosure.objects.get(expertise=work).ended_on==date(2026,10,10)
    assert ResultRevision.objects.get(expertise=work).questions==4
    assert AuditEvent.objects.filter(action='issue.confirm').count()==1
    assert result['accepted_result_file']!=result['late_result_file']
    # Inspect the actual downloaded workbook, not the calculator's expected-values helper.
    with ZipFile(BytesIO(result.pop('xlsx'))) as archive:
        ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
        section1=ET.fromstring(archive.read('xl/worksheets/sheet2.xml'))
        section2=ET.fromstring(archive.read('xl/worksheets/sheet3.xml'))
        assert section1.find(".//s:c[@r='J108']/s:v",ns).text=='1'
        assert section2.find(".//s:c[@r='D107']/s:v",ns).text=='4'
    assert result['issued_on']=='2026-10-14'


def test_transfer_current_lists_and_head_as_expert_use_real_sessions(acceptance_url,settings,tmp_path):
    settings.MEDIA_ROOT=tmp_path
    world=create_people(PASSWORD);profiles=world['profiles']
    clerk=WorkflowSession(acceptance_url,profiles['clerk']['username'],PASSWORD)
    head=WorkflowSession(acceptance_url,profiles['head']['username'],PASSWORD)
    first=WorkflowSession(acceptance_url,profiles['expert']['username'],PASSWORD)
    recipient=WorkflowSession(acceptance_url,profiles['expert2']['username'],PASSWORD)
    work=register_work(clerk,world,number='2/3-1-26')
    path=f"/expertises/{work['id']}"
    work=head.ok(path+'/assignments/','POST',{'expected_version':work['version'],'employee_ids':[profiles['expert']['employee_id']],'reason':'ПРИЁМКА · первый исполнитель'})
    assert first.ok('/expertises/')['count']==1 and recipient.ok('/expertises/')['count']==0
    work=head.ok(path+'/reassign/','POST',{'expected_version':work['version'],'employee_ids':[profiles['expert2']['employee_id']],'reason':'ПРИЁМКА · перепоручение'})
    assert first.ok('/expertises/')['count']==0 and recipient.ok('/expertises/')['count']==1
    assert work['current_assignments'][0]['employee']['id']==profiles['expert2']['employee_id']
    own=register_work(clerk,world,number='3/3-1-26')
    own_path=f"/expertises/{own['id']}"
    own=head.ok(own_path+'/assignments/','POST',{'expected_version':own['version'],'employee_ids':[profiles['head']['employee_id']],'reason':'ПРИЁМКА · начальник выполняет как эксперт'})
    own=head.ok(own_path+'/suspend/','POST',{'expected_version':own['version'],'suspended_on':'2026-10-03','reason':'ПРИЁМКА · ожидание материалов'})['expertise']
    own=head.ok(own_path+'/resume/','POST',{'expected_version':own['version'],'resumed_on':'2026-10-04','reason':'ПРИЁМКА · материалы поступили'})['expertise']
    own=complete_simple_work(head,own)
    assert own['state']=='completed' and own['current_assignments'][0]['employee']['id']==profiles['head']['employee_id']
    assert recipient.ok(path+'/')['state']=='in_progress'


def test_explicit_demo_case_is_not_in_director_report(acceptance_url,settings,tmp_path):
    settings.MEDIA_ROOT=tmp_path
    world=create_people(PASSWORD);profiles=world['profiles']
    clerk=WorkflowSession(acceptance_url,profiles['clerk']['username'],PASSWORD)
    director=WorkflowSession(acceptance_url,profiles['director']['username'],PASSWORD)
    work=register_work(clerk,world,number='4/3-1-26',is_demo=True)
    report=director.ok('/reports/form151/?source=registry&year=2026&month=10&opening_balances_complete=true')
    assert report['source']['row_count']==0 and report['source']['excluded_demo_count']==1
    assert work['id'] not in report['records']
    assert next(cell['value'] for cell in report['cells'] if cell['sheet']=='Раздел 1' and cell['address']=='E108')==0
