from datetime import date
from importlib.util import find_spec
from io import BytesIO
from zipfile import ZipFile
from xml.etree import ElementTree as ET
import pytest
from apps.expertises.models import Expertise,ResultRevision,WorkClosure
from apps.documents.models import Document
from apps.imports.models import ImportRow
from apps.intake.models import Material
from historical_samples import historical_setup as setup_history
from test_registration import registration_setup,register
from test_form151 import value

pytestmark=pytest.mark.django_db


def calculate(**options):
    assert find_spec('apps.reports.registry') is not None,'Typed working registry report is not implemented'
    from apps.reports.registry import calculate_registry
    return calculate_registry(year=2026,month=10,opening_balances_complete=True,**options)


def test_live_history_fields_not_old_source_drive_report(employee_factory,grant,settings,tmp_path):
    _,_,work,history,_,_=setup_history(employee_factory,grant,settings,tmp_path)
    original=ImportRow.objects.get().facts.copy()
    history.result_kind='sndz';history.save()
    result=calculate()
    assert value(result,1,'F108')==1 and value(result,1,'J108')==0
    assert result['source']['type']=='registry' and result['source']['row_count']==1
    assert result['records'][str(work.pk)]['registration_number']=='151/4-1-26'
    assert str(work.pk) in next(c['rows'] for c in result['cells'] if c['sheet']=='Раздел 1' and c['address']=='F108')
    assert ImportRow.objects.get().facts==original


def test_registry_does_not_fill_missing_typed_question_counts_with_zero(employee_factory,grant,settings,tmp_path):
    _,_,work,history,_,_=setup_history(employee_factory,grant,settings,tmp_path)
    history.probable=None;history.unresolved=None;history.save()
    result=calculate()
    assert value(result,2,'D107')==2 and value(result,2,'F107')==2
    assert value(result,2,'E107') is None and value(result,2,'G107') is None and value(result,2,'H107') is None
    assert any(str(work.pk) in g['rows'] for g in result['gaps'] if g['code']=='questions')


def test_issue_date_is_not_typed_return_decision(employee_factory,grant,settings,tmp_path):
    _,_,work,history,_,_=setup_history(employee_factory,grant,settings,tmp_path,state='without_execution',ended=None,issued=date(2026,10,10))
    result=calculate()
    assert value(result,4,'O107') is None and value(result,1,'Q108') is None
    assert any(str(work.pk) in g['rows'] for g in result['gaps'] if g['code']=='returnDate')


def test_unknown_specialty_preserves_known_institution_total(employee_factory,grant,settings,tmp_path):
    setup_history(employee_factory,grant,settings,tmp_path,state='in_progress',ended=None,specialty_known=False)
    result=calculate()
    assert value(result,1,'E108')==1 and value(result,1,'Q108')==1
    assert value(result,1,'E65') is None and value(result,1,'J108')==0


def test_native_open_work_and_accepted_revision_not_latest_draft(employee_factory,grant):
    client,actor,receipt,department,specialty,data=registration_setup(employee_factory,grant)
    work=Expertise.objects.get(pk=register(client,receipt,data).json()['id'])
    draft=ResultRevision.objects.create(expertise=work,number=1,kind='expert_conclusion',completed_on=date(2026,10,28),questions=99,actor=actor.user,reason='Черновик')
    opened=calculate()
    assert value(opened,1,'E108')==1 and value(opened,1,'Q108')==1 and value(opened,1,'J108')==0
    doc=Document.objects.create(kind='expert_conclusion',source_kind='paper_original',title='Принятый итог',created_by=actor)
    accepted=ResultRevision.objects.create(expertise=work,number=2,kind='expert_conclusion',completed_on=date(2026,10,28),questions=2,categorical=2,probable=0,unresolved=0,statistics_complete=True,complexity_level=1,document=doc,actor=actor.user,reason='Принято')
    WorkClosure.objects.create(expertise=work,number=1,kind='completed',ended_on=date(2026,10,28),result=accepted,document=doc,actor=actor.user,reason='Окончание')
    work.state='completed';work.save()
    ResultRevision.objects.create(expertise=work,number=3,kind='sndz',questions=100,actor=actor.user,reason='Не принят')
    result=calculate()
    assert value(result,1,'J108')==1 and value(result,1,'F108')==0 and value(result,2,'D107')==2
    assert value(result,1,'Q108')==0
    corrected=ResultRevision.objects.create(expertise=work,number=4,kind='expert_conclusion',questions=3,categorical=3,probable=0,unresolved=0,document=doc,actor=actor.user,reason='Исправлено')
    WorkClosure.objects.create(expertise=work,number=2,kind='completed',ended_on=date(2026,10,28),result=corrected,document=doc,actor=actor.user,reason='Подтверждено исправление')
    assert value(calculate(),2,'D107')==3


