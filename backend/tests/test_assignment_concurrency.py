from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
from django.db import close_old_connections, connection
from django.test import Client
from test_expert_assignments import assignment_setup, qualified, assign

pytestmark=pytest.mark.django_db(transaction=True)


def test_concurrent_assignments_check_work_version_under_lock(employee_factory,grant):
    _,head,work,_,specialty=assignment_setup(employee_factory,grant)
    employees=[qualified(employee_factory,specialty) for _ in range(2)]
    barrier=Barrier(2)
    def run(employee):
        close_old_connections()
        try:
            client=Client();client.force_login(head.user)
            barrier.wait(timeout=10)
            return assign(client,work,[employee]).status_code
        finally:connection.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses=list(pool.map(run,employees))
    assert sorted(statuses)==[200,409]
    from apps.expertises.models import ExpertAssignment, Expertise
    assert ExpertAssignment.objects.count()==1 and Expertise.objects.get().version==2
