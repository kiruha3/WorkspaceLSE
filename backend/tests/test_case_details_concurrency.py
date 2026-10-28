from concurrent.futures import ThreadPoolExecutor,TimeoutError
from threading import Event,Barrier
import pytest
from django.db import transaction,close_old_connections,connection
from django.test import Client
from apps.intake.models import Material
from apps.expertises.models import Expertise,WorkCaseDetails,CaseDetailsRevision
from apps.references.models import Specialty
from apps.audit.models import AuditEvent
from test_case_details import setup,body,send
from test_journal_updates import prepare,update,packet

pytestmark=pytest.mark.django_db(transaction=True)

def test_case_waits_for_material_and_rechecks_a_winning_source_version(employee_factory,grant,settings,tmp_path):
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
            with pytest.raises(TimeoutError):future.result(timeout=0.4)
            assert update(client,new).status_code==201
        assert future.result(timeout=15)==409
    assert not WorkCaseDetails.objects.exists() and not CaseDetailsRevision.objects.exists()

@pytest.mark.parametrize('same_key',[True,False])
def test_competing_case_updates_have_one_revision(employee_factory,grant,settings,tmp_path,same_key):
    _,actor,work,_,_,_=setup(employee_factory,grant,settings,tmp_path);barrier=Barrier(2)
    def run(n):
        close_old_connections()
        try:
            client=Client();client.force_login(actor.user);barrier.wait(timeout=10)
            return send(client,work,key='same' if same_key else f'case-{n}').status_code
        finally:connection.close()
    with ThreadPoolExecutor(max_workers=2) as pool:statuses=list(pool.map(run,range(2)))
    assert sorted(statuses)==([200,200] if same_key else [200,409])
    assert CaseDetailsRevision.objects.count()==1 and Expertise.objects.get().version==2

def test_manual_profile_wins_even_without_changes_to_old_source_scalars(employee_factory,grant,settings,tmp_path):
    client,actor,_,new,_,_=prepare(employee_factory,grant,settings,tmp_path);grant(actor,'expertise.closed.correct')
    work=Expertise.objects.get();assert send(client,work).status_code==200
    response=update(client,new,packet(new));assert response.status_code==409
    assert 'карточк' in response.json()['message'] or 'дела' in response.json()['message']
    assert CaseDetailsRevision.objects.count()==1 and Expertise.objects.get().historical.complexity_level==1

@pytest.mark.parametrize('same_key',[True,False])
def test_reference_unique_race_has_one_item_and_no_server_error(employee_factory,grant,same_key):
    actor=employee_factory();grant(actor,'references.manage');barrier=Barrier(2)
    def run(n):
        close_old_connections()
        try:
            client=Client();client.force_login(actor.user);barrier.wait(timeout=10)
            return client.post('/api/v1/references/specialties/',{'code':'99.1','name':'ДЕМО · конкурентный код'},content_type='application/json',HTTP_IDEMPOTENCY_KEY='same' if same_key else f'create-{n}').status_code
        finally:connection.close()
    with ThreadPoolExecutor(max_workers=2) as pool:statuses=list(pool.map(run,range(2)))
    assert sorted(statuses)==[201,201] if same_key else sorted(statuses) in ([201,400],[201,409])
    assert Specialty.objects.filter(code='99.1').count()==1
    assert AuditEvent.objects.filter(action='reference.create').count()==1
