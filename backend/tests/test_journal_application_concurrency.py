from concurrent.futures import ThreadPoolExecutor,TimeoutError
from threading import Barrier,Event
import pytest
from django.db import close_old_connections,connection
from django.test import Client
from apps.expertises.models import Expertise,HistoricalWork,ComplexGroup
from application_samples import application_setup,source_batch,selection_body,select_row,apply_rows
from journal_samples import row

pytestmark=pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize('two_works',[False,True])
def test_concurrent_different_snapshots_of_same_numbers_never_duplicate_or_partially_apply(employee_factory,grant,settings,tmp_path,two_works):
    records=[row()]+([row(B='152/4-1-26',M='19.1.')] if two_works else [])
    client,first,batch,department,specialty=application_setup(employee_factory,grant,settings,tmp_path,records)
    second=employee_factory()
    for code in ('imports.results.view','imports.reconcile','imports.apply'):grant(second,code)
    newer=source_batch(second,list(reversed(records)))
    from apps.references.models import Specialty
    other=Specialty.objects.create(code='19.1',name='ДЕМО · 19.1') if two_works else None
    packets=[]
    for actor,source_batch_ in [(first,batch),(second,newer)]:
        browser=Client();browser.force_login(actor.user);sources=list(source_batch_.rows.all())
        for index,source in enumerate(sources):
            ref=specialty if source.facts['specialty_code']=='18.1' else other
            selected=select_row(browser,source_batch_,source,selection_body(department,ref,complex_known=two_works,complex_group_key='same' if two_works else None),f'select-{index}')
            assert selected.status_code==200
        packets.append((actor,source_batch_,sources))
    barrier=Barrier(2)
    def run(packet):
        close_old_connections()
        try:
            actor,source_batch_,sources=packet
            browser=Client();browser.force_login(actor.user)
            barrier.wait(timeout=10)
            return apply_rows(browser,source_batch_,sources).status_code
        finally:connection.close()
    with ThreadPoolExecutor(max_workers=2) as pool:statuses=list(pool.map(run,packets))
    assert sorted(statuses)==[201,409]
    assert Expertise.objects.count()==(2 if two_works else 1) and HistoricalWork.objects.count()==(2 if two_works else 1)
    assert ComplexGroup.objects.count()==(1 if two_works else 0)


def test_later_packet_waits_for_material_lock_and_rechecks_issue_after_wait(employee_factory,grant,settings,tmp_path):
    from datetime import date
    from django.db import transaction
    from apps.intake.models import Material
    from apps.references.models import Specialty
    client,actor,batch,department,specialty=application_setup(employee_factory,grant,settings,tmp_path,[row(),row(B='152/4-1-26',M='19.1.')])
    other=Specialty.objects.create(code='19.1',name='ДЕМО ·19.1')
    sources=list(batch.rows.all())
    for index,(source,ref) in enumerate(zip(sources,[specialty,other])):
        assert select_row(client,batch,source,selection_body(department,ref,complex_known=True,complex_group_key='same'),f'select-{index}').status_code==200
    assert apply_rows(client,batch,[sources[0]]).status_code==201
    work=Expertise.objects.get();started=Event()
    def run():
        close_old_connections()
        try:
            browser=Client();browser.force_login(actor.user);started.set()
            return apply_rows(browser,batch,[sources[1]],key='wait-for-issue').status_code
        finally:connection.close()
    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction.atomic():
            Material.objects.select_for_update().get(pk=work.material_id)
            future=pool.submit(run);assert started.wait(timeout=5)
            with pytest.raises(TimeoutError):future.result(timeout=0.7)
            HistoricalWork.objects.filter(expertise=work).update(issued_on=date(2026,3,7))
        assert future.result(timeout=10)==400
    assert Expertise.objects.count()==1
