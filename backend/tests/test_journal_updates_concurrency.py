from concurrent.futures import ThreadPoolExecutor,TimeoutError
from threading import Event,Barrier
import pytest
from django.db import transaction,close_old_connections,connection
from django.test import Client
from apps.intake.models import Material
from apps.expertises.models import HistoricalWork,Expertise
from apps.imports.models import ImportApplication
from application_samples import source_batch,select_row,selection_body
from test_journal_updates import prepare,packet,update
from journal_samples import row

pytestmark=pytest.mark.django_db(transaction=True)


def test_update_waits_for_material_and_rechecks_native_activation(employee_factory,grant,settings,tmp_path):
    _,actor,old,new,_,_=prepare(employee_factory,grant,settings,tmp_path)
    work=Expertise.objects.get();body=packet(new);started=Event()
    def run():
        close_old_connections()
        try:
            client=Client();client.force_login(actor.user);started.set()
            return update(client,new,body).status_code
        finally:connection.close()
    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction.atomic():
            Material.objects.select_for_update().get(pk=work.material_id)
            future=pool.submit(run);assert started.wait(5)
            with pytest.raises(TimeoutError):future.result(timeout=0.4)
            HistoricalWork.objects.filter(expertise=work).update(operational=True)
        assert future.result(timeout=15)==409
    assert HistoricalWork.objects.get().complexity_level==1 and ImportApplication.objects.count()==1


def test_competing_snapshot_updates_have_one_winner_without_duplicate_history(employee_factory,grant,settings,tmp_path):
    client,actor,old,new,department,specialty=prepare(employee_factory,grant,settings,tmp_path)
    newer=source_batch(actor,[row(N='3',Q='2',R='2',S='0',T='0')])
    assert select_row(client,newer,newer.rows.get(),selection_body(department,specialty,employee_ids=[str(actor.pk)]),'other').status_code==200
    barrier=Barrier(2);commands=[(new,packet(new),'first'),(newer,packet(newer),'second')]
    def run(command):
        close_old_connections()
        try:
            source,body,key=command;browser=Client();browser.force_login(actor.user);barrier.wait(timeout=10)
            return update(browser,source,body,key).status_code
        finally:connection.close()
    with ThreadPoolExecutor(max_workers=2) as pool:statuses=list(pool.map(run,commands))
    assert sorted(statuses)==[201,409]
    assert Expertise.objects.get().version==2 and HistoricalWork.objects.get().complexity_level in (2,3)
    assert ImportApplication.objects.count()==2 and HistoricalWork.objects.count()==1