def test_explicit_demo_flag_excludes_material_not_name(employee_factory,grant,settings,tmp_path):
    _,_,work,history,_,_=setup_history(employee_factory,grant,settings,tmp_path)
    assert value(calculate(),1,'J108')==1 # Fixture title has ДЕМО, but no flag.
    assert hasattr(work.material,'is_demo'),'Explicit demo classification is not implemented'
    work.material.is_demo=True;work.material.save()
    result=calculate()
    assert result['source']['row_count']==0 and result['source']['excluded_demo_count']==1
    assert value(result,1,'J108')==0 and result['records']=={}


def test_registry_api_separate_permissions_and_download_revision(employee_factory,grant,settings,tmp_path):
    client,actor,work,history,_,_=setup_history(employee_factory,grant,settings,tmp_path)
    grant(actor,'reports.form151.run');grant(actor,'reports.form151.download')
    # Registry requires work-view, not access to the original Google snapshot.
    actor.role_assignments.filter(role__permissions__permission_code='imports.results.view').update(is_active=False)
    url='/api/v1/reports/form151/?source=registry&year=2026&month=10'
    response=client.get(url);assert response.status_code==200,response.content
    result=response.json();assert result['source']['row_count']==1
    # Exact browser download Accept: DRF must also be able to render JSON errors.
    accept='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, application/json'
    archive=client.get(result['download_url'],HTTP_ACCEPT=accept);assert archive.status_code==200
    with ZipFile(BytesIO(archive.content)) as z:
        assert len([n for n in z.namelist() if n.startswith('xl/worksheets/sheet') and n.endswith('.xml')])==9
        sheet=ET.fromstring(z.read('xl/worksheets/sheet2.xml'))
        assert sheet.find(".//s:c[@r='J108']/s:v",{'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}).text=='1'
    history.questions=7;history.save()
    assert client.get(result['download_url'],HTTP_ACCEPT=accept).status_code==409
    actor.role_assignments.filter(role__permissions__permission_code='reports.form151.download').update(is_active=False)
    assert client.get(url).status_code==200
    assert client.get(client.get(url).json()['download_url']).status_code==403


@pytest.mark.parametrize('scope',['own','departments'])
def test_registry_does_not_expose_institution_through_narrow_work_scope(employee_factory,grant,settings,tmp_path,scope):
    client,actor,work,history,department,_=setup_history(employee_factory,grant,settings,tmp_path)
    actor.role_assignments.filter(role__permissions__permission_code='expertise.view').update(is_active=False)
    grant(actor,'expertise.view',scope,departments=[department]);grant(actor,'reports.form151.run')
    assert client.get('/api/v1/reports/form151/?source=registry&year=2026&month=10').status_code==403


def test_registry_uses_one_coherent_domain_select(employee_factory,grant,settings,tmp_path,django_assert_num_queries):
    setup_history(employee_factory,grant,settings,tmp_path)
    with django_assert_num_queries(1):result=calculate()
    assert result['source']['row_count']==1


def test_registry_rejects_ambiguous_parameters_and_does_not_write_domain_state(employee_factory,grant,settings,tmp_path):
    client,actor,work,history,_,_=setup_history(employee_factory,grant,settings,tmp_path)
    grant(actor,'reports.form151.run')
    from apps.audit.models import AuditEvent
    counts=lambda:(Expertise.objects.count(),ResultRevision.objects.count(),WorkClosure.objects.count(),ImportRow.objects.count(),AuditEvent.objects.count())
    before=counts();version=work.version
    base='/api/v1/reports/form151/?source=registry&year=2026&month=10'
    assert client.get(base).status_code==200
    for query in ('source=journal','batch_id='+str(history.source_row.batch_id),'month=11','expected_revision=bad','extra=1'):
        assert client.get(base+'&'+query).status_code==400
    work.refresh_from_db();assert work.version==version and counts()==before
