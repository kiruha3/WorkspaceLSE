from concurrent.futures import ThreadPoolExecutor,TimeoutError
from threading import Event,Barrier
import pytest
from django.db import transaction,close_old_connections,connection
from django.test import Client
from apps.intake.models import Material
from apps.expertises.models import Expertise,HistoricalCorrection
from apps.imports.updates import current_values
from test_historical_report_correction import setup_correction,body,send
from test_journal_updates import prepare,update,packet

pytestmark=pytest.mark.django_db(transaction=True)


def test_correction_waits_for_material_and_rechecks_a_winning_source_update(employee_factory,grant,settings,tmp_path):
    client,actor,_,new,_,_=prepare(employee_factory,grant,settings,tmp_path)
    grant(actor,'expertise.closed.correct');work=Expertise.objects.get();started=Event();payload=body(work)
    def run():
        close_old_connections()
        try:
            browser=Client();browser.force_login(actor.user);started.set()
            return send(browser,work,payload).status_code
        finally:connection.close()
    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction.atomic():
            Material.objects.select_for_update().get(pk=work.material_id)
            future=pool.submit(run);assert started.wait(5)
            with pytest.raises(TimeoutError):future.result(timeout=0.4)
            assert update(client,new).status_code==201
        assert future.result(timeout=15)==409
    assert not HistoricalCorrection.objects.exists()
    assert Expertise.objects.get().historical.complexity_level==2


@pytest.mark.parametrize('same_key',[True,False])
def test_competing_archival_corrections_have_one_revision(employee_factory,grant,settings,tmp_path,same_key):
    _,actor,work,_,_,_=setup_correction(employee_factory,grant,settings,tmp_path);barrier=Barrier(2)
    def run(n):
        close_old_connections()
        try:
            browser=Client();browser.force_login(actor.user);barrier.wait(timeout=10)
            return send(browser,work,key='same' if same_key else f'key-{n}').status_code
        finally:connection.close()
    with ThreadPoolExecutor(max_workers=2) as pool:statuses=list(pool.map(run,range(2)))
    assert sorted(statuses)==([200,200] if same_key else [200,409])
    assert HistoricalCorrection.objects.count()==1 and Expertise.objects.get().version==2


def test_reason_only_manual_change_blocks_later_source_even_with_no_old_scalar_drift(employee_factory,grant,settings,tmp_path):
    client,actor,_,new,_,_=prepare(employee_factory,grant,settings,tmp_path);grant(actor,'expertise.closed.correct')
    work=Expertise.objects.get();history=work.historical;before=current_values(work);payload=body(work)
    payload['result'].update(kind=history.result_kind,completed_on=history.completed_on.isoformat(),complexity_level=history.complexity_level,questions=history.questions,categorical=history.categorical,probable=history.probable,unresolved=history.unresolved,statistics_complete=history.statistics_confirmed,note='Ручное уточнение без старых scalar-изменений')
    assert send(client,work,payload).status_code==200
    work=Expertise.objects.get();assert current_values(work)==before
    response=update(client,new,packet(new));assert response.status_code==409
    assert 'уточнение' in response.json()['message'].lower()
    assert HistoricalCorrection.objects.count()==1 and work.historical.complexity_level==1
