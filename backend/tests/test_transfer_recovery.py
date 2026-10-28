import importlib.util
from pathlib import Path
import pytest
from apps.references.models import Department
from apps.expertises.models import Expertise
from apps.imports.models import ImportApplication
from application_samples import application_setup,selection_body,select_row,apply_rows

pytestmark=pytest.mark.django_db


def helper():
    path=Path(__file__).resolve().parents[2]/'infra'/'journal_transfer.py'
    assert path.exists(),'Durable transfer recovery helper is not implemented'
    spec=importlib.util.spec_from_file_location('journal_transfer',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_reference_creation_and_deactivation_roll_back_together(employee_factory,grant,settings,tmp_path,monkeypatch):
    client,actor,_,_,_=application_setup(employee_factory,grant,settings,tmp_path)
    grant(actor,'references.manage')
    h=helper()
    def interrupted(*args,**kwargs):raise RuntimeError('Interrupted between POST and PATCH')
    monkeypatch.setattr(client,'patch',interrupted)
    with pytest.raises(RuntimeError,match='Interrupted'):
        h.ensure_historical_department(client)
    assert not Department.objects.filter(code='1').exists()


def test_retry_finishes_deactivation_of_its_existing_historical_reference(employee_factory,grant,settings,tmp_path):
    client,actor,_,_,_=application_setup(employee_factory,grant,settings,tmp_path)
    grant(actor,'references.manage')
    ref=Department.objects.create(code='1',name='Отдел 1 (исторический код)')
    result=helper().ensure_historical_department(client)
    ref.refresh_from_db()
    assert result.pk==ref.pk and not ref.is_active and Department.objects.filter(code='1').count()==1


def test_recovery_checks_real_links_instead_of_accepting_only_the_row_count(employee_factory,grant,settings,tmp_path):
    client,actor,batch,department,specialty=application_setup(employee_factory,grant,settings,tmp_path)
    h=helper();source=batch.rows.get()
    backup=tmp_path/'before.dump';backup.write_bytes(b'PGDMP-test-fixture')
    baseline={'batch_id':str(batch.pk),'source_sha256':batch.source_sha256,'source_digest':h.source_digest(batch),'before_counts':h.workflow_counts(),'backup':str(backup)}
    assert select_row(client,batch,source,selection_body(department,specialty)).status_code==200
    assert apply_rows(client,batch,[source]).status_code==201
    app=ImportApplication.objects.get()
    receipt=h.verify_transfer(batch,{str(source.pk):[]},baseline)
    assert receipt['application_id']==str(app.pk) and receipt['verified_rows']==1
    # The same number of applied rows must not hide a modified department.
    other=Department.objects.create(code='3',name='Неправильная подмена')
    Expertise.objects.update(department=other)
    with pytest.raises(AssertionError,match='department'):
        h.verify_transfer(batch,{str(source.pk):[]},baseline)
