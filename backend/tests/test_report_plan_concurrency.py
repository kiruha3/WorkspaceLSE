from concurrent.futures import ThreadPoolExecutor,TimeoutError
from threading import Barrier,Event
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

@pytest.mark.parametrize('method',['GET','POST'])
def test_plan_response_holds_one_revision_until_its_whole_dto_is_assembled(employee_factory,grant,monkeypatch,method):
 from apps.reports import plan_api
 client,actor=setup(employee_factory,grant);specialty=Specialty.objects.create(code='16.1',name='Строительная')
 initial=body(total=10,lines=[line(specialty,1)])
 if method=='GET':assert send(client,initial).status_code==200
 entered=Event();release=Event();original=plan_api.plan_output
 def paused(plan,user,year):
  if not entered.is_set():entered.set();assert release.wait(10)
  return original(plan,user,year)
 monkeypatch.setattr(plan_api,'plan_output',paused)
 def first_read():
  close_old_connections()
  try:
   browser=Client();browser.force_login(actor.user)
   return browser.get('/api/v1/report-plans/2027/') if method=='GET' else send(browser,initial,key='initial')
  finally:connection.close()
 def writer():
  close_old_connections()
  try:
   browser=Client();browser.force_login(actor.user)
   return send(browser,body(expected_version=1,total=20,lines=[line(specialty,2)]),key='concurrent')
  finally:connection.close()
 with ThreadPoolExecutor(max_workers=2) as pool:
  response=pool.submit(first_read);assert entered.wait(10);write=pool.submit(writer)
  try:
   with pytest.raises(TimeoutError):write.result(timeout=.4)
  finally:release.set()
  observed=response.result(timeout=15);assert observed.status_code==200,observed.content
  assert observed.json()['version']==1 and observed.json()['total']==10 and observed.json()['lines'][0]['count']==1
  assert len(observed.json()['revisions'])==1
  assert write.result(timeout=15).status_code==200
 assert StateAssignmentPlan.objects.get(year=2027).version==2
