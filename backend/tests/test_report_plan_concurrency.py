from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
from django.db import close_old_connections,connection
from django.test import Client
from apps.reports.models import StateAssignmentPlan,StateAssignmentPlanRevision,StateAssignmentPlanLine
from test_report_plans import setup,send,body,line
from apps.references.models import Specialty
pytestmark=pytest.mark.django_db(transaction=True)

@pytest.mark.parametrize('existing',[False,True])
@pytest.mark.parametrize('same_key',[False,True])
def test_competing_plan_commands_leave_one_winning_revision(employee_factory,grant,existing,same_key):
 client,actor=setup(employee_factory,grant);specialty=Specialty.objects.create(code='16.1',name='Строительная')
 if existing:assert send(client,body(total=10)).status_code==200
 data=body(expected_version=1 if existing else 0,total=10,lines=[line(specialty,3)])
 barrier=Barrier(2)
 def run(n):
  close_old_connections()
  try:
   browser=Client();browser.force_login(actor.user);barrier.wait(timeout=10)
   return send(browser,data,key='same' if same_key else f'plan-{n}').status_code
  finally:connection.close()
 with ThreadPoolExecutor(max_workers=2) as pool:statuses=list(pool.map(run,range(2)))
 assert sorted(statuses)==([200,200] if same_key else [200,409])
 assert StateAssignmentPlan.objects.filter(year=2027).count()==1
 assert StateAssignmentPlan.objects.get(year=2027).version==(2 if existing else 1)
 assert StateAssignmentPlanRevision.objects.filter(plan__year=2027).count()==(2 if existing else 1)
 assert StateAssignmentPlanLine.objects.filter(plan__year=2027).count()==1
