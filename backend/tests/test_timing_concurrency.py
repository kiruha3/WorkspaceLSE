from concurrent.futures import ThreadPoolExecutor,TimeoutError
from threading import Event,Barrier
import pytest
from django.db import transaction,close_old_connections,connection
from django.test import Client
from apps.intake.models import Material
from apps.expertises.models import Expertise,WorkTimingFacts,TimingRevision
from test_timing_facts import setup,body,send
from test_journal_updates import prepare,update
pytestmark=pytest.mark.django_db(transaction=True)

@pytest.mark.parametrize('same_key',[True,False])
def test_competing_timing_updates_produce_one_revision(employee_factory,grant,settings,tmp_path,same_key):
 _,actor,work,_,_,_=setup(employee_factory,grant,settings,tmp_path);barrier=Barrier(2)
 def run(n):
  close_old_connections()
  try:
   browser=Client();browser.force_login(actor.user);barrier.wait(timeout=10)
   return send(browser,work,key='same' if same_key else f'timing-{n}').status_code
  finally:connection.close()
 with ThreadPoolExecutor(max_workers=2) as pool:statuses=list(pool.map(run,range(2)))
 assert sorted(statuses)==([200,200] if same_key else [200,409])
 assert WorkTimingFacts.objects.count()==1 and TimingRevision.objects.count()==1 and Expertise.objects.get().version==2

def test_timing_waits_for_material_and_rechecks_winning_import_version(employee_factory,grant,settings,tmp_path):
 client,actor,_,new,_,_=prepare(employee_factory,grant,settings,tmp_path);grant(actor,'expertise.closed.correct')
 work=Expertise.objects.get();payload=body(work);started=Event()
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
   with pytest.raises(TimeoutError):future.result(timeout=.4)
   assert update(client,new).status_code==201
  assert future.result(timeout=15)==409
 assert not WorkTimingFacts.objects.exists() and not TimingRevision.objects.exists()
