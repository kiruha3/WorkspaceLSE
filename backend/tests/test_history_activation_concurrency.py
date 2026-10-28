from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
from django.db import close_old_connections,connection
from django.test import Client
from apps.audit.models import AuditEvent
from apps.accounts.models import CommandReceipt
from activation_samples import activation_setup,activation_body,activate

pytestmark=pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize('same_key',[True,False])
def test_concurrent_history_confirmation_creates_one_event(employee_factory,grant,settings,tmp_path,same_key):
    _,actor,work,_,_,specialty,basis=activation_setup(employee_factory,grant,settings,tmp_path,state='in_progress',ended=None)
    barrier=Barrier(2)
    def run(index):
        close_old_connections()
        try:
            client=Client();client.force_login(actor.user)
            barrier.wait(timeout=10)
            return activate(client,work,activation_body(basis,specialty),key='same-key' if same_key else f'different-{index}').status_code
        finally:connection.close()
    with ThreadPoolExecutor(max_workers=2) as pool:statuses=list(pool.map(run,range(2)))
    assert sorted(statuses)==([200,200] if same_key else [200,409])
    assert AuditEvent.objects.filter(action='imports.history.activate').count()==1
    assert CommandReceipt.objects.filter(action='imports.history.activate').count()==1
    work.refresh_from_db();assert work.version==2
